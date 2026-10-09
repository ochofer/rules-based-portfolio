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

from . import config, factors, ledger as ledger_module, lookthrough, metrics, positions, prices, risk
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
    held = positions.build(records, today)
    values = valuations.build(held, navs)
    base = metrics.base_day(records, navs)
    ref_a = references.simulate(records, navs, today, "rules")
    ref_b = references.simulate(records, navs, today, "calendar")

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
    table = metrics.daily(records, values, ref_a, ref_b, blend, base)
    placed = metrics.orders(records)
    band, issues = metrics.compliance(records, navs, today)
    monthly = metrics.monthly(records, table, values, placed, today)

    # The state now: the units held at the end of today at the latest net asset values.
    now = valuations.at(held, navs, pd.Timestamp(today))
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
    impl = table[["implementation_cost_bps"]].dropna().reset_index()
    written.append(_write(impl, "implementation_cost.csv", as_of, out_dir))
    now_frame = pd.DataFrame(
        [{"weights_as_of": now["nav_date"], "positions_as_of": pd.Timestamp(today),
          "weight_equity": weights_now[E], "weight_bonds": weights_now[B], "weight_cash": weights_now["cash"]}]
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
    written.append(_write(metrics.attribution(daily_out), "attribution.csv", as_of, out_dir))

    checks = _checks(records, navs, look, weights_now, loadings)
    written.append(_write(checks, "checks.csv", as_of, out_dir))
    sources = _sources(series, msci, equity_as_of, bonds_as_of, latest_sheet.name, daily_factors, vintage, risk_sources)
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
    history = risk.record_estimate(history, end, estimate, current.index[0], first_purchase)
    calibration, calibration_months = risk.calibration(history, monthly)
    complete = monthly[monthly["complete"] == "yes"] if len(monthly) else monthly
    realised = float(complete["volatility_12m"].iloc[-1]) if len(complete) else float("nan")
    summary = pd.DataFrame([{**window_text, "earlier_window_start": str(earlier.index[0]),
                             "earlier_window_end": str(earlier.index[-1]), "weights_as_of": nav_date,
                             "estimated_volatility": estimate, "estimated_return": float(full_mean @ weights),
                             "minimum_variance_volatility": float(np.sqrt(minimum @ cov @ minimum)),
                             "minimum_variance_return": float(mean @ minimum), "israel_share_of_portfolio": israel,
                             "cash_weight": weights[risk.CASH], "calibration": calibration,
                             "calibration_months": calibration_months, "realised_volatility_12m": realised}])  # fmt: skip
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
    return pd.DataFrame(
        [
            {"source": s, "downloaded": downloaded(name), "last_date_covered": pd.Timestamp(last)}
            for s, name, last in rows
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
