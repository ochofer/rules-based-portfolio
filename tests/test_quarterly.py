"""The quarterly report: the figures of each quarter, the commentary's checks, the static charts, the issue page
and the comparison of a PDF's words with its page's. The issue is built from the committed tables, with the
last quarter taken as complete."""

import html as html_module
import re
import shutil
import subprocess

import pandas as pd
import pytest

from portfolio import config, metrics, quarterly, site

Q4 = pd.Period("2026Q4", "Q")
WORDS_160 = " ".join(
    ["The portfolio ran under its rules through the quarter, and the record shows each order beside the rule that "
     "produced it. The top-up bought the sleeve furthest below its target weight on each cycle day, and the band "
     "was not reached, so no rebalancing was due. Prices moved within the range the mandate allows for, and the "
     "worst fall stayed far from the test limit. Costs came from the spread and the commissions, as the table of "
     "costs shows by month and source. The look-through moved with the markets, and the shares of the regions and "
     "of the maturity groups drifted a little from those at the start. The reference portfolios moved with the "
     "portfolio, and the difference between them is the cost of placing the orders. A quarter is far too short to "
     "say anything about the rules, and the record is read as a record of how the rules were run. The notes of "
     "each month give the detail, and the cycle reports give each rule as it applied on the day, before the orders "
     "were placed."]
)


# The figures of a quarter ---------------------------------------------------------------------------


def ledger_of(flows):
    records = type("L", (), {})()
    records.contributions = pd.DataFrame(
        {"moment": [pd.Timestamp(m) for m, _ in flows], "amount_eur": [a for _, a in flows]}
    )
    return records


def test_the_money_weighted_return_of_a_period_without_contributions_is_its_simple_return():
    records = ledger_of([("2026-01-02 10:00", 1000.0)])
    rate = metrics.money_weighted_between(records, pd.Timestamp("2026-03-31"), 1050.0, pd.Timestamp("2026-06-30"), 1071.0)
    assert rate == pytest.approx(0.02, abs=1e-9)


def test_a_contribution_inside_the_period_is_not_a_gain():
    # 1,000 at the start, 100 added in the middle, 1,100 at the end: nothing was earned.
    records = ledger_of([("2026-01-02 10:00", 1000.0), ("2026-05-05 10:00", 100.0)])
    rate = metrics.money_weighted_between(records, pd.Timestamp("2026-03-31"), 1000.0, pd.Timestamp("2026-06-30"), 1100.0)
    assert rate == pytest.approx(0.0, abs=1e-9)


def test_with_no_start_day_the_period_opens_with_the_first_contribution():
    records = ledger_of([("2026-10-08 09:32", 1000.0)])
    rate = metrics.money_weighted_between(records, None, None, pd.Timestamp("2026-12-31"), 1030.0)
    assert rate == pytest.approx(metrics.money_weighted_cumulative(records, pd.Timestamp("2026-12-31"), 1030.0))


def table_over(days, growth, cost):
    index = pd.to_datetime(days)
    return pd.DataFrame({
        "growth_portfolio": growth, "growth_reference_a": [g * 1.001 for g in growth],
        "growth_reference_b": [g * 1.002 for g in growth], "growth_index_blend": [float("nan")] * len(days),
        "drawdown_portfolio": metrics.drawdown(pd.Series(growth, index=index)).values, "implementation_cost_bps": cost,
    }, index=index)  # fmt: skip


