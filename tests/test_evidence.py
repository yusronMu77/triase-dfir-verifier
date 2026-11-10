import pytest
from helpers import EV1, EV2, bukti_asli

from astria_verifier.evidence import ambil_bukti

pytestmark = pytest.mark.anyio


class Ingest:
    """Ingest tiruan: ID dalam `telat` baru tersedia pada panggilan kedua."""

    def __init__(self, telat: set[str]) -> None:
        self.telat = telat
        self.calls: list[list[str]] = []

    async def fetch(self, ids):
        self.calls.append(list(ids))
        siap = {i for i in ids if i not in self.telat or len(self.calls) > 1}
        return {i: b for i, b in bukti_asli().items() if i in siap}


async def test_complete_answer_is_fetched_once() -> None:
    ingest = Ingest(set())
    assert set(await ambil_bukti(ingest, [EV1, EV2], jeda=0)) == {EV1, EV2}
    assert ingest.calls == [[EV1, EV2]]


async def test_missing_ids_are_retried_once() -> None:
    ingest = Ingest({EV2})
    assert set(await ambil_bukti(ingest, [EV1, EV2], jeda=0)) == {EV1, EV2}
    assert ingest.calls == [[EV1, EV2], [EV2]]


async def test_ids_still_missing_after_retry_are_left_out() -> None:
    ingest = Ingest({"EV-hilang-1"})
    assert set(await ambil_bukti(ingest, [EV1, "EV-hilang-1"], jeda=0)) == {EV1}
    assert len(ingest.calls) == 2
