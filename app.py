"""Runrate — Deal intelligence Streamlit app."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

from modules.valuation import (
    dcf_valuation,
    comparable_valuation,
    blended_valuation,
    five_year_projection,
)
from modules.vc_matching import score_investors
from types import SimpleNamespace as MatchResult
from types import SimpleNamespace as _NS

# ── Sector betas (Damodaran Jan 2025, unlevered) ──────────────────────────────
SECTOR_BETAS = {
    "Pure SaaS / Subscription Software": 1.20,
    "Enterprise Software (B2B)": 1.10,
    "Cybersecurity": 1.35,
    "Semiconductors & Hardware": 1.40,
    "AI / Machine Learning": 1.50,
    "FinTech": 1.30,
    "InsurTech": 1.20,
    "Payments & Transaction Processing": 1.25,
    "Wealth Management & Trading": 1.15,
    "HealthTech / Digital Health": 0.95,
    "Biotech & Pharmaceuticals": 0.85,
    "Medical Devices": 0.90,
    "E-Commerce (inventory-based)": 1.10,
    "Consumer Marketplace (asset-light)": 1.25,
    "Consumer Apps & Social": 1.30,
    "Consumer Goods & FMCG": 0.80,
    "Food & Beverage": 0.75,
    "DeepTech & Advanced Manufacturing": 1.45,
    "CleanTech & Renewable Energy": 1.15,
    "Logistics & Supply Chain": 1.05,
    "Aerospace & Defence": 0.85,
    "EdTech": 1.05,
    "PropTech & Real Estate": 1.10,
    "Media & Entertainment": 1.00,
    "Telecoms": 0.80,
    "Energy (Oil, Gas, Mining)": 1.20,
    "Retail (Physical)": 0.90,
    "Professional Services": 0.85,
    "Other": 1.20,
}

# ── Sector-specific model defaults ───────────────────────────────────────────
SECTOR_DEFAULTS = {
    "Pure SaaS / Subscription Software": {"revenue": 3_000_000, "growth": 80, "ebitda": -15, "tax": 25, "capex": 3, "target_margin": 30, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "£1m-£10m ARR", "burn_note": "High burn typical pre-profitability"},
    "Enterprise Software (B2B)": {"revenue": 5_000_000, "growth": 40, "ebitda": 5, "tax": 25, "capex": 4, "target_margin": 25, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "£2m-£20m ARR", "burn_note": "Longer sales cycles, more stable burn"},
    "Cybersecurity": {"revenue": 4_000_000, "growth": 60, "ebitda": -10, "tax": 25, "capex": 3, "target_margin": 28, "terminal_growth": 3.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "£1m-£15m ARR", "burn_note": "R&D heavy, high burn expected"},
    "Semiconductors & Hardware": {"revenue": 8_000_000, "growth": 25, "ebitda": 10, "tax": 25, "capex": 15, "target_margin": 22, "terminal_growth": 2.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Mixed recurring and project revenue", "burn_note": "High capex intensity"},
    "AI / Machine Learning": {"revenue": 2_000_000, "growth": 120, "ebitda": -30, "tax": 25, "capex": 5, "target_margin": 35, "terminal_growth": 4.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Early ARR, rapid growth", "burn_note": "Very high compute costs"},
    "FinTech": {"revenue": 4_000_000, "growth": 70, "ebitda": 10, "tax": 25, "capex": 4, "target_margin": 25, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "£1m-£10m revenue", "burn_note": "Regulatory costs significant"},
    "InsurTech": {"revenue": 5_000_000, "growth": 45, "ebitda": 5, "tax": 25, "capex": 3, "target_margin": 20, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Mix of premium and SaaS revenue", "burn_note": "Claims reserves affect burn"},
    "Payments & Transaction Processing": {"revenue": 6_000_000, "growth": 55, "ebitda": 15, "tax": 25, "capex": 5, "target_margin": 28, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Transaction volume driven", "burn_note": "Capital efficient at scale"},
    "Wealth Management & Trading": {"revenue": 3_000_000, "growth": 35, "ebitda": 20, "tax": 25, "capex": 3, "target_margin": 30, "terminal_growth": 2.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "AUM-based fees", "burn_note": "Relatively capital efficient"},
    "HealthTech / Digital Health": {"revenue": 3_000_000, "growth": 60, "ebitda": -10, "tax": 25, "capex": 4, "target_margin": 22, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "£500k-£5m ARR", "burn_note": "Clinical validation costs significant"},
    "Biotech & Pharmaceuticals": {"revenue": 2_000_000, "growth": 50, "ebitda": -60, "tax": 25, "capex": 8, "target_margin": 35, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Pre-revenue to early revenue", "burn_note": "Very high R&D burn, long timeline"},
    "Medical Devices": {"revenue": 4_000_000, "growth": 30, "ebitda": 5, "tax": 25, "capex": 10, "target_margin": 20, "terminal_growth": 2.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Hardware + recurring revenue", "burn_note": "Manufacturing capex heavy"},
    "E-Commerce (inventory-based)": {"revenue": 10_000_000, "growth": 30, "ebitda": 5, "tax": 25, "capex": 5, "target_margin": 12, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "GMV-based", "burn_note": "Working capital intensive, thin margins"},
    "Consumer Marketplace (asset-light)": {"revenue": 5_000_000, "growth": 55, "ebitda": -5, "tax": 25, "capex": 3, "target_margin": 25, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Take rate on GMV", "burn_note": "Supply-demand balance key"},
    "Consumer Apps & Social": {"revenue": 2_000_000, "growth": 80, "ebitda": -25, "tax": 25, "capex": 3, "target_margin": 20, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Ad or subscription revenue", "burn_note": "User acquisition costs high"},
    "Consumer Goods & FMCG": {"revenue": 8_000_000, "growth": 25, "ebitda": 12, "tax": 25, "capex": 6, "target_margin": 18, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Product revenue", "burn_note": "Distribution and marketing heavy"},
    "Food & Beverage": {"revenue": 6_000_000, "growth": 20, "ebitda": 8, "tax": 25, "capex": 6, "target_margin": 15, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Product revenue", "burn_note": "Logistics and COGS intensive"},
    "DeepTech & Advanced Manufacturing": {"revenue": 3_000_000, "growth": 50, "ebitda": -20, "tax": 25, "capex": 12, "target_margin": 25, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Project and licence revenue", "burn_note": "High R&D and capex"},
    "CleanTech & Renewable Energy": {"revenue": 5_000_000, "growth": 40, "ebitda": 10, "tax": 25, "capex": 15, "target_margin": 22, "terminal_growth": 3.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Project and recurring revenue", "burn_note": "Capital intensive deployment"},
    "Logistics & Supply Chain": {"revenue": 10_000_000, "growth": 25, "ebitda": 8, "tax": 25, "capex": 8, "target_margin": 15, "terminal_growth": 2.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Volume-based revenue", "burn_note": "Asset and working capital heavy"},
    "Aerospace & Defence": {"revenue": 8_000_000, "growth": 15, "ebitda": 12, "tax": 25, "capex": 10, "target_margin": 18, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Government contract revenue", "burn_note": "Long contract cycles"},
    "EdTech": {"revenue": 3_000_000, "growth": 45, "ebitda": 5, "tax": 25, "capex": 3, "target_margin": 22, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "B2B or B2C subscription", "burn_note": "Content costs significant"},
    "PropTech & Real Estate": {"revenue": 5_000_000, "growth": 35, "ebitda": 10, "tax": 25, "capex": 4, "target_margin": 20, "terminal_growth": 2.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Transaction or SaaS revenue", "burn_note": "Market cycle sensitive"},
    "Media & Entertainment": {"revenue": 5_000_000, "growth": 20, "ebitda": 10, "tax": 25, "capex": 5, "target_margin": 18, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Ad, subscription, or licensing", "burn_note": "Content production costs"},
    "Telecoms": {"revenue": 15_000_000, "growth": 10, "ebitda": 20, "tax": 25, "capex": 18, "target_margin": 25, "terminal_growth": 1.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Subscription revenue", "burn_note": "Infrastructure capex very high"},
    "Energy (Oil, Gas, Mining)": {"revenue": 20_000_000, "growth": 10, "ebitda": 25, "tax": 30, "capex": 25, "target_margin": 28, "terminal_growth": 1.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Commodity price linked", "burn_note": "Exploration capex very high"},
    "Retail (Physical)": {"revenue": 10_000_000, "growth": 8, "ebitda": 6, "tax": 25, "capex": 5, "target_margin": 10, "terminal_growth": 1.5, "rfr": 4.2, "erp": 5.5, "typical_arr": "Store-based revenue", "burn_note": "Lease and inventory costs high"},
    "Professional Services": {"revenue": 5_000_000, "growth": 15, "ebitda": 18, "tax": 25, "capex": 2, "target_margin": 22, "terminal_growth": 2.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Fee-based revenue", "burn_note": "People cost is main expense"},
    "Other": {"revenue": 4_000_000, "growth": 40, "ebitda": 10, "tax": 25, "capex": 5, "target_margin": 20, "terminal_growth": 3.0, "rfr": 4.2, "erp": 5.5, "typical_arr": "Varies", "burn_note": "Varies by business model"},
}

_ALL_SECTORS = [
    "Pure SaaS / Subscription Software", "Enterprise Software (B2B)", "Cybersecurity",
    "Semiconductors & Hardware", "AI / Machine Learning",
    "FinTech", "InsurTech", "Payments & Transaction Processing", "Wealth Management & Trading",
    "HealthTech / Digital Health", "Biotech & Pharmaceuticals", "Medical Devices",
    "E-Commerce (inventory-based)", "Consumer Marketplace (asset-light)", "Consumer Apps & Social",
    "Consumer Goods & FMCG", "Food & Beverage",
    "DeepTech & Advanced Manufacturing", "CleanTech & Renewable Energy",
    "Logistics & Supply Chain", "Aerospace & Defence",
    "EdTech", "PropTech & Real Estate", "Media & Entertainment",
    "Telecoms", "Energy (Oil, Gas, Mining)", "Retail (Physical)",
    "Professional Services", "Other",
]

COMPARABLE_TRANSACTIONS = {
    "FinTech": [
        {"target": "Currencycloud", "acquirer": "Visa", "year": 2021, "deal_size_gbp": 700_000_000, "revenue_gbp": 60_000_000, "ev_rev_multiple": 11.7, "detail": "Cross-border payments infrastructure"},
        {"target": "Yapily", "acquirer": "Mastercard", "year": 2023, "deal_size_gbp": 180_000_000, "revenue_gbp": 18_000_000, "ev_rev_multiple": 10.0, "detail": "Open banking API platform"},
        {"target": "Divido", "acquirer": "Solarisbank", "year": 2023, "deal_size_gbp": 45_000_000, "revenue_gbp": 6_000_000, "ev_rev_multiple": 7.5, "detail": "White-label BNPL infrastructure"},
        {"target": "Salt Edge", "acquirer": "Mastercard", "year": 2022, "deal_size_gbp": 90_000_000, "revenue_gbp": 10_000_000, "ev_rev_multiple": 9.0, "detail": "Open banking data platform"},
        {"target": "Tink", "acquirer": "Visa", "year": 2022, "deal_size_gbp": 1_800_000_000, "revenue_gbp": 120_000_000, "ev_rev_multiple": 15.0, "detail": "Open banking platform"},
    ],
    "SaaS": [
        {"target": "Enghouse", "acquirer": "PE Consortium", "year": 2023, "deal_size_gbp": 320_000_000, "revenue_gbp": 40_000_000, "ev_rev_multiple": 8.0, "detail": "Enterprise communications SaaS"},
        {"target": "Episerver", "acquirer": "Optimizely", "year": 2021, "deal_size_gbp": 1_100_000_000, "revenue_gbp": 110_000_000, "ev_rev_multiple": 10.0, "detail": "CMS and digital experience platform"},
        {"target": "IRIS Software", "acquirer": "Hg Capital", "year": 2023, "deal_size_gbp": 1_400_000_000, "revenue_gbp": 120_000_000, "ev_rev_multiple": 11.7, "detail": "Accounting and HR SaaS for SMEs"},
        {"target": "Aptean", "acquirer": "Vista Equity", "year": 2022, "deal_size_gbp": 800_000_000, "revenue_gbp": 80_000_000, "ev_rev_multiple": 10.0, "detail": "ERP software for manufacturing"},
        {"target": "Calabrio", "acquirer": "KKR", "year": 2022, "deal_size_gbp": 400_000_000, "revenue_gbp": 50_000_000, "ev_rev_multiple": 8.0, "detail": "Workforce management SaaS"},
    ],
    "HealthTech": [
        {"target": "Babylon Health", "acquirer": "AlbaCore Capital", "year": 2023, "deal_size_gbp": 150_000_000, "revenue_gbp": 60_000_000, "ev_rev_multiple": 2.5, "detail": "AI-powered telehealth"},
        {"target": "Huma Therapeutics", "acquirer": "Bayer AG", "year": 2023, "deal_size_gbp": 80_000_000, "revenue_gbp": 12_000_000, "ev_rev_multiple": 6.7, "detail": "Remote patient monitoring"},
        {"target": "Cera Care", "acquirer": "Francisco Partners", "year": 2022, "deal_size_gbp": 200_000_000, "revenue_gbp": 40_000_000, "ev_rev_multiple": 5.0, "detail": "AI-powered home care platform"},
        {"target": "DrDoctor", "acquirer": "Imprivata", "year": 2023, "deal_size_gbp": 60_000_000, "revenue_gbp": 10_000_000, "ev_rev_multiple": 6.0, "detail": "NHS patient engagement platform"},
        {"target": "Graphnet Health", "acquirer": "Nordic Capital", "year": 2022, "deal_size_gbp": 120_000_000, "revenue_gbp": 20_000_000, "ev_rev_multiple": 6.0, "detail": "Integrated care records platform"},
    ],
    "MarketPlace": [
        {"target": "Treatwell", "acquirer": "EQT", "year": 2022, "deal_size_gbp": 220_000_000, "revenue_gbp": 44_000_000, "ev_rev_multiple": 5.0, "detail": "Beauty booking marketplace"},
        {"target": "Housesimple", "acquirer": "Aviva", "year": 2022, "deal_size_gbp": 40_000_000, "revenue_gbp": 8_000_000, "ev_rev_multiple": 5.0, "detail": "Online estate agency"},
        {"target": "GoCardless", "acquirer": "Stripe (partial)", "year": 2023, "deal_size_gbp": 312_000_000, "revenue_gbp": 60_000_000, "ev_rev_multiple": 5.2, "detail": "Bank payment network"},
        {"target": "Cazoo", "acquirer": "Constellation Automotive", "year": 2024, "deal_size_gbp": 200_000_000, "revenue_gbp": 300_000_000, "ev_rev_multiple": 0.7, "detail": "Online used car marketplace"},
        {"target": "Farfetch", "acquirer": "Coupang", "year": 2024, "deal_size_gbp": 500_000_000, "revenue_gbp": 1_800_000_000, "ev_rev_multiple": 0.3, "detail": "Luxury fashion marketplace"},
    ],
    "DeepTech": [
        {"target": "Darktrace", "acquirer": "Thoma Bravo", "year": 2024, "deal_size_gbp": 4_300_000_000, "revenue_gbp": 430_000_000, "ev_rev_multiple": 10.0, "detail": "AI cybersecurity platform"},
        {"target": "Oxford Ionics", "acquirer": "Honeywell", "year": 2023, "deal_size_gbp": 120_000_000, "revenue_gbp": 8_000_000, "ev_rev_multiple": 15.0, "detail": "Quantum computing chips"},
        {"target": "Wayve", "acquirer": "SoftBank led", "year": 2024, "deal_size_gbp": 850_000_000, "revenue_gbp": 20_000_000, "ev_rev_multiple": 42.5, "detail": "Autonomous vehicle AI"},
        {"target": "Tractable", "acquirer": "Apax Partners", "year": 2023, "deal_size_gbp": 900_000_000, "revenue_gbp": 45_000_000, "ev_rev_multiple": 20.0, "detail": "AI for insurance claims"},
        {"target": "PolyAI", "acquirer": "General Atlantic", "year": 2024, "deal_size_gbp": 400_000_000, "revenue_gbp": 30_000_000, "ev_rev_multiple": 13.3, "detail": "Voice AI for enterprise"},
    ],
    "EdTech": [
        {"target": "Multiverse", "acquirer": "GA growth equity", "year": 2022, "deal_size_gbp": 180_000_000, "revenue_gbp": 30_000_000, "ev_rev_multiple": 6.0, "detail": "Apprenticeship platform"},
        {"target": "Busuu", "acquirer": "McGraw Hill", "year": 2022, "deal_size_gbp": 360_000_000, "revenue_gbp": 36_000_000, "ev_rev_multiple": 10.0, "detail": "Language learning platform"},
        {"target": "Codeweavers", "acquirer": "ITC Group", "year": 2023, "deal_size_gbp": 25_000_000, "revenue_gbp": 5_000_000, "ev_rev_multiple": 5.0, "detail": "Automotive finance software"},
        {"target": "Twinkl", "acquirer": "Growth equity round", "year": 2023, "deal_size_gbp": 55_000_000, "revenue_gbp": 40_000_000, "ev_rev_multiple": 1.4, "detail": "Teacher resources platform"},
        {"target": "Firefly Learning", "acquirer": "Juniper Education", "year": 2022, "deal_size_gbp": 20_000_000, "revenue_gbp": 5_000_000, "ev_rev_multiple": 4.0, "detail": "School learning management system"},
    ],
    "CleanTech": [
        {"target": "Octopus Energy (partial)", "acquirer": "KKR", "year": 2023, "deal_size_gbp": 3_000_000_000, "revenue_gbp": 2_000_000_000, "ev_rev_multiple": 1.5, "detail": "Green energy retailer"},
        {"target": "Zenobe Energy", "acquirer": "APG and CDPQ", "year": 2022, "deal_size_gbp": 600_000_000, "revenue_gbp": 40_000_000, "ev_rev_multiple": 15.0, "detail": "Grid-scale battery storage"},
        {"target": "Connexin", "acquirer": "Basalt Infrastructure", "year": 2023, "deal_size_gbp": 250_000_000, "revenue_gbp": 30_000_000, "ev_rev_multiple": 8.3, "detail": "Smart city connectivity"},
        {"target": "Pod Point", "acquirer": "EDF Energy", "year": 2021, "deal_size_gbp": 130_000_000, "revenue_gbp": 20_000_000, "ev_rev_multiple": 6.5, "detail": "EV charging network"},
        {"target": "Habitat Energy", "acquirer": "Sonnedix", "year": 2023, "deal_size_gbp": 90_000_000, "revenue_gbp": 12_000_000, "ev_rev_multiple": 7.5, "detail": "Battery optimisation software"},
    ],
    "Cybersecurity": [
        {"target": "Darktrace", "acquirer": "Thoma Bravo", "year": 2024, "deal_size_gbp": 4_300_000_000, "revenue_gbp": 430_000_000, "ev_rev_multiple": 10.0, "detail": "AI cybersecurity platform"},
        {"target": "Digital Shadows", "acquirer": "ReliaQuest", "year": 2022, "deal_size_gbp": 150_000_000, "revenue_gbp": 20_000_000, "ev_rev_multiple": 7.5, "detail": "Digital risk protection"},
        {"target": "Panaseer", "acquirer": "Xona Partners", "year": 2023, "deal_size_gbp": 40_000_000, "revenue_gbp": 6_000_000, "ev_rev_multiple": 6.7, "detail": "Security metrics platform"},
        {"target": "Immersive Labs", "acquirer": "KKR", "year": 2022, "deal_size_gbp": 500_000_000, "revenue_gbp": 40_000_000, "ev_rev_multiple": 12.5, "detail": "Cyber skills platform"},
        {"target": "Osirium", "acquirer": "Shearwater Group", "year": 2023, "deal_size_gbp": 8_000_000, "revenue_gbp": 3_000_000, "ev_rev_multiple": 2.7, "detail": "Privileged access management"},
    ],
    "E-Commerce": [
        {"target": "Depop", "acquirer": "Etsy", "year": 2021, "deal_size_gbp": 1_600_000_000, "revenue_gbp": 50_000_000, "ev_rev_multiple": 32.0, "detail": "Peer-to-peer fashion resale"},
        {"target": "Gymshark (minority)", "acquirer": "General Atlantic", "year": 2021, "deal_size_gbp": 258_000_000, "revenue_gbp": 260_000_000, "ev_rev_multiple": 4.0, "detail": "DTC fitness apparel"},
        {"target": "Butternut Box (minority)", "acquirer": "Nestle", "year": 2023, "deal_size_gbp": 280_000_000, "revenue_gbp": 100_000_000, "ev_rev_multiple": 2.8, "detail": "Fresh pet food subscription"},
        {"target": "Huel (minority)", "acquirer": "TESI", "year": 2023, "deal_size_gbp": 100_000_000, "revenue_gbp": 200_000_000, "ev_rev_multiple": 2.5, "detail": "Nutritionally complete food brand"},
        {"target": "Bloom & Wild", "acquirer": "Verdane", "year": 2022, "deal_size_gbp": 75_000_000, "revenue_gbp": 150_000_000, "ev_rev_multiple": 0.5, "detail": "Online flower delivery"},
    ],
    "Other": [
        {"target": "Wayve", "acquirer": "SoftBank led", "year": 2024, "deal_size_gbp": 850_000_000, "revenue_gbp": 20_000_000, "ev_rev_multiple": 42.5, "detail": "AI for autonomous vehicles"},
        {"target": "Darktrace", "acquirer": "Thoma Bravo", "year": 2024, "deal_size_gbp": 4_300_000_000, "revenue_gbp": 430_000_000, "ev_rev_multiple": 10.0, "detail": "Cybersecurity AI"},
        {"target": "Depop", "acquirer": "Etsy", "year": 2021, "deal_size_gbp": 1_600_000_000, "revenue_gbp": 50_000_000, "ev_rev_multiple": 32.0, "detail": "Consumer marketplace"},
        {"target": "Busuu", "acquirer": "McGraw Hill", "year": 2022, "deal_size_gbp": 360_000_000, "revenue_gbp": 36_000_000, "ev_rev_multiple": 10.0, "detail": "EdTech platform"},
        {"target": "Currencycloud", "acquirer": "Visa", "year": 2021, "deal_size_gbp": 700_000_000, "revenue_gbp": 60_000_000, "ev_rev_multiple": 11.7, "detail": "FinTech infrastructure"},
    ],
}

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Runrate — Deal intelligence",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "page":         "landing",
    "active_tab":   "Valuation",
    "inp_company":  "FinTechX",
    "inp_sector":   "FinTech",
    "inp_stage":    "Series A",
    "inp_geo":      "UK",
    "inp_revenue":  4_000_000,
    "inp_growth":   80,
    "inp_ebitda":   15,
    "inp_cash":     1_500_000,
    "inp_burn":     200_000,
    "inp_debt":     0,
    "inp_cod":      8,
    "inp_openai":   "",
    # DCF assumption overrides
    "inp_tax_rate":      25,
    "inp_capex_pct":     5,
    "inp_nwc_pct":       3,
    "inp_da_pct":        3.0,
    "inp_target_margin": 25,
    "inp_terminal_g":    3.0,
    "inp_tv_method":     "Gordon Growth Model",
    "inp_exit_multiple": 12.0,
    # WACC
    "inp_use_custom_wacc": False,
    "inp_custom_wacc":     28.0,
    "inp_rfr":             4.2,
    "inp_erp":             5.5,
    "inp_beta":            None,
    "inp_wacc_kd":         8.0,
    "inp_wacc_debt":       0,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&display=swap');

  /* ── Streamlit chrome removal ── */
  #MainMenu, footer, header { visibility: hidden; }
  [data-testid="stSidebar"]        { display: none !important; }
  [data-testid="collapsedControl"] { display: none !important; }

  /* ── Layout & background ── */
  html, body,
  [data-testid="stAppViewContainer"],
  [data-testid="stApp"], .main {
    background-color: #F8FAFC !important;
  }
  .main .block-container {
    padding-top: 0 !important;
    padding-left: 1.5rem !important;
    padding-right: 1.5rem !important;
    max-width: 100% !important;
  }

  /* ── Typography ── */
  *, *::before, *::after {
    font-family: 'Inter', 'SF Pro Display', -apple-system, system-ui, sans-serif !important;
    -webkit-font-smoothing: antialiased;
  }
  h1, h2, h3, h4 { font-weight: 500 !important; color: #0F172A !important; }
  p { font-size: 14px; color: #0F172A; margin: 0; }
  label { color: #64748B !important; font-size: 12px !important; font-weight: 400 !important; }

  /* ── Inputs ── */
  .stTextInput > div > div > input,
  .stNumberInput > div > div > input {
    background: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    color: #0F172A !important;
    font-size: 13px !important;
  }
  .stTextInput > div > div > input:focus,
  .stNumberInput > div > div > input:focus {
    border-color: #1D4ED8 !important;
    box-shadow: 0 0 0 3px rgba(29,78,216,0.1) !important;
  }
  .stSelectbox [data-baseweb="select"] > div {
    background: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
    color: #0F172A !important;
    font-size: 13px !important;
  }
  .stTextInput [type="password"] {
    background: #F1F5F9 !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 6px !important;
  }

  /* ── Buttons — default primary ── */
  .stButton > button {
    background: #1D4ED8 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 10px 32px !important;
    letter-spacing: 0.01em !important;
    transition: background 0.15s !important;
  }
  .stButton > button:hover { background: #1E40AF !important; }

  /* ── Nav active button (wrapper trick) ── */
  .element-container:has(.nav-active) + .element-container .stButton > button {
    background: #1D4ED8 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    text-align: left !important;
    padding: 9px 14px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    width: 100% !important;
    display: flex !important;
    justify-content: flex-start !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }

  /* ── Nav inactive button (wrapper trick) ── */
  .element-container:has(.nav-inactive) + .element-container .stButton > button {
    background: transparent !important;
    color: #64748B !important;
    border: none !important;
    border-radius: 6px !important;
    text-align: left !important;
    padding: 9px 14px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    width: 100% !important;
    display: flex !important;
    justify-content: flex-start !important;
    white-space: nowrap !important;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
  }
  .element-container:has(.nav-inactive) + .element-container .stButton > button:hover {
    background: #F1F5F9 !important;
    color: #0F172A !important;
  }

  /* ── Top nav button (app title link) ── */
  .element-container:has(.topnav-link) + .element-container .stButton > button {
    background: transparent !important;
    color: #1D4ED8 !important;
    border: none !important;
    padding: 0 4px !important;
    font-size: 16px !important;
    font-weight: 500 !important;
    box-shadow: none !important;
    height: auto !important;
    min-height: unset !important;
    line-height: 1 !important;
    text-decoration: underline !important;
    text-underline-offset: 2px !important;
  }
  .element-container:has(.topnav-link) + .element-container .stButton > button:hover {
    background: transparent !important;
    color: #1E40AF !important;
  }

  /* ── Demo-company buttons ── */
  .element-container:has(.demo-btn) + .element-container .stButton > button {
    background: #FFFFFF !important;
    color: #1D4ED8 !important;
    border: 1px solid #BFDBFE !important;
    border-radius: 6px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    padding: 7px 16px !important;
  }
  .element-container:has(.demo-btn) + .element-container .stButton > button:hover {
    background: #EFF6FF !important;
  }

  /* ── Disclaimer ! button ── */
  button[kind="secondary"]#disclaimer_btn,
  .element-container:has(button[data-testid="baseButton-secondary"]) button[data-testid="baseButton-secondary"] {
    background: #1D4ED8 !important;
    color: #ffffff !important;
    border-radius: 50% !important;
    width: 28px !important;
    height: 28px !important;
    min-height: unset !important;
    padding: 0 !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    border: none !important;
    box-shadow: none !important;
  }

  /* ── Back button ── */
  .element-container:has(.back-link) + .element-container .stButton > button {
    background: transparent !important;
    color: #64748B !important;
    border: none !important;
    padding: 0 4px !important;
    font-size: 13px !important;
    font-weight: 400 !important;
    box-shadow: none !important;
    height: auto !important;
    min-height: unset !important;
  }
  .element-container:has(.back-link) + .element-container .stButton > button:hover {
    color: #0F172A !important;
    background: transparent !important;
  }

  /* ── Cards (bordered container) ── */
  [data-testid="stVerticalBlockBorderWrapper"] > div:first-child {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
  }

  /* ── Metric cards ── */
  [data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 8px !important;
    padding: 16px !important;
  }
  [data-testid="stMetricValue"]  { color: #0F172A !important; font-size: 26px !important; font-weight: 500 !important; }
  [data-testid="stMetricLabel"]  { color: #94A3B8 !important; font-size: 11px !important; text-transform: uppercase !important; letter-spacing: 0.06em !important; }

  /* ── DataFrames ── */
  [data-testid="stDataFrame"] { border: 1px solid #E2E8F0 !important; border-radius: 8px !important; }

  /* ── Dividers ── */
  hr { border-color: #E2E8F0 !important; margin: 1rem 0 !important; }

  /* Sidebar nav fixes */
  [data-testid="column"]:first-child {
      min-width: 200px !important;
      padding-left: 0 !important;
      overflow: visible !important;
  }

  /* Prevent sidebar buttons clipping */
  div[data-testid="stVerticalBlock"] button {
      white-space: nowrap !important;
      overflow: hidden !important;
      text-overflow: ellipsis !important;
      width: 100% !important;
      text-align: left !important;
      padding-left: 12px !important;
      padding-right: 12px !important;
  }

  /* Typography system */
  h1, .page-title { font-size: 28px !important; font-weight: 500 !important; color: #0F172A !important; letter-spacing: -0.01em !important; margin-bottom: 4px !important; }
  h2, h3, .section-header { font-size: 20px !important; font-weight: 500 !important; color: #0F172A !important; margin-bottom: 4px !important; }
  .overline { font-size: 11px !important; font-weight: 400 !important; letter-spacing: 0.1em !important; text-transform: uppercase !important; color: #64748B !important; }
  p, li, span, div { font-size: 14px !important; color: #1F2937 !important; line-height: 1.6 !important; }
  .metric-value { font-size: 26px !important; font-weight: 500 !important; color: #0F172A !important; }
  .caption, small { font-size: 12px !important; color: #64748B !important; }
  .sidebar-nav-item { font-size: 14px !important; font-weight: 400 !important; color: #64748B !important; }
  .sidebar-nav-item-active { font-size: 14px !important; font-weight: 500 !important; color: #FFFFFF !important; }

  /* ── Dark sidebar shell ── */
  [data-testid="column"]:first-child > div:first-child {
    background: #0A0F1E !important;
    border-radius: 12px !important;
    padding: 16px 10px !important;
    min-height: 600px !important;
  }
  [data-testid="column"]:first-child button {
    background: transparent !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 7px 10px !important;
    width: 100% !important;
    text-align: left !important;
    cursor: pointer !important;
    font-size: 13px !important;
    color: #8892AA !important;
    font-weight: 400 !important;
  }
  [data-testid="column"]:first-child button:hover {
    background: rgba(255,255,255,0.06) !important;
    color: #C4CAD8 !important;
  }
  [data-testid="column"]:first-child button[kind="primary"] {
    background: #00D4AA !important;
    color: #0A0F1E !important;
    font-weight: 500 !important;
  }
  [data-testid="column"]:first-child button[kind="primary"]:hover {
    background: #00BF99 !important;
  }
  .sidebar-section-label {
    font-size: 10px; letter-spacing: 0.12em; text-transform: uppercase;
    color: #4A5568; padding: 0 8px; margin: 12px 0 6px; display: block;
  }
  .sidebar-logo {
    display: flex; align-items: center; gap: 8px;
    padding: 0 8px; margin-bottom: 18px;
  }

</style>
""", unsafe_allow_html=True)

