"""Valuation calculations: DCF, comparable multiples, blended, and projections."""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

import pandas as pd


# ── Sector multiple benchmarks (EV/Revenue) — Damodaran Jan 2026 + 20-30% private discount ──
SECTOR_MULTIPLES = {
    "Pure SaaS / Subscription Software":  {"low": 4.0,  "base": 7.0,  "high": 12.0},
    "Enterprise Software (B2B)":          {"low": 3.5,  "base": 6.0,  "high": 10.0},
    "Cybersecurity":                       {"low": 5.0,  "base": 8.5,  "high": 14.0},
    "Semiconductors & Hardware":          {"low": 2.0,  "base": 4.0,  "high": 7.0},
    "AI / Machine Learning":              {"low": 6.0,  "base": 12.0, "high": 22.0},
    "FinTech":                            {"low": 4.0,  "base": 7.0,  "high": 12.0},
    "InsurTech":                          {"low": 3.0,  "base": 5.5,  "high": 9.0},
    "Payments & Transaction Processing":  {"low": 4.0,  "base": 7.5,  "high": 13.0},
    "Wealth Management & Trading":        {"low": 2.5,  "base": 5.0,  "high": 8.0},
    "HealthTech / Digital Health":        {"low": 3.0,  "base": 6.0,  "high": 10.0},
    "Biotech & Pharmaceuticals":          {"low": 3.0,  "base": 7.0,  "high": 15.0},
    "Medical Devices":                    {"low": 2.5,  "base": 5.0,  "high": 9.0},
    "E-Commerce (inventory-based)":       {"low": 0.4,  "base": 1.0,  "high": 2.5},
    "Consumer Marketplace (asset-light)": {"low": 3.0,  "base": 5.5,  "high": 9.0},
    "Consumer Apps & Social":             {"low": 2.0,  "base": 4.5,  "high": 9.0},
    "Consumer Goods & FMCG":             {"low": 1.0,  "base": 2.5,  "high": 5.0},
    "Food & Beverage":                    {"low": 0.8,  "base": 1.8,  "high": 3.5},
    "DeepTech & Advanced Manufacturing":  {"low": 3.0,  "base": 7.0,  "high": 14.0},
    "CleanTech & Renewable Energy":       {"low": 2.5,  "base": 5.0,  "high": 9.0},
    "Logistics & Supply Chain":           {"low": 0.8,  "base": 2.0,  "high": 4.0},
    "Aerospace & Defence":                {"low": 0.8,  "base": 1.8,  "high": 3.5},
    "EdTech":                            {"low": 2.0,  "base": 4.0,  "high": 7.0},
    "PropTech & Real Estate":            {"low": 1.5,  "base": 3.5,  "high": 6.5},
    "Media & Entertainment":             {"low": 1.0,  "base": 2.5,  "high": 5.0},
    "Telecoms":                          {"low": 0.8,  "base": 1.5,  "high": 2.8},
    "Energy (Oil, Gas, Mining)":         {"low": 0.5,  "base": 1.2,  "high": 2.5},
    "Retail (Physical)":                 {"low": 0.3,  "base": 0.7,  "high": 1.5},
    "Professional Services":             {"low": 0.8,  "base": 1.8,  "high": 3.5},
    # Legacy keys — kept for backward compatibility with COMPARABLE_TRANSACTIONS lookups
    "SaaS":        {"low": 4.0,  "base": 7.0,  "high": 12.0},
    "HealthTech":  {"low": 3.0,  "base": 6.0,  "high": 10.0},
    "CleanTech":   {"low": 2.5,  "base": 5.0,  "high": 9.0},
    "DeepTech":    {"low": 3.0,  "base": 7.0,  "high": 14.0},
    "MarketPlace": {"low": 3.0,  "base": 5.5,  "high": 9.0},
    "E-Commerce":  {"low": 0.4,  "base": 1.0,  "high": 2.5},
    "Other":       {"low": 2.0,  "base": 4.0,  "high": 7.0},
}

# Stage-based WACC (cost of equity, 100% equity assumed)
WACC_BY_STAGE = {
    "Pre-Seed":  0.45,
    "Seed":      0.35,
    "Series A":  0.28,
    "Series B":  0.22,
    "Series C+": 0.18,
    "Series C":  0.18,
    "Growth":    0.15,
}


