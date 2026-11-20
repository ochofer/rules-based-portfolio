"""Rule 11: the target follows the allocation test.

Each month end from 30 November 2026 gives a reading of the allocation test of mandate/allocation_check.py, or gives
none. A reading is the test run on the equity ETF's weights by region in the issuer's holdings file dated the month's
last trading day on Xetra's calendar, or, where the issuer publishes none for that day, in the first file dated after
it and before the cycle day that follows the month end. Its row is written once to outputs/allocation_record.csv,
on that cycle day at the latest and before the rules are applied on it, and never rewritten. The rules count as
applied on a cycle day once its cycle report or its row of outputs/allocation_targets.csv is written. A month end
gives no reading, and its row says why, when no such file is found, when no row is written in time, when the test
runs on files of French's library other than the five whose hashes are committed, or on values of the European
Central Bank's three series other than those whose digests are committed, or when the holdings file has a country
that method/french_regions.csv does not place. Later month ends are still read. Where no split is within 35 per
cent, the reading is none.

From the cycle day of 5 January 2027, each cycle day reads the two month ends before it, and both must give a
reading. When they give the same split, other than none, and it differs from the target weights, it becomes the
target weights from that cycle day, in either direction, and the band is 5 points either side of the new equity
target weight. The change adds no order. Rule 5 applies with the new band from the first cycle day on which the
equity weight, after the top-up, is inside it. Until then the edge, on that side, of the last band the equity weight
was inside stays in force, and beyond it rule 5 brings the portfolio to the new target weights.
outputs/allocation_targets.csv keeps, as first written, one row for each cycle day from 5 January 2027: the two month
ends, the reading of each, the target before and after, and the band in force that day. Every other part of the
program reads the target and the band from that table, and on a day between two cycle days the band of the last
cycle day's row.
"""

from __future__ import annotations

import importlib.util
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from . import config, lookthrough, prices, rules_engine, trading_days

E, B = config.EQUITY, config.BONDS
FIRST_MONTH_END = pd.Period("2026-11", "M")
FROM = date(2027, 1, 5)
RECORD = config.OUTPUTS_DIR / "allocation_record.csv"
TARGETS = config.OUTPUTS_DIR / "allocation_targets.csv"
HALF_WIDTH = 0.05
NONE, NO_READING = "none", "no reading"
HOLDINGS_AT = prices.ISHARES_DOCUMENT.format(component="holdings") + "&asOfDate={day:%Y%m%d}"
RECORD_COLUMNS = [
    "month_end", "written_on", "reading", "reason", "holdings_as_of", "weight_north_america", "weight_europe",
    "weight_japan", "weight_asia_pacific_ex_japan", "weight_emerging", "french_database", "french_files_as_committed",
    "ecb_values_as_committed",
    "worst_fall_65_35", "worst_fall_70_30", "worst_fall_75_25", "largest_split",
    "msci_regions_worst_fall_65_35_low", "msci_regions_worst_fall_65_35_high",
    "msci_regions_worst_fall_70_30_low", "msci_regions_worst_fall_70_30_high",
    "msci_regions_worst_fall_75_25_low", "msci_regions_worst_fall_75_25_high", "msci_regions_largest_split",
    "msci_acwi_worst_fall_65_35_low", "msci_acwi_worst_fall_65_35_high",
    "msci_acwi_worst_fall_70_30_low", "msci_acwi_worst_fall_70_30_high",
    "msci_acwi_worst_fall_75_25_low", "msci_acwi_worst_fall_75_25_high", "msci_acwi_largest_split",
]  # fmt: skip
TARGET_COLUMNS = ["cycle_day", "first_month_end", "first_reading", "second_month_end", "second_reading",
                  "target_before", "target_after", "band_low", "band_high"]  # fmt: skip


