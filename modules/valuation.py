"""Valuation calculations: DCF, comparable multiples, blended, and projections."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


# ── Sector multiple benchmarks (EV/Revenue) ─────────────────────────────────
SECTOR_MULTIPLES = {
    "FinTech":        {"low": 4.0,  "base": 7.0,  "high": 12.0},
    "SaaS":           {"low": 5.0,  "base": 9.0,  "high": 15.0},
    "HealthTech":     {"low": 3.5,  "base": 6.0,  "high": 10.0},
    "EdTech":         {"low": 2.5,  "base": 4.5,  "high": 8.0},
    "CleanTech":      {"low": 3.0,  "base": 5.5,  "high": 9.0},
    "E-Commerce":     {"low": 1.5,  "base": 3.0,  "high": 5.5},
    "DeepTech":       {"low": 4.0,  "base": 8.0,  "high": 14.0},
    "Cybersecurity":  {"low": 5.0,  "base": 9.5,  "high": 16.0},
    "MarketPlace":    {"low": 2.0,  "base": 4.0,  "high": 7.0},
    "Other":          {"low": 2.0,  "base": 4.0,  "high": 7.0},
}

# Stage-based WACC (cost of equity, 100% equity assumed)
WACC_BY_STAGE = {
    "Pre-Seed":  0.40,
    "Seed":      0.35,
    "Series A":  0.30,
    "Series B":  0.25,
    "Series C+": 0.20,
    "Growth":    0.18,
}


@dataclass
class CompanyInputs:
    """Holds all user-supplied company parameters for valuation."""
    stage: str

    # DCF assumption overrides
    tax_rate_pct: Optional[float] = 25.0
    capex_pct_of_ebitda: Optional[float] = 5.0
    nwc_pct_of_ebitda: Optional[float] = 3.0
    target_ebitda_margin_pct: Optional[float] = 25.0
    terminal_growth_rate_pct: Optional[float] = 3.0

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


def calculate_wacc(inputs: CompanyInputs, estimated_ev: float = None) -> tuple:
    """
    Returns (wacc_rate, wacc_method_string).
    Priority: 1) direct custom WACC, 2) WACC formula if beta provided, 3) stage-based default.
    """
    # Priority 1: user enters WACC directly
    if inputs.use_custom_wacc and inputs.custom_wacc_pct is not None:
        wacc = inputs.custom_wacc_pct / 100
        return wacc, "User-specified WACC"

    # Priority 2: build WACC from formula components if beta is provided
    if inputs.beta is not None:
        rfr = (inputs.risk_free_rate_pct or 4.2) / 100
        erp = (inputs.equity_risk_premium_pct or 5.5) / 100
        cost_of_equity = rfr + inputs.beta * erp

        tax = (inputs.tax_rate_pct or 25.0) / 100
        kd = (inputs.cost_of_debt_pct or 8.0) / 100
        after_tax_kd = kd * (1 - tax)

        debt = inputs.debt_gbp or 0.0
        equity = inputs.equity_gbp or (estimated_ev if estimated_ev else 0.0)
        total = debt + equity if (debt + equity) > 0 else 1

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

    # Priority 3: stage-based default
    wacc = WACC_BY_STAGE.get(inputs.stage, 0.25)
    return wacc, "Stage-based required return (Damodaran methodology) — provide beta to use WACC formula"


def _dcf_value(revenue: float, growth_rate: float, ebitda_margin: float,
               wacc: float, terminal_growth: float,
               tax_rate: float = 0.25, capex_pct: float = 0.05,
               nwc_pct: float = 0.03,
               years: int = 5, scenario_adj: float = 0.0) -> float:
    """Return DCF enterprise value for a single scenario."""
    g = growth_rate / 100 + scenario_adj
    # Guard: wacc must exceed terminal_growth
    if wacc <= terminal_growth:
        wacc = terminal_growth + 0.01
    margin = ebitda_margin / 100
    pv = 0.0
    rev = revenue
    for yr in range(1, years + 1):
        rev = rev * (1 + g)
        ebitda = rev * margin
        ebit = ebitda * (1 - capex_pct)
        nopat = ebit * (1 - tax_rate)
        fcf = nopat - ebitda * nwc_pct
        pv += fcf / (1 + wacc) ** yr
    # Terminal value (Gordon Growth)
    terminal_fcf = rev * margin * (1 - capex_pct) * (1 - tax_rate) * (1 + terminal_growth)
    tv = terminal_fcf / (wacc - terminal_growth)
    pv += tv / (1 + wacc) ** years
    return max(pv, 0)


def dcf_valuation(revenue: float, growth_pct: float, ebitda_margin: float,
                  inputs: CompanyInputs) -> dict:
    """Return low/base/high DCF values in GBP, plus wacc and wacc_method."""
    tax_rate   = (inputs.tax_rate_pct or 25.0) / 100
    capex_pct  = (inputs.capex_pct_of_ebitda or 5.0) / 100
    nwc_pct    = (inputs.nwc_pct_of_ebitda or 3.0) / 100
    tg         = (inputs.terminal_growth_rate_pct or 3.0) / 100

    # Compute a proxy base EV with stage WACC to seed the WACC formula (avoids circularity)
    stage_wacc = WACC_BY_STAGE.get(inputs.stage, 0.30)
    proxy_ev = _dcf_value(revenue, growth_pct, ebitda_margin, stage_wacc, tg,
                          tax_rate, capex_pct, nwc_pct)

    wacc, wacc_method = calculate_wacc(inputs, estimated_ev=proxy_ev)

    kwargs = dict(tax_rate=tax_rate, capex_pct=capex_pct, nwc_pct=nwc_pct)
    return {
        "low":         _dcf_value(revenue, growth_pct, ebitda_margin, wacc + 0.05, tg - 0.005, scenario_adj=-0.05, **kwargs),
        "base":        _dcf_value(revenue, growth_pct, ebitda_margin, wacc,         tg,                           **kwargs),
        "high":        _dcf_value(revenue, growth_pct, ebitda_margin, wacc - 0.05, tg + 0.005, scenario_adj=0.05,  **kwargs),
        "wacc":        wacc,
        "wacc_method": wacc_method,
    }


def comparable_valuation(revenue: float, sector: str) -> dict:
    """Return low/base/high EV via revenue multiples."""
    m = SECTOR_MULTIPLES.get(sector, SECTOR_MULTIPLES["Other"])
    return {
        "low":  revenue * m["low"],
        "base": revenue * m["base"],
        "high": revenue * m["high"],
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
    }


def five_year_projection(revenue: float, growth_pct: float,
                         ebitda_margin: float) -> pd.DataFrame:
    """Return DataFrame with 5-year revenue and EBITDA projections."""
    rows = []
    rev = revenue
    g = growth_pct / 100
    margin = ebitda_margin / 100
    for yr in range(1, 6):
        rev = rev * (1 + g)
        ebitda = rev * margin
        rows.append({
            "Year": f"Y{yr}",
            "Revenue (£m)": round(rev / 1_000_000, 2),
            "EBITDA (£m)":  round(ebitda / 1_000_000, 2),
            "EBITDA Margin": f"{ebitda_margin:.0f}%",
        })
    return pd.DataFrame(rows)