@dataclass
class CompanyInputs:
    """Holds all user-supplied company parameters for valuation."""
    stage: str

    # DCF assumption overrides
    tax_rate_pct: Optional[float] = 25.0
    capex_pct_of_ebitda: Optional[float] = 5.0
    nwc_pct_of_ebitda: Optional[float] = 3.0
    da_pct_of_revenue: Optional[float] = 3.0
    target_ebitda_margin_pct: Optional[float] = 25.0
    terminal_growth_rate_pct: Optional[float] = 3.0
    terminal_value_method: Optional[str] = "gordon_growth"   # "gordon_growth" | "exit_multiple"
    exit_multiple_ebitda: Optional[float] = None

    # WACC builder inputs
    use_custom_wacc: Optional[bool] = False
    custom_wacc_pct: Optional[float] = None

    # WACC formula components
    risk_free_rate_pct: Optional[float] = 4.2
    equity_risk_premium_pct: Optional[float] = 5.5
    beta: Optional[float] = None
    cost_of_debt_pct: Optional[float] = 8.0
    debt_gbp: Optional[float] = 0.0
    equity_gbp: Optional[float] = None

    # Projection horizon
    projection_years: Optional[int] = 5

    # Comparable valuation override
    custom_ev_rev_multiple: Optional[float] = None


def calculate_wacc(inputs: CompanyInputs, estimated_ev: float = None) -> tuple:
    """
    Returns (wacc_rate, wacc_method_string).
    Priority: 1) direct custom WACC, 2) WACC formula if beta provided, 3) stage-based default.
    """
    if inputs.use_custom_wacc and inputs.custom_wacc_pct is not None:
        return inputs.custom_wacc_pct / 100, "User-specified WACC"

    if inputs.beta is not None:
        rfr = (inputs.risk_free_rate_pct or 4.2) / 100
        erp = (inputs.equity_risk_premium_pct or 5.5) / 100
        cost_of_equity = rfr + inputs.beta * erp

        tax = (inputs.tax_rate_pct or 25.0) / 100
        kd = (inputs.cost_of_debt_pct or 8.0) / 100
        after_tax_kd = kd * (1 - tax)

        debt   = inputs.debt_gbp or 0.0
        equity = inputs.equity_gbp or (estimated_ev if estimated_ev else 0.0)
        total  = (debt + equity) if (debt + equity) > 0 else 1

        wd = debt / total
        we = equity / total

        wacc = we * cost_of_equity + wd * after_tax_kd
        method = (
            "WACC formula: Ke=" + str(round(cost_of_equity * 100, 1)) + "% "
            "(Rf=" + str(inputs.risk_free_rate_pct) + "% + B=" + str(inputs.beta)
            + " x ERP=" + str(inputs.equity_risk_premium_pct) + "%) "
            "Kd=" + str(round(after_tax_kd * 100, 1)) + "% after-tax "
            "D/E=" + str(round(wd * 100, 0)) + "/" + str(round(we * 100, 0)) + "%"
        )
        return wacc, method

    wacc = WACC_BY_STAGE.get(inputs.stage, 0.25)
    return wacc, "Stage-based required return (Damodaran methodology) — provide beta to use WACC formula"


def _project_fcf(revenues: list, ebitda: list,
                 capex_pct: float = 0.05, nwc_pct: float = 0.03,
                 tax_rate: float = 0.25, da_pct: float = 0.03) -> list:
    """
    Return list of unlevered FCFs.
    FCF = (EBITDA - D&A) * (1 - tax) + D&A - CapEx - NWC
        = EBITDA*(1-tax) + D&A*tax - CapEx - NWC
    """
    fcfs = []
    for rev, e in zip(revenues, ebitda):
        da     = rev * da_pct
        capex  = e * capex_pct
        nwc    = e * nwc_pct
        nopat  = (e - da) * (1 - tax_rate)
        fcf    = nopat + da - capex - nwc
        fcfs.append(fcf)
    return fcfs


def _project_revenues_ebitda(revenue: float, growth_rate: float,
                              ebitda_margin: float, years: int = 5,
                              scenario_adj: float = 0.0) -> tuple:
    """Return (revenues list, ebitda list) for each year."""
    g      = growth_rate / 100 + scenario_adj
    margin = ebitda_margin / 100
    revs, ebs = [], []
    rev = revenue
    for _ in range(years):
        rev = rev * (1 + g)
        revs.append(rev)
        ebs.append(rev * margin)
    return revs, ebs