def test_the_quarters_chain_to_the_record_since_the_first_purchase():
    days = ["2026-10-08", "2026-11-30", "2026-12-31", "2027-02-26", "2027-03-31", "2027-04-01"]
    growth = [100.0, 103.0, 101.0, 99.0, 104.0, 104.5]
    cost = [0.0, 4.0, 6.0, 7.0, 9.0, 9.0]
    table = table_over(days, growth, cost)
    values = pd.DataFrame({"value_eur": [1000.0, 1030.0, 1010.0, 990.0, 1040.0, 1045.0]}, index=table.index)
    placed = pd.DataFrame({"date": pd.to_datetime(["2026-10-08", "2026-10-08", "2026-11-05", "2027-03-05"])})
    records = ledger_of([("2026-10-08 09:32", 1000.0)])
    frame = metrics.quarters(records, table, values, placed, pd.Timestamp("2027-04-02").date())
    assert list(frame["quarter"]) == ["2026Q4", "2027Q1", "2027Q2"]
    assert list(frame["complete"]) == ["yes", "yes", "to date"]
    # The first quarter runs from the base, the first purchase, so its return is the record's to its end.
    assert frame.loc[0, "return_time_weighted"] == pytest.approx(101 / 100 - 1)
    assert frame.loc[1, "return_time_weighted"] == pytest.approx(104 / 101 - 1)
    chained = (1 + frame["return_time_weighted"]).prod() - 1
    assert chained == pytest.approx(frame["return_time_weighted_since_start"].iloc[-1])
    # The quarters' implementation costs add up to the cost since the first purchase.
    assert frame["implementation_cost_bps"].sum() == pytest.approx(frame["implementation_cost_since_start_bps"].iloc[-1])
    assert list(frame["orders"]) == [3, 1, 0] and list(frame["orders_since_start"]) == [3, 4, 4]
    assert list(frame["allowance"]) == [15, 15, 15] and list(frame["allowance_since_start"]) == [15, 30, 45]
    # The worst fall of the first quarter is the fall from 103 to 101, and to date the one from 103 to 99.
    assert frame.loc[0, "worst_fall"] == pytest.approx(1 - 101 / 103)
    assert frame.loc[1, "worst_fall_to_date"] == pytest.approx(1 - 99 / 103)


# The commentary --------------------------------------------------------------------------------------


def commentary(tmp_path, text):
    path = tmp_path / "2026-Q4-commentary.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_commentary_in_the_form_reads(tmp_path):
    read = quarterly.parse_commentary(commentary(tmp_path, f"Dated: 2027-01-05\n\n{WORDS_160}\n"), Q4)
    assert str(read.dated) == "2027-01-05" and len(read.paragraphs) == 1


@pytest.mark.parametrize("text, fault", [
    (WORDS_160, "Dated: YYYY-MM-DD"),
    (f"Dated: 2026-12-31\n\n{WORDS_160}", "inside the quarter"),
    ("Dated: 2027-01-05\n\nThe quarter was quiet.", "a commentary has 150 to 300 words"),
    (f"Dated: 2027-01-05\n\n{WORDS_160} The next quarter will be the same.", "looks forward"),
    (f"Dated: 2027-01-05\n\nWrite the note here. {WORDS_160}", "placeholder"),
])  # fmt: skip
def test_a_commentary_out_of_form_stops_the_issue(tmp_path, text, fault):
    with pytest.raises(quarterly.ReportError, match=fault):
        quarterly.parse_commentary(commentary(tmp_path, text), Q4)


def test_a_missing_commentary_stops_the_issue(tmp_path):
    with pytest.raises(quarterly.ReportError, match="not built without the commentary"):
        quarterly.parse_commentary(tmp_path / "2026-Q4-commentary.txt", Q4)


def test_the_commentary_shows_no_figure_the_issue_does_not():
    issue = type("Issue", (), {})()
    issue.quarter = Q4
    issue.commentary = quarterly.Commentary(pd.Timestamp("2027-01-05").date(), ("The equity weight ended at 70.4%.",))
    quarterly._figures_check(issue, "Equity weight 70.4% at the end")
    issue.commentary = quarterly.Commentary(pd.Timestamp("2027-01-05").date(), ("The equity weight ended at 71.2%.",))
    with pytest.raises(quarterly.ReportError, match="71.2%"):
        quarterly._figures_check(issue, "Equity weight 70.4% at the end")


def test_quarters_are_named_in_files_and_in_words():
    assert quarterly.parse_quarter("2026-Q4") == Q4 and quarterly.label(Q4) == "2026-Q4"
    assert quarterly.quarter_name(Q4) == "fourth quarter 2026"
    assert quarterly._period_words(pd.Timestamp("2026-10-08"), pd.Timestamp("2026-12-31")) == "8 October to 31 December 2026"
    with pytest.raises(quarterly.ReportError):
        quarterly.parse_quarter("2026Q4")