def allocation_check():
    """mandate/allocation_check.py as a module."""
    spec = importlib.util.spec_from_file_location("allocation_check", config.ROOT / "mandate" / "allocation_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def split_weight(split: str) -> float:
    """The equity target weight of a split written equity/bonds: "65/35" -> 0.65."""
    return int(split.split("/")[0]) / 100


def split_name(weight: float) -> str:
    return f"{round(weight * 100)}/{round((1 - weight) * 100)}"


def band_of(weight: float) -> tuple:
    return (round(weight - HALF_WIDTH, 4), round(weight + HALF_WIDTH, 4))


def last_trading_day(month: pd.Period) -> date:
    day = month.to_timestamp(how="end").date()
    while not trading_days.is_trading_day(day):
        day -= timedelta(days=1)
    return day


def cycle_day_after(month: pd.Period) -> date:
    """The cycle day that follows a month end: the cycle day of the next month."""
    following = month + 1
    return trading_days.cycle_day(following.year, following.month)


def _words(day: date) -> str:
    return f"{day.day} {day:%B %Y}"


# The record ---------------------------------------------------------------------------------------------------


def holdings_at(month: pd.Period, today: date, refresh: bool = False, cache_dir: Path = config.CACHE_DIR):
    """The issuer's holdings file for a month end: the file dated the month's last trading day, or the first file
    dated after it and before the cycle day that follows the month end, where the issuer publishes none for that day.
    Files dated after today are not tried. Returns its path and date, or None when no such file is served."""
    day, before = last_trading_day(month), cycle_day_after(month)
    while day < before and day <= today:
        name = f"ishares/IE00B6R52259_holdings_{day:%Y-%m-%d}.csv"
        path = prices.fetch(name, HOLDINGS_AT.format(day=day), refresh, cache_dir=cache_dir)
        first = Path(path).read_text(encoding="utf-8-sig").splitlines()[0]
        if '"-"' not in first:
            frame, as_of = lookthrough.parse_ishares_holdings(path)
            return path, as_of
        Path(path).unlink()
        day += timedelta(days=1)
        while not trading_days.is_trading_day(day):
            day += timedelta(days=1)
    return None


def _no_reading(month: pd.Period, today: date, reason: str) -> dict:
    return {c: "" for c in RECORD_COLUMNS} | {"month_end": str(month), "written_on": today.isoformat(),
                                               "reading": "no", "reason": reason}


def record_row(month: pd.Period, path: Path, as_of, today: date, module=None) -> dict:
    """One row of the record: the allocation test at the equity ETF's weights by region in the holdings file. The row
    gives no reading when the file has a country that method/french_regions.csv does not place, or when the test ran
    on files of French's library other than those whose hashes are committed, or on values of the European Central
    Bank's three series other than those whose digests are committed."""
    frame, _ = lookthrough.parse_ishares_holdings(path)
    held_on = pd.Timestamp(as_of).date().isoformat()
    unplaced = lookthrough.unplaced_countries(frame)
    if unplaced:
        row = _no_reading(month, today, "The holdings file has a country that method/french_regions.csv does not "
                                        f"place: {', '.join(unplaced)}")  # fmt: skip
        return row | {"holdings_as_of": held_on}
    module = module or allocation_check()
    table = lookthrough.allocation_regions(lookthrough.equity_lines(frame), as_of)
    run = module.run_at(table)
    row = {"month_end": str(month), "written_on": today.isoformat(), "reading": "yes", "reason": "",
           "holdings_as_of": held_on, **run}
    reasons = []
    if run["french_files_as_committed"] != "yes":
        reasons.append("The five regional files of French's library are not those whose hashes are committed in "
                       "mandate/allocation_check_files.csv")
    if run.get("ecb_values_as_committed") != "yes":
        reasons.append("The values the test reads from the European Central Bank's three series are not those whose "
                       "digests are committed in mandate/allocation_check_files.csv")
    if reasons:
        row.update(reading="no", reason=". ".join(reasons))
    return {c: row.get(c, "") for c in RECORD_COLUMNS}


def applied_on(day: date, kept: pd.DataFrame = None, cycles_dir: Path = config.CYCLES_DIR) -> bool:
    """Whether the rules have been applied on a cycle day: its cycle report or its row of the targets table exists."""
    if (Path(cycles_dir) / f"{day:%Y-%m}.md").exists():
        return True
    return kept is not None and len(kept) > 0 and day.isoformat() in set(kept["cycle_day"].astype(str))


def update_record(record: pd.DataFrame, today: date, holdings=holdings_at, row=record_row,
                  applied=lambda day: False) -> pd.DataFrame:
    """The record with a row added for each month end from 30 November 2026 whose last trading day is before today
    and that has none yet, in order. A row is written once and never rewritten. A month end whose cycle day has
    passed, or whose rules have been applied, gets a row with no reading; one whose holdings file is not served yet,
    with its cycle day still to come, waits for a later run, and so do the month ends after it. holdings(month,
    today) gives the file, and applied(day) whether the rules have been applied on a cycle day."""
    record = record.reindex(columns=RECORD_COLUMNS) if len(record) else pd.DataFrame(columns=RECORD_COLUMNS)
    done = set(record["month_end"].astype(str))
    month, rows = FIRST_MONTH_END, []
    while last_trading_day(month) < today:
        if str(month) not in done:
            cycle = cycle_day_after(month)
            if today > cycle:
                rows.append(_no_reading(month, today, f"No row was written on or before the cycle day of {_words(cycle)}"))
            elif today == cycle and applied(cycle):
                rows.append(_no_reading(month, today, "No row was written before the rules were applied on the "
                                                      f"cycle day of {_words(cycle)}"))  # fmt: skip
            else:
                found = holdings(month, today)
                if found is None and today < cycle:
                    break
                if found is None:
                    rows.append(_no_reading(month, today, f"No holdings file is dated from {_words(last_trading_day(month))} "
                                                          f"to the day before the cycle day of {_words(cycle)}"))  # fmt: skip
                else:
                    rows.append(row(month, *found, today))
        month += 1
    if rows:
        record = pd.concat([record, pd.DataFrame(rows, columns=RECORD_COLUMNS)], ignore_index=True)
    return record.reset_index(drop=True)


def missing_rows(day: date, record: pd.DataFrame) -> list:
    """The month ends from 30 November 2026 that a cycle day reads, the two before it, with no row in the record."""
    have = set(record["month_end"].astype(str)) if len(record) else set()
    month = pd.Period(day, "M")
    return [m for m in (month - 2, month - 1) if m >= FIRST_MONTH_END and str(m) not in have]


def readings(record: pd.DataFrame) -> dict:
    """Each month end's reading: its largest split within the limit, none, or no reading."""
    if not len(record):
        return {}
    out = {}
    for r in record.to_dict("records"):
        out[str(r["month_end"])] = str(r["largest_split"]) if str(r.get("reading", "yes")) == "yes" else NO_READING
    return out


# The target and the band ----------------------------------------------------------------------------------------


def band_for(weight: float, target: float, inside: tuple) -> tuple:
    """The band in force on a cycle day for an equity weight after the top-up, at an equity target weight, given
    the last band the weight was inside; and that last band after the day. Inside the target's own band, that band.
    Outside it, the edge on that side of the last band the weight was inside, and beyond that edge rule 5 brings
    the portfolio to the target weights, inside the target's own band."""
    new = band_of(target)
    if new[0] <= weight <= new[1]:
        return new, new
    band = (inside[0] if weight < new[0] else new[0], inside[1] if weight > new[1] else new[1])
    return band, (inside if band[0] <= weight <= band[1] else new)


def cycle_days(last: date) -> list:
    """The cycle days from 5 January 2027 up to last."""
    out, year, month = [], FROM.year, FROM.month
    while (year, month) <= (last.year, last.month):
        day = trading_days.cycle_day(year, month)
        if FROM <= day <= last:
            out.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return out


def targets(record: pd.DataFrame, last: date, weight_after_top_up, kept: pd.DataFrame = None) -> pd.DataFrame:
    """One row for each cycle day from 5 January 2027 up to last: the two month ends read, the reading of each, the
    target before and after, and the band in force. A row of kept, the table as first written, stands as it is, and
    the days after it continue from its target. weight_after_top_up(day, target) gives the equity weight after rule
    4 on the day at that equity target weight."""
    read = readings(record)
    kept_rows = {str(r["cycle_day"]): r for r in kept.to_dict("records")} if kept is not None and len(kept) else {}
    target = config.TARGET[E]
    inside = band_of(target)  # the last band the equity weight was inside
    rows = []
    for day in cycle_days(last):
        if day.isoformat() in kept_rows:
            row = {c: kept_rows[day.isoformat()][c] for c in TARGET_COLUMNS}
            target = split_weight(str(row["target_after"]))
            weight = weight_after_top_up(day, {E: target, B: round(1 - target, 4)})
            _, inside = band_for(weight, target, inside)
            rows.append(row)
            continue
        month = pd.Period(day, "M")
        first, second = month - 2, month - 1
        a, b = read.get(str(first), ""), read.get(str(second), "")
        before = target
        if a and a == b and a not in (NONE, NO_READING) and split_weight(a) != target:
            target = split_weight(a)
        weight = weight_after_top_up(day, {E: target, B: round(1 - target, 4)})
        band, inside = band_for(weight, target, inside)
        rows.append({"cycle_day": day.isoformat(), "first_month_end": str(first), "first_reading": a,
                     "second_month_end": str(second), "second_reading": b, "target_before": split_name(before),
                     "target_after": split_name(target), "band_low": band[0], "band_high": band[1]})
    return pd.DataFrame(rows, columns=TARGET_COLUMNS)


def weight_after_top_up_from(records, navs_eur: pd.DataFrame):
    """weight_after_top_up for targets(): the values before the orders of the day, from the ledger and the last net
    asset values, and the purchases of rule 4 at the target given."""
    from . import cycle_report

    def weight(day: date, target: dict) -> float:
        last_close = pd.Timestamp(trading_days.previous_trading_day(day))
        if not len(navs_eur.loc[:last_close]):
            return target[E]
        state = cycle_report.state_before(records, day)
        unit_value = navs_eur.loc[:last_close].iloc[-1]
        values = {s: state["units"][s] * float(unit_value[s]) for s in config.SLEEVES}
        buys = rules_engine.rule_4(values, state["cash"], target)
        total = values[E] + values[B] + state["cash"]
        return (values[E] + buys[E]) / total if total else target[E]

    return weight


def load_record(path: Path = RECORD) -> pd.DataFrame:
    if not Path(path).exists():
        return pd.DataFrame(columns=RECORD_COLUMNS)
    return pd.read_csv(path, dtype={"month_end": str, "written_on": str, "reading": str, "reason": str,
                                    "holdings_as_of": str, "largest_split": str}, keep_default_na=False)  # fmt: skip


def in_force(records, navs_eur: pd.DataFrame, day: date, record: pd.DataFrame = None,
             kept: pd.DataFrame = None) -> tuple:
    """The target weights and the band in force on a cycle day, with the day's row of the targets table, or None
    before 5 January 2027. The day's row as first written stands where the table has it."""
    if day < FROM:
        return dict(config.TARGET), tuple(config.BAND), None
    record = load_record() if record is None else record
    kept = load() if kept is None else kept
    table = targets(record, day, weight_after_top_up_from(records, navs_eur), kept)
    on = table[table["cycle_day"].astype(str) == day.isoformat()]
    if not len(on):
        target = target_on(day, table)
        return target, band_on(day, table), None
    row = on.iloc[-1].to_dict()
    weight = split_weight(str(row["target_after"]))
    return {E: weight, B: round(1 - weight, 4)}, (float(row["band_low"]), float(row["band_high"])), row


def load(path: Path = TARGETS) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False) if Path(path).exists() else pd.DataFrame(columns=TARGET_COLUMNS)


