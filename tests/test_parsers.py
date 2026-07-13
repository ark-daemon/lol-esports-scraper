from lol_esports_scraper.models import SourcePage
from lol_esports_scraper.parsers import parse_gol, parse_loltv


def test_parse_loltv_html_match_table_defensively() -> None:
    page = SourcePage(
        source="loltv",
        url="https://example.test",
        region="LCK",
        html="""
        <table>
          <tr><th>Date</th><th>Tournament</th><th>Team 1</th><th>Team 2</th><th>Score</th><th>Format</th></tr>
          <tr><td>2026-01-01</td><td>LCK Spring</td><td>T1</td><td>GEN</td><td>2-1</td><td>Bo3</td></tr>
        </table>
        """,
    )

    batch = parse_loltv(page)

    assert len(batch.matches) == 1
    assert batch.matches[0].team1 == "T1"
    assert batch.matches[0].team1_score == 2
    assert batch.matches[0].series_format == "Bo3"


def test_parse_gol_json_match_before_html() -> None:
    page = SourcePage(
        source="gol",
        url="https://example.test",
        region="LEC",
        html="<html></html>",
        json_payloads=[
            {
                "_request_url": "https://example.test/api",
                "payload": {
                    "matches": [
                        {
                            "date": "2026-02-03",
                            "tournament": "LEC Winter",
                            "team 1": "G2",
                            "team 2": "FNC",
                            "score": "1-0",
                            "patch": "16.1",
                        }
                    ]
                },
            }
        ],
    )

    batch = parse_gol(page)

    assert len(batch.matches) == 1
    assert batch.matches[0].team1 == "G2"
    assert batch.games[0].patch == "16.1"
