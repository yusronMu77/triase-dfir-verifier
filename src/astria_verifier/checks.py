"""Pemeriksaan klaim narasi terhadap kode kartu dan bukti asli (note app-verifier 5.4-5.6). Kode murni, tanpa I/O.

Verifier membuktikan keterlacakan (klaim menunjuk bukti yang ada dan nilainya cocok), bukan kebenaran semantik.
Pengenalan nama akun dan host adalah heuristik: token berbentuk identifier (memuat `-`, `_`, `.`, `\\`, atau
campuran huruf dan angka). Skema narasi (pemeriksaan 1) sudah ditegakkan model kontrak saat event diurai.
"""

from __future__ import annotations

import ipaddress
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime

from astria_contracts.events.card_skeleton_created import Kode
from astria_contracts.events.narration_completed import Narasi

TANPA_BUKTI = "TANPA_BUKTI"
ID_TIDAK_DITEMUKAN = "ID_TIDAK_DITEMUKAN"
VALID_TAPI_SALAH = "VALID_TAPI_SALAH"
ENTITAS_TIDAK_BERDASAR = "ENTITAS_TIDAK_BERDASAR"
BERTENTANGAN_DENGAN_KODE = "BERTENTANGAN_DENGAN_KODE"
KODE_LANGKAH_ASING = "KODE_LANGKAH_ASING"
PERAN_BERTENTANGAN = "PERAN_BERTENTANGAN"
BUKTI_BERUBAH = "BUKTI_BERUBAH"
BUKTI_TIDAK_TERSEDIA = "BUKTI_TIDAK_TERSEDIA"

SINONIM_PERAN: dict[str, tuple[str, ...]] = {
    "DIDUGA_TERBOBOL": ("diduga terbobol", "terbobol", "diambil alih"),
    "SUMBER_SERANGAN": ("sumber serangan", "penyerang"),
    "TERDAMPAK": ("terdampak",),
}
KATA_UMUM = frozenset({"e-mail", "log-in", "log-on", "non-aktif", "real-time", "follow-up"})

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"))
_SAMAKAN = str.maketrans({"’": "'", "‘": "'", "–": "-", "—": "-"})

IPV4 = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
HASH = re.compile(r"\b(?:[0-9a-fA-F]{64}|[0-9a-fA-F]{40}|[0-9a-fA-F]{32})\b")
PATH = re.compile(r"(?:\b[A-Za-z]:\\|\\\\)[^\s,;()\"']+")
EVENT = re.compile(r"\b(?:EventID\s*=\s*|ID event\s+|event\s+)(\d{1,5})\b", re.IGNORECASE)
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._\\-]*[A-Za-z0-9]")
EV_ID = re.compile(r"\bEV-[A-Za-z0-9_-]+")
KODE_LAIN = re.compile(r"^(?:EV|P|K|S|IC)-|^T\d{4}")
BAND = re.compile(r"\b(KRITIS|TINGGI|SEDANG|RENDAH)\b")
SKOR = re.compile(r"\bskor\s+(\d{1,3})\b|\b(\d{1,3})\s*/\s*100\b", re.IGNORECASE)
POLA = re.compile(r"\bP-[A-Z0-9][A-Z0-9-]*")
TEMUAN = re.compile(r"\bK-[A-Z0-9][A-Z0-9-]*")
TEKNIK = re.compile(r"\bT\d{4}(?:\.\d{3})?\b")
LANGKAH = re.compile(r"\bS-[A-Z0-9][A-Z0-9-]*")


@dataclass(frozen=True)
class Bukti:
    """Bukti asli dari ingest: hash rekaman, field terstruktur, dan teks lain (host, akun, kutipan)."""

    sha256: str
    fields: Mapping[str, str] = field(default_factory=dict)
    teks: tuple[str, ...] = ()


@dataclass(frozen=True)
class Klaim:
    index: int
    posisi: tuple[str, int]
    """Letak di narasi, mis. ("ringkasan", 2) atau ("pembantah", 0); dipakai kebijakan untuk membuang klaim."""
    teks: str
    bukti: tuple[str, ...] = ()
    nilai: Mapping[str, str] = field(default_factory=dict)

    @property
    def jenis(self) -> str:
        return self.posisi[0]

    @property
    def dihitung(self) -> bool:
        """`belum_diketahui` diperiksa tetapi tidak dihitung dalam persentase lolos."""
        return self.jenis != "belum_diketahui"


@dataclass(frozen=True)
class HasilKlaim:
    klaim: Klaim
    kode_gagal: tuple[str, ...]

    @property
    def lulus(self) -> bool:
        return not self.kode_gagal


