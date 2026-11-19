"""The notes that state what a claim rests on: the test at other settings under the allocation test's figure, the
rules' notes under the rules card, and the series that prices Europe and the Middle East."""

import pandas as pd

from portfolio import config, site

MANDATE = config.ROOT / "mandate"


def test_the_allocation_figure_gives_both_of_msci_s_shares_and_the_state_of_the_target():
    allocation = pd.read_csv(MANDATE / "allocation_check_results.csv")
    settings = pd.read_csv(MANDATE / "allocation_check_settings.csv")
    turning = pd.read_csv(MANDATE / "allocation_check_settings_turning.csv").set_index("bond_maturity_years")
    text = site._settings_text(allocation, settings)
    assert text.startswith(" At the test's own settings 70/30's worst fall is 34.7 per cent, 0.3 points inside the limit")
    late = text.index("At MSCI's share of emerging markets for 2002, 4.0 per cent, the test gives 65/35 with the bond at 7 or 6.7 years")
    early = text.index("At its share for 1997, 6.8 per cent, it gives 70/30")
    assert late < early
    assert (f"the answer turns at a share of {turning.loc[7.0, 'turning_share'] * 100:.1f} per cent at 7 years and "
            f"{turning.loc[6.7, 'turning_share'] * 100:.1f} at 6.7, so on MSCI's own figures the test does not decide "
            "between 70/30 and 65/35.") in text
    assert f"Over the 24 settings of mandate/allocation_check_settings.csv, 70/30 stays within 35 per cent in " \
           f"{int((settings['worst_fall_70_30'] <= 0.35).sum())}." in text
    assert "The target is 70/30 and has not been amended. A change would be an amendment under rule 9." in text
    assert ("65/35 is the lower edge of the band rule 5 allows around a target of 70/30. A weight at that edge is not "
            "a target, and a target of 65/35 would carry a band of its own.") in text
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