# ── Design tokens ─────────────────────────────────────────────────────────────
BLUE      = "#1D4ED8"
BLUE_MID  = "#3B82F6"
GREEN     = "#10B981"
AMBER     = "#F59E0B"
PURPLE    = "#8B5CF6"
RED       = "#EF4444"

PLOTLY_BASE = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    font=dict(color="#0F172A", family="Inter, system-ui, sans-serif"),
    legend=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0"),
    margin=dict(l=0, r=0, t=30, b=0),
)
AXIS_CLEAN = dict(showgrid=False, zeroline=False, linecolor="#E2E8F0",
                  tickcolor="#94A3B8", color="#64748B")


# ── Helpers ───────────────────────────────────────────────────────────────────
def fmt_gbp(val: float) -> str:
    return f"£{val / 1_000_000:.1f}m"


def overline(text: str) -> None:
    st.markdown(
        f"<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        f"color:#64748B;margin:0 0 8px;'>{text}</p>",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    html = (f"<h2 style='font-size:22px;font-weight:500;color:#0F172A;"
            f"margin:0 0 4px;'>{title}</h2>")
    if subtitle:
        html += (f"<p style='font-size:13px;color:#64748B;"
                 f"margin:0 0 20px;'>{subtitle}</p>")
    st.markdown(html, unsafe_allow_html=True)


