"""The build: every step of the pipeline, ending in the public files in outputs/.

outputs/ holds weights, percentages, basis points, loadings and indices only: no euro amount, no unit
count and no account detail. privacy() fails the build if a column is named for euro or units, or if
any figure equals the starting amount, the top-up, a unit count or a euro amount of the ledger.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from . import comparisons, config, factors, ledger as ledger_module, lookthrough, metrics, positions, prices, risk
from . import references, valuations

E, B = config.EQUITY, config.BONDS
COST_COLUMNS = ("month", "commissions_bps", "half_spread_bps", "orders_without_bid_and_ask", "currency_conversion_bps",
                "execution_against_nav_bps", "implementation_cost_month_bps")  # fmt: skip


class PrivacyError(RuntimeError):
    """A public output would carry a private figure."""


def _write(frame: pd.DataFrame, name: str, as_of, out_dir: Path) -> Path:
    frame = frame.copy()
    frame.insert(0, "as_of", pd.Timestamp(as_of).strftime("%Y-%m-%d"))
    for column in frame.columns:
        if pd.api.types.is_datetime64_any_dtype(frame[column]):
            frame[column] = frame[column].dt.strftime("%Y-%m-%d")
        elif pd.api.types.is_float_dtype(frame[column]):
            # Ten decimal places: floating-point noise from one machine to another does not reach the file.
            # Adding zero turns a negative zero into zero.
            frame[column] = frame[column].round(10) + 0.0
    path = out_dir / name
    frame.to_csv(path, index=False, float_format="%.10g", lineterminator="\n")
    return path


def _lookthrough_frame(table: pd.DataFrame, label: str) -> pd.DataFrame:
    frame = table.reset_index()
    frame = frame.rename(columns={frame.columns[0]: label})
    return frame


def build(refresh: bool = False, today: date = None, out_dir: Path = config.OUTPUTS_DIR) -> dict:
    today = today or date.today()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = ledger_module.read()
    series = prices.load(refresh=refresh)
    navs = prices.navs_in_euro(series)
    # The S&P 500 alternative's fund, valued on the same days in euro. The record runs to the last day on which
    # all three funds have published a net asset value, so the whole page keeps one date.
    alt_name, alt_isin = references.alternative_fund()
    alt_usd = prices.load_alternative(alt_isin, refresh)
    navs = navs.loc[: min(navs.index.max(), alt_usd.index.max())]
    alt_eur = alt_usd.reindex(alt_usd.index.union(navs.index)).ffill().reindex(navs.index) / navs["usd_per_eur"]
    held = positions.build(records, today)
    values = valuations.build(held, navs)
    base = metrics.base_day(records, navs)
    ref_a = references.simulate(records, navs, today, "rules")
    ref_b = references.simulate(records, navs, today, "calendar")
    alternative = references.sp500_alternative(records, alt_eur, today)

    first = records.contributions.iloc[0]["moment"].date()
    msci_start = (pd.Timestamp(first.year, first.month, 1) - pd.Timedelta(days=40)).date()
    msci_path = references.fetch_msci(refresh, config.CACHE_DIR, msci_start, today)
    msci = references.parse_msci(msci_path)
    holdings = lookthrough.fetch(refresh)
    factsheets = lookthrough.factsheet_history(holdings["factsheet"])
    bond_month = pd.Series(factsheets["benchmark_1m"].values, index=factsheets.index.to_period("M"))

    growth = metrics.growth_index(values["value_eur"], metrics.flows_on_days(records, values.index),
                                  metrics.start_amount(records), base)  # fmt: skip
    blend = references.index_blend(growth.iloc[1:], msci, bond_month, today)
    table = metrics.daily(records, values, ref_a, ref_b, blend, base, alternative)
    rate = prices.load_estr(refresh)
    placed = metrics.orders(records, navs)
    band, issues = metrics.compliance(records, navs, today)
    monthly = metrics.monthly(records, table, values, placed, today)

    # The state now, on one date for the whole record: the units held at the end of the last valuation day, at
    # its net asset values. An order or a contribution after that day enters with the next net asset values, and
    # the page names it as not yet valued.
    record_day = table.index.max() if len(table) > 1 else None
    positions_day = record_day if record_day is not None else pd.Timestamp(today)
    now = valuations.at(held, navs, positions_day)
    total = now[E] + now[B] + now["cash"]
    weights_now = {E: now[E] / total, B: now[B] / total, "cash": now["cash"] / total}

    equity_frame, equity_as_of = lookthrough.parse_ishares_holdings(holdings["ishares"])
    bond_frame, bonds_as_of = lookthrough.parse_vanguard_holdings(holdings["vanguard"])
    equity = lookthrough.equity_lines(equity_frame)
    bonds = lookthrough.bond_lines(bond_frame, bonds_as_of)
    latest_sheet = factsheets.iloc[-1]
    look = lookthrough.tables(equity, bonds, latest_sheet, weights_now)

    french = factors.fetch(refresh)
    daily_factors, vintage = factors.daily_factors(french)
    end_month = factors.last_full_month(daily_factors, series["equity_usd"])
    loadings = factors.loadings(series["equity_usd"], daily_factors, end_month)
    rolling = factors.rolling(series["equity_usd"], daily_factors, end_month)

    as_of = table.index.max() if len(table) > 1 else now["nav_date"]
    written = []
    daily_out = table.reset_index()
    written.append(_write(daily_out, "portfolio_daily.csv", as_of, out_dir))
    public_orders = placed.drop(columns=["_fee", "_half_spread"]) if len(placed) else placed
    written.append(_write(public_orders, "orders.csv", as_of, out_dir))
    written.append(_write(band, "band_events.csv", as_of, out_dir))
    written.append(_write(issues, "compliance.csv", as_of, out_dir))
    written.append(_write(metrics.departures(issues, placed), "departures.csv", as_of, out_dir))
    written.append(_write(metrics.sleeve_correlation(navs), "etf_correlation.csv", as_of, out_dir))
    if len(monthly):
        written.append(_write(monthly, "metrics_monthly.csv", as_of, out_dir))
        costs = monthly[list(COST_COLUMNS)]
    else:
        costs = pd.DataFrame(columns=list(COST_COLUMNS))
        written.append(_write(pd.DataFrame(columns=["month"]), "metrics_monthly.csv", as_of, out_dir))
    written.append(_write(costs, "costs_monthly.csv", as_of, out_dir))
    written.append(_write(metrics.quarters(records, table, values, placed, today), "quarters.csv", as_of, out_dir))
    impl = table[["implementation_cost_bps"]].dropna().reset_index()
    written.append(_write(impl, "implementation_cost.csv", as_of, out_dir))
    later = records.contributions[records.contributions["moment"].dt.normalize() > positions_day]
    now_frame = pd.DataFrame(
        [{"weights_as_of": now["nav_date"], "positions_as_of": positions_day, "built": pd.Timestamp(today),
          "weight_equity": weights_now[E], "weight_bonds": weights_now[B], "weight_cash": weights_now["cash"],
          "contributions_after": "|".join(sorted({m.strftime("%Y-%m-%d") for m in later["moment"]}))}]
    )  # fmt: skip
    written.append(_write(now_frame, "allocation_now.csv", now["nav_date"], out_dir))

    names = {
        "equity_region": ("lookthrough_equity_region.csv", "region", equity_as_of),
        "equity_country": ("lookthrough_equity_country.csv", "country", equity_as_of),
        "equity_sector": ("lookthrough_equity_sector.csv", "sector", equity_as_of),
        "top10": ("lookthrough_top10.csv", "company", equity_as_of),
        "currency": ("lookthrough_currency.csv", "currency", equity_as_of),
        "bonds_country": ("lookthrough_bonds_country.csv", "country", bonds_as_of),
        "bonds_maturity": ("lookthrough_bonds_maturity.csv", "maturity", bonds_as_of),
        "bonds_rating": ("lookthrough_bonds_rating.csv", "rating", latest_sheet.name),
        "bonds_duration": ("lookthrough_bonds_duration.csv", None, latest_sheet.name),
    }
    for key, (name, label, source_as_of) in names.items():
        frame = look[key] if label is None else _lookthrough_frame(look[key], label)
        frame = frame.copy()
        frame["holdings_as_of"] = pd.Timestamp(source_as_of)
        frame["weights_as_of"] = pd.Timestamp(now["nav_date"])
        written.append(_write(frame, name, now["nav_date"], out_dir))
    written.append(_write(loadings, "factor_loadings.csv", loadings["window_end"].max(), out_dir))
    written.append(_write(rolling, "factor_rolling.csv", rolling["window_end"].max(), out_dir))

    risk_written, risk_sources = _risk(refresh, today, out_dir, as_of, look, equity, weights_now, monthly, records,
                                       now["nav_date"])  # fmt: skip
    written += risk_written

    extra, comparison_sources = _comparison_inputs(refresh, today, navs, table, alt_usd, alt_eur, look, equity_as_of,
                                                   factsheets.iloc[-1], out_dir)  # fmt: skip
    compared = comparisons.build(records, navs, values, table, ref_a, ref_b, blend, rate, today, extra)
    for frame, name in ((compared["summary"], "comparisons.csv"), (compared["daily"], "comparisons_daily.csv"),
                        (compared["effects"], "comparison_effects.csv"), (compared["regions"], "comparison_regions.csv"),
                        (extra["fees"], "comparison_fees.csv"),
                        (_market_table(compared["market"], extra["market_funds"]), "comparison_market.csv")):  # fmt: skip
        written.append(_write(frame, name, as_of, out_dir))
    written.append(_write(metrics.attribution(daily_out), "attribution.csv", as_of, out_dir))

    checks = _checks(records, navs, look, weights_now, loadings)
    written.append(_write(checks, "checks.csv", as_of, out_dir))
    alt_source = (f"{alt_name}, {alt_isin}, net asset values in US dollars", f"hsbc/{alt_isin}_nav.json", alt_usd.index.max())
    rate_source = ("ECB, euro short-term rate, volume-weighted", "ecb/estr.csv", rate.index.max())
    sources = _sources(series, msci, equity_as_of, bonds_as_of, latest_sheet.name, daily_factors, vintage,
                       [alt_source, rate_source, *risk_sources, *comparison_sources])  # fmt: skip
    written.append(_write(sources, "sources.csv", as_of, out_dir))
    privacy(records, out_dir)
    return {"as_of": as_of, "files": written}


def _checks(records, navs, look, weights_now, loadings) -> pd.DataFrame:
    rows = []
    carried = int(navs["rate_carried"].sum())
    rows.append(
        ("ECB rate carried forward", "information", f"{carried} days since 2011, each the last rate before")
    )
    for key, sleeve in (("equity_country", E), ("equity_sector", E), ("equity_region", E), ("bonds_country", B),
                        ("bonds_maturity", B)):  # fmt: skip
        share = float(look[key]["share_of_portfolio"].sum())
        ok = abs(share - weights_now[sleeve]) <= 0.0005
        rows.append((f"look-through {key} sums to the sleeve weight", "pass" if ok else "fail",
                     f"difference {abs(share - weights_now[sleeve]) * 100:.3f} points"))  # fmt: skip
    missing = [g for g in records.gaps if "bid and ask" in g]
    rows.append(("orders without a recorded bid and ask", "information", str(len(missing))))
    rows.append(("orders outside the rule 7 window", "information", str(len(records.breaches))))
    weekly = loadings[loadings["method"] == "weekly"].iloc[0]
    rows.append(("factor regression observations", "information",
                 f"{int(weekly['observations'])} weeks, Newey-West lag {int(weekly['newey_west_lag'])}"))  # fmt: skip
    rows.append(("statement valuation gap", "not yet available", "from the first month-end statement"))
    return pd.DataFrame(rows, columns=["check", "result", "detail"])


def _risk(refresh, today, out_dir, as_of, look, equity, weights_now, monthly, records, nav_date) -> tuple:
    """The look-through's risk (risk.py): components, correlations, risk contributions, the frontier, the
    estimate and its record, the episodes, and the cost of ownership."""
    levels = risk.fetch_regions(refresh, today)
    spot = risk.fetch_curve(refresh)
    components = risk.component_returns(levels, spot)
    end = risk.last_complete_month(components, today)
    current = risk.window(components, end)
    earlier = risk.window(components, end - risk.WINDOW_MONTHS)
    mean, cov = risk.moments(current)
    mean_earlier, cov_earlier = risk.moments(earlier)
    regions = _lookthrough_frame(look["equity_region"], "region")
    maturities = _lookthrough_frame(look["bonds_maturity"], "maturity")
    weights = risk.component_weights(regions, maturities, weights_now["cash"])
    contributions = risk.risk_contributions(weights, cov)
    estimate = risk.volatility(weights, cov)
    full_mean = mean.reindex(weights.index).fillna(0.0)
    minimum = risk.minimum_variance(cov)
    israel = float(equity.loc[equity["country"] == "Israel", "weight"].sum()) * weights_now[E]
    series = {name: f"{index}, net total return in euro" for name, _, index in risk.REGIONS}
    series.update({name: f"ECB curve, {maturity:g}-year zero-coupon bond" for name, _, _, maturity, _ in risk.MATURITY_GROUPS})
    rows = [{"component": c, "sleeve": risk.SLEEVE_OF.get(c, "cash"), "weight": weights[c],
             "risk_contribution": contributions[c],
             "estimated_volatility": float(np.sqrt(cov.loc[c, c])) if c in cov.index else 0.0,
             "estimated_return": float(mean[c]) if c in mean.index else 0.0, "series": series.get(c, "no return")}
            for c in weights.index]  # fmt: skip
    window_text = {"window_start": str(current.index[0]), "window_end": str(end)}
    components_table = pd.DataFrame(rows).assign(**window_text)
    correlation = current.corr()
    pairs = pd.DataFrame([{"component_a": a, "component_b": b, "correlation": correlation.loc[a, b]}
                          for a in correlation.index for b in correlation.columns])  # fmt: skip
    frontiers = pd.concat([risk.frontier(mean, cov).assign(window="current"),
                           risk.frontier(mean_earlier, cov_earlier).assign(window="earlier")], ignore_index=True)  # fmt: skip
    history_path = out_dir / "ex_ante_risk.csv"
    history = pd.read_csv(history_path).drop(columns=["as_of"], errors="ignore") if history_path.exists() else pd.DataFrame()
    first_purchase = records.orders["moment"].min()
    tails = risk.tail(current, weights, estimate)
    history = risk.record_estimate(history, end, estimate, current.index[0], first_purchase,
                                   tails["value_at_risk_historical"])
    calibration, calibration_months = risk.calibration(history, monthly)
    beyond, beyond_months = risk.exceedances(history, monthly)
    complete = monthly[monthly["complete"] == "yes"] if len(monthly) else monthly
    realised = float(complete["volatility_12m"].iloc[-1]) if len(complete) else float("nan")
    summary = pd.DataFrame([{**window_text, "earlier_window_start": str(earlier.index[0]),
                             "earlier_window_end": str(earlier.index[-1]), "weights_as_of": nav_date,
                             "estimated_volatility": estimate, "estimated_return": float(full_mean @ weights),
                             "minimum_variance_volatility": float(np.sqrt(minimum @ cov @ minimum)),
                             "minimum_variance_return": float(mean @ minimum), "israel_share_of_portfolio": israel,
                             "cash_weight": weights[risk.CASH], "calibration": calibration,
                             "calibration_months": calibration_months, "realised_volatility_12m": realised,
                             **tails, "months_beyond_value_at_risk": beyond, "months_with_value_at_risk": beyond_months}])  # fmt: skip
    test = risk.allocation_test_returns()
    episodes = risk.stress(components, test, weights)
    kids = risk.fetch_kids(refresh)
    cost_rows = []
    for sleeve in config.SLEEVES:
        k = kids[sleeve]
        cost_rows.append({"sleeve": sleeve, "fund": config.NAME[sleeve], "isin": config.ISIN[sleeve], "weight": weights_now[sleeve],
                          "management_fees": k["management_fees"], "transaction_costs": k["transaction_costs"],
                          "ongoing_costs": k["management_fees"] + k["transaction_costs"], "document_date": k["document_date"]})  # fmt: skip
    costs = pd.DataFrame(cost_rows)
    costs = pd.concat([costs, pd.DataFrame([{"sleeve": "portfolio", "fund": "Weighted by the sleeve weights",
                                             "weight": float(costs["weight"].sum()),
                                             "management_fees": float((costs["weight"] * costs["management_fees"]).sum()),
                                             "transaction_costs": float((costs["weight"] * costs["transaction_costs"]).sum()),
                                             "ongoing_costs": float((costs["weight"] * costs["ongoing_costs"]).sum())}])],
                      ignore_index=True)  # fmt: skip
    sources = [
        ("MSCI North America, Europe, Pacific and Emerging Markets, net total return in euro, month-end levels",
         f"msci/region_{risk.REGIONS[0][1]}_netr_eur_monthly.json", levels.attrs["last_day"]),
        ("ECB, yield curve of all euro area government bonds, spot rates at 3, 7.5 and 20 years",
         f"ecb/curve_spot_{risk.MATURITY_GROUPS[0][4]}.csv", spot.attrs["last_day"]),
        ("iShares, IE00B6R52259, key information document", risk.KIDS[E][0], kids[E]["document_date"]),
        ("Vanguard, IE00BH04GL39, key information document", risk.KIDS[B][0], kids[B]["document_date"]),
    ]  # fmt: skip
    return [
        _write(components_table, "risk_components.csv", as_of, out_dir),
        _write(pairs, "risk_correlation.csv", as_of, out_dir),
        _write(frontiers, "risk_frontier.csv", as_of, out_dir),
        _write(summary, "risk_summary.csv", as_of, out_dir),
        _write(history, "ex_ante_risk.csv", as_of, out_dir),
        _write(episodes, "stress.csv", as_of, out_dir),
        _write(costs, "cost_of_ownership.csv", as_of, out_dir),
    ], sources


UNREADABLE = (SystemExit, ValueError, OSError, KeyError)
BANK_STATUS = "Rabobank publishes no return for its managed profiles"


def _comparison_inputs(refresh, today, navs, table, alt_usd, alt_eur, look, equity_as_of, sheet, out_dir) -> tuple:
    """The second stage's inputs to the comparisons, each from its publisher, and their rows of the sources table.

    A comparator whose series cannot be read, or does not reach the record's last day, shows n/a with the date, and
    no other publisher stands in for it. Region weights are kept from earlier builds at each month end
    (comparisons.keep_snapshots)."""
    funds = references.comparator_funds()
    isin_of = {r.comparator: r.isin for r in funds.itertuples() if r.sleeve in ("equity", "mixed")}
    starts = {r.comparator: r.series_from for r in funds.itertuples() if r.series_from}
    fixed_on = pd.Timestamp(funds["fixed_on"].min())
    last = table.index.max()
    read_on = pd.Timestamp(today).strftime("%Y-%m-%d")
    sources, spec = [], {"sp500": {"eur": alt_eur, "usd": alt_usd, "share": 1.0}}
    for key in ("msci_world", "lifestrategy_60", "lifestrategy_80", "nasdaq100", "mag7", "first_ranked"):
        isin = isin_of[key]
        try:
            values, currency = prices.load_comparator(isin, refresh)
        except UNREADABLE:
            spec[key] = {"eur": None, "status": f"series not read on {read_on}"}
            continue
        if values.index.max() < last:
            spec[key] = {"eur": None, "status": f"net asset values only to {values.index.max():%Y-%m-%d}"}
            continue
        on_days = values.reindex(values.index.union(navs.index)).ffill().reindex(navs.index)
        dollar = currency == "USD"
        spec[key] = {"eur": on_days / navs["usd_per_eur"] if dollar else on_days, "usd": values if dollar else None, "share": 1.0}
        if key in starts:
            spec[key]["from"] = pd.Timestamp(starts[key])
        issuer = prices.ISSUER_NAME[prices.COMPARATOR_FEEDS[isin][0]]
        label = f"{issuer}, {isin}, net asset values in {'US dollars' if dollar else 'euro'}"
        if issuer == "DWS":
            label += ", from the product page's historical data after its entry gate for the Netherlands, non-professional investor"
        sources.append((label, prices.comparator_cache_name(isin), values.index.max()))

    rows = []

    def snapshot(key, weights, day):
        rows.extend({"comparator": key, "snapshot": pd.Timestamp(day), "region": r, "weight": float(w)}
                    for r, w in comparisons.region_shares(weights).items())  # fmt: skip

    held = comparisons.region_shares(look["equity_region"]["share_of_sleeve"])
    snapshot("held", held, equity_as_of)
    msci_regions = pd.read_csv(config.METHOD_DIR / "msci_regions.csv")
    world = held
    for key in ("msci_world", "first_ranked"):
        if spec[key].get("eur") is None:
            continue
        try:
            holdings, as_of = prices.load_ssga_holdings(isin_of[key], refresh)
        except UNREADABLE:
            continue
        weights = comparisons.by_country(holdings, msci_regions)
        snapshot(key, weights, as_of)
        world = weights if key == "msci_world" else world
        sources.append((f"State Street, {isin_of[key]}, daily holdings", f"ssga/{isin_of[key]}_holdings.xlsx", as_of))
    for key in ("sp500", "nasdaq100", "mag7"):
        snapshot(key, pd.Series({"North America": 1.0}), fixed_on)
    mapping = pd.read_csv(config.METHOD_DIR / "lifestrategy_underlying.csv")
    charges = {}
    for key in ("lifestrategy_60", "lifestrategy_80"):
        if spec[key].get("eur") is None:
            continue
        allocation, dated = prices.load_lifestrategy_allocation(isin_of[key], refresh)
        share, weights = comparisons.mixed_regions(allocation, mapping, held, world)
        spec[key].update(share=share, bonds_na=True)
        snapshot(key, weights, dated)
        charges[key] = prices.load_lifestrategy_charges(isin_of[key], refresh)
        sources.append((f"Vanguard, {isin_of[key]}, monthly factsheet", f"vanguard/{isin_of[key]}_factsheet.pdf", dated))
    previous_path = Path(out_dir) / "comparison_regions.csv"
    previous = None
    if previous_path.exists():
        previous = pd.read_csv(previous_path).drop(columns=["as_of"], errors="ignore")
        previous["snapshot"] = pd.to_datetime(previous["snapshot"])
    regions = comparisons.keep_snapshots(previous, pd.DataFrame(rows), today)

    levels = risk.fetch_regions_daily(refresh, table.index.min() - pd.Timedelta(days=10), today)
    sources.append(("MSCI North America, Europe, Pacific and Emerging Markets, net total return in euro, daily levels",
                    f"msci/region_{risk.REGIONS[0][1]}_netr_eur_daily.json", levels.index.max()))  # fmt: skip
    duration = float(sheet["duration_years"])
    years = int(round(duration))
    spot = risk.fetch_spot_daily(years, refresh)
    sources.append((f"ECB, yield curve of all euro area government bonds, spot rate at {years} years, daily",
                    f"ecb/curve_spot_{years}Y.csv", spot.index.max()))  # fmt: skip
    try:
        bank = prices.load_rabobank_costs(refresh)
        sources.append(("Rabobank, cost overview of Rabo Beheerd Beleggen Basis", "rabobank/kostenoverzicht_basis.pdf", bank["dated"]))
    except UNREADABLE:
        bank = None
    ownership = pd.read_csv(Path(out_dir) / "cost_of_ownership.csv")
    first = spec.pop("first_ranked")
    market, market_sources, market_funds = _market_inputs(refresh, navs, last, read_on, funds)
    sources += market_sources
    extra = {"one_fund": spec, "first_ranked": first, "regions": regions, "region_levels": levels,
             "bond": {"spot": spot, "duration": duration}, "unavailable": {"bank_offensief": BANK_STATUS},
             "market_portfolio": market, "market_funds": market_funds,
             "fees": comparisons.fees(ownership, table["implementation_cost_bps"], charges, bank,
                                      comparisons.market_fees(market_funds, market["weights"]))}  # fmt: skip
    return extra, sources


def _market_table(weights: pd.DataFrame, funds: pd.DataFrame) -> pd.DataFrame:
    """The global market portfolio's weight table beside each class's fund, its ISIN, its income and its TER."""
    out = weights.merge(funds.reset_index().rename(columns={"index": "sleeve"}), on="sleeve", how="left")
    return out[["sleeve", "fund", "isin", "income", "ter_per_cent", "published", "published_as_of", "start", "start_as_of",
                "current", "current_as_of"]]  # fmt: skip


def _market_inputs(refresh, navs, last, read_on, funds) -> tuple:
    """The global market portfolio's inputs: each asset class fund's net asset values in euro, US dollar values at
    the ECB's reference rate of the day, a distributing class's with its distributions added back on their ex-dates,
    and the dollar values of the dollar funds; the published weights and their date; the rows of the sources table;
    and each class's fund with its TER and factsheet date. A fund whose series cannot be read or stops before the
    record's last day leaves the comparator n/a with the date."""
    weights, as_of = comparisons.market_weights()
    held = funds[funds["comparator"] == "market_portfolio"].set_index("sleeve").reindex(list(comparisons.MARKET_SLEEVES))
    ranking = pd.read_csv(config.METHOD_DIR / "selection_market_portfolio.csv").drop_duplicates("isin").set_index("isin")
    equity_ranking = pd.read_csv(config.METHOD_DIR / "selection_tracking_difference.csv").drop_duplicates("isin").set_index("isin")
    table = held[["fund", "isin", "income"]].copy()
    table["ter_per_cent"] = [(ranking if i in ranking.index else equity_ranking).loc[i, "ter_per_cent"] for i in table["isin"]]
    table["factsheet_date"] = [(ranking if i in ranking.index else equity_ranking).loc[i, "factsheet_date"] for i in table["isin"]]
    source = ("Doeswijk, Lam and Swinkels (2024), Data update: The Global Multi-Asset Market Portfolio, 1959-2012, "
              "version 6, the eight asset classes' weights at 31 December 2023")  # fmt: skip
    weights_table = pd.read_csv(config.METHOD_DIR / "market_portfolio_weights.csv")
    sources = [(source, "method/market_portfolio_weights.csv", as_of, weights_table["read_on"].iloc[0],
                f"https://doi.org/{weights_table['doi'].iloc[0]}")]  # fmt: skip
    rate = navs["usd_per_eur"]
    eur, usd, loaded = {}, {}, {}
    for sleeve in comparisons.MARKET_SLEEVES:
        isin = held.loc[sleeve, "isin"]
        if isin == config.ISIN[config.EQUITY]:
            eur[sleeve] = navs[config.EQUITY]  # the equity fund held, as the record values it
            continue
        if isin not in loaded:
            try:
                values, currency = prices.load_comparator(isin, refresh)
                distributing = held.loc[sleeve, "income"] == "distributing"
                if distributing:
                    values = prices.with_distributions(values, prices.load_distributions(isin, refresh))
            except UNREADABLE:
                return {"eur": None, "status": f"series not read on {read_on}", "weights": weights}, sources, table
            if values.index.max() < last:
                return ({"eur": None, "status": f"net asset values of {isin} only to {values.index.max():%Y-%m-%d}",
                         "weights": weights}, sources, table)  # fmt: skip
            loaded[isin] = (values, currency)
            issuer = prices.ISSUER_NAME[prices.COMPARATOR_FEEDS[isin][0]]
            label = f"{issuer}, {isin}, net asset values in {'US dollars' if currency == 'USD' else 'euro'}"
            if distributing:
                label += ", with the distributions by ex-date from the same file"
            if issuer == "DWS":
                label += ", from the product page's historical data after its entry gate for the Netherlands, non-professional investor"
            sources.append((label, prices.comparator_cache_name(isin), values.index.max()))
        values, currency = loaded[isin]
        on_days = values.reindex(values.index.union(navs.index)).ffill().reindex(navs.index)
        eur[sleeve] = on_days / rate if currency == "USD" else on_days
        if currency == "USD":
            usd[sleeve] = on_days
    market = {"eur": pd.DataFrame(eur)[list(comparisons.MARKET_SLEEVES)], "usd": pd.DataFrame(usd) if usd else None,
              "weights": weights, "as_of": as_of}  # fmt: skip
    return market, sources, table


