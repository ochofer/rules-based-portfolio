"""Rule 11 on invented records and weights: no change; a change with the equity weight inside the new band; a change
with the weight outside it and inside the old edge, where nothing is sold; a weight beyond the old edge; a change in
each direction; two changes before the weight has entered a band. The readings: a month end without one breaks the
pair, none changes nothing, and a row written late, on files not as committed or with a country the French list does
not place gives none. The record and the targets table: each row written once and kept as first written. The cycle
command's stop, and the band on a day between two cycle days."""

from datetime import date

import pandas as pd
import pytest

from portfolio import __main__ as cli, config, cycle_report, lookthrough, rule_11, rules_engine

E, B = config.EQUITY, config.BONDS


def record(*splits, first="2026-11"):
    """An invented record: one row per month end from first, with the largest split within 35 per cent given, or no
    reading where the split is None."""
    month = pd.Period(first, "M")
    rows = []
    for split in splits:
        reading = {"reading": "yes", "largest_split": split} if split else {"reading": "no", "reason": "Invented"}
        rows.append({c: "" for c in rule_11.RECORD_COLUMNS} | {"month_end": str(month)} | reading)
        month += 1
    return pd.DataFrame(rows, columns=rule_11.RECORD_COLUMNS)


def weights(*by_day):
    """weight_after_top_up for targets(): the equity weight after the top-up on each cycle day in turn."""
    days = rule_11.cycle_days(date(2027, 12, 31))
    table = dict(zip(days, by_day))
    return lambda day, target: table.get(day, target[E])


def rows(table):
    return table.set_index("cycle_day")


def sells(weight: float, band: tuple, target: float) -> bool:
    """Whether rule 5 sells on a cycle day at this equity weight after the top-up, with no cash left."""
    plan = rules_engine.plan(weight * 100, (1 - weight) * 100, 0.0, target={E: target, B: 1 - target}, band=band)
    return any(o.side == "sell" for o in plan.orders)


def test_no_change_keeps_70_30_and_its_band():
    table = rows(rule_11.targets(record("70/30", "70/30", "70/30"), date(2027, 2, 28), weights(0.70, 0.71)))
    assert list(table["target_after"]) == ["70/30", "70/30"]
    assert (table["band_low"].iloc[0], table["band_high"].iloc[0]) == (0.65, 0.75)
    assert rule_11.target_on(date(2027, 3, 1), table.reset_index()) == {E: 0.70, B: 0.30}


def test_a_change_with_the_weight_inside_the_new_band_takes_the_new_band_that_day():
    table = rows(rule_11.targets(record("65/35", "65/35"), date(2027, 1, 31), weights(0.68)))
    row = table.loc["2027-01-05"]
    assert (row["first_reading"], row["second_reading"], row["target_before"], row["target_after"]) == (
        "65/35", "65/35", "70/30", "65/35")
    assert (row["band_low"], row["band_high"]) == (0.60, 0.70)


def test_a_change_with_the_weight_outside_the_new_band_and_inside_the_old_edge_sells_nothing():
    table = rows(rule_11.targets(record("65/35", "65/35"), date(2027, 1, 31), weights(0.72)))
    band = (table.loc["2027-01-05", "band_low"], table.loc["2027-01-05", "band_high"])
    assert band == (0.60, 0.75)  # the new band's lower edge, and the old band's upper edge on the weight's side
    assert not sells(0.72, band, 0.65)


def test_a_weight_beyond_the_old_edge_is_brought_to_the_new_target():
    table = rows(rule_11.targets(record("65/35", "65/35"), date(2027, 2, 28), weights(0.76, 0.70)))
    band = (table.loc["2027-01-05", "band_low"], table.loc["2027-01-05", "band_high"])
    assert band == (0.60, 0.75) and sells(0.76, band, 0.65)
    plan = rules_engine.plan(76.0, 24.0, 0.0, target={E: 0.65, B: 0.35}, band=band)
    assert plan.after[E] / sum(plan.after.values()) == pytest.approx(0.65, abs=1e-4)
    # After the band order the weight is inside the new band, so the next cycle day has the new band alone.
    assert (table.loc["2027-02-05", "band_low"], table.loc["2027-02-05", "band_high"]) == (0.60, 0.70)


