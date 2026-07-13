from lol_esports_scraper.models import MatchRecord, ParsedBatch
from lol_esports_scraper.reconcile import Reconciler


def test_reconciles_same_series_from_two_sources() -> None:
    left = MatchRecord(source="gol", tournament="LCK Spring", match_date="2026-01-01", team1="T1", team2="GEN")
    right = MatchRecord(
        source="loltv",
        tournament="LCK Spring",
        match_date="2026-01-01",
        team1="GEN",
        team2="T1",
        series_format="Bo3",
    )

    batch = Reconciler().reconcile_batch(ParsedBatch(matches=[left, right]))

    assert len(batch.matches) == 1
    assert batch.matches[0].series_format == "Bo3"
    assert set(batch.matches[0].source.split(",")) == {"gol", "loltv"}
