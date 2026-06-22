"""VC matching logic: score investors against company profile."""

from __future__ import annotations
from dataclasses import dataclass
import pandas as pd


SECTOR_NAME_MAP = {
    "Pure SaaS / Subscription Software": ["SaaS", "Software", "B2B SaaS",
                                           "Enterprise Software", "Pure SaaS"],
    "Enterprise Software (B2B)": ["Enterprise Software", "B2B", "SaaS",
                                   "Software", "B2B SaaS"],
    "Cybersecurity": ["Cybersecurity", "Security", "Cyber"],
    "Semiconductors & Hardware": ["Hardware", "Semiconductors", "Deep Tech",
                                   "DeepTech"],
    "AI / Machine Learning": ["AI", "Machine Learning", "Artificial Intelligence",
                               "ML", "Deep Tech", "DeepTech"],
    "FinTech": ["FinTech", "Fintech", "Financial Services", "Financial Technology",
                 "Finance"],
    "InsurTech": ["InsurTech", "Insurance", "Insurtech", "FinTech", "Fintech"],
    "Payments & Transaction Processing": ["Payments", "FinTech", "Fintech",
                                           "Financial Services", "Transaction"],
    "Wealth Management & Trading": ["Wealth Management", "Trading", "FinTech",
                                     "Fintech", "Investment"],
    "HealthTech / Digital Health": ["HealthTech", "Health Tech", "Digital Health",
                                     "Healthcare", "MedTech", "Health"],
    "Biotech & Pharmaceuticals": ["Biotech", "Pharmaceuticals", "Life Sciences",
                                   "BioTech", "Healthcare"],
    "Medical Devices": ["Medical Devices", "MedTech", "HealthTech", "Healthcare"],
    "E-Commerce (inventory-based)": ["E-Commerce", "eCommerce", "Retail",
                                      "Consumer", "D2C"],
    "Consumer Marketplace (asset-light)": ["Marketplace", "Consumer",
                                            "E-Commerce", "Platform"],
    "Consumer Apps & Social": ["Consumer", "Social", "Mobile", "Apps",
                                "Consumer Tech"],
    "Consumer Goods & FMCG": ["Consumer", "FMCG", "Consumer Goods", "Retail"],
    "Food & Beverage": ["Food & Beverage", "FoodTech", "Consumer", "FMCG"],
    "DeepTech & Advanced Manufacturing": ["DeepTech", "Deep Tech", "Hardware",
                                           "Manufacturing", "Industrial"],
    "CleanTech & Renewable Energy": ["CleanTech", "Clean Tech", "GreenTech",
                                      "Energy", "Sustainability", "Climate"],
    "Logistics & Supply Chain": ["Logistics", "Supply Chain", "Transport",
                                  "Delivery"],
    "Aerospace & Defence": ["Aerospace", "Defence", "Defense", "Deep Tech",
                             "DeepTech"],
    "EdTech": ["EdTech", "Education", "Ed Tech", "Learning"],
    "PropTech & Real Estate": ["PropTech", "Property", "Real Estate",
                                "Prop Tech"],
    "Media & Entertainment": ["Media", "Entertainment", "Content", "Publishing"],
    "Telecoms": ["Telecoms", "Telecommunications", "Telecom"],
    "Energy (Oil, Gas, Mining)": ["Energy", "Oil & Gas", "Mining", "Resources"],
    "Retail (Physical)": ["Retail", "Consumer", "High Street"],
    "Professional Services": ["Professional Services", "Consulting", "Services"],
    "Other": [],
}


def get_sector_aliases(sector: str) -> list:
    aliases = SECTOR_NAME_MAP.get(sector, [])
    if sector not in aliases:
        aliases = [sector] + aliases
    return [s.lower().strip() for s in aliases]


ADJACENCY = {
    "fintech":       ["saas", "marketplace"],
    "saas":          ["fintech", "cybersecurity", "deeptech"],
    "healthtech":    ["deeptech"],
    "edtech":        ["saas"],
    "cleantech":     ["deeptech"],
    "cybersecurity": ["saas", "deeptech"],
    "deeptech":      ["saas", "cleantech", "healthtech", "cybersecurity"],
    "marketplace":   ["fintech", "e-commerce"],
    "e-commerce":    ["marketplace", "saas"],
}