def _sources(series, msci, equity_as_of, bonds_as_of, sheet_as_at, daily_factors, vintage, extra=()) -> pd.DataFrame:
    log_path = config.CACHE_DIR / "sources.json"
    log = json.loads(log_path.read_text()) if log_path.exists() else {}

    def downloaded(name):
        return log.get(name, {}).get("downloaded_utc", "")[:10]

    rows = [
        ("iShares, IE00B6R52259, net asset values in US dollars", "ishares/IE00B6R52259_fund.xml",
         series["equity_usd"].index.max()),
        ("Vanguard, IE00BH04GL39, net asset values in euro", "vanguard/IE00BH04GL39_nav.json",
         series["bonds_eur"].index.max()),
        ("ECB, euro reference rate against the US dollar", "ecb/usd_per_eur.csv", series["usd_per_eur"].index.max()),
        ("iShares, IE00B6R52259, holdings", "ishares/IE00B6R52259_holdings.csv", equity_as_of),
        ("Vanguard, IE00BH04GL39, holdings", "vanguard/IE00BH04GL39_holdings.json", bonds_as_of),
        ("Vanguard, IE00BH04GL39, monthly factsheet", "vanguard/factsheet_latest.pdf", sheet_as_at),
        ("Kenneth French, Developed 5 Factors and Momentum, daily, Bloomberg database "
         + "".join(ch for ch in vintage if ch.isdigit()),
         "french/Developed_5_Factors_Daily_CSV.zip", daily_factors.index.max()),
        ("MSCI ACWI net total return in euro, end-of-day levels", "msci/acwi_netr_eur.json", msci.index.max()),
        *extra,
    ]  # fmt: skip
    # A row may carry its own date read and address, for a source that is not downloaded at each build.
    return pd.DataFrame(
        [
            {"source": row[0], "downloaded": row[3] if len(row) > 3 else downloaded(row[1]),
             "last_date_covered": pd.Timestamp(row[2]), "address": row[4] if len(row) > 4 else log.get(row[1], {}).get("url", "")}
            for row in rows
        ]
    )


def privacy(records, out_dir: Path = config.OUTPUTS_DIR) -> None:
    """Fail if a public output names a euro or unit column, or carries a private figure."""
    private = {round(float(c.amount_eur), 2) for c in records.contributions.itertuples()}
    for o in records.orders.itertuples():
        private |= {round(abs(o.units), 4), round(o.gross, 2), round(o.price, 3)}
    private |= {round(float(records.contributions["amount_eur"].sum()), 2)}
    private.discard(0.0)
    for path in sorted(Path(out_dir).glob("*.csv")):
        frame = pd.read_csv(path)
        bad = [c for c in frame.columns if "eur" in c.lower().split("_") or c.lower().endswith("_units_held")]
        if bad:
            raise PrivacyError(f"{path.name}: column {bad} is named for euro or units")
        numbers = frame.select_dtypes(include=[np.number]).to_numpy().ravel()
        numbers = numbers[~np.isnan(numbers)]
        for x in numbers:
            for p in private:
                if abs(x - p) < 1e-9 or (p >= 1 and abs(round(x, 2) - p) < 1e-9 and abs(x - p) < 0.005):
                    raise PrivacyError(f"{path.name}: a figure equals a private value of the ledger")