# Charts ----------------------------------------------------------------------------------------------


def chart(width):
    days = list(pd.to_datetime(["2026-10-08", "2026-10-30", "2026-11-30", "2026-12-31"]))
    series = [("Portfolio", days, [100, 101.2, 99.8, 102.1], quarterly.NAVY, 2.0, False),
              ("Index blend", days[1:], [100.4, 99.1, 101.0], quarterly.BLEND, 1.2, True)]  # fmt: skip
    return quarterly.line_chart(series, [(d, d.strftime("%d %b")) for d in days], width, "Growth of 100", lines=[(100, quarterly.FRAME, "")])


def test_a_chart_is_the_same_on_every_build_and_draws_the_portfolio_last():
    assert chart(quarterly.WIDE) == chart(quarterly.WIDE)
    svg = chart(quarterly.WIDE)
    lines = re.findall(r'<polyline[^>]*stroke="(#[0-9a-f]{6})"', svg)
    assert lines == [quarterly.BLEND, quarterly.NAVY]  # the portfolio is drawn on top
    assert "<script" not in svg and " id=" not in svg


def test_the_phone_drawing_keeps_its_tick_labels_at_11_px():
    sizes = {float(s) for s in re.findall(r'font-size="([\d.]+)"', chart(quarterly.NARROW))}
    assert min(sizes) >= 11


# The words of the page and of the PDF ---------------------------------------------------------------


PAGE = """<html><head><title>T</title><style>p{} .rp-narrow{display:none} @media print { .ch-menu, .ch-back { display: none; }
.rp-narrow { display: none; } .rp-tw::after { display: none; } }</style></head><body>
<div class="ch-menu" role="navigation"><a>Projects</a></div><p class="ch-back">Back</p><main><h1>8 October to 31 December 2026</h1>
<section class="rp-ex" id="figure-1"><h3>Figure 1 | Growth of 100</h3>
<div class="rp-wide"><svg><line x1="0"/><text>Portfolio</text><text>31 Dec</text></svg></div>
<div class="rp-narrow"><svg><text>Phone</text></svg></div><p class="cap">Real money.</p></section>
<section class="rp-ex" id="table-1"><h3>Table 1 | Key figures</h3><table><tr><td>Worst fall</td><td>2.6%</td></tr></table></section>
</main><script>var x = 1;</script></body></html>"""


def test_the_page_words_are_those_that_print():
    assert quarterly._print_hidden(PAGE) == {"ch-menu", "ch-back", "rp-narrow"}
    words, chart_words = quarterly.page_words(PAGE)
    assert "projects" not in words and "back" not in words and "phone" not in words and "var" not in words
    assert words[:6] == ["8", "october", "to", "31", "december", "2026"]
    assert chart_words == ["portfolio", "31", "dec"]  # kept although a self-closing line comes before them
    assert words[-6:] == ["worst", "fall", "2", ".", "6", "%"]


def test_a_print_with_the_page_words_passes_and_one_without_them_does_not(monkeypatch):
    words, _ = quarterly.page_words(PAGE)
    printed = words[:12] + ["dec", "31", "oiloftrop"] + words[12:]  # the chart's labels in their own order
    monkeypatch.setattr(quarterly, "pdf_words", lambda path: printed)
    assert quarterly.compare_words(PAGE, "x.pdf") == []
    monkeypatch.setattr(quarterly, "pdf_words", lambda path: [w for w in printed if w != "worst"])
    assert any("lacks words" in f for f in quarterly.compare_words(PAGE, "x.pdf"))
    monkeypatch.setattr(quarterly, "pdf_words", lambda path: printed + ["extra"])
    assert any("not the charts' labels" in f for f in quarterly.compare_words(PAGE, "x.pdf"))
    table_first = words[words.index("table"):] + words[:words.index("table")] + ["dec", "31", "portfolio"]
    monkeypatch.setattr(quarterly, "pdf_words", lambda path: table_first)
    assert any("another order" in f for f in quarterly.compare_words(PAGE, "x.pdf"))