def test_a_change_upwards_keeps_the_old_lower_edge_until_the_weight_is_inside():
    table = rows(rule_11.targets(record("75/25", "75/25"), date(2027, 2, 28), weights(0.68, 0.71)))
    assert table.loc["2027-01-05", "target_after"] == "75/25"
    assert (table.loc["2027-01-05", "band_low"], table.loc["2027-01-05", "band_high"]) == (0.65, 0.80)
    assert not sells(0.68, (0.65, 0.80), 0.75)
    assert (table.loc["2027-02-05", "band_low"], table.loc["2027-02-05", "band_high"]) == (0.70, 0.80)


def test_two_changes_before_the_weight_enters_a_band_keep_the_edge_of_the_last_band_it_was_inside():
    # 65/35 at November and December moves the target on 5 January; 60/40 at December and January would need both
    # month ends, so 60/40 at January and February moves it again on 5 March. The weight stays at 0.72 and 0.71.
    table = rows(rule_11.targets(record("65/35", "65/35", "60/40", "60/40"), date(2027, 3, 31), weights(0.72, 0.72, 0.71)))
    assert list(table["target_after"]) == ["65/35", "65/35", "60/40"]
    assert (table.loc["2027-03-05", "band_low"], table.loc["2027-03-05", "band_high"]) == (0.55, 0.75)
    assert not sells(0.71, (0.55, 0.75), 0.60)


def test_a_missing_month_end_or_two_different_splits_change_nothing():
    table = rows(rule_11.targets(record("65/35"), date(2027, 2, 28), weights(0.70, 0.70)))
    assert list(table["target_after"]) == ["70/30", "70/30"]
    assert table.loc["2027-01-05", "second_reading"] == ""
    table = rows(rule_11.targets(record("65/35", "75/25"), date(2027, 1, 31), weights(0.70)))
    assert table.loc["2027-01-05", "target_after"] == "70/30"


def test_the_cycle_report_line_names_the_month_ends_the_splits_and_the_change():
    row = rule_11.targets(record("65/35", "65/35"), date(2027, 1, 31), weights(0.72)).iloc[0].to_dict()
    check = cycle_report.check_rule_11(row, record("65/35", "65/35"))
    assert check.rule == "11" and check.passed
    assert check.figure == ("30 November 2026: 65/35. 31 December 2026: 65/35. New target 65/35 from this cycle day, "
                            "band in force 60 to 75")
    row = rule_11.targets(record("70/30", "70/30"), date(2027, 1, 31), weights(0.70)).iloc[0].to_dict()
    assert rule_11.line(row, record("70/30", "70/30")).endswith("No change: target 70/30, band 65 to 75")
    row = rule_11.targets(record("65/35", None), date(2027, 1, 31), weights(0.70)).iloc[0].to_dict()
    assert rule_11.line(row, record("65/35", None)).startswith("30 November 2026: 65/35. 31 December 2026: no reading, invented.")


def test_the_record_writes_each_month_end_once_and_never_rewrites_a_row():
    served = []

    def holdings(month, today):
        served.append(str(month))
        return (f"file-{month}", pd.Timestamp(rule_11.last_trading_day(month)))

    def row(month, path, as_of, today):
        return {c: "" for c in rule_11.RECORD_COLUMNS} | {"month_end": str(month), "holdings_as_of": str(as_of.date()),
                                                          "written_on": today.isoformat(), "reading": "yes",
                                                          "largest_split": "70/30"}

    first = rule_11.update_record(pd.DataFrame(), date(2026, 12, 2), holdings, row)
    assert list(first["month_end"]) == ["2026-11"] and served == ["2026-11"]
    edited = first.copy()
    edited.loc[0, "largest_split"] = "kept as written"
    second = rule_11.update_record(edited, date(2027, 1, 4), holdings, row)
    assert list(second["month_end"]) == ["2026-11", "2026-12"] and served == ["2026-11", "2026-12"]
    assert second.loc[0, "largest_split"] == "kept as written"
    assert len(rule_11.update_record(pd.DataFrame(), date(2026, 11, 30), holdings, row)) == 0


def test_the_record_stops_at_a_month_end_whose_file_is_not_served_yet():
    table = rule_11.update_record(pd.DataFrame(), date(2026, 12, 4), lambda month, today: None, lambda *a: {})
    assert len(table) == 0 and list(table.columns) == rule_11.RECORD_COLUMNS