def _rows_to(day, table: pd.DataFrame) -> pd.DataFrame:
    day = pd.Timestamp(day).date()
    return table[pd.to_datetime(table["cycle_day"]).dt.date <= day] if len(table) else table


def target_on(day, table: pd.DataFrame = None) -> dict:
    """The target weights in force on a day: those of the last cycle day of the table on or before it, and the
    rules' 70/30 before 5 January 2027."""
    table = load() if table is None else table
    rows = _rows_to(day, table)
    weight = split_weight(str(rows["target_after"].iloc[-1])) if len(rows) else config.TARGET[E]
    return {E: weight, B: round(1 - weight, 4)}


def band_on(day, table: pd.DataFrame = None) -> tuple:
    """The band in force on a day: that of the last cycle day's row of the table on or before it, on every day, and
    the rules' band before 5 January 2027."""
    table = load() if table is None else table
    rows = _rows_to(day, table)
    if len(rows):
        return (float(rows["band_low"].iloc[-1]), float(rows["band_high"].iloc[-1]))
    return band_of(config.TARGET[E])


def line(row: dict, record: pd.DataFrame = None) -> str:
    """The figure of the cycle report's line for rule 11, with the reason of a month end that gives no reading."""
    record = load_record() if record is None else record
    reasons = {}
    if len(record):
        reasons = {str(r["month_end"]): str(r["reason"]) for r in record.to_dict("records") if str(r["reason"])}

    def month_end(period: str) -> str:
        end = pd.Period(period, "M").to_timestamp(how="end")
        return f"{end.day} {end:%B %Y}"

    def reading(period: str, value: str) -> str:
        if not value:
            return "no row in the record"
        if value == NO_READING and reasons.get(period):
            reason = reasons[period]
            return f"no reading, {reason[0].lower()}{reason[1:]}"
        return value

    read = (f"{month_end(row['first_month_end'])}: {reading(row['first_month_end'], row['first_reading'])}. "
            f"{month_end(row['second_month_end'])}: {reading(row['second_month_end'], row['second_reading'])}")  # fmt: skip
    low, high = round(float(row["band_low"]) * 100), round(float(row["band_high"]) * 100)
    if row["target_after"] == row["target_before"]:
        return f"{read}. No change: target {row['target_after']}, band {low} to {high}"
    return f"{read}. New target {row['target_after']} from this cycle day, band in force {low} to {high}"


def current_target(day=None) -> dict:
    """The target weights in force today, or on the day given, from outputs/allocation_targets.csv."""
    return target_on(day or date.today())


def current_band(day=None) -> tuple:
    """The band in force today, or on the day given: that of the last cycle day's row of
    outputs/allocation_targets.csv."""
    return band_on(day or date.today())