def test_the_metadata_holds_the_title_the_author_and_the_printing_tool_only(tmp_path):
    pikepdf = pytest.importorskip("pikepdf")
    pytest.importorskip("pdfplumber")

    def pdf(name, xmp=False, **info):
        path = tmp_path / name
        with pikepdf.new() as doc:
            doc.add_blank_page()
            for key, value in info.items():
                doc.docinfo[f"/{key}"] = value
            if xmp:
                with doc.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
                    meta["dc:title"] = "Quarterly report"
            doc.save(path)
        return path

    printed = dict(Title="Quarterly report", Author=quarterly.AUTHOR, Creator="Chromium", Producer="Skia/PDF m141")
    assert quarterly.pdf_metadata_faults(pdf("good.pdf", **printed), "Quarterly report") == []
    faults = quarterly.pdf_metadata_faults(pdf("bad.pdf", Title="Quarterly report", Author="Someone else",
                                               Producer="Another tool", Keywords="x"), "Quarterly report")  # fmt: skip
    assert len(faults) == 3 and "author" in faults[0] and "producer" in faults[1] and "Keywords" in faults[2]
    faults = quarterly.pdf_metadata_faults(pdf("xmp.pdf", xmp=True, **printed), "Quarterly report")
    assert faults and "Metadata" in faults[0]


# The issue -------------------------------------------------------------------------------------------


@pytest.fixture
def tree(tmp_path):
    """A copy of the committed tables, notes and styles, with the last quarter taken as complete and a
    commentary dated after it."""
    root = tmp_path / "repo"
    for folder in ("outputs", "notes", "site"):
        if (config.ROOT / folder).exists():
            shutil.copytree(config.ROOT / folder, root / folder)
    (root / "mandate").mkdir()
    shutil.copy(config.ROOT / "mandate" / "simulation_bootstrap.csv", root / "mandate")
    shutil.copy(config.ROOT / "README.md", root)
    frame = pd.read_csv(root / "outputs" / "quarters.csv")
    last = frame.index[-1]
    frame.loc[last, "complete"] = "yes"
    frame.to_csv(root / "outputs" / "quarters.csv", index=False)
    quarter = pd.Period(frame.loc[last, "quarter"], "Q")
    dated = (quarter.end_time + pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    # The record runs past the quarter's end, as it does when an issue is built.
    daily = pd.read_csv(root / "outputs" / "portfolio_daily.csv")
    after = daily.iloc[[-1]].copy()
    after["date"] = (quarter.end_time + pd.Timedelta(days=4)).strftime("%Y-%m-%d")
    pd.concat([daily, after]).to_csv(root / "outputs" / "portfolio_daily.csv", index=False)
    (root / "quarterly").mkdir()
    (root / "quarterly" / f"{quarterly.label(quarter)}-commentary.txt").write_text(f"Dated: {dated}\n\n{WORDS_160}\n")
    return root, quarter


def visible(page):
    body = re.sub(r"<(style|script)>.*?</\1>", " ", page, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))


def test_an_issue_is_the_same_on_every_build_and_in_the_order_of_the_standard(tree):
    root, quarter = tree
    page = quarterly.build(root, quarter, "abc1234")
    assert page == quarterly.build(root, quarter, "abc1234")
    text = visible(page)
    order = ["Rules-based portfolio · Quarterly report", "Figures as of", "Period", "Status", "Table 1 | Key figures",
             "Commentary", f"{quarterly.AUTHOR},", "Monthly notes, as issued", quarterly.CLOSING, "Terms", "Code on GitHub"]  # fmt: skip
    places = [html_module.unescape(text).find(o) for o in order]
    assert all(p >= 0 for p in places) and places == sorted(places), list(zip(order, places))
    for kind in ("figure", "table"):
        numbers = [int(n) for n in re.findall(rf'<section class="rp-ex" id="{kind}-(\d+)"', page)]
        assert numbers == list(range(1, len(numbers) + 1))
    ids = re.findall(r' id="([^"]+)"', page)
    assert len(ids) == len(set(ids))
    assert "\u2014" not in page and ";" not in html_module.unescape(text)
    assert '<meta name="commit" content="abc1234">' in page and "commit abc1234" in text