def _pv_fcfs(fcfs: list, wacc: float) -> float:
    return sum(f / (1 + wacc) ** (i + 1) for i, f in enumerate(fcfs))


def _terminal_value(fcfs: list, ebitda_last: float, wacc: float,
                    terminal_growth: float, method: str,
                    exit_multiple: Optional[float]) -> float:
    """Return present value of terminal value."""
    years = len(fcfs)
    if wacc <= terminal_growth:
        wacc = terminal_growth + 0.01
    if method == "exit_multiple" and exit_multiple:
        tv_gross = ebitda_last * exit_multiple
    else:
        tv_gross = fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    return tv_gross / (1 + wacc) ** years


def _dcf_scenario(revenue: float, growth_pct: float, ebitda_margin: float,
                  wacc: float, terminal_growth: float, tax_rate: float,
                  capex_pct: float, nwc_pct: float, da_pct: float,
                  tv_method: str, exit_multiple: Optional[float],
                  scenario_adj: float = 0.0, years: int = 5) -> float:
    revs, ebs = _project_revenues_ebitda(revenue, growth_pct, ebitda_margin,
                                         years=years, scenario_adj=scenario_adj)
    eff_wacc = max(wacc, terminal_growth + 0.01)
    fcfs = _project_fcf(revs, ebs, capex_pct, nwc_pct, tax_rate, da_pct)
    pv   = _pv_fcfs(fcfs, eff_wacc)
    pv  += _terminal_value(fcfs, ebs[-1], eff_wacc, terminal_growth,
                           tv_method, exit_multiple)
    return max(pv, 0)


def dcf_valuation(revenue: float, growth_pct: float, ebitda_margin: float,
                  inputs: CompanyInputs) -> dict:
    """Return low/base/high DCF values in GBP, plus wacc, wacc_method, tv_method."""
    def _pct(val, default): return (val if val is not None else default) / 100
    tax_rate    = _pct(inputs.tax_rate_pct, 25.0)
    capex_pct   = _pct(inputs.capex_pct_of_ebitda, 5.0)
    nwc_pct     = _pct(inputs.nwc_pct_of_ebitda, 3.0)
    da_pct      = _pct(inputs.da_pct_of_revenue, 3.0)
    tg          = _pct(inputs.terminal_growth_rate_pct, 3.0)
    tv_method   = inputs.terminal_value_method or "gordon_growth"
    exit_mult   = inputs.exit_multiple_ebitda
    proj_years  = getattr(inputs, "projection_years", None) or 5

    # Proxy EV with stage WACC to seed WACC formula (avoids circularity)
    stage_wacc = WACC_BY_STAGE.get(inputs.stage, 0.30)
    proxy_ev   = _dcf_scenario(revenue, growth_pct, ebitda_margin, stage_wacc, tg,
                                tax_rate, capex_pct, nwc_pct, da_pct,
                                tv_method, exit_mult, years=proj_years)

    wacc, wacc_method = calculate_wacc(inputs, estimated_ev=proxy_ev)
    print(f"[WACC DEBUG] stage={inputs.stage}, wacc={wacc:.4f} ({wacc*100:.1f}%), method={wacc_method}")
    # Floor WACC at 12% for revenue > £500m to prevent terminal value explosion
    if revenue > 500_000_000:
        wacc = max(wacc, 0.12)

    sc = dict(tax_rate=tax_rate, capex_pct=capex_pct, nwc_pct=nwc_pct,
              da_pct=da_pct, tv_method=tv_method, exit_multiple=exit_mult,
              years=proj_years)

    # Compute base-case detail for waterfall / sensitivity
    revs, ebs = _project_revenues_ebitda(revenue, growth_pct, ebitda_margin, years=proj_years)
    eff_wacc = max(wacc, tg + 0.01)
    fcfs = _project_fcf(revs, ebs, capex_pct, nwc_pct, tax_rate, da_pct)
    pv_fcfs_list = [f / (1 + eff_wacc) ** (i + 1) for i, f in enumerate(fcfs)]
    pv_fcfs_sum = sum(pv_fcfs_list)
    terminal_value_pv = _terminal_value(fcfs, ebs[-1], eff_wacc, tg, tv_method, exit_mult)
    nopat_y1 = ebs[0] * (1 - tax_rate)

    return {
        "low":        _dcf_scenario(revenue, growth_pct, ebitda_margin,
                                    wacc + 0.05, tg - 0.005, scenario_adj=-0.05, **sc),
        "base":       _dcf_scenario(revenue, growth_pct, ebitda_margin,
                                    wacc, tg, **sc),
        "high":       _dcf_scenario(revenue, growth_pct, ebitda_margin,
                                    wacc - 0.05, tg + 0.005, scenario_adj=0.05, **sc),
        "wacc":        wacc,
        "wacc_method": wacc_method,
        "tv_method":   tv_method,
        "terminal_growth_pct": (inputs.terminal_growth_rate_pct or 3.0),
        "exit_multiple_ebitda": exit_mult,
        "dcf_detail": {
            "pv_fcfs_sum":      pv_fcfs_sum,
            "terminal_value_pv": terminal_value_pv,
            "fcfs":             fcfs,
            "pv_fcfs_list":     pv_fcfs_list,
            "nopat_y1":         nopat_y1,
            "ebitda_y1":        ebs[0],
            "revenue_y1":       revs[0],
        },
    }


