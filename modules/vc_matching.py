"""VC matching logic: score investors against company profile."""

import pandas as pd


def _sector_score(investor_sectors: str, company_sector: str) -> int:
    """Return 0–40 based on sector overlap."""
    if pd.isna(investor_sectors):
        return 20
    sectors = [s.strip().lower() for s in str(investor_sectors).split(",")]
    if company_sector.lower() in sectors:
        return 40
    # Partial: fintech / saas are adjacent
    adjacency = {
        "fintech":  ["saas", "marketplace"],
        "saas":     ["fintech", "cybersecurity", "deeptech"],
        "healthtech": ["deeptech"],
        "edtech":   ["saas"],
        "cleantech": ["deeptech"],
    }
    for adj in adjacency.get(company_sector.lower(), []):
        if adj in sectors:
            return 20
    return 5


def _stage_score(investor_stages: str, company_stage: str) -> int:
    """Return 0–30 based on stage match."""
    if pd.isna(investor_stages):
        return 15
    stages = [s.strip().lower() for s in str(investor_stages).split(",")]
    if company_stage.lower() in stages:
        return 30
    # Adjacent stage partial credit
    order = ["pre-seed", "seed", "series a", "series b", "series c+", "growth"]
    try:
        ci = order.index(company_stage.lower())
        for s in stages:
            if s in order:
                si = order.index(s)
                if abs(ci - si) == 1:
                    return 15
    except ValueError:
        pass
    return 0


def _geo_score(investor_geos: str, company_geo: str) -> int:
    """Return 0–20 based on geography match."""
    if pd.isna(investor_geos):
        return 10
    geos = [g.strip().lower() for g in str(investor_geos).split(",")]
    if company_geo.lower() in geos or "global" in geos:
        return 20
    # Europe / EMEA partial match for UK
    europe_terms = ["europe", "emea", "western europe"]
    if company_geo.lower() in ["uk", "united kingdom"]:
        for e in europe_terms:
            if e in geos:
                return 12
    return 5


def _cheque_score(min_cheque: float, max_cheque: float, revenue: float) -> int:
    """Return 0–10 based on typical cheque vs company funding need estimate."""
    # Rough estimate: company needs ~12–18 months runway capital ≈ 30% of revenue
    estimated_raise = revenue * 0.30
    if pd.isna(min_cheque) or pd.isna(max_cheque):
        return 5
    if min_cheque <= estimated_raise <= max_cheque:
        return 10
    if estimated_raise < min_cheque and estimated_raise > min_cheque * 0.5:
        return 5
    if estimated_raise > max_cheque and estimated_raise < max_cheque * 2:
        return 5
    return 2


def score_investors(df: pd.DataFrame, sector: str, stage: str,
                    geography: str, revenue: float) -> pd.DataFrame:
    """Score each investor and return sorted DataFrame."""
    results = []
    for _, row in df.iterrows():
        s_score  = _sector_score(row.get("sectors", ""), sector)
        st_score = _stage_score(row.get("stages", ""), stage)
        g_score  = _geo_score(row.get("geographies", ""), geography)
        c_score  = _cheque_score(
            float(row.get("min_cheque_gbp", 0) or 0),
            float(row.get("max_cheque_gbp", 0) or 0),
            revenue,
        )
        total = s_score + st_score + g_score + c_score
        results.append({
            "Investor":        row.get("name", "Unknown"),
            "Type":            row.get("type", "VC"),
            "Sector Fit":      s_score,
            "Stage Fit":       st_score,
            "Geo Fit":         g_score,
            "Cheque Fit":      c_score,
            "Score /100":      total,
            "Min Cheque (£m)": round(float(row.get("min_cheque_gbp", 0) or 0) / 1e6, 1),
            "Max Cheque (£m)": round(float(row.get("max_cheque_gbp", 0) or 0) / 1e6, 1),
            "Website":         row.get("website", ""),
        })
    out = pd.DataFrame(results).sort_values("Score /100", ascending=False)
    return out.reset_index(drop=True)