def callout(text: str, kind: str = "info") -> None:
    bc = {"info": BLUE, "warning": AMBER, "danger": RED, "success": GREEN}.get(kind, BLUE)
    st.markdown(
        f"<div style='background:#F8FAFC;border-left:3px solid {bc};"
        f"border-radius:0 8px 8px 0;padding:12px 16px;margin:8px 0;'>"
        f"<p style='font-size:13px;color:#0F172A;margin:0;line-height:1.6;'>{text}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def card_html(label: str, value: str, sub: str = "",
              border: str = "1px solid #E2E8F0",
              val_color: str = "#0F172A") -> str:
    return (
        f"<div style='background:#FFFFFF;border:{border};border-radius:8px;"
        f"padding:16px;'>"
        f"<p style='font-size:10px;letter-spacing:0.08em;text-transform:uppercase;"
        f"color:#94A3B8;margin:0 0 6px;'>{label}</p>"
        f"<p style='font-size:26px;font-weight:500;color:{val_color};"
        f"margin:0;'>{value}</p>"
        + (f"<p style='font-size:11px;color:#94A3B8;margin:4px 0 0;'>{sub}</p>" if sub else "")
        + "</div>"
    )


def _get_use_of_funds_summary(sector):
    _summaries = {
        "FinTech": "accelerate product development and expand our compliance infrastructure",
        "SaaS": "scale our go-to-market and grow our engineering team",
        "HealthTech": "fund our next clinical validation phase and expand into new NHS trusts",
        "MarketPlace": "deepen supply-side liquidity and invest in demand generation",
        "DeepTech": "advance our core R&D and move from prototype to commercial deployment",
        "E-Commerce": "scale marketing and expand into new geographies",
        "EdTech": "grow our content library and expand our school partnerships",
        "CleanTech": "fund our next deployment cohort and build out our data platform",
        "Cybersecurity": "obtain certifications and scale our enterprise sales motion",
        "Other": "accelerate growth and expand the team",
    }
    return _summaries.get(sector, _summaries["Other"])


def _get_vc_rationale(match):
    if match.sector_score >= 30:
        _sector_line = "you are a sector specialist with deep domain knowledge"
    elif match.sector_score >= 18:
        _sector_line = "you have relevant sector experience"
    else:
        _sector_line = "your portfolio companies have adjacent expertise"
    if match.notable_portfolio:
        _cos = [p.strip() for p in str(match.notable_portfolio).split(",")[:2]]
        _sector_line += " and your work with " + " and ".join(_cos) + " demonstrates the value-add we are looking for"
    return _sector_line


def _generate_cold_email(match, company_name, sector, stage, revenue_gbp, growth_pct,
                          ebitda_margin, geography, blended_ev, raise_mid):
    _format_rev   = fmt_gbp(revenue_gbp)
    _format_ev    = fmt_gbp(blended_ev)
    _format_raise = fmt_gbp(raise_mid)
    subject = ("Intro: " + str(company_name) + " — " + _format_rev + " ARR, "
               + str(int(growth_pct)) + "% growth, raising " + _format_raise)
    body = (
        "Hi [Partner name],\n\n"
        "I'm reaching out because " + str(match.name) + "'s focus on " + str(sector)
        + " at " + str(stage) + " stage aligns closely with what we're building at " + str(company_name) + ".\n\n"
        + str(company_name) + " is a " + str(geography) + "-based " + str(sector)
        + " company generating " + _format_rev + " ARR, growing at " + str(int(growth_pct)) + "% year-on-year"
        + (" with " + str(int(ebitda_margin)) + "% EBITDA margins" if ebitda_margin > 0 else ", currently pre-profitability and investing in growth")
        + ". We are raising " + _format_raise + " at a pre-money valuation of " + _format_ev
        + " to " + _get_use_of_funds_summary(sector) + ".\n\n"
        "We believe " + str(match.name) + " is the right partner because " + _get_vc_rationale(match) + ".\n\n"
        "Would you have 20 minutes for a call in the next two weeks? Happy to share our deck in advance.\n\n"
        "Best regards,\n"
        "[Your name]\n"
        "[Your title], " + str(company_name) + "\n"
        "[Your email] | [Your phone]"
    )
    return subject, body


def _nav_btn(label: str, is_active: bool, key: str) -> bool:
    cls = "nav-active" if is_active else "nav-inactive"
    st.markdown(f'<div class="{cls}" style="display:none;"></div>', unsafe_allow_html=True)
    return st.button(label, key=key, use_container_width=True)


# ── Preset callbacks ──────────────────────────────────────────────────────────
def _load_preset(name: str) -> None:
    presets = {
        "Wise": dict(
            inp_company="Wise plc", sector_select="Payments & Transaction Processing",
            inp_stage="Growth", inp_geo="Global",
            inp_revenue=1_869_000_000, inp_growth=21, inp_ebitda=29,
            inp_cash=1_430_000_000, inp_burn=0,
            inp_tax=25, inp_capex=4, inp_target_margin=32, inp_terminal_growth=3.0,
            inp_ev_rev_multiple=3.4, inp_rfr=4.2, inp_erp=5.5,
            inp_wacc_debt=230_000_000,
        ),
        "Revolut": dict(
            inp_company="Revolut", sector_select="FinTech",
            inp_stage="Growth", inp_geo="Global",
            inp_revenue=3_100_000_000, inp_growth=72, inp_ebitda=36,
            inp_cash=2_100_000_000, inp_burn=0,
            inp_tax=25, inp_capex=3, inp_target_margin=40, inp_terminal_growth=4.0,
            inp_ev_rev_multiple=11.25, inp_rfr=4.2, inp_erp=5.5,
            inp_wacc_debt=500_000_000,
        ),
        "Darktrace": dict(
            inp_company="Darktrace", sector_select="Cybersecurity",
            inp_stage="Growth", inp_geo="Global",
            inp_revenue=552_000_000, inp_growth=26, inp_ebitda=22,
            inp_cash=280_000_000, inp_burn=0,
            inp_tax=25, inp_capex=4, inp_target_margin=28, inp_terminal_growth=3.5,
            inp_ev_rev_multiple=6.2, inp_rfr=4.2, inp_erp=5.5,
            inp_wacc_debt=0,
        ),
    }
    for k, v in presets[name].items():
        st.session_state[k] = v
    st.session_state["inp_stage"] = "Growth"
    # Keep inp_sector in sync with sector_select
    st.session_state["inp_sector"] = st.session_state.get("sector_select", "FinTech")


