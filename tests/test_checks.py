import pytest
from helpers import EV1, EV2, bukti_asli, klaim, kode, narasi

from astria_verifier import checks as c
from astria_verifier.checks import Bukti, entitas, nilai_sama, normalisasi, periksa


def _gagal(teks: str, bukti=None, nilai=None, *, asli="ada") -> tuple[str, ...]:
    sumber = bukti_asli() if asli == "ada" else None
    return periksa(kode(), narasi([klaim(teks, bukti, nilai)]), sumber)[0].kode_gagal


def test_normalisasi_is_idempotent_and_strips_invisible() -> None:
    raw = "  Akun\u200b  ‘svc–backup’\t\n  "
    assert normalisasi(raw) == "akun 'svc-backup'"
    assert normalisasi(normalisasi(raw)) == normalisasi(raw)


@pytest.mark.parametrize(
    ("a", "b", "sama"),
    [
        ("10.20.8.31", "10.20.8.31", True),
        ("20", "020", True),
        ("SVC-BACKUP", "svc-backup", True),
        ("svc-backup", "svc-backup2", False),
        ("2026-11-10T09:16:31+07:00", "2026-11-10T02:16:31Z", True),
        ("2026-11-10T09:16:31", "2026-11-10T02:16:31Z", False),
        ("C:/ProgramData/upd/chk.exe", "c:\\programdata\\upd\\CHK.EXE", True),
        ("A" * 64, "a" * 64, True),
    ],
)
def test_nilai_sama_per_type(a: str, b: str, sama: bool) -> None:
    assert nilai_sama(a, b) is sama


def test_entitas_recognizes_identifiers_but_not_plain_words() -> None:
    found = entitas(
        "Akun svc-backup di WS-ADM-04 dari 10.20.8.31 menjalankan C:\\ProgramData\\upd\\chk.exe (EventID=4698)"
    )
    assert found == {"svc-backup", "ws-adm-04", "10.20.8.31", "c:\\programdata\\upd\\chk.exe", "eventid=4698"}
    assert entitas("Triage menilai insiden ini masing-masing KRITIS skor 71 pada 2026-11-10 pola P-AKUN-X") == set()


def test_clean_claims_pass_with_and_without_original_evidence() -> None:
    teks = "Akun svc-backup gagal logon dari 10.20.8.31 ke WS-ADM-04."
    assert _gagal(teks, nilai={"SrcIP": "10.20.8.31"}) == ()
    assert _gagal("Akun svc-backup gagal logon ke WS-ADM-04.", asli="tidak") == ()


@pytest.mark.parametrize(
    ("teks", "bukti", "nilai", "kode_gagal"),
    [
        ("Akun svc-backup gagal logon.", ["EV-palsu-1"], None, c.ID_TIDAK_DITEMUKAN),
        ("Lihat juga EV-palsu-2 untuk svc-backup.", None, None, c.ID_TIDAK_DITEMUKAN),
        ("Logon dari 10.20.8.31.", None, {"SrcIP": "10.20.8.99"}, c.VALID_TAPI_SALAH),
        ("Logon oleh svc-backup.", None, {"Workstation": "WS-HR-11"}, c.VALID_TAPI_SALAH),
        ("Akun svc-backup2 gagal logon.", None, None, c.ENTITAS_TIDAK_BERDASAR),
        ("Koneksi dari 10.99.0.1 ke WS-ADM-04.", None, None, c.ENTITAS_TIDAK_BERDASAR),
        ("Insiden ini TINGGI.", None, None, c.BERTENTANGAN_DENGAN_KODE),
        ("Skor 45/100 untuk svc-backup.", None, None, c.BERTENTANGAN_DENGAN_KODE),
        ("Cocok dengan pola P-BRUTE-TANPA-AKSES.", None, None, c.BERTENTANGAN_DENGAN_KODE),
        ("Teknik T1059.001 terlihat.", None, None, c.BERTENTANGAN_DENGAN_KODE),
        ("Jalankan langkah S-ISOLASI-HOST segera.", None, None, c.KODE_LANGKAH_ASING),
        ("Akun svc-backup adalah sumber serangan.", None, None, c.PERAN_BERTENTANGAN),
    ],
)
def test_each_check_has_its_failure_code(teks: str, bukti, nilai, kode_gagal: str) -> None:
    assert kode_gagal in _gagal(teks, bukti, nilai)


def test_quoted_value_without_original_evidence_is_not_trusted() -> None:
    assert _gagal("Logon dari 10.20.8.31.", nilai={"SrcIP": "10.20.8.31"}, asli="tidak") == (c.BUKTI_TIDAK_TERSEDIA,)


def test_changed_or_missing_evidence_is_flagged() -> None:
    berubah = bukti_asli() | {EV1: Bukti("0" * 64, {"TargetUserName": "svc-backup"})}
    hasil = periksa(kode(), narasi([klaim("Akun svc-backup gagal logon.")]), berubah)
    assert c.BUKTI_BERUBAH in hasil[0].kode_gagal
    hilang = {EV2: bukti_asli()[EV2]}
    hasil = periksa(kode(), narasi([klaim("Akun svc-backup gagal logon.")]), hilang)
    assert c.ID_TIDAK_DITEMUKAN in hasil[0].kode_gagal


def test_matching_role_passes_and_counter_hypotheses_are_checked_without_evidence() -> None:
    n = narasi(
        [klaim("Akun svc-backup diduga terbobol.", [EV1, EV2])],
        hipotesis_tandingan=[
            {"teks": "Skrip cadangan memakai kredensial lama.", "pembantah": "Tidak menjelaskan akun baru."}
        ],
        belum_diketahui=["Log WS-HR-11 tidak tersedia."],
    )
    hasil = periksa(kode(), n, bukti_asli())
    assert [(h.klaim.jenis, h.kode_gagal) for h in hasil] == [
        ("ringkasan", ()),
        ("hipotesis_utama", ()),
        ("tandingan", ()),
        ("pembantah", ()),
        ("belum_diketahui", ()),
    ]
    n = narasi(hipotesis_tandingan=[{"teks": "Teknik T1059.001 dipakai.", "pembantah": ""}])
    assert periksa(kode(), n, None)[2].kode_gagal == (c.BERTENTANGAN_DENGAN_KODE,)
