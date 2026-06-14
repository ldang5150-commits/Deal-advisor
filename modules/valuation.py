"""Valuation calculations: DCF, comparable multiples, blended, and projections."""

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

# Stage-based discount / premium applied to DCF terminal growth
STAGE_GROWTH_PREMIUM = {
    "Pre-Seed":  0.01,
    "Seed":      0.02,
    "Series A":  0.025,
    "Series B":  0.03,
    "Series C+": 0.035,
    "Growth":    0.03,
}

# Stage-based WACC
STAGE_WACC = {
    "Pre-Seed":  0.40,
    "Seed":      0.35,
    "Series A":  0.30,
    "Series B":  0.25,
    "Series C+": 0.20,
    "Growth":    0.18,
}


def _dcf_value(revenue: float, growth_rate: float, ebitda_margin: float,
               wacc: float, terminal_growth: float,
               years: int = 5, scenario_adj: float = 0.0) -> float:
    """Return DCF enterprise value for a single scenario."""
    g = growth_rate / 100 + scenario_adj
    margin = ebitda_margin / 100
    pv = 0.0
    rev = revenue
    for yr in range(1, years + 1):
        rev = rev * (1 + g)
        fcf = rev * margin * 0.7          # rough EBIT → FCF conversion
        pv += fcf / (1 + wacc) ** yr
    # Terminal value (Gordon Growth)
    terminal_fcf = rev * margin * 0.7 * (1 + terminal_growth)
    tv = terminal_fcf / (wacc - terminal_growth)
    pv += tv / (1 + wacc) ** years
    return max(pv, 0)


def dcf_valuation(revenue: float, growth_pct: float, ebitda_margin: float,
                  stage: str) -> dict:
    """Return low/base/high DCF values in GBP."""
    wacc = STAGE_WACC.get(stage, 0.30)
    tg = STAGE_GROWTH_PREMIUM.get(stage, 0.025)
    return {
        "low":  _dcf_value(revenue, growth_pct, ebitda_margin, wacc + 0.05, tg - 0.005, scenario_adj=-0.05),
        "base": _dcf_value(revenue, growth_pct, ebitda_margin, wacc,        tg),
        "high": _dcf_value(revenue, growth_pct, ebitda_margin, wacc - 0.05, tg + 0.005, scenario_adj=0.05),
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
    """Blend DCF and comps with given weight."""
    w2 = 1 - dcf_weight
    return {
        "low":  dcf["low"]  * dcf_weight + comps["low"]  * w2,
        "base": dcf["base"] * dcf_weight + comps["base"] * w2,
        "high": dcf["high"] * dcf_weight + comps["high"] * w2,
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
