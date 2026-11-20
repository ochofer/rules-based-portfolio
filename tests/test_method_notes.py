"""The notes that state what a claim rests on: the three sources under the allocation test's figure, the
rules' notes under the rules card, and the series that prices Europe and the Middle East."""

import pandas as pd

from portfolio import config, site

MANDATE = config.ROOT / "mandate"


def test_the_allocation_figure_gives_the_three_sources_and_what_of_their_gap_is_measured():
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv")
    text = site._sources_text(allocation)
    held = allocation[allocation["chosen"] == "yes"].iloc[0]
    assert text.startswith(f" At the equity ETF's weights by region in the holdings file of 13 November 2026, 70/30's "
                           f"worst fall is {held['worst_fall'] * 100:.2f} per cent")
    order = [text.index(s) for s in ("The fund tracks MSCI ACWI.", "The two sources disagree about the split.",
                                     "French's series decides because", "French's market returns include dividends",
                                     "are not measured.", "With the bond at 5 years", "rule 11 moves it")]
    assert order == sorted(order)
    assert "the largest split within 35 per cent is 65/35" in text
    assert site._sources_text(allocation, comparison=pd.DataFrame()) == ""


def test_every_note_of_the_rules_table_stands_under_the_rules_card():
    rules = (config.ROOT / "rules" / "RULES.md").read_text(encoding="utf-8")
    notes = site._rules_notes()
    assert "A note says what a statement of this file rests on and changes no rule and no order." in rules
    assert notes.count('<p class="note">Note of ') == rules.count(" | Note | ") == 2
    assert "Note of 19 November 2026: &quot;The order was fixed before the funds were compared&quot; rests on" in notes


def test_europe_and_the_middle_east_is_priced_by_msci_europe_for_the_reason_the_note_gives():
    summary = pd.read_csv(config.OUTPUTS_DIR / "risk_summary.csv").iloc[0]
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    start = site._month_name(summary["earlier_window_start"])
    assert ("MSCI publishes an index of Europe and the Middle East, but its month-end levels in MSCI&#x27;s public tool "
            f"begin in May 2010, after the start of the earlier window in {start} and of the episode of 2007 to 2009") in page
    assert "MSCI publishes no series" not in page