STAGE_ORDER = ["pre-seed", "seed", "series a", "series b", "series c+", "growth"]


@dataclass
class MatchResult:
    name: str
    score: int
    sector_score: int
    stage_score: int
    geo_score: int
    cheque_score: int
    sector_rationale: str
    stage_rationale: str
    geo_rationale: str
    cheque_rationale: str
    notable_portfolio: str
    cheque_range: str
    website: str
    description: str
    investor_type: str


def _sector_score(investor_sectors: str, company_sector: str,
                  sector_count: int) -> tuple[int, str]:
    if pd.isna(investor_sectors):
        return 8, "Sector coverage unknown"
    vc_sectors = [s.strip().lower() for s in str(investor_sectors).split(",")]
    user_aliases = get_sector_aliases(company_sector)

    sector_fit = any(
        any(alias in vc_s or vc_s in alias for alias in user_aliases)
        for vc_s in vc_sectors
    )

    if sector_fit:
        n = max(1, int(sector_count) if not pd.isna(sector_count) else len(vc_sectors))
        if n == 1:
            s_score, s_rat = 35, "Primary sector specialist"
        elif n == 2:
            s_score, s_rat = 30, f"Dual-sector focus includes {company_sector}"
        elif n == 3:
            s_score, s_rat = 24, f"One of {n} sectors covered — some specialisation"
        elif n == 4:
            s_score, s_rat = 18, f"One of {n} sectors covered — generalist fund"
        else:
            s_score, s_rat = 12, f"One of {n} sectors covered — broad generalist fund"

        # Position penalty: sector listed later gets reduced score
        sector_position = -1
        for i, vc_s in enumerate(vc_sectors):
            if any(alias in vc_s or vc_s in alias for alias in user_aliases):
                sector_position = i
                break
        if sector_position == 1:
            s_score = int(s_score * 0.85)
        elif sector_position >= 2:
            s_score = int(s_score * 0.70)

        return s_score, s_rat

    # Adjacency fallback using legacy short names
    cs_short = company_sector.lower().split("/")[0].strip().split("(")[0].strip()
    for adj in ADJACENCY.get(cs_short, []):
        if any(adj in vc_s or vc_s in adj for vc_s in vc_sectors):
            return 8, f"Adjacent sector investor — {company_sector} not primary focus"

    return 0, "No sector overlap identified"


def _stage_score(investor_stages: str, company_stage: str,
                 stage_count: int) -> tuple[int, str]:
    if pd.isna(investor_stages):
        return 10, "Stage coverage unknown"
    stages = [s.strip().lower() for s in str(investor_stages).split(",")]
    cs = company_stage.lower()

    if cs in stages:
        n = max(1, int(stage_count) if not pd.isna(stage_count) else len(stages))
        if n == 1:
            return 35, f"{company_stage} specialist"
        elif n == 2:
            return 30, f"{company_stage} is one of {n} stages — active deployment"
        elif n == 3:
            return 24, f"{company_stage} is one of {n} stages — confirm active deployment"
        elif n == 4:
            return 18, f"{company_stage} is one of {n} stages — confirm it is actively deployed"
        else:
            return 12, f"{company_stage} is one of {n} stages — confirm it is actively deployed"

    try:
        ci = STAGE_ORDER.index(cs)
        for s in stages:
            if s in STAGE_ORDER:
                if abs(STAGE_ORDER.index(s) - ci) == 1:
                    return 10, f"Adjacent stage — may consider {company_stage} in right circumstances"
    except ValueError:
        pass

    return 0, "Stage not in active investment mandate"