def normalisasi(teks: str) -> str:
    t = unicodedata.normalize("NFKC", teks).translate(_ZERO_WIDTH).translate(_SAMAKAN)
    t = "".join(" " if c.isspace() else c for c in t if c.isspace() or unicodedata.category(c)[0] != "C")
    return " ".join(t.split()).casefold()


def _ip(s: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(s)
    except ValueError:
        return None


def _waktu(s: str) -> datetime | None:
    if not re.match(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", s):
        return None
    try:
        parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def nilai_sama(dikutip: str, asli: str) -> bool:
    """Perbandingan per tipe setelah normalisasi; eksak, tanpa fuzzy."""
    a, b = dikutip.strip(), asli.strip()
    if (ia := _ip(a)) is not None and (ib := _ip(b)) is not None:
        return ia == ib
    if a.isdigit() and b.isdigit():
        return int(a) == int(b)
    if (wa := _waktu(a)) is not None and (wb := _waktu(b)) is not None:
        return wa == wb
    if HASH.fullmatch(a) and HASH.fullmatch(b):
        return a.lower() == b.lower()
    if PATH.fullmatch(a) or PATH.fullmatch(b):
        return a.replace("/", "\\").casefold() == b.replace("/", "\\").casefold()
    return normalisasi(a) == normalisasi(b)


def _identifier(token: str) -> bool:
    if KODE_LAIN.match(token) or token.casefold() in KATA_UMUM:
        return False
    if not any(c.isalpha() for c in token):
        return False  # angka, tanggal, versi
    parts = token.casefold().split("-")
    if len(parts) > 1 and len(set(parts)) == 1:
        return False  # kata ulang: masing-masing
    has_sep = any(c in "._\\-" for c in token)
    return has_sep or any(c.isdigit() for c in token)


def entitas(teks: str) -> set[str]:
    """Entitas yang disebut teks, dinormalisasi: IP, hash, path, ID event, dan nama berbentuk identifier."""
    found: set[str] = set()
    sisa = teks
    for pola, norm in (
        (IPV4, lambda m: str(ip) if (ip := _ip(m)) else None),
        (HASH, str.lower),
        (PATH, lambda m: m.replace("/", "\\").casefold()),
        (EVENT, lambda n: f"eventid={n}"),
    ):
        for m in pola.findall(sisa):
            if (v := norm(m)) is not None:
                found.add(v)
        sisa = pola.sub(" ", sisa)
    found |= {normalisasi(t) for t in IDENT.findall(sisa) if _identifier(t)}
    return found


def daftar_klaim(narasi: Narasi) -> list[Klaim]:
    """Klaim berurutan: ringkasan, hipotesis utama, tandingan dan pembantahnya, lalu belum_diketahui."""
    out: list[Klaim] = []

    def tambah(posisi: tuple[str, int], teks: str, bukti: Iterable = (), nilai: Mapping[str, str] | None = None):
        out.append(Klaim(len(out), posisi, teks, tuple(b.root for b in bukti), dict(nilai or {})))

    for i, k in enumerate(narasi.ringkasan):
        tambah(("ringkasan", i), k.klaim, k.bukti, k.nilai_dikutip)
    tambah(("hipotesis_utama", 0), narasi.hipotesis_utama.teks, narasi.hipotesis_utama.bukti)
    for i, h in enumerate(narasi.hipotesis_tandingan):
        tambah(("tandingan", i), h.teks)
        if h.pembantah.strip():
            tambah(("pembantah", i), h.pembantah)
    for i, b in enumerate(narasi.belum_diketahui):
        tambah(("belum_diketahui", i), b.root)
    return out


def _korpus(teks: Iterable[str]) -> frozenset[str]:
    hasil: set[str] = set()
    for t in teks:
        hasil.add(normalisasi(t))
        hasil |= entitas(t)
    return frozenset(hasil)


@dataclass(frozen=True)
class _Kartu:
    """Turunan kode dan bukti yang dihitung sekali per kartu, bukan per klaim."""

    kode: Kode
    sha: Mapping[str, str]
    korpus_kode: frozenset[str]
    korpus_bukti: Mapping[str, frozenset[str]]
    kode_teks: str
    entitas_peran: tuple[tuple[re.Pattern[str], str], ...]
    sinonim_peran: tuple[tuple[str, re.Pattern[str]], ...]

    @classmethod
    def dari(cls, kode: Kode, bukti: Mapping[str, Bukti] | None) -> _Kartu:
        semua_peran = sorted(set(SINONIM_PERAN) | {e.peran for e in kode.entitas})
        return cls(
            kode=kode,
            sha={b.id.root: b.sha256 for b in kode.bukti},
            korpus_kode=_korpus([kode.judul, *(e.nilai for e in kode.entitas), *(f.alasan for f in kode.faktor)]),
            korpus_bukti={i: _korpus([*b.fields.values(), *b.teks]) for i, b in (bukti or {}).items()},
            kode_teks=kode.model_dump_json(),
            entitas_peran=tuple(
                (re.compile(rf"(?<![\w.-]){re.escape(normalisasi(e.nilai))}(?![\w-])"), e.peran) for e in kode.entitas
            ),
            sinonim_peran=tuple(
                (
                    peran,
                    re.compile(
                        r"\b(?:"
                        + "|".join(
                            re.escape(s) for s in (*SINONIM_PERAN.get(peran, ()), peran.replace("_", " ").casefold())
                        )
                        + r")\b"
                    ),
                )
                for peran in semua_peran
            ),
        )


def _peran_bertentangan(kartu: _Kartu, teks: str) -> bool:
    norm = normalisasi(teks)
    peran_entitas = {peran for pola, peran in kartu.entitas_peran if pola.search(norm)}
    if not peran_entitas:
        return False
    return any(pola.search(norm) and peran not in peran_entitas for peran, pola in kartu.sinonim_peran)


def _bertentangan_dengan_kode(kartu: _Kartu, teks: str) -> bool:
    kode = kartu.kode
    if any(band != kode.band for band in BAND.findall(teks)):
        return True
    if any(int(a or b) != kode.skor for a, b in SKOR.findall(teks)):
        return True
    if any(p != kode.pola for p in POLA.findall(teks)):
        return True
    return any(t not in kartu.kode_teks for t in (*TEMUAN.findall(teks), *TEKNIK.findall(teks)))


def _periksa_klaim(kartu: _Kartu, klaim: Klaim, bukti: Mapping[str, Bukti] | None) -> HasilKlaim:
    gagal: list[str] = []

    # 2 dan 3: klaim faktual wajib menunjuk bukti, dan setiap ID (juga yang disebut di teks) milik kartu ini.
    if klaim.jenis in ("ringkasan", "hipotesis_utama") and not klaim.bukti:
        gagal.append(TANPA_BUKTI)
    dirujuk = (*klaim.bukti, *EV_ID.findall(klaim.teks))
    if any(i not in kartu.sha or (bukti is not None and i not in bukti) for i in dirujuk):
        gagal.append(ID_TIDAK_DITEMUKAN)
    sumber = {i: bukti[i] for i in klaim.bukti if i in bukti} if bukti is not None else {}
    if any(b.sha256 != kartu.sha.get(i) for i, b in sumber.items()):
        gagal.append(BUKTI_BERUBAH)

    # 4: setiap nilai yang dikutip ada di field bukti yang dirujuk.
    if klaim.nilai:
        if bukti is None:
            gagal.append(BUKTI_TIDAK_TERSEDIA)
        elif not all(
            any(k in b.fields and nilai_sama(v, b.fields[k]) for b in sumber.values()) for k, v in klaim.nilai.items()
        ):
            gagal.append(VALID_TAPI_SALAH)

    # 5: entitas di teks berdasar pada kode kartu atau bukti (bukti dirujuk; tanpa rujukan: semua bukti kartu).
    dasar = sumber if klaim.bukti else kartu.korpus_bukti
    korpus = kartu.korpus_kode.union(*(kartu.korpus_bukti[i] for i in dasar))
    if entitas(klaim.teks) - korpus:
        gagal.append(ENTITAS_TIDAK_BERDASAR)

    # 6, 7, 8: konsisten dengan kode, tanpa kode langkah, peran tidak bertentangan.
    if _bertentangan_dengan_kode(kartu, klaim.teks):
        gagal.append(BERTENTANGAN_DENGAN_KODE)
    if LANGKAH.search(klaim.teks):
        gagal.append(KODE_LANGKAH_ASING)
    if _peran_bertentangan(kartu, klaim.teks):
        gagal.append(PERAN_BERTENTANGAN)
    return HasilKlaim(klaim, tuple(gagal))


def periksa(kode: Kode, narasi: Narasi, bukti: Mapping[str, Bukti] | None) -> list[HasilKlaim]:
    """Periksa semua klaim. `bukti` None berarti bukti asli tidak dibaca (ingest belum dikonfigurasi)."""
    kartu = _Kartu.dari(kode, bukti)
    return [_periksa_klaim(kartu, k, bukti) for k in daftar_klaim(narasi)]