def test_before_5_january_2027_the_rules_of_version_1_0_are_in_force():
    assert rule_11.in_force(None, None, date(2026, 12, 7)) == (dict(config.TARGET), tuple(config.BAND), None)
    assert rule_11.target_on(date(2026, 12, 7), pd.DataFrame(columns=rule_11.TARGET_COLUMNS)) == {E: 0.70, B: 0.30}


# The readings ---------------------------------------------------------------------------------------------------


def found(month, today):
    return (f"file-{month}", pd.Timestamp(rule_11.last_trading_day(month)))


def reading_row(month, path, as_of, today):
    return {c: "" for c in rule_11.RECORD_COLUMNS} | {"month_end": str(month), "written_on": today.isoformat(),
                                                      "reading": "yes", "holdings_as_of": str(as_of.date()),
                                                      "largest_split": "65/35"}


def test_a_month_end_without_a_reading_breaks_the_pair():
    # November 65/35, December without a reading, January and February 65/35: nothing changes on the cycle days of
    # January and February, and the cycle day of March reads January and February.
    table = rows(rule_11.targets(record("65/35", None, "65/35", "65/35"), date(2027, 3, 31), weights(0.70, 0.70, 0.66)))
    assert list(table["target_after"]) == ["70/30", "70/30", "65/35"]
    assert (table.loc["2027-01-05", "second_reading"], table.loc["2027-02-05", "first_reading"]) == ("no reading",) * 2
    assert (table.loc["2027-03-05", "first_month_end"], table.loc["2027-03-05", "second_month_end"]) == ("2027-01", "2027-02")


def test_a_reading_of_none_changes_nothing_and_raises_no_error():
    table = rows(rule_11.targets(record("none", "none", "65/35"), date(2027, 2, 28), weights(0.70, 0.70)))
    assert list(table["target_after"]) == ["70/30", "70/30"]
    assert table.loc["2027-01-05", "first_reading"] == "none"


def test_a_row_written_on_the_cycle_day_before_the_rules_are_applied_counts():
    # The December row, written on 5 January 2027 before the cycle command, gives a reading. Once the rules have been
    # applied that day, a row written then gives none.
    before = rule_11.update_record(record("65/35"), date(2027, 1, 5), found, reading_row, applied=lambda day: False)
    assert before.loc[1, "reading"] == "yes" and before.loc[1, "written_on"] == "2027-01-05"
    after = rule_11.update_record(record("65/35"), date(2027, 1, 5), found, reading_row, applied=lambda day: True)
    assert after.loc[1, "reading"] == "no"
    assert after.loc[1, "reason"] == "No row was written before the rules were applied on the cycle day of 5 January 2027"


def test_a_row_written_after_its_cycle_day_gives_no_reading_and_the_targets_rows_stay_as_first_written():
    # The build of 6 February 2027 finds no January row and writes one with no reading. The rows of 5 January and
    # 5 February are kept: a later record cannot move the target on a day whose orders are done.
    late = rule_11.update_record(record("70/30", "65/35"), date(2027, 2, 6), found, reading_row)
    assert (late.loc[2, "month_end"], late.loc[2, "reading"]) == ("2027-01", "no")
    assert late.loc[2, "reason"] == "No row was written on or before the cycle day of 5 February 2027"
    kept = rule_11.targets(late, date(2027, 2, 28), weights(0.70, 0.70)).astype(str)
    assert list(kept["target_after"]) == ["70/30", "70/30"]
    rewritten = record("70/30", "65/35", "65/35", "65/35")
    table = rows(rule_11.targets(rewritten, date(2027, 3, 31), weights(0.70, 0.70, 0.66), kept))
    assert list(table["target_after"]) == ["70/30", "70/30", "65/35"]
    assert table.loc["2027-02-05", "second_reading"] == "no reading"


def test_a_month_end_with_no_file_before_its_cycle_day_gives_no_reading_and_later_month_ends_are_read():
    none = lambda month, today: None if str(month) == "2026-12" else found(month, today)  # noqa: E731
    first = rule_11.update_record(record("70/30"), date(2027, 1, 4), none, reading_row)
    assert list(first["month_end"]) == ["2026-11"]  # the cycle day of 5 January is still to come: it waits
    second = rule_11.update_record(first, date(2027, 1, 5), none, reading_row)
    assert (second.loc[1, "reading"], second.loc[1, "reason"]) == (
        "no", "No holdings file is dated from 30 December 2026 to the day before the cycle day of 5 January 2027")
    third = rule_11.update_record(second, date(2027, 2, 2), none, reading_row)
    assert (third.loc[2, "month_end"], third.loc[2, "reading"]) == ("2027-01", "yes")


