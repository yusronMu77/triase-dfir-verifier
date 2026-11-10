from helpers import EV1, EV2, bukti_asli, klaim, kode, narasi

from astria_verifier.checks import periksa
from astria_verifier.policy import evidence_set_hash, perlu_ulang, permintaan_ulang, putuskan

BAIK = "Akun svc-backup gagal logon ke WS-ADM-04."
BURUK = "Insiden ini RENDAH."


def _hasil(ringkasan, **overrides):
    n = narasi([klaim(t) for t in ringkasan], **overrides)
    return n, periksa(kode(), n, bukti_asli())


def _putuskan(ringkasan, **overrides):
    n, hasil = _hasil(ringkasan, **overrides)
    return putuskan(kode(), n, hasil)


def test_all_pass_is_lulus_with_full_model() -> None:
    kep = _putuskan([BAIK, BAIK])
    assert (kep.status, kep.klaim_total, kep.klaim_lolos, kep.ditolak) == ("LULUS", 3, 3, [])
    assert len(kep.model["ringkasan"]) == 2


def test_only_failed_counted_claims_on_attempt_1_request_retry_with_codes_only() -> None:
    _, hasil = _hasil([BAIK, BURUK])
    assert perlu_ulang(hasil, 1) and not perlu_ulang(hasil, 2)
    assert not perlu_ulang(_hasil([BAIK])[1], 1)
    assert not perlu_ulang(_hasil([BAIK], belum_diketahui=["Host WS-XX-99 belum diperiksa."])[1], 1)
    permintaan = permintaan_ulang(hasil)
    assert permintaan.attempt == 2
    assert permintaan.model_dump(mode="json")["kegagalan"] == [{"klaim_no": 1, "kode": "BERTENTANGAN_DENGAN_KODE"}]


def test_at_least_seventy_percent_is_sebagian_and_failed_claims_are_dropped() -> None:
    kep = _putuskan([BAIK, BAIK, BAIK, BURUK])  # 4 dari 5 klaim lolos (80%)
    assert kep.status == "SEBAGIAN"
    assert kep.ditolak == [{"klaim_index": 3, "kode_gagal": ["BERTENTANGAN_DENGAN_KODE"]}]
    assert [k["klaim"] for k in kep.model["ringkasan"]] == [BAIK, BAIK, BAIK]


def test_failed_main_hypothesis_is_replaced_by_card_title() -> None:
    kep = _putuskan([BAIK, BAIK, BAIK], hipotesis_utama={"teks": "Jelas TINGGI.", "bukti": [EV2]})
    assert kep.status == "SEBAGIAN"
    assert kep.model["hipotesis_utama"] == {"teks": kode().judul, "bukti": [EV1, EV2]}


def test_below_threshold_or_empty_is_templat_without_model_text() -> None:
    kep = _putuskan([BURUK, BURUK])
    assert (kep.status, kep.model) == ("TEMPLAT", {})
    n = narasi([], hipotesis_utama={"teks": "Insiden ini RENDAH.", "bukti": [EV1]})
    assert putuskan(kode(), n, periksa(kode(), n, bukti_asli())).status == "TEMPLAT"


def test_failed_unknowns_are_dropped_but_not_counted() -> None:
    kep = _putuskan([BAIK], belum_diketahui=["Host WS-XX-99 belum diperiksa.", "Log WS-HR-11 tidak ada."])
    assert (kep.status, kep.klaim_total) == ("LULUS", 2)
    assert kep.model["belum_diketahui"] == ["Log WS-HR-11 tidak ada."]


def test_evidence_set_hash_is_order_independent() -> None:
    k = kode()
    dibalik = k.model_copy(update={"bukti": list(reversed(k.bukti))})
    assert evidence_set_hash(k) == evidence_set_hash(dibalik)
    assert evidence_set_hash(k).startswith("sha256:")