def _geo_score(investor_geos: str, company_geo: str,
               geo_count: int) -> tuple[int, str]:
    if pd.isna(investor_geos):
        return 8, "Geography coverage unknown"
    geos = [g.strip().lower() for g in str(investor_geos).split(",")]
    cg = company_geo.lower()

    direct_match = cg in geos or "global" in geos
    europe_match = (
        cg in ["uk", "united kingdom"]
        and any(e in geos for e in ["europe", "emea", "western europe"])
    )

    if direct_match or europe_match:
        n = max(1, int(geo_count) if not pd.isna(geo_count) else len(geos))
        if "global" in geos or n >= 4:
            return 8, f"Global fund — {company_geo} is within scope but not a focus"
        elif n == 1:
            return 20, f"{company_geo}-focused fund"
        elif n == 2:
            return 16, f"Active in {company_geo} among {n} regions"
        else:
            return 12, f"Active in {company_geo} among {n} regions"

    return 0, "Geography outside investment mandate"


def _cheque_score(min_cheque: float, max_cheque: float,
                  estimated_raise: float) -> tuple[int, int, str]:
    """Return (score, penalty, rationale). Penalty is subtracted from total."""
    if pd.isna(min_cheque) or pd.isna(max_cheque) or max_cheque == 0:
        return 5, 0, "Cheque size data unavailable"

    if min_cheque <= estimated_raise <= max_cheque:
        return 10, 0, "Raise amount squarely within typical cheque range"

    half_min = min_cheque * 0.5
    one_half_max = max_cheque * 1.5

    if estimated_raise < half_min:
        return 0, 5, "Raise likely too small for this fund"

    if estimated_raise > max_cheque * 2:
        return 0, 5, "Raise exceeds typical cheque size"

    if half_min <= estimated_raise < min_cheque or max_cheque < estimated_raise <= one_half_max:
        return 6, 0, "Raise slightly outside typical range but within reach"

    return 6, 0, "Raise slightly outside typical range but within reach"


def score_investors(df: pd.DataFrame, sector: str, stage: str,
                    geography: str, revenue: float) -> pd.DataFrame:
    """Score each investor and return sorted DataFrame with full rationale fields."""
    estimated_raise = revenue * 0.30
    results = []

    for _, row in df.iterrows():
        s_score, s_rat = _sector_score(
            row.get("sectors", ""), sector,
            row.get("sector_count", 0) or 0,
        )
        st_score, st_rat = _stage_score(
            row.get("stages", ""), stage,
            row.get("stage_count", 0) or 0,
        )
        g_score, g_rat = _geo_score(
            row.get("geographies", ""), geography,
            row.get("geo_count", 0) or 0,
        )
        min_c = float(row.get("min_cheque_gbp", 0) or 0)
        max_c = float(row.get("max_cheque_gbp", 0) or 0)
        c_score, penalty, c_rat = _cheque_score(min_c, max_c, estimated_raise)

        raw_total = s_score + st_score + g_score + c_score - penalty
        cheque_range = max_c - min_c
        if cheque_range > 50_000_000:
            raw_total -= 5
        total = max(0, min(100, raw_total))

        cheque_range = (
            f"£{min_c/1e6:.1f}m – £{max_c/1e6:.1f}m"
            if min_c > 0 and max_c > 0 else "Unknown"
        )

        results.append({
            "Investor":          row.get("name", "Unknown"),
            "Type":              row.get("type", "VC"),
            "Score /100":        total,
            "Sector Fit":        s_score,
            "Stage Fit":         st_score,
            "Geo Fit":           g_score,
            "Cheque Fit":        c_score,
            "Sector Rationale":  s_rat,
            "Stage Rationale":   st_rat,
            "Geo Rationale":     g_rat,
            "Cheque Rationale":  c_rat,
            "Notable Portfolio": row.get("notable_portfolio", ""),
            "Description":       row.get("description", ""),
            "Cheque Range":      cheque_range,
            "Website":           row.get("website", ""),
            "Min Cheque (£m)":   round(min_c / 1e6, 1),
            "Max Cheque (£m)":   round(max_c / 1e6, 1),
        })

    out = pd.DataFrame(results).sort_values("Score /100", ascending=False)
    return out.reset_index(drop=True)