def comparable_valuation(revenue: float, sector: str,
                         custom_ev_rev_multiple: Optional[float] = None,
                         growth_pct: float = 0.0) -> dict:
    """Return low/base/high EV via revenue multiples with optional override and growth premium."""
    m = SECTOR_MULTIPLES.get(sector, SECTOR_MULTIPLES["Other"])

    _ev_multiple = custom_ev_rev_multiple
    if _ev_multiple and float(_ev_multiple) > 0:
        base  = float(_ev_multiple)
        low   = base * 0.6
        high  = base * 1.4
        source = "User-specified " + str(round(base, 1)) + "x base multiple"
    else:
        low   = m["low"]
        base  = m["base"]
        high  = m["high"]
        source = sector + " sector average (Damodaran 2026)"

    growth_premium = (1.4 if growth_pct >= 100 else
                      1.25 if growth_pct >= 75 else
                      1.15 if growth_pct >= 50 else
                      1.05 if growth_pct >= 30 else 1.0)

    return {
        "low":  revenue * low,
        "base": revenue * base * growth_premium,
        "high": revenue * high * growth_premium,
        "source": source,
        "multiples": {"low": low, "base": base, "high": high},
        "growth_premium": growth_premium,
        "note": (str(round(base, 1)) + "x EV/Rev × "
                 + str(round(growth_premium, 2)) + "x growth premium ("
                 + str(round(growth_pct, 0)) + "% YoY growth)"),
    }


def blended_valuation(dcf: dict, comps: dict, dcf_weight: float = 0.5) -> dict:
    """Blend DCF and comps with given weight. Passes through wacc metadata."""
    w2 = 1 - dcf_weight
    return {
        "low":         dcf["low"]  * dcf_weight + comps["low"]  * w2,
        "base":        dcf["base"] * dcf_weight + comps["base"] * w2,
        "high":        dcf["high"] * dcf_weight + comps["high"] * w2,
        "wacc":        dcf.get("wacc", 0.30),
        "wacc_method": dcf.get("wacc_method", ""),
        "tv_method":   dcf.get("tv_method", "gordon_growth"),
        "terminal_growth_pct":  dcf.get("terminal_growth_pct", 3.0),
        "exit_multiple_ebitda": dcf.get("exit_multiple_ebitda"),
    }


def five_year_projection(revenue: float, growth_pct: float,
                         ebitda_margin: float,
                         target_ebitda_margin: float = None) -> pd.DataFrame:
    """Return DataFrame with 5-year revenue and EBITDA projections."""
    rows = []
    rev = revenue
    g = growth_pct / 100
    base_m = ebitda_margin
    target_m = target_ebitda_margin if target_ebitda_margin is not None else base_m
    for yr in range(1, 6):
        margin_pct = base_m + (target_m - base_m) * ((yr - 1) / max(4, 1))
        margin = margin_pct / 100
        rev = rev * (1 + g)
        ebitda = rev * margin
        rows.append({
            "Year":          f"Y{yr}",
            "Revenue (£m)":  round(rev / 1_000_000, 2),
            "EBITDA (£m)":   round(ebitda / 1_000_000, 2),
            "EBITDA Margin": f"{margin_pct:.0f}%",
        })
    return pd.DataFrame(rows)