def test_no_issue_before_the_record_runs_past_the_quarter_end(tree):
    root, quarter = tree
    daily = pd.read_csv(root / "outputs" / "portfolio_daily.csv")
    daily.iloc[:-1].to_csv(root / "outputs" / "portfolio_daily.csv", index=False)
    with pytest.raises(quarterly.ReportError, match="does not run past the quarter's end"):
        quarterly.build(root, quarter, "abc1234")


def test_an_issue_is_written_once(tree):
    root, quarter = tree
    quarterly.write(root, quarter, "abc1234")
    with pytest.raises(quarterly.ReportError):
        quarterly.write(root, quarter, "abc1234")


def test_an_issue_is_built_from_its_commit_and_rebuilds_from_it(tree):
    # The page comes from the commit's own tree: a table changed in the working tree after the commit does
    # not reach it, and the check rebuilds it byte for byte.
    root, quarter = tree
    shutil.copytree(config.ROOT / "src", root / "src", ignore=shutil.ignore_patterns("__pycache__"))
    git = ["git", "-c", "user.name=Test", "-c", "user.email=test@example.org", "-c", "commit.gpgsign=false"]
    subprocess.run(git + ["init", "-q"], cwd=root, check=True)
    subprocess.run(git + ["add", "-A"], cwd=root, check=True)
    subprocess.run(git + ["commit", "-q", "-m", "Tables"], cwd=root, check=True)
    commit = subprocess.run(["git", "rev-parse", "--short=7", "HEAD"], cwd=root, check=True, capture_output=True,
                            text=True).stdout.strip()  # fmt: skip
    expected = quarterly.build(root, quarter, commit)
    (root / "outputs" / "orders.csv").write_text("changed after the commit\n")
    page = quarterly.build_at(root, quarter, commit)
    assert page == expected
    quarterly.write(root, quarter, commit, page)
    assert quarterly.check(root) == []
    (root / "quarterly" / f"{quarterly.label(quarter)}.html").write_text(page.replace("Commentary", "Comment"))
    assert any("differs from its rebuild" in f for f in quarterly.check(root))


def test_an_incomplete_quarter_has_no_issue(tree):
    root, quarter = tree
    frame = pd.read_csv(root / "outputs" / "quarters.csv")
    frame.loc[frame.index[-1], "complete"] = "to date"
    frame.to_csv(root / "outputs" / "quarters.csv", index=False)
    with pytest.raises(quarterly.ReportError, match="not complete"):
        quarterly.build(root, quarter, "abc1234")


def test_the_log_lists_each_issue_with_its_pdf(tmp_path):
    folder = tmp_path / "quarterly"
    folder.mkdir()
    (folder / "2026-Q4.html").write_text('<meta name="commit" content="abc1234"><h1>8 October to 31 December 2026</h1>'
                                         '<p class="rp-stamp">Issue 1 &middot; Figures as of 2026-12-31 &middot; Built</p>')  # fmt: skip
    (folder / "2026-Q4_2027-01-05.pdf").write_bytes(b"%PDF-1.7")
    (folder / "2026-Q4-commentary.txt").write_text("Dated: 2027-01-05")
    issues = site._quarterly_issues(tmp_path)
    assert issues == [(1, "8 October to 31 December 2026", "2026-12-31", "abc1234", "quarterly/2026-Q4.html",
                       [("2027-01-05", "quarterly/2026-Q4_2027-01-05.pdf")])]  # fmt: skip


# The committed tables -----------------------------------------------------------------------------


def test_the_committed_quarters_chain_to_the_record():
    frame = pd.read_csv(config.OUTPUTS_DIR / "quarters.csv")
    daily = pd.read_csv(config.OUTPUTS_DIR / "portfolio_daily.csv")
    assert (1 + frame["return_time_weighted"]).prod() == pytest.approx(daily["growth_portfolio"].iloc[-1] / 100, rel=1e-6)
    assert frame["implementation_cost_bps"].sum() == pytest.approx(frame["implementation_cost_since_start_bps"].iloc[-1], abs=1e-6)
    assert set(frame["complete"].iloc[:-1]) <= {"yes"}
