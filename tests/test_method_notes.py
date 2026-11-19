"""The notes that state what a claim rests on: the test at other settings under the allocation test's figure, the
rules' notes under the rules card, and the series that prices Europe and the Middle East."""

import pandas as pd

from portfolio import config, site

MANDATE = config.ROOT / "mandate"


def test_the_allocation_figure_gives_the_test_at_the_share_for_2002_first():
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv")
    settings = pd.read_csv(MANDATE / "allocation_check_settings.csv")
    text = site._settings_text(allocation, settings)
    sourced = settings[settings["added_with"] == "MSCI's share for 2002"].set_index("bond_maturity_years")
    split = sourced.loc[7.0, "largest_split_within_limit"]
    assert text.startswith(f" At the share of emerging markets MSCI reports for 2002, 4.0 per cent, the test gives {split}:")
    assert f"over the 20 settings of mandate/allocation_check_settings.csv, 70/30 stays within 35 per cent in " \
           f"{int((settings['worst_fall_70_30'] <= 0.35).sum())}." in text
    assert "0.3 points inside the limit" in text and "65/35 is the lower edge of the band" in text
    assert site._settings_text(allocation, pd.DataFrame()) == ""


def test_every_note_of_the_rules_table_stands_under_the_rules_card():
    rules = (config.ROOT / "rules" / "RULES.md").read_text(encoding="utf-8")
    notes = site._rules_notes()
    assert "A note says what a statement of this file rests on and changes no rule and no order." in rules
    assert notes.count('<p class="note">Note of ') == rules.count(" | Note | ") == 1
    assert "Note of 19 November 2026: &quot;The order was fixed before the funds were compared&quot; rests on" in notes


def test_europe_and_the_middle_east_is_priced_by_msci_europe_for_the_reason_the_note_gives():
    summary = pd.read_csv(config.OUTPUTS_DIR / "risk_summary.csv").iloc[0]
    page = (config.ROOT / "index.html").read_text(encoding="utf-8")
    start = site._month_name(summary["earlier_window_start"])
    assert ("MSCI publishes an index of Europe and the Middle East, but its month-end levels in MSCI&#x27;s public tool "
            f"begin in May 2010, after the start of the earlier window in {start} and of the episode of 2007 to 2009") in page
    assert "MSCI publishes no series" not in page