def test_the_holdings_file_is_tried_from_the_last_trading_day_to_the_day_before_the_cycle_day(monkeypatch, tmp_path):
    tried = []

    def fetch(name, url, refresh, cache_dir):
        tried.append(name[-14:-4])
        path = tmp_path / name.split("/")[-1]
        path.write_text('Fund Holdings as of,"-"\n', encoding="utf-8")
        return path

    monkeypatch.setattr(rule_11.prices, "fetch", fetch)
    assert rule_11.holdings_at(pd.Period("2026-12", "M"), date(2027, 1, 20)) is None
    assert tried == ["2026-12-30", "2027-01-04"]  # Xetra closes on 31 December and 1 January, and 5 January is the cycle day


def test_files_or_values_not_as_committed_or_a_country_not_placed_give_no_reading(monkeypatch):
    monkeypatch.setattr(lookthrough, "parse_ishares_holdings", lambda path: (pd.DataFrame(), pd.Timestamp("2026-11-30")))
    monkeypatch.setattr(lookthrough, "equity_lines", lambda frame: frame)
    monkeypatch.setattr(lookthrough, "allocation_regions", lambda lines, as_of: pd.DataFrame())

    class Module:
        def __init__(self, committed, ecb="yes"):
            self.committed, self.ecb = committed, ecb

        def run_at(self, table):
            return {"largest_split": "65/35", "french_files_as_committed": self.committed,
                    "ecb_values_as_committed": self.ecb}

    month, day = pd.Period("2026-11", "M"), date(2026, 12, 2)
    monkeypatch.setattr(lookthrough, "unplaced_countries", lambda frame: [])
    assert rule_11.record_row(month, "f", pd.Timestamp("2026-11-30"), day, Module("yes"))["reading"] == "yes"
    row = rule_11.record_row(month, "f", pd.Timestamp("2026-11-30"), day, Module("no"))
    assert row["reading"] == "no" and "not those whose hashes are committed" in row["reason"]
    row = rule_11.record_row(month, "f", pd.Timestamp("2026-11-30"), day, Module("yes", ecb="no"))
    assert row["reading"] == "no" and row["reason"].startswith("The values the test reads from the European Central Bank's")
    monkeypatch.setattr(lookthrough, "unplaced_countries", lambda frame: ["Atlantis"])
    row = rule_11.record_row(month, "f", pd.Timestamp("2026-11-30"), day, Module("yes"))
    assert row["reading"] == "no" and row["reason"].endswith("does not place: Atlantis") and row["largest_split"] == ""
    assert rule_11.readings(pd.DataFrame([row]))["2026-11"] == "no reading"


def test_a_country_the_french_list_does_not_place_is_found():
    frame = pd.DataFrame({"Asset Class": ["Equity", "Equity", "Cash"], "Ticker": ["AAPL", "ZZZ", "EUR"],
                          "Location": ["United States", "Atlantis", "Atlantis"]})  # fmt: skip
    assert lookthrough.unplaced_countries(frame) == ["Atlantis"]


def test_the_cycle_command_stops_when_a_month_end_it_reads_has_no_row():
    with pytest.raises(SystemExit, match="no row for the month end of 30 November 2026"):
        cli._stop_without_rows(date(2026, 12, 7), record())
    with pytest.raises(SystemExit, match="31 December 2026"):
        cli._stop_without_rows(date(2027, 1, 5), record("70/30"))
    cli._stop_without_rows(date(2027, 1, 5), record("70/30", None))
    cli._stop_without_rows(date(2026, 11, 5), record())


def test_between_two_cycle_days_the_band_is_that_of_the_last_cycle_days_row():
    table = rule_11.targets(record("65/35", "65/35"), date(2027, 2, 28), weights(0.72, 0.72)).astype(str)
    assert rule_11.band_on(date(2027, 1, 20), table) == (0.60, 0.75)
    assert rule_11.band_on(date(2027, 2, 20), table) == (0.60, 0.75)
    assert rule_11.band_on(date(2026, 12, 20), table) == (0.65, 0.75)
    assert rule_11.target_on(date(2027, 1, 20), table) == {E: 0.65, B: 0.35}
