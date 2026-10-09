"""The monthly notes' form, the departures register and the rolling correlation of the two ETFs."""

import numpy as np
import pandas as pd
import pytest

from portfolio import config, metrics, notes

E, B = config.EQUITY, config.BONDS
BODY = " ".join(["The equity weight drifted down with the market and the top-up bought equity."] * 12)


def write(folder, name, text):
    path = folder / name
    path.write_text(text, encoding="utf-8")
    return path


def note_text(body=BODY, title="# November 2026", cycle=notes.CYCLE_DAY + ": 2026-11-05."):
    return (
        f"{title}\n\n{cycle}\n\nFigures: Band not triggered. 1 order placed against 1 proposed.\n\n{body}\n"
    )


def test_a_note_in_the_form_reads(tmp_path):
    note = notes.parse(write(tmp_path, "2026-11.md", note_text()))
    assert note.month == "2026-11" and str(note.cycle_day) == "2026-11-05"
    assert note.figures.startswith("Band not triggered") and 120 <= notes.words(note.body) <= 200


@pytest.mark.parametrize(
    "name, text, fault",
    [
        ("2026-11.md", note_text(body="Too short."), "words"),
        ("2026-11.md", note_text(body=BODY + " " + BODY), "words"),
        ("2026-11.md", note_text(title="# Note for November"), "first line"),
        ("2026-11.md", note_text(cycle=notes.CYCLE_DAY + ": 2026-12-07."), "is not in"),
        ("2026-11.md", note_text(body=BODY + " The band will hold."), "looks forward"),
        (
            "2026-11.md",
            notes.draft(pd.Period("2026-11", "M"), "2026-11-05", "Band not triggered."),
            "placeholder",
        ),
        ("november.md", note_text(), "file name"),
    ],
)
def test_a_note_out_of_form_stops_the_build(tmp_path, name, text, fault):
    with pytest.raises(notes.NoteError, match=fault):
        notes.parse(write(tmp_path, name, text))


def test_notes_are_read_newest_first(tmp_path):
    write(tmp_path, "2026-11.md", note_text())
    write(tmp_path, "2026-12.md", note_text(title="# December 2026", cycle=notes.CYCLE_DAY + ": 2026-12-07."))
    assert [n.month for n in notes.read(tmp_path)] == ["2026-12", "2026-11"]
    assert notes.read(tmp_path / "missing") == []


def test_the_departures_register_names_the_rule_and_the_consequence():
    day = pd.Timestamp("2026-10-08")
    issues = pd.DataFrame(
        [{"date": day, "sleeve": E, "side": "buy", "issue": "outside the rule 7 window"},
         {"date": day, "sleeve": B, "side": "buy", "issue": "outside the rule 7 window"},
         {"date": pd.Timestamp("2026-12-07"), "sleeve": B, "side": "buy", "issue": "called for by the rules and not placed"}]
    )  # fmt: skip
    placed = pd.DataFrame(
        [{"date": day, "sleeve": E, "side": "buy", "rule": "start", "produced_by_rules": "yes"},
         {"date": day, "sleeve": B, "side": "buy", "rule": "start", "produced_by_rules": "yes"}]
    )  # fmt: skip
    register = metrics.departures(issues, placed)
    assert list(register.columns) == ["date", "rule", "what_happened", "consequence"]
    assert list(register["rule"]) == ["7", "7", "3"]
    assert register["what_happened"].iloc[0] == (
        "The first purchase of the equity ETF was placed outside 15:45 to 17:00 Amsterdam time."
    )
    assert register["consequence"].iloc[0].endswith("only its time departed.")
    assert (
        register["consequence"].iloc[2]
        == "The next cycle day applies the rules to the weights as they stand."
    )


def test_the_rolling_correlation_uses_complete_months_only():
    days = pd.bdate_range("2019-02-19", "2026-10-08")
    rng = np.random.default_rng(1)
    navs = pd.DataFrame({E: 100 * np.exp(np.cumsum(rng.normal(0, 0.01, len(days)))),
                         B: 50 * np.exp(np.cumsum(rng.normal(0, 0.003, len(days))))}, index=days)  # fmt: skip
    table = metrics.sleeve_correlation(navs)
    # Returns from March 2019 (the change from the end of February), the first window of 36 ends in
    # February 2022, and October 2026 is not complete on 8 October.
    assert table["window_end"].iloc[0] == "2022-02" and table["window_end"].iloc[-1] == "2026-09"
    month_end = navs.groupby(navs.index.to_period("M")).last().loc[:"2026-09"]
    r = month_end.pct_change().dropna().iloc[-36:]
    assert table["correlation"].iloc[-1] == pytest.approx(r[E].corr(r[B]))