# ══════════════════════════════════════════════════════════════════════════════
# LANDING PAGE
# ══════════════════════════════════════════════════════════════════════════════
def render_landing() -> None:
    st.markdown("""
<style>
.landing-hero { text-align: center; padding: 80px 20px 40px; }
.landing-logo { display: inline-flex; align-items: center; gap: 12px; margin-bottom: 40px; }
.landing-h1 { font-size: 56px; font-weight: 600; color: #0A0F1E; letter-spacing: -0.03em; line-height: 1.05; margin: 0 0 20px; }
.landing-h1 .accent { color: #00D4AA; }
.landing-sub { font-size: 20px; color: #475569; max-width: 620px; margin: 0 auto 16px; line-height: 1.5; }
.landing-microcopy { font-size: 14px; color: #94A3B8; margin-bottom: 36px; }
.feature-card { background: #FFFFFF; border: 0.5px solid #E2E8F0; border-radius: 14px; padding: 28px 24px; height: 100%; }
.feature-icon { width: 44px; height: 44px; background: #E0FFF7; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 22px; margin-bottom: 16px; }
.feature-title { font-size: 17px; font-weight: 600; color: #0A0F1E; margin: 0 0 8px; }
.feature-desc { font-size: 14px; color: #64748B; line-height: 1.6; margin: 0; }
.stat-num { font-size: 40px; font-weight: 600; color: #00D4AA; margin: 0; letter-spacing: -0.02em; }
.stat-label { font-size: 13px; color: #64748B; margin: 4px 0 0; }
.how-step { display: flex; gap: 16px; align-items: flex-start; margin-bottom: 20px; }
.how-num { width: 32px; height: 32px; background: #0A0F1E; color: #00D4AA; border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 600; font-size: 15px; flex-shrink: 0; }
</style>
""", unsafe_allow_html=True)

    _l, _m, _r = st.columns([1, 6, 1])
    with _m:
        # ── Section A: Hero ───────────────────────────────────────────────────
        st.markdown("""
<div class='landing-hero'>
  <div class='landing-logo'>
    <div style='width:40px;height:40px;background:#00D4AA;border-radius:10px;
      display:inline-flex;align-items:center;justify-content:center;'>
      <svg width='22' height='22' viewBox='0 0 22 22' fill='none'>
        <polyline points='3,16 8,10 12,13 19,5' stroke='#0A0F1E' stroke-width='2.2'
          stroke-linecap='round' stroke-linejoin='round'/>
        <polyline points='15,5 19,5 19,9' stroke='#0A0F1E' stroke-width='2.2'
          stroke-linecap='round' stroke-linejoin='round'/>
      </svg>
    </div>
    <span style='font-size:22px;font-weight:600;color:#0A0F1E;'>Runrate</span>
  </div>
  <h1 class='landing-h1'>Institutional deal analysis.<br><span class='accent'>In 30 seconds.</span></h1>
  <p class='landing-sub'>Runrate turns seven numbers into a full valuation, investor shortlist, and outreach plan — the analysis a junior banker would take a week to produce.</p>
  <p class='landing-microcopy'>Built for founders and CFOs raising their next round.</p>
</div>
""", unsafe_allow_html=True)

        _cl, _cc, _cr = st.columns([1, 1, 1])
        with _cc:
            if st.button("Start your analysis", use_container_width=True, type="primary", key="landing_cta_top"):
                st.session_state.page = "home"
                st.rerun()

        st.markdown("<div style='text-align:center;margin-top:8px;'>", unsafe_allow_html=True)
        st.caption("No sign-up. No API key. Free.")
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

        # ── Section B: Trust stats ────────────────────────────────────────────
        _s1, _s2, _s3 = st.columns(3)
        with _s1:
            st.markdown("<div style='text-align:center;'><p class='stat-num'>30s</p><p class='stat-label'>From inputs to full analysis</p></div>", unsafe_allow_html=True)
        with _s2:
            st.markdown("<div style='text-align:center;'><p class='stat-num'>29</p><p class='stat-label'>Sectors with calibrated benchmarks</p></div>", unsafe_allow_html=True)
        with _s3:
            st.markdown("<div style='text-align:center;'><p class='stat-num'>70+</p><p class='stat-label'>VCs scored on specialist fit</p></div>", unsafe_allow_html=True)

        st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

        # ── Section C: Feature grid ───────────────────────────────────────────
        st.markdown("### What Runrate delivers")
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        _features = [
            ("📊", "Valuation", "Blended DCF and comparables across three scenarios, with a full value bridge and sensitivity table."),
            ("💰", "Fundraising", "Runway, recommended raise, dilution timeline, and sector-specific use of funds."),
            ("🎯", "VC matching", "Your top investor matches scored on sector, stage, geography, and cheque fit — with warm intro paths."),
            ("🔍", "Comparable transactions", "Recent M&A deals in your sector and where your valuation sits against them."),
            ("✉️", "Investor outreach", "Cold email templates pre-filled with your actual metrics, ready to send."),
        ]

        _row1 = st.columns(3)
        _row2 = st.columns(2)
        for _i, (icon, title, desc) in enumerate(_features):
            _col = _row1[_i] if _i < 3 else _row2[_i - 3]
            with _col:
                st.markdown(f"""
<div class='feature-card'>
  <div class='feature-icon'>{icon}</div>
  <p class='feature-title'>{title}</p>
  <p class='feature-desc'>{desc}</p>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

        # ── Section D: How it works ───────────────────────────────────────────
        st.markdown("### How it works")
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        _steps = [
            ("1", "Enter your company", "Revenue, growth, margin, sector, stage. Or load a demo company."),
            ("2", "Runrate runs the analysis", "DCF, comparables, VC scoring, and outreach — all computed in seconds."),
            ("3", "Act on the output", "Download your valuation, shortlist investors, and send tailored outreach."),
        ]
        for _num, _title, _desc in _steps:
            st.markdown(f"""
<div class='how-step'>
  <div class='how-num'>{_num}</div>
  <div>
    <p style='font-size:15px;font-weight:600;color:#0A0F1E;margin:0 0 4px;'>{_title}</p>
    <p style='font-size:14px;color:#64748B;margin:0;'>{_desc}</p>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)

        # ── Section E: Methodology ────────────────────────────────────────────
        st.markdown("""
<div style='background:#F0FDF9;border-radius:12px;padding:20px 24px;'>
  <p style='font-size:14px;color:#0F766E;margin:0;line-height:1.6;'>
    Built on Damodaran sector benchmarks, standard DCF methodology, and real market transaction data.
    Every number is explainable — no black box.
  </p>
</div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:48px;'></div>", unsafe_allow_html=True)

        # ── Section F: Final CTA ──────────────────────────────────────────────
        _fl, _fc, _fr = st.columns([1, 1, 1])
        with _fc:
            if st.button("Start your analysis", use_container_width=True, type="primary", key="landing_cta_bottom"):
                st.session_state.page = "home"
                st.rerun()

        st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
        st.caption("Runrate · Deal intelligence · Built for the Arete Finance Hackathon 2026")

        st.markdown("<div style='height:60px;'></div>", unsafe_allow_html=True)


# ── Top nav bar ───────────────────────────────────────────────────────────────
def render_topnav(company: str = "") -> None:
    breadcrumb = (
        f"<span style='color:#94A3B8;margin:0 6px;'>/</span>"
        f"<span style='font-size:14px;color:#64748B;'>{company} analysis</span>"
    ) if company else ""

    st.markdown(
        f"<div style='background:#FFFFFF;border-bottom:1px solid #E2E8F0;"
        f"padding:14px 0;margin-bottom:20px;display:flex;"
        f"align-items:center;justify-content:space-between;'>"
        f"<div style='display:flex;align-items:center;gap:0;'>"
        f"<div style='width:28px;height:28px;background:#00D4AA;border-radius:6px;"
        f"display:inline-flex;align-items:center;justify-content:center;"
        f"color:#0A0F1E;font-size:13px;font-weight:700;margin-right:10px;'>R</div>"
        f"<span id='nav-app-name' style='font-size:16px;font-weight:600;"
        f"color:#0A0F1E;cursor:pointer;'>&nbsp;</span>"
        f"{breadcrumb}"
        f"</div>"
        f"</div>",
        unsafe_allow_html=True,
    )
    # Functional navigation button — styled via CSS to blend with nav bar
    st.markdown('<div class="topnav-link" style="display:none;"></div>',
                unsafe_allow_html=True)
    if st.button("Runrate", key="topnav_home_btn"):
        st.session_state.page = "landing"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ══════════════════════════════════════════════════════════════════════════════
def _on_sector_change():
    new_sector = st.session_state["sector_select"]
    d = SECTOR_DEFAULTS.get(new_sector, SECTOR_DEFAULTS["Other"])
    st.session_state["inp_revenue"]         = d["revenue"]
    st.session_state["inp_growth"]          = d["growth"]
    st.session_state["inp_ebitda"]          = d["ebitda"]
    st.session_state["inp_tax"]             = d["tax"]
    st.session_state["inp_capex"]           = d["capex"]
    st.session_state["inp_target_margin"]   = d["target_margin"]
    st.session_state["inp_terminal_growth"] = d["terminal_growth"]
    st.session_state["inp_rfr"]             = d["rfr"]
    st.session_state["inp_erp"]             = d["erp"]
    from modules.valuation import SECTOR_MULTIPLES
    st.session_state["inp_ev_rev_multiple"] = float(
        SECTOR_MULTIPLES.get(new_sector, SECTOR_MULTIPLES["Other"])["base"]
    )


def render_home() -> None:
    render_topnav()

    # ── Initialise session state defaults on first load ──
    if "sector_select" not in st.session_state:
        st.session_state["sector_select"] = "FinTech"
    if "inp_revenue" not in st.session_state:
        _d0 = SECTOR_DEFAULTS.get(st.session_state["sector_select"], SECTOR_DEFAULTS["Other"])
        st.session_state["inp_revenue"]         = _d0["revenue"]
        st.session_state["inp_growth"]          = _d0["growth"]
        st.session_state["inp_ebitda"]          = _d0["ebitda"]
        st.session_state["inp_tax"]             = _d0["tax"]
        st.session_state["inp_capex"]           = _d0["capex"]
        st.session_state["inp_target_margin"]   = _d0["target_margin"]
        st.session_state["inp_terminal_growth"] = _d0["terminal_growth"]
        st.session_state["inp_rfr"]             = _d0["rfr"]
        st.session_state["inp_erp"]             = _d0["erp"]
        from modules.valuation import SECTOR_MULTIPLES as _SM0
        st.session_state["inp_ev_rev_multiple"] = float(
            _SM0.get(st.session_state["sector_select"], _SM0["Other"])["base"]
        )

    # ── Demo quick-load ──
    st.markdown(
        "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        "color:#94A3B8;margin:0 0 8px;text-align:center;'>Quick-load demo</p>",
        unsafe_allow_html=True,
    )
    _qd1, _qd2, _qd3, _qd4, _qd5 = st.columns([3, 1, 1, 1, 3])
    for col, name in [(_qd2, "Wise"), (_qd3, "Revolut"), (_qd4, "Darktrace")]:
        with col:
            st.markdown('<div class="demo-btn" style="display:none;"></div>',
                        unsafe_allow_html=True)
            if st.button(name, key=f"demo_{name}", use_container_width=True):
                _load_preset(name)
                st.rerun()

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Page heading ──
    st.markdown(
        "<h1 style='font-size:28px;font-weight:500;color:#0F172A;margin:0 0 16px;'>"
        "Enter company details</h1>",
        unsafe_allow_html=True,
    )

    # ── Three input cards ──
    card1, card2, card3 = st.columns(3)

    with card1:
        with st.container(border=True):
            overline("Company profile")
            company_name = st.text_input("Name", key="inp_company")
            sector = st.selectbox(
                "Sector",
                options=list(SECTOR_DEFAULTS.keys()),
                key="sector_select",
                on_change=_on_sector_change,
            )
            # Keep inp_sector in sync so the rest of the app can read it
            st.session_state["inp_sector"] = sector
            stage = st.selectbox("Stage",
                ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Growth"],
                key="inp_stage",
            )
            _cur_sd = SECTOR_DEFAULTS.get(st.session_state.get("sector_select", "FinTech"), SECTOR_DEFAULTS["Other"])
            st.caption(_cur_sd["typical_arr"] + " · " + _cur_sd["burn_note"])

    with card2:
        with st.container(border=True):
            overline("Financials")
            revenue = st.number_input(
                "Annual revenue (£)", min_value=0, step=100_000, format="%d", key="inp_revenue")
            growth_pct = st.number_input(
                "Revenue growth (%)", min_value=-100, max_value=500, step=1, key="inp_growth")
            ebitda_margin = st.number_input(
                "EBITDA margin (%)", min_value=-200, max_value=100, step=1, key="inp_ebitda")

    with card3:
        with st.container(border=True):
            _col_lbl, _col_icon = st.columns([8, 1])
            with _col_lbl:
                st.markdown(
                    "<p style='font-size:11px;letter-spacing:0.1em;text-transform:uppercase;"
                    "color:#64748B;margin:0 0 8px;'>Capital position</p>",
                    unsafe_allow_html=True,
                )
            with _col_icon:
                st.button(
                    "!",
                    key="disclaimer_btn",
                )
            geography = st.selectbox("Geography",
                ["UK", "Europe", "US", "Asia", "Global", "MENA", "LatAm"],
                key="inp_geo",
            )
            cash = st.number_input("Cash on hand (£)", min_value=0,
                                   key="inp_cash", step=100_000, format="%d")
            burn = st.number_input("Monthly burn (£)", min_value=0,
                                   key="inp_burn", step=10_000, format="%d")

    # ── Section 4: DCF assumptions ──
    st.markdown("---")
    st.markdown("**DCF assumptions**")
    _d1, _d2 = st.columns(2)
    with _d1:
        st.number_input("Tax rate (%)", min_value=0, max_value=50, step=1, key="inp_tax")
        st.number_input("CapEx (% of EBITDA)", min_value=0, max_value=50, step=1, key="inp_capex")
    with _d2:
        st.number_input("Target EBITDA margin Year 5 (%)", min_value=-50, max_value=80, step=1,
                        key="inp_target_margin")
        st.number_input("Terminal growth rate (%)", min_value=0.0, max_value=8.0, step=0.5,
                        key="inp_terminal_growth")
        _projection_years = st.selectbox(
            "Projection horizon (years)",
            options=[3, 5, 7],
            index=1,
            key="inp_projection_years",
        )
        _tv_method = st.radio(
            "Terminal value method",
            options=["Gordon Growth Model", "Exit Multiple (EV/EBITDA)"],
            key="inp_tv_method",
        )
        if _tv_method == "Exit Multiple (EV/EBITDA)":
            st.number_input("Exit EV/EBITDA multiple", min_value=1.0, max_value=40.0,
                            value=12.0, key="inp_exit_multiple", step=0.5)

    # ── Section 4b: Comparable company assumptions ──
    st.markdown("---")
    st.markdown("**Comparable company assumptions**")
    from modules.valuation import SECTOR_MULTIPLES as _SM_UI
    _ev_sector = st.session_state.get("sector_select", "FinTech")
    _ev_sector_default = float(_SM_UI.get(_ev_sector, _SM_UI["Other"])["base"])
    if "inp_ev_rev_multiple" not in st.session_state:
        st.session_state["inp_ev_rev_multiple"] = _ev_sector_default
    st.markdown("**EV/Revenue multiple (comparable companies)**")
    _ev_rev_val = st.number_input(
        "Base EV/Revenue multiple",
        min_value=0.1, max_value=50.0, step=0.5,
        key="inp_ev_rev_multiple",
    )
    if abs(_ev_rev_val - _ev_sector_default) > 0.01:
        st.markdown(
            "<span style='font-size:11px; color:#92400E; background:#FEF3C7; padding:3px 8px; "
            "border-radius:4px;'>Override active: " + str(_ev_rev_val) + "x vs sector default of "
            + str(_ev_sector_default) + "x</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            "<span style='font-size:11px; color:#64748B; background:#F1F5F9; padding:3px 8px; "
            "border-radius:4px;'>Using " + _ev_sector + " sector default ("
            + str(_ev_sector_default) + "x)</span>",
            unsafe_allow_html=True,
        )

    # ── Section 5: WACC ──
    st.markdown("---")
    st.markdown("**WACC inputs**")
    _use_custom = st.toggle("Enter WACC directly instead of using formula",
                            key="inp_use_custom_wacc")
    if _use_custom:
        st.number_input("WACC (%)", min_value=1.0, max_value=80.0,
                        value=28.0, key="inp_custom_wacc", step=0.5)
        st.caption("Overrides all formula inputs below")
    else:
        _w1, _w2 = st.columns(2)
        with _w1:
            st.number_input("Risk-free rate (%)", min_value=0.0, max_value=15.0, step=0.1,
                            key="inp_rfr")
            st.number_input("Equity risk premium (%)", min_value=0.0, max_value=15.0, step=0.1,
                            key="inp_erp")
            _beta_source = st.selectbox(
                "Beta source",
                options=["Use sector average (recommended)", "Leave blank (use stage-based rate)"],
                key="inp_beta_source",
            )
            _current_sector = st.session_state.get("sector_select", "Other")
            if _beta_source == "Use sector average (recommended)":
                _beta_val_display = SECTOR_BETAS.get(_current_sector, 1.20)
            else:
                pass
        with _w2:
            st.number_input("Cost of debt (%)", min_value=0.0, max_value=25.0,
                            value=8.0, key="inp_wacc_kd", step=0.5)
            st.number_input("Total debt (£)", min_value=0,
                            value=0, key="inp_wacc_debt", step=50_000, format="%d")

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Run analysis button (centered) ──
    _r1, _r2, _r3 = st.columns([3, 2, 3])
    with _r2:
        if st.button("Run analysis", key="run_analysis_btn", use_container_width=True):
            with st.spinner("Running valuation models..."):
                import time; time.sleep(0.6)
            st.session_state.page = "results"
            st.session_state.active_tab = "Valuation"
            st.rerun()

    st.markdown(
        "<p style='font-size:12px;color:#94A3B8;text-align:center;"
        "margin-top:8px;'>Results open in a new view</p>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS PAGE
# ══════════════════════════════════════════════════════════════════════════════
def render_results() -> None:
    company = st.session_state.inp_company

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

    # ── Compute valuations from session state ──
    _revenue       = st.session_state.inp_revenue
    _growth_pct    = st.session_state.inp_growth
    _ebitda_margin = st.session_state.inp_ebitda
    _stage         = st.session_state.inp_stage
    _sector        = st.session_state.inp_sector
    _geography     = st.session_state.inp_geo
    _cash          = st.session_state.inp_cash
    _burn          = st.session_state.inp_burn
    _total_debt    = st.session_state.inp_debt
    _cod           = st.session_state.inp_cod
    _openai_key    = st.session_state.inp_openai

    _beta_source_val = st.session_state.get("inp_beta_source", "Use sector average (recommended)")
    if _beta_source_val == "Use sector average (recommended)":
        _beta_val = SECTOR_BETAS.get(_sector, 1.20)
    else:
        _beta_val = None
    _tv_label  = st.session_state.get("inp_tv_method", "Gordon Growth Model")
    _tv_method = "exit_multiple" if _tv_label == "Exit Multiple (EV/EBITDA)" else "gordon_growth"
    _exit_mult = float(st.session_state.get("inp_exit_multiple", 12.0)) if _tv_method == "exit_multiple" else None
    _projection_years_val = int(st.session_state.get("inp_projection_years", 5))
    _inputs = _NS(
        stage=_stage,
        tax_rate_pct=float(st.session_state.get("inp_tax", 25)),
        capex_pct_of_ebitda=float(st.session_state.get("inp_capex", 5)),
        nwc_pct_of_ebitda=3.0,
        da_pct_of_revenue=3.0,
        target_ebitda_margin_pct=float(st.session_state.get("inp_target_margin", 25)),
        terminal_growth_rate_pct=float(st.session_state.get("inp_terminal_growth", 3.0)),
        terminal_value_method=_tv_method,
        exit_multiple_ebitda=_exit_mult,
        use_custom_wacc=bool(st.session_state.get("inp_use_custom_wacc", False)),
        custom_wacc_pct=float(st.session_state.get("inp_custom_wacc", 28.0)),
        risk_free_rate_pct=float(st.session_state.get("inp_rfr", 4.2)),
        equity_risk_premium_pct=float(st.session_state.get("inp_erp", 5.5)),
        beta=float(_beta_val) if _beta_val is not None else None,
        cost_of_debt_pct=float(st.session_state.get("inp_wacc_kd", 8.0)),
        debt_gbp=float(st.session_state.get("inp_wacc_debt", 0)),
        total_debt_gbp=float(st.session_state.get("inp_wacc_debt", 0)),
        equity_gbp=None,
        projection_years=_projection_years_val,
        custom_ev_rev_multiple=float(st.session_state.get("inp_ev_rev_multiple", 0)) or None,
    )
    _dcf   = dcf_valuation(_revenue, _growth_pct, _ebitda_margin, _inputs)
    _comps = comparable_valuation(
        _revenue, _sector,
        custom_ev_rev_multiple=_inputs.custom_ev_rev_multiple,
        growth_pct=_growth_pct,
    )
    _blend = blended_valuation(_dcf, _comps)
    _runway = int(_cash / _burn) if _burn > 0 else 999

    # ── Layout: sidebar + main ──
    nav_col, main_col = st.columns([1.3, 5], gap="large")

    # ── LEFT SIDEBAR NAV ──
    with nav_col:
        st.markdown("""
<div class="sidebar-logo">
    <div style="width:28px;height:28px;background:#00D4AA;border-radius:6px;
                display:flex;align-items:center;justify-content:center;flex-shrink:0;">
        <svg width="16" height="12" viewBox="0 0 16 12" fill="none">
            <polyline points="1,10 5,6 8,8 12,2 15,1"
                      stroke="#0A0F1E" stroke-width="2.2"
                      stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            <circle cx="15" cy="1" r="1.8" fill="#0A0F1E"/>
        </svg>
    </div>
    <div>
        <div style="font-size:14px;font-weight:500;color:#F5F5F0;
                    letter-spacing:-0.01em;line-height:1;">Runrate</div>
        <div style="font-size:9px;color:#4A5568;letter-spacing:0.06em;
                    text-transform:uppercase;margin-top:1px;">Deal intelligence</div>
    </div>
</div>
""", unsafe_allow_html=True)

        if st.button("← Back", key="sidebar_back", use_container_width=True):
            st.session_state.page = "landing"
            st.rerun()

        st.markdown('<span class="sidebar-section-label">Analysis</span>',
                    unsafe_allow_html=True)

        NAV_ITEMS = [
            "Valuation",
            "Fundraising",
            "VC matching",
            "Comparable transactions",
            "Investor outreach",
        ]
        for item in NAV_ITEMS:
            is_active = st.session_state.active_tab == item
            btn_type = "primary" if is_active else "secondary"
            if st.button(item, key=f"nav_{item.replace(' ', '_')}",
                         use_container_width=True, type=btn_type):
                st.session_state.active_tab = item
                st.rerun()

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
        _cname = st.session_state.get("inp_company", "")
        _csector = st.session_state.get("inp_sector", "")
        _cstage = st.session_state.get("inp_stage", "")
        if _cname:
            st.markdown(
                f"<div style='border-top:0.5px solid #1A2035;padding:12px 8px 0;margin-top:4px;'>"
                f"<div style='font-size:11px;font-weight:500;color:#C4CAD8;margin-bottom:2px;"
                f"overflow:hidden;text-overflow:ellipsis;white-space:nowrap;'>{_cname}</div>"
                f"<div style='font-size:10px;color:#4A5568;'>{_csector} · {_cstage}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

    # ── MAIN CONTENT ──
    with main_col:
        tab = st.session_state.active_tab

        # ──────────────────────────────────────────────────────────────────
        # VALUATION
        # ──────────────────────────────────────────────────────────────────
        if tab == "Valuation":
            section_header(
                "Valuation",
                f"Enterprise value range · {company} · {_sector} · {_stage}"
            )

            # WACC + terminal value callout
            _tv_m = _blend.get("tv_method", "gordon_growth")
            if _tv_m == "exit_multiple" and _blend.get("exit_multiple_ebitda"):
                _tv_line = "Terminal value: " + str(_blend["exit_multiple_ebitda"]) + "x EV/EBITDA exit on Year 5 EBITDA"
            else:
                _tv_line = "Terminal value: Gordon Growth at " + str(round(_blend.get("terminal_growth_pct", 3.0), 1)) + "% perpetuity growth"
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            # Headline cards
            _optimistic_color = GREEN if _blend["high"] > 0 else RED
            st.markdown(
                "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;"
                "gap:12px;margin-bottom:20px;'>"
                + card_html("Conservative", fmt_gbp(_blend["low"]),
                            "25th percentile", "1px solid #E2E8F0", "#64748B")
                + card_html("Base case", fmt_gbp(_blend["base"]),
                            "Most likely", f"2px solid {BLUE}", BLUE)
                + card_html("Optimistic", fmt_gbp(_blend["high"]),
                            "75th percentile", "1px solid #E2E8F0", GREEN)
                + "</div>",
                unsafe_allow_html=True,
            )

            # DCF vs Comps side by side
            _dl, _dr = st.columns(2)
            with _dl:
                overline("DCF valuation — three scenarios")
                dcf_df = pd.DataFrame({
                    "Scenario": ["Conservative", "Base", "Optimistic"],
                    "Value (£m)": [
                        round(_dcf["low"]/1e6, 1),
                        round(_dcf["base"]/1e6, 1),
                        round(_dcf["high"]/1e6, 1),
                    ],
                })
                st.dataframe(dcf_df, hide_index=True, use_container_width=True)

                fig_dcf = go.Figure(go.Bar(
                    x=["Conservative", "Base", "Optimistic"],
                    y=[_dcf["low"]/1e6, _dcf["base"]/1e6, _dcf["high"]/1e6],
                    marker_color=[BLUE_MID, BLUE, GREEN],
                    text=[fmt_gbp(v) for v in [_dcf["low"], _dcf["base"], _dcf["high"]]],
                    textposition="outside",
                ))
                _dcf_layout = dict(**PLOTLY_BASE)
                _dcf_layout["margin"] = dict(l=0, r=0, t=30, b=0)
                fig_dcf.update_layout(
                    title="DCF (£m)",
                    xaxis=dict(**AXIS_CLEAN),
                    yaxis=dict(**AXIS_CLEAN),
                    **_dcf_layout,
                )
                st.plotly_chart(fig_dcf, use_container_width=True)

            with _dr:
                overline("Comparable multiples — three scenarios")
                _sector_mult = {
                    "FinTech": {"low":4.0,"base":7.0,"high":12.0},
                    "SaaS": {"low":5.0,"base":9.0,"high":15.0},
                    "HealthTech": {"low":3.5,"base":6.0,"high":10.0},
                    "EdTech": {"low":2.5,"base":4.5,"high":8.0},
                    "CleanTech": {"low":3.0,"base":5.5,"high":9.0},
                    "E-Commerce": {"low":1.5,"base":3.0,"high":5.5},
                    "DeepTech": {"low":4.0,"base":8.0,"high":14.0},
                    "Cybersecurity": {"low":5.0,"base":9.5,"high":16.0},
                    "MarketPlace": {"low":2.0,"base":4.0,"high":7.0},
                    "Other": {"low":2.0,"base":4.0,"high":7.0},
                }
                _m = _sector_mult.get(_sector, _sector_mult["Other"])
                comps_df = pd.DataFrame({
                    "Scenario": ["Conservative", "Base", "Optimistic"],
                    "EV/Rev":   [_m["low"], _m["base"], _m["high"]],
                    "Value (£m)": [
                        round(_comps["low"]/1e6, 1),
                        round(_comps["base"]/1e6, 1),
                        round(_comps["high"]/1e6, 1),
                    ],
                })
                st.dataframe(comps_df, hide_index=True, use_container_width=True)

                fig_comps = go.Figure(go.Bar(
                    x=["Conservative", "Base", "Optimistic"],
                    y=[_comps["low"]/1e6, _comps["base"]/1e6, _comps["high"]/1e6],
                    marker_color=[BLUE_MID, BLUE, GREEN],
                    text=[fmt_gbp(v) for v in [_comps["low"], _comps["base"], _comps["high"]]],
                    textposition="outside",
                ))
                fig_comps.update_layout(
                    title="Comparables (£m)",
                    xaxis=dict(**AXIS_CLEAN),
                    yaxis=dict(**AXIS_CLEAN),
                    **_dcf_layout,
                )
                st.plotly_chart(fig_comps, use_container_width=True)

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("5-year revenue projection")

            _proj = five_year_projection(_revenue, _growth_pct, _ebitda_margin)

            # Styled HTML table
            _trows = ""
            for i, row in _proj.iterrows():
                _bg = "#F8FAFC" if i % 2 == 0 else "#FFFFFF"
                _ebitda_color = RED if row["EBITDA (£m)"] < 0 else "#0F172A"
                _trows += (
                    f"<tr style='background:{_bg};'>"
                    f"<td style='padding:10px 14px;font-size:13px;color:#0F172A;"
                    f"border-bottom:1px solid #F1F5F9;'>{row['Year']}</td>"
                    f"<td style='padding:10px 14px;font-size:13px;color:#0F172A;"
                    f"border-bottom:1px solid #F1F5F9;'>£{row['Revenue (£m)']}m</td>"
                    f"<td style='padding:10px 14px;font-size:13px;color:{_ebitda_color};"
                    f"border-bottom:1px solid #F1F5F9;'>£{row['EBITDA (£m)']}m</td>"
                    f"<td style='padding:10px 14px;font-size:13px;color:#0F172A;"
                    f"border-bottom:1px solid #F1F5F9;'>{row['EBITDA Margin']}</td>"
                    f"</tr>"
                )
            st.markdown(
                "<div style='background:#FFFFFF;border:1px solid #E2E8F0;"
                "border-radius:8px;overflow:hidden;'>"
                "<table style='width:100%;border-collapse:collapse;'>"
                "<thead><tr style='background:#F8FAFC;'>"
                "<th style='padding:10px 14px;font-size:11px;letter-spacing:0.06em;"
                "text-transform:uppercase;color:#94A3B8;text-align:left;font-weight:400;"
                "border-bottom:1px solid #E2E8F0;'>Year</th>"
                "<th style='padding:10px 14px;font-size:11px;letter-spacing:0.06em;"
                "text-transform:uppercase;color:#94A3B8;text-align:left;font-weight:400;"
                "border-bottom:1px solid #E2E8F0;'>Revenue</th>"
                "<th style='padding:10px 14px;font-size:11px;letter-spacing:0.06em;"
                "text-transform:uppercase;color:#94A3B8;text-align:left;font-weight:400;"
                "border-bottom:1px solid #E2E8F0;'>EBITDA</th>"
                "<th style='padding:10px 14px;font-size:11px;letter-spacing:0.06em;"
                "text-transform:uppercase;color:#94A3B8;text-align:left;font-weight:400;"
                "border-bottom:1px solid #E2E8F0;'>Margin</th>"
                "</tr></thead>"
                f"<tbody>{_trows}</tbody>"
                "</table></div>",
                unsafe_allow_html=True,
            )

            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

            fig_proj = go.Figure()
            fig_proj.add_trace(go.Scatter(
                x=_proj["Year"], y=_proj["Revenue (£m)"],
                mode="lines+markers+text", name="Revenue",
                line=dict(color=BLUE, width=2),
                text=[f"£{v}m" for v in _proj["Revenue (£m)"]],
                textposition="top center", textfont=dict(size=11, color="#0F172A"),
            ))
            fig_proj.add_trace(go.Scatter(
                x=_proj["Year"], y=_proj["EBITDA (£m)"],
                mode="lines+markers+text", name="EBITDA",
                line=dict(color=GREEN, width=2, dash="dot"),
                text=[f"£{v}m" for v in _proj["EBITDA (£m)"]],
                textposition="bottom center", textfont=dict(size=11, color="#0F172A"),
            ))
            _proj_layout = dict(**PLOTLY_BASE)
            _proj_layout["legend"] = dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0",
                                          orientation="h", y=-0.15)
            fig_proj.update_layout(
                title="5-year revenue & EBITDA (£m)",
                xaxis=dict(**AXIS_CLEAN),
                yaxis=dict(**AXIS_CLEAN),
                **_proj_layout,
            )
            st.plotly_chart(fig_proj, use_container_width=True)

            # ── VALUE BRIDGE waterfall ────────────────────────────────────
            overline("VALUE BRIDGE")
            _detail = _dcf.get("dcf_detail", {})
            if _detail:
                _rv1 = _detail.get("revenue_y1", 0)
                _eb1 = _detail.get("ebitda_y1", 0)
                _np1 = _detail.get("nopat_y1", 0)
                _fcfs = _detail.get("fcfs", [])
                _pv_fcfs = _detail.get("pv_fcfs_sum", 0)
                _pv_tv = _detail.get("terminal_value_pv", 0)
                _ev_base = _dcf.get("base", 0)

                _tax_hit = _np1 - _eb1
                _capex_nwc = (_fcfs[0] if _fcfs else 0) - _np1

                _wf_x = ["Revenue (Y1)", "EBITDA margin", "Tax (NOPAT)", "CapEx + NWC", "PV of FCFs", "Terminal value", "Enterprise value"]
                _wf_y = [_rv1, _eb1 - _rv1, _tax_hit, _capex_nwc, _pv_fcfs, _pv_tv, 0]
                _wf_measure = ["relative", "relative", "relative", "relative", "absolute", "relative", "total"]

                fig_wf = go.Figure(go.Waterfall(
                    orientation="v",
                    measure=_wf_measure,
                    x=_wf_x,
                    y=_wf_y,
                    connector=dict(line=dict(color="#E2E8F0", width=1)),
                    increasing=dict(marker=dict(color="#10B981")),
                    decreasing=dict(marker=dict(color="#EF4444")),
                    totals=dict(marker=dict(color="#1D4ED8")),
                    text=[fmt_gbp(abs(v)) for v in _wf_y],
                    textposition="outside",
                ))
                fig_wf.update_layout(
                    paper_bgcolor="#F8FAFC",
                    plot_bgcolor="#F8FAFC",
                    height=380,
                    margin=dict(l=20, r=20, t=20, b=20),
                    showlegend=False,
                    yaxis=dict(showgrid=False, zeroline=True, zerolinecolor="#E2E8F0"),
                    xaxis=dict(showgrid=False),
                )
                st.plotly_chart(fig_wf, use_container_width=True, config={"displayModeBar": False})

            # ── SENSITIVITY TABLE ─────────────────────────────────────────
            overline("SENSITIVITY ANALYSIS - ENTERPRISE VALUE (BASE CASE DCF)")
            _base_wacc = _blend.get("wacc", 0.30)
            _pv_fcfs_sum = _detail.get("pv_fcfs_sum", 0)
            _fcfs_list = _detail.get("fcfs", [])
            _wacc_rows = [_base_wacc - 0.04, _base_wacc - 0.02, _base_wacc, _base_wacc + 0.02, _base_wacc + 0.04]
            _tg_cols = [0.01, 0.02, 0.03, 0.04, 0.05]
            _sens_data = {}
            for _w in _wacc_rows:
                _row = {}
                for _tg in _tg_cols:
                    if _w > _tg and _fcfs_list:
                        _tv = _fcfs_list[-1] * (1 + _tg) / (_w - _tg)
                        _pv_tv = _tv / ((1 + _w) ** 5)
                        _ev = _pv_fcfs_sum + _pv_tv
                    else:
                        _ev = _pv_fcfs_sum
                    _row[f"{_tg*100:.1f}%"] = fmt_gbp(_ev)
                _sens_data[f"{_w*100:.1f}%"] = _row
            _sens_df = pd.DataFrame(_sens_data).T
            _sens_df.index.name = "WACC \\ Term. Growth"
            st.dataframe(_sens_df, use_container_width=True)

        # ──────────────────────────────────────────────────────────────────
        # FUNDRAISING
        # ──────────────────────────────────────────────────────────────────
        elif tab == "Fundraising":
            section_header(
                "Fundraising",
                f"Runway, raise sizing, and readiness · {company}"
            )

            gauge_color = RED if _runway < 12 else GREEN if _runway >= 18 else AMBER
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=_runway,
                domain={"x": [0, 1], "y": [0, 1]},
                title={"text": "Runway (months)", "font": {"color": "#64748B", "size": 13}},
                gauge={
                    "axis": {"range": [0, 36], "tickcolor": "#94A3B8",
                             "tickfont": {"color": "#94A3B8"}},
                    "bar": {"color": gauge_color},
                    "bgcolor": "#F1F5F9", "bordercolor": "#E2E8F0",
                    "steps": [
                        {"range": [0, 12],  "color": "#FEE2E2"},
                        {"range": [12, 18], "color": "#FEF3C7"},
                        {"range": [18, 36], "color": "#D1FAE5"},
                    ],
                    "threshold": {"line": {"color": BLUE, "width": 3}, "value": 18},
                },
                number={"font": {"color": gauge_color, "size": 48}},
            ))
            fig_gauge.update_layout(
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                font=dict(color="#0F172A"), height=260,
                margin=dict(l=20, r=20, t=40, b=20),
            )
            st.plotly_chart(fig_gauge, use_container_width=True)

            st.markdown("<hr/>", unsafe_allow_html=True)

            _recommended = _burn * 18
            _dilution     = 0.20 if _stage == "Seed" else 0.15 if _stage == "Series A" else 0.12
            _post_money   = _blend["base"] + _recommended

            _fm1, _fm2, _fm3 = st.columns(3)
            _fm1.metric("Recommended raise", fmt_gbp(_recommended))
            _fm2.metric("Estimated dilution", f"{_dilution*100:.0f}%")
            _fm3.metric("Post-money (base)",  fmt_gbp(_post_money))

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("Suggested use of funds")

            _SECTOR_FUNDS = {
                "FinTech":      {"Engineering & Product": 35, "Sales & Marketing": 25, "Compliance & Regulation": 15, "Operations": 15, "G&A / Legal": 7, "Reserve": 3},
                "SaaS":         {"Engineering & Product": 40, "Sales & Marketing": 35, "Customer Success": 10, "Operations": 8, "G&A / Legal": 5, "Reserve": 2},
                "HealthTech":   {"R&D & Clinical": 35, "Engineering & Product": 25, "Regulatory Affairs": 15, "Sales & Marketing": 15, "G&A / Legal": 7, "Reserve": 3},
                "MarketPlace":  {"Engineering & Product": 30, "Sales & Marketing": 30, "Supply Acquisition": 20, "Operations": 12, "G&A / Legal": 5, "Reserve": 3},
                "DeepTech":     {"R&D": 45, "Engineering & Product": 25, "Business Development": 15, "Operations": 8, "G&A / Legal": 5, "Reserve": 2},
                "EdTech":       {"Engineering & Product": 35, "Content & Curriculum": 20, "Sales & Marketing": 25, "Operations": 12, "G&A / Legal": 5, "Reserve": 3},
                "CleanTech":    {"R&D & Engineering": 40, "Pilots & Deployment": 25, "Business Development": 15, "Operations": 12, "G&A / Legal": 5, "Reserve": 3},
                "E-Commerce":   {"Marketing & Brand": 40, "Engineering & Product": 25, "Operations & Logistics": 20, "G&A / Legal": 10, "Reserve": 5},
                "Cybersecurity":{"Engineering & Product": 40, "Sales & Marketing": 30, "Compliance": 15, "Operations": 10, "G&A / Legal": 5},
                "Other":        {"Engineering & Product": 35, "Sales & Marketing": 30, "Operations": 15, "G&A / Legal": 12, "Reserve": 8},
            }
            _fund_alloc = _SECTOR_FUNDS.get(_sector, _SECTOR_FUNDS["Other"])
            _cats = list(_fund_alloc.keys())
            _weights = [v / 100 for v in _fund_alloc.values()]
            _amounts = [_recommended * w for w in _weights]

            fig_pie = go.Figure(go.Pie(
                labels=_cats, values=_amounts, hole=0.45,
                marker=dict(colors=[BLUE, BLUE_MID, GREEN, AMBER, "#CBD5E1"]),
                textinfo="label+percent",
                textfont=dict(color="#0F172A", size=12),
            ))
            fig_pie.update_layout(
                title=f"Use of {fmt_gbp(_recommended)} raise",
                showlegend=False, **{k: v for k, v in PLOTLY_BASE.items() if k not in ("legend",)},
            )
            st.plotly_chart(fig_pie, use_container_width=True)

            uof_df = pd.DataFrame({
                "Category":   _cats,
                "Allocation": [f"{w*100:.0f}%" for w in _weights],
                "Amount (£)": [f"£{a:,.0f}" for a in _amounts],
            })
            st.dataframe(uof_df, hide_index=True, use_container_width=True)

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("Cash runway bridge")

            _mo = list(range(0, min(_runway + 1, 37)))
            _cv = [max(_cash - _burn * m, 0) for m in _mo]
            fig_burn = go.Figure()
            fig_burn.add_trace(go.Scatter(
                x=_mo, y=[c/1e6 for c in _cv],
                fill="tozeroy", mode="lines",
                line=dict(color=BLUE, width=2),
                fillcolor="rgba(29,78,216,0.07)",
                name="Cash (£m)",
            ))
            if 12 <= _runway:
                fig_burn.add_vline(x=12, line_dash="dot", line_color=RED,
                                   annotation_text="12-month warning",
                                   annotation_font_color=RED)
            if _runway < 36:
                fig_burn.add_vline(x=_runway, line_dash="dash", line_color=AMBER,
                                   annotation_text=f"Zero cash (M{_runway})",
                                   annotation_font_color=AMBER)
            fig_burn.update_layout(
                title="Cash balance over time (£m)",
                xaxis=dict(title="Month", **AXIS_CLEAN),
                yaxis=dict(title="£m", **AXIS_CLEAN),
                legend=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0"),
                margin=dict(l=0, r=0, t=30, b=0),
                **{k: v for k, v in PLOTLY_BASE.items() if k not in ("margin", "legend", "showlegend")},
            )
            st.plotly_chart(fig_burn, use_container_width=True)

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("Fundraising readiness checklist")
            _tips = [
                ("Runway",            _runway >= 18, f"{_runway} months remaining" if _runway >= 18 else f"Only {_runway} months — raise urgently"),
                ("Revenue traction",  _revenue > 0,  fmt_gbp(_revenue) + " ARR"),
                ("Growth rate",       _growth_pct >= 50, f"{_growth_pct}% YoY growth"),
                ("EBITDA visibility", _ebitda_margin >= 0, f"{_ebitda_margin}% margin"),
            ]
            for _lbl, _ok, _note in _tips:
                _color = "#10B981" if _ok else "#EF4444"
                st.markdown(
                    f'<div style="border-left:3px solid {_color};padding:8px 16px;margin-bottom:8px;background:#F8FAFC;border-radius:0 6px 6px 0;">'
                    f'<span style="font-size:14px;color:#1F2937;"><strong>{_lbl}</strong> — {_note}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("DILUTION TIMELINE - FOUNDER OWNERSHIP")

            _rounds = ["Founding", "Seed", "Series A", "Series B", "Series C"]
            _dilutions = [0, 15, 20, 18, 15]
            _ownership = []
            _own = 100.0
            for _d in _dilutions:
                _own = _own * (1 - _d / 100)
                _ownership.append(_own)

            fig_dil = go.Figure()
            fig_dil.add_trace(go.Scatter(
                x=_rounds, y=_ownership,
                mode="lines+markers",
                line=dict(color="#1D4ED8", width=2),
                fill="tozeroy",
                fillcolor="rgba(29,78,216,0.1)",
                name="Founder ownership",
            ))
            fig_dil.add_hline(y=50, line_dash="dash", line_color="#EF4444",
                               annotation_text="Control threshold", annotation_position="top right")
            fig_dil.add_hline(y=20, line_dash="dash", line_color="#F59E0B",
                               annotation_text="Typical floor", annotation_position="top right")
            # Mark current stage with a highlighted point on the line
            _stage_idx = {"Pre-Seed": 0, "Seed": 1, "Series A": 2, "Series B": 3, "Series C+": 4, "Growth": 4}.get(_stage, 0)
            if _stage_idx > 0:
                fig_dil.add_trace(go.Scatter(
                    x=[_rounds[_stage_idx]], y=[_ownership[_stage_idx]],
                    mode="markers+text",
                    marker=dict(color="#1D4ED8", size=14, symbol="circle"),
                    text=["Current stage"],
                    textposition="top center",
                    textfont=dict(size=11, color="#64748B"),
                    showlegend=False,
                ))
            fig_dil.update_layout(
                paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                height=300, margin=dict(l=0, r=0, t=20, b=0),
                yaxis=dict(title="Founder ownership %", range=[0, 105], **AXIS_CLEAN),
                xaxis=dict(**AXIS_CLEAN),
                showlegend=False,
            )
            st.plotly_chart(fig_dil, use_container_width=True, config={"displayModeBar": False})

            _dil_rows = []
            _own2 = 100.0
            for _rnd, _d in zip(_rounds, _dilutions):
                _own2 = _own2 * (1 - _d / 100)
                _implied = _own2 / 100 * _blend.get("base", 0)
                _dil_rows.append({"Round": _rnd, "Dilution sold": f"{_d}%", "Founder ownership": f"{_own2:.1f}%", "Implied stake value": fmt_gbp(_implied)})
            st.dataframe(pd.DataFrame(_dil_rows), use_container_width=True, hide_index=True)

            st.markdown("<hr/>", unsafe_allow_html=True)
            overline("COMPARABLE RAISES - RECENT MARKET DATA")

            _COMP_RAISES = {
                ("FinTech", "Series A"): [
                    {"Company": "Cleo", "Amount": "£80m", "Valuation": "£500m", "Year": 2024, "Description": "AI-powered financial assistant"},
                    {"Company": "Liberis", "Amount": "£64m", "Valuation": "£320m", "Year": 2024, "Description": "Embedded finance for SMEs"},
                    {"Company": "Comma", "Amount": "£10m", "Valuation": "£50m", "Year": 2024, "Description": "Open banking payments infrastructure"},
                ],
                ("FinTech", "Series B"): [
                    {"Company": "Atoa", "Amount": "£15m", "Valuation": "£75m", "Year": 2024, "Description": "Account-to-account payments"},
                    {"Company": "Hokodo", "Amount": "£40m", "Valuation": "£180m", "Year": 2024, "Description": "B2B BNPL for trade credit"},
                    {"Company": "Wagestream", "Amount": "£57m", "Valuation": "£300m", "Year": 2024, "Description": "Earned wage access platform"},
                ],
                ("SaaS", "Series A"): [
                    {"Company": "Koor", "Amount": "£8m", "Valuation": "£40m", "Year": 2024, "Description": "Procurement analytics SaaS"},
                    {"Company": "Drata", "Amount": "£50m", "Valuation": "£400m", "Year": 2024, "Description": "Compliance automation"},
                    {"Company": "Paddle", "Amount": "£60m", "Valuation": "£800m", "Year": 2024, "Description": "Revenue delivery platform"},
                ],
                ("SaaS", "Series B"): [
                    {"Company": "Zelt", "Amount": "£25m", "Valuation": "£120m", "Year": 2024, "Description": "HR and payroll platform"},
                    {"Company": "Personio", "Amount": "£200m", "Valuation": "£6bn", "Year": 2024, "Description": "HR SaaS for SMEs"},
                    {"Company": "Rippling", "Amount": "£400m", "Valuation": "£9bn", "Year": 2024, "Description": "Workforce management"},
                ],
                ("HealthTech", "Seed"): [
                    {"Company": "Maia", "Amount": "£3m", "Valuation": "£15m", "Year": 2024, "Description": "AI menopause care"},
                    {"Company": "Suvera", "Amount": "£5m", "Valuation": "£25m", "Year": 2024, "Description": "Virtual chronic disease clinic"},
                    {"Company": "Thymia", "Amount": "£4m", "Valuation": "£20m", "Year": 2024, "Description": "Mental health biomarkers"},
                ],
                ("HealthTech", "Series A"): [
                    {"Company": "Feebris", "Amount": "£12m", "Valuation": "£60m", "Year": 2024, "Description": "AI health assessment"},
                    {"Company": "Huma", "Amount": "£50m", "Valuation": "£300m", "Year": 2024, "Description": "Digital health platform"},
                    {"Company": "Vinehealth", "Amount": "£8m", "Valuation": "£40m", "Year": 2024, "Description": "Cancer care companion"},
                ],
            }

            _comp_key = (_sector, _stage)
            _comp_data = _COMP_RAISES.get(_comp_key)
            if not _comp_data:
                # Try any stage for same sector
                _comp_data = next((v for k, v in _COMP_RAISES.items() if k[0] == _sector), None)
            if _comp_data:
                st.dataframe(pd.DataFrame(_comp_data), use_container_width=True, hide_index=True)
            else:
                st.info("No comparable raises found for this sector and stage combination.")

        # ──────────────────────────────────────────────────────────────────
        # VC MATCHING
        # ──────────────────────────────────────────────────────────────────
        elif tab == "VC matching":
            csv_path = os.path.join(os.path.dirname(__file__), "data", "vc_database.csv")
            try:
                vc_df = pd.read_csv(csv_path)
            except FileNotFoundError:
                st.error(f"VC database not found at {csv_path}")
                st.stop()

            _scored = score_investors(vc_df, _sector, _stage, _geography, _revenue)
            _top5   = _scored.head(5).copy()

            match_list = []
            for _, _r in _top5.iterrows():
                match_list.append(MatchResult(
                    name              = _r["Investor"],
                    score             = int(_r["Score /100"]),
                    sector_score      = int(_r["Sector Fit"]),
                    stage_score       = int(_r["Stage Fit"]),
                    geo_score         = int(_r["Geo Fit"]),
                    cheque_score      = int(_r["Cheque Fit"]),
                    sector_rationale  = str(_r["Sector Rationale"]),
                    stage_rationale   = str(_r["Stage Rationale"]),
                    geo_rationale     = str(_r["Geo Rationale"]),
                    cheque_rationale  = str(_r["Cheque Rationale"]),
                    notable_portfolio = str(_r["Notable Portfolio"]),
                    cheque_range      = str(_r["Cheque Range"]),
                    website           = str(_r["Website"]),
                    description       = str(_r["Description"]),
                    investor_type     = str(_r["Type"]),
                ))
            st.session_state["vc_matches"] = match_list

            st.markdown("### VC Matching")
            st.caption("Top 5 investors ranked by specialist fit score")

            names         = [m.name         for m in match_list]
            sector_scores = [m.sector_score for m in match_list]
            stage_scores  = [m.stage_score  for m in match_list]
            geo_scores    = [m.geo_score    for m in match_list]
            cheque_scores = [m.cheque_score for m in match_list]
            totals        = [m.score        for m in match_list]

            fig = go.Figure()
            fig.add_trace(go.Bar(name="Sector /35",    y=names, x=sector_scores, orientation="h", marker_color="#1F2937", text=sector_scores, textposition="inside", insidetextanchor="middle", textfont=dict(color="white",   size=11)))
            fig.add_trace(go.Bar(name="Stage /35",     y=names, x=stage_scores,  orientation="h", marker_color="#EAB308", text=stage_scores,  textposition="inside", insidetextanchor="middle", textfont=dict(color="#1F2937", size=11)))
            fig.add_trace(go.Bar(name="Geography /20", y=names, x=geo_scores,    orientation="h", marker_color="#F97316", text=geo_scores,    textposition="inside", insidetextanchor="middle", textfont=dict(color="white",   size=11)))
            fig.add_trace(go.Bar(name="Cheque /10",    y=names, x=cheque_scores, orientation="h", marker_color="#65A30D", text=cheque_scores, textposition="inside", insidetextanchor="middle", textfont=dict(color="white",   size=11)))

            for name, total in zip(names, totals):
                fig.add_annotation(x=total + 1, y=name, text="<b>" + str(total) + "</b>", showarrow=False, xanchor="left", font=dict(size=13, color="#1F2937"))

            fig.update_layout(
                barmode="stack",
                paper_bgcolor="#FAF8F1",
                plot_bgcolor="#FAF8F1",
                height=280,
                margin=dict(l=130, r=60, t=10, b=80),
                xaxis=dict(range=[0, 110], showgrid=False, title="Score /100"),
                yaxis=dict(showgrid=False, autorange="reversed"),
                legend=dict(orientation="h", yanchor="top", y=-0.25, xanchor="center", x=0.5, font=dict(size=11, color="#6B7280"), bgcolor="rgba(0,0,0,0)"),
                showlegend=True,
            )

            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            st.divider()

            def _bar(score, max_score):
                pct = score / max_score if max_score > 0 else 0
                if max_score == 35:
                    color = "#10B981" if pct >= 0.85 else "#EAB308" if pct >= 0.60 else "#EF4444"
                elif max_score == 20:
                    color = "#10B981" if pct >= 0.80 else "#EAB308" if pct >= 0.55 else "#EF4444"
                else:  # max_score == 10
                    color = "#10B981" if pct >= 0.80 else "#EAB308" if pct >= 0.55 else "#EF4444"
                return f'<div style="background:#F1F5F9;border-radius:4px;height:8px;width:100%;margin:4px 0 8px 0;"><div style="background:{color};border-radius:4px;height:8px;width:{pct*100:.0f}%;"></div></div>'

            _VC_INTRO = {
                "Finch Capital": "Via Techleap.nl alumni, Startupbootcamp FinTech graduates, or founders of Fourthline and Tokenize",
                "Episode 1": "Via founders of Zoopla, Simply Business, or alumni of Seedcamp portfolio",
                "Connect Ventures": "Via Typeform, Citymapper, or Curve founders — all active angels from their portfolio",
                "Notion Capital": "Via GoCardless, Paddle, or ComplyAdvantage founders — or through SaaS founders in their network",
                "Cherry Ventures": "Via FlixBus, Forto, or Contentful founding teams — strong Berlin-London network",
                "Accel": "Via Monzo, Revolut, or Atlassian alumni — or through Y Combinator batch connections",
                "Balderton Capital": "Via Revolut, Depop, or Betfair founding teams — or through Index Ventures co-investments",
                "Index Ventures": "Via Wise, Robinhood UK, or Cazoo founders — or through LocalGlobe portfolio overlap",
                "Anthemis": "Via Wealthsimple, Betterment, or Simple founding teams — strong US-UK FinTech network",
                "Augmentum Fintech": "Via portfolio company founders or through fintech accelerators like Barclays Accelerator",
                "LocalGlobe": "Via Transferwise or Cazoo alumni — or through Oxford and Cambridge angel networks",
                "Seedcamp": "Via Revolut or UiPath alumni — or through accelerator programme application directly",
                "Octopus Ventures": "Via Elvie, Zoopla, or Secret Escapes founders — or through UK angel networks",
            }

            for rank, match in enumerate(match_list, start=1):
                total_pct = match.score / 100
                badge_color = "#10B981" if total_pct >= 0.85 else "#EAB308" if total_pct >= 0.70 else "#EF4444"
                label = "No." + str(rank) + "  " + str(match.name) + "  |  " + str(match.score) + "/100"
                st.markdown("---")
                st.markdown(
                    f'<span style="background:{badge_color};color:#fff;border-radius:4px;padding:2px 8px;font-size:12px;font-weight:500;">'
                    f'{match.score}/100</span> <strong>{label}</strong>',
                    unsafe_allow_html=True,
                )
                st.divider()
                st.markdown("**" + str(match.name) + "**")
                st.caption(str(match.description))
                st.link_button("Visit website", str(match.website))
                st.caption("Portfolio: " + str(match.notable_portfolio))
                st.divider()
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**SECTOR FIT - " + str(match.sector_score) + "/35**")
                    st.markdown(_bar(int(match.sector_score), 35), unsafe_allow_html=True)
                    st.caption(str(match.sector_rationale))
                    st.divider()
                    st.markdown("**GEOGRAPHY FIT - " + str(match.geo_score) + "/20**")
                    st.markdown(_bar(int(match.geo_score), 20), unsafe_allow_html=True)
                    st.caption(str(match.geo_rationale))
                with col_b:
                    st.markdown("**STAGE FIT - " + str(match.stage_score) + "/35**")
                    st.markdown(_bar(int(match.stage_score), 35), unsafe_allow_html=True)
                    st.caption(str(match.stage_rationale))
                    st.divider()
                    st.markdown("**CHEQUE SIZE - " + str(match.cheque_score) + "/10**")
                    st.markdown(_bar(int(match.cheque_score), 10), unsafe_allow_html=True)
                    st.caption(str(match.cheque_rationale))
                st.divider()
                st.markdown("**WARM INTRODUCTION PATH**")
                _intro = _VC_INTRO.get(str(match.name), "Research portfolio company founders on LinkedIn for warm introduction opportunities")
                st.caption(_intro)

        # ──────────────────────────────────────────────────────────────────
        # COMPARABLE TRANSACTIONS
        # ──────────────────────────────────────────────────────────────────
        elif tab == "Comparable transactions":
            section_header("Comparable transactions",
                           "Recent M&A deals in " + str(_sector) + " — what acquirers have paid")

            _txns = COMPARABLE_TRANSACTIONS.get(_sector, COMPARABLE_TRANSACTIONS["Other"])
            _multiples = [t["ev_rev_multiple"] for t in _txns]
            _avg_mult  = sum(_multiples) / len(_multiples)
            _med_deal  = sorted([t["deal_size_gbp"] for t in _txns])[len(_txns) // 2]
            _years     = [t["year"] for t in _txns]

            # Summary metrics
            _sm1, _sm2, _sm3 = st.columns(3)
            with _sm1:
                st.markdown(
                    "<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:16px;'>"
                    "<p style='font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:#94A3B8;margin:0 0 6px;'>Avg EV/Revenue multiple</p>"
                    "<p style='font-size:26px;font-weight:500;color:#0F172A;margin:0;'>" + str(round(_avg_mult, 1)) + "x</p>"
                    "</div>", unsafe_allow_html=True)
            with _sm2:
                st.markdown(
                    "<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:16px;'>"
                    "<p style='font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:#94A3B8;margin:0 0 6px;'>Median deal size</p>"
                    "<p style='font-size:26px;font-weight:500;color:#0F172A;margin:0;'>" + fmt_gbp(_med_deal) + "</p>"
                    "</div>", unsafe_allow_html=True)
            with _sm3:
                st.markdown(
                    "<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:8px;padding:16px;'>"
                    "<p style='font-size:10px;letter-spacing:0.08em;text-transform:uppercase;color:#94A3B8;margin:0 0 6px;'>Deal date range</p>"
                    "<p style='font-size:26px;font-weight:500;color:#0F172A;margin:0;'>" + str(min(_years)) + " – " + str(max(_years)) + "</p>"
                    "</div>", unsafe_allow_html=True)

            st.markdown("<div style='height:16px;'></div>", unsafe_allow_html=True)

            # Transactions table
            overline("RECENT TRANSACTIONS")
            _txn_df = pd.DataFrame([{
                "Target":         t["target"],
                "Acquirer":       t["acquirer"],
                "Year":           t["year"],
                "Deal size":      fmt_gbp(t["deal_size_gbp"]),
                "Revenue (est.)": fmt_gbp(t["revenue_gbp"]),
                "EV/Rev":         str(t["ev_rev_multiple"]) + "x",
                "Description":    t["detail"],
            } for t in _txns])
            st.dataframe(_txn_df, use_container_width=True, hide_index=True)

            # Positioning analysis
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            overline("WHERE DOES " + str(company).upper() + " SIT?")
            _company_mult = (_blend["base"] / _revenue) if _revenue > 0 else 0
            _min_mult = min(_multiples)
            _max_mult = max(_multiples)
            if _company_mult < _avg_mult * 0.9:
                _position = "This implies the company is valued below recent transaction averages — potential upside in an M&A scenario."
            elif _company_mult > _avg_mult * 1.1:
                _position = "This implies a premium to recent transactions — a strategic acquirer would need a compelling rationale for the premium."
            else:
                _position = "This is broadly in line with recent comparable transactions."
            st.info(
                "At the base case valuation of " + fmt_gbp(_blend["base"]) + ", " + str(company)
                + " implies an EV/Revenue multiple of " + str(round(_company_mult, 1)) + "x. "
                "Comparable " + str(_sector) + " transactions have ranged from " + str(round(_min_mult, 1))
                + "x to " + str(round(_max_mult, 1)) + "x with an average of " + str(round(_avg_mult, 1)) + "x. "
                + _position
            )

        # ──────────────────────────────────────────────────────────────────
        # INVESTOR OUTREACH
        # ──────────────────────────────────────────────────────────────────
        elif tab == "Investor outreach":
            section_header("Investor outreach",
                           "Personalised cold email templates for your top 5 investor matches")

            st.info("These templates are pre-filled with your actual metrics. Before sending: personalise the opening line by referencing a specific portfolio company or recent investment, address a named partner not a generic inbox, and attach your pitch deck.")

            # Get matches from session state or compute them
            _outreach_matches = st.session_state.get("vc_matches", [])
            if not _outreach_matches:
                _vc_df_o = pd.read_csv(os.path.join(os.path.dirname(__file__), "data", "vc_database.csv"))
                _vc_scored_o = score_investors(_vc_df_o, _sector, _stage, _geography, _revenue)
                _top5_o = _vc_scored_o.head(5)
                _outreach_matches = [
                    MatchResult(
                        name=r["Investor"], score=int(r["Score /100"]),
                        sector_score=int(r["Sector Fit"]), stage_score=int(r["Stage Fit"]),
                        geo_score=int(r["Geo Fit"]), cheque_score=int(r["Cheque Fit"]),
                        sector_rationale=r["Sector Rationale"], stage_rationale=r["Stage Rationale"],
                        geo_rationale=r["Geo Rationale"], cheque_rationale=r["Cheque Rationale"],
                        notable_portfolio=r["Notable Portfolio"], cheque_range=r["Cheque Range"],
                        website=r["Website"], description=r["Description"],
                        investor_type=r["Type"],
                    )
                    for _, r in _top5_o.iterrows()
                ]

            # Get raise mid-point for email
            _raise_mid = _burn * 18  # fallback: 18-month runway raise

            for _rank, _match in enumerate(_outreach_matches[:5], start=1):
                _subj, _body = _generate_cold_email(
                    _match, company, _sector, _stage, _revenue,
                    _growth_pct, _ebitda_margin, _geography,
                    _blend.get("base", 0), _raise_mid,
                )
                _hc1, _hc2 = st.columns([4, 1])
                with _hc1:
                    st.markdown("**No." + str(_rank) + " " + str(_match.name) + "**")
                with _hc2:
                    st.markdown("Score: **" + str(_match.score) + "/100**")
                st.markdown("**Subject:** " + _subj)
                st.text_area(
                    label="",
                    value=_body,
                    height=280,
                    key="email_" + str(_rank),
                )
                if st.button("Copied!", key="copy_" + str(_rank)):
                    st.write("Paste directly into your email client.")
                if _rank < 5:
                    st.divider()

        # ──────────────────────────────────────────────────────────────────
        # INVESTMENT MEMO
        # ──────────────────────────────────────────────────────────────────


# ── Page router ───────────────────────────────────────────────────────────────
if st.session_state.page == "landing":
    render_landing()
elif st.session_state.page == "home":
    render_home()
else:
    render_results()
