"""AI Deal Advisor — two-page Streamlit app."""

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

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Deal Advisor",
    page_icon="D",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS = {
    "page":         "home",
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


def _nav_btn(label: str, is_active: bool, key: str) -> bool:
    cls = "nav-active" if is_active else "nav-inactive"
    st.markdown(f'<div class="{cls}" style="display:none;"></div>', unsafe_allow_html=True)
    return st.button(label, key=key, use_container_width=True)


# ── Preset callbacks ──────────────────────────────────────────────────────────
def _load_preset(name: str) -> None:
    presets = {
        "FinTechX":  dict(inp_company="FinTechX",  inp_sector="FinTech",
                          inp_stage="Series A", inp_geo="UK",
                          inp_revenue=4_000_000,  inp_growth=80,  inp_ebitda=15,
                          inp_cash=1_500_000, inp_burn=200_000),
        "CloudBase": dict(inp_company="CloudBase", inp_sector="SaaS",
                          inp_stage="Series B", inp_geo="UK",
                          inp_revenue=12_000_000, inp_growth=55,  inp_ebitda=8,
                          inp_cash=3_000_000, inp_burn=400_000),
        "HealthOS":  dict(inp_company="HealthOS",  inp_sector="HealthTech",
                          inp_stage="Seed",     inp_geo="UK",
                          inp_revenue=800_000,   inp_growth=120, inp_ebitda=-30,
                          inp_cash=600_000, inp_burn=80_000),
    }
    for k, v in presets[name].items():
        st.session_state[k] = v


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
        f"<div style='width:28px;height:28px;background:{BLUE};border-radius:6px;"
        f"display:inline-flex;align-items:center;justify-content:center;"
        f"color:#fff;font-size:13px;font-weight:500;margin-right:10px;'>D</div>"
        f"<span id='nav-app-name' style='font-size:16px;font-weight:500;"
        f"color:{BLUE};cursor:pointer;'>&nbsp;</span>"
        f"{breadcrumb}"
        f"</div>"
        f"<span style='font-size:13px;color:#94A3B8;'>Settings</span>"
        f"</div>",
        unsafe_allow_html=True,
    )
    # Functional navigation button — styled via CSS to blend with nav bar
    st.markdown('<div class="topnav-link" style="display:none;"></div>',
                unsafe_allow_html=True)
    if st.button("AI Deal Advisor", key="topnav_home_btn"):
        st.session_state.page = "home"
        st.session_state.active_tab = "Valuation"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# HOME PAGE
# ══════════════════════════════════════════════════════════════════════════════
def render_home() -> None:
    render_topnav()

    # ── Demo quick-load ──
    st.markdown(
        "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        "color:#94A3B8;margin:0 0 8px;text-align:center;'>Quick-load demo</p>",
        unsafe_allow_html=True,
    )
    _qd1, _qd2, _qd3, _qd4, _qd5 = st.columns([3, 1, 1, 1, 3])
    for col, name in [(_qd2, "FinTechX"), (_qd3, "CloudBase"), (_qd4, "HealthOS")]:
        with col:
            st.markdown('<div class="demo-btn" style="display:none;"></div>',
                        unsafe_allow_html=True)
            if st.button(name, key=f"demo_{name}", use_container_width=True):
                _load_preset(name)
                st.rerun()

    st.markdown("<div style='height:24px;'></div>", unsafe_allow_html=True)

    # ── Page heading ──
    st.markdown(
        "<h1 style='font-size:28px;font-weight:500;color:#0F172A;margin:0 0 6px;'>"
        "Enter company details</h1>"
        "<p style='font-size:14px;color:#64748B;margin:0 0 24px;'>"
        "Provide financial and contextual information to generate your analysis</p>",
        unsafe_allow_html=True,
    )

    # ── Three input cards ──
    card1, card2, card3 = st.columns(3)

    with card1:
        with st.container(border=True):
            overline("Company profile")
            company_name = st.text_input("Name",   key="inp_company")
            sector = st.selectbox("Sector",
                ["FinTech", "SaaS", "HealthTech", "EdTech", "CleanTech",
                 "E-Commerce", "DeepTech", "Cybersecurity", "MarketPlace", "Other"],
                key="inp_sector",
            )
            stage = st.selectbox("Stage",
                ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Growth"],
                key="inp_stage",
            )

    with card2:
        with st.container(border=True):
            overline("Financials")
            revenue = st.number_input("Annual revenue (£)", min_value=0,
                                      key="inp_revenue", step=100_000, format="%d")
            growth_pct = st.number_input("Revenue growth (%)", min_value=-100,
                                         key="inp_growth", step=5)
            ebitda_margin = st.number_input("EBITDA margin (%)", min_value=-100,
                                            key="inp_ebitda", step=1)

    with card3:
        with st.container(border=True):
            overline("Capital position")
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
    show_dcf = st.checkbox("Show DCF assumption overrides", value=False)
    if show_dcf:
        st.markdown("**DCF assumptions**")
        _d1, _d2 = st.columns(2)
        with _d1:
            st.number_input("Tax rate (%)", min_value=0, max_value=50,
                            key="inp_tax_rate", step=1,
                            help="UK corporation tax is 25%")
            st.number_input("CapEx (% of EBITDA)", min_value=0, max_value=30,
                            key="inp_capex_pct", step=1,
                            help="Asset-light SaaS: 2-5%. Asset-heavy: 10-20%")
            st.number_input("NWC change (% of EBITDA)", min_value=0, max_value=20,
                            key="inp_nwc_pct", step=1,
                            help="Working capital requirements as % of EBITDA")
            st.number_input("D&A as % of revenue", min_value=0.0, max_value=20.0,
                            key="inp_da_pct", step=0.5,
                            help="Depreciation and amortisation as % of revenue. SaaS/software: 2-5%. Asset-heavy: 8-15%.")
        with _d2:
            st.number_input("Target EBITDA margin Year 5 (%)", min_value=-50, max_value=80,
                            key="inp_target_margin", step=1,
                            help="Expected mature margin at end of 5-year projection")
            st.number_input("Terminal growth rate (%)", min_value=0.0, max_value=8.0,
                            key="inp_terminal_g", step=0.5,
                            help="Long-run growth rate beyond Year 5. Typically 2-4% for developed markets.")
            _tv_method = st.radio(
                "Terminal value method",
                options=["Gordon Growth Model", "Exit Multiple (EV/EBITDA)"],
                key="inp_tv_method",
                help="Gordon Growth: assumes FCF grows at terminal rate forever. Exit Multiple: applies an industry EV/EBITDA multiple to Year 5 EBITDA — often more intuitive for early-stage companies.",
            )
            if _tv_method == "Exit Multiple (EV/EBITDA)":
                st.number_input("Exit EV/EBITDA multiple", min_value=1.0, max_value=40.0,
                                key="inp_exit_multiple", step=0.5,
                                help="Typical exit multiples by sector: SaaS 12-18x, FinTech 10-15x, HealthTech 8-14x, Marketplace 8-12x")

    # ── Section 5: WACC ──
    show_wacc = st.checkbox("Show WACC inputs", value=False)
    if show_wacc:
        st.markdown("**WACC inputs**")
        _use_custom = st.toggle("Enter WACC directly instead of using formula",
                                key="inp_use_custom_wacc")
        if _use_custom:
            st.number_input("WACC (%)", min_value=1.0, max_value=80.0,
                            key="inp_custom_wacc", step=0.5,
                            help="Enter your own WACC directly")
            st.caption("Overrides all formula inputs below")
        else:
            _w1, _w2 = st.columns(2)
            with _w1:
                st.number_input("Risk-free rate (%)", min_value=0.0, max_value=20.0,
                                key="inp_rfr", step=0.1,
                                help="UK 10-year gilt yield. Currently ~4.2% (June 2026)")
                st.number_input("Equity risk premium (%)", min_value=0.0, max_value=20.0,
                                key="inp_erp", step=0.1,
                                help="Damodaran UK ERP estimate. Typically 4.5-6.5%")
                st.number_input("Beta", min_value=0.0, max_value=5.0,
                                key="inp_beta", step=0.1,
                                help="Unlevered beta. FinTech ~1.2-1.5, SaaS ~1.1-1.4, HealthTech ~0.8-1.2. Leave blank to use stage-based rate.")
            with _w2:
                st.number_input("Cost of debt (%)", min_value=0.0, max_value=30.0,
                                key="inp_wacc_kd", step=0.5,
                                help="Interest rate on company debt")
                st.number_input("Total debt (£)", min_value=0,
                                key="inp_wacc_debt", step=50_000, format="%d")
            st.info(
                "WACC = (E/V x Ke) + (D/V x Kd x (1-t))\n"
                "Ke = Risk-free rate + Beta x Equity risk premium\n"
                "If beta is left blank, stage-based required return is used instead."
            )

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
    render_topnav(company=company)

    # ── Back link ──
    st.markdown('<div class="back-link" style="display:none;"></div>',
                unsafe_allow_html=True)
    if st.button("← Back to home", key="back_home_btn"):
        st.session_state.page = "home"
        st.rerun()

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

    _beta_val  = st.session_state.get("inp_beta", None)
    _tv_label  = st.session_state.get("inp_tv_method", "Gordon Growth Model")
    _tv_method = "exit_multiple" if _tv_label == "Exit Multiple (EV/EBITDA)" else "gordon_growth"
    _exit_mult = float(st.session_state.get("inp_exit_multiple", 12.0)) if _tv_method == "exit_multiple" else None
    _inputs = _NS(
        stage=_stage,
        tax_rate_pct=float(st.session_state.get("inp_tax_rate", 25)),
        capex_pct_of_ebitda=float(st.session_state.get("inp_capex_pct", 5)),
        nwc_pct_of_ebitda=float(st.session_state.get("inp_nwc_pct", 3)),
        da_pct_of_revenue=float(st.session_state.get("inp_da_pct", 3.0)),
        target_ebitda_margin_pct=float(st.session_state.get("inp_target_margin", 25)),
        terminal_growth_rate_pct=float(st.session_state.get("inp_terminal_g", 3.0)),
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
    )
    _dcf   = dcf_valuation(_revenue, _growth_pct, _ebitda_margin, _inputs)
    _comps = comparable_valuation(_revenue, _sector)
    _blend = blended_valuation(_dcf, _comps)
    _runway = int(_cash / _burn) if _burn > 0 else 999

    # ── Layout: sidebar (1) + main (4) ──
    nav_col, main_col = st.columns([1.2, 4], gap="large")

    # ── LEFT SIDEBAR NAV ──
    with nav_col:
        st.markdown(
            "<div style='background:#FFFFFF;border:1px solid #E2E8F0;"
            "border-radius:8px;padding:12px 8px;'>"
            "<p style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:#94A3B8;margin:0 0 10px;padding:0 8px;'>Analysis</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        NAV_ITEMS = [
            "Valuation",
            "Fundraising",
            "VC matching",
        ]
        for item in NAV_ITEMS:
            is_active = st.session_state.active_tab == item
            if _nav_btn(item, is_active, key=f"nav_{item.replace(' ', '_')}"):
                st.session_state.active_tab = item
                st.rerun()

        st.markdown(
            "<div style='border-top:1px solid #E2E8F0;margin:12px 8px;'></div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            "<p style='font-size:10px;letter-spacing:0.1em;text-transform:uppercase;"
            "color:#94A3B8;margin:0 0 6px;padding:0 8px;'>Settings</p>",
            unsafe_allow_html=True,
        )
        st.markdown("**API key**")
        st.text_input(
            "OpenAI API key",
            key="inp_openai",
            type="password",
            placeholder="sk-...",
            label_visibility="collapsed",
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
            st.info(
                "WACC: " + str(round(_blend["wacc"] * 100, 1)) + "% — " + str(_blend["wacc_method"])
                + "\n\n" + _tv_line
            )

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
            st.caption("Sensitivity shows enterprise value (DCF only) across WACC and terminal growth rate combinations. Higher WACC or lower terminal growth reduces value.")

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
            _fm1.metric("Recommended raise", fmt_gbp(_recommended),
                        help="18 months runway at current burn")
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
            st.caption("Assumes standard dilution at each round. Actual dilution depends on valuation and round size negotiated.")

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
                st.caption("Source: Beauhurst, Crunchbase, public announcements. Valuations are estimates where not publicly confirmed.")
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
                color = "#10B981" if pct >= 0.85 else "#EAB308" if pct >= 0.60 else "#EF4444"
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
                label = "No." + str(rank) + "  " + str(match.name) + "  |  " + str(match.score) + "/100"
                st.markdown("---")
                st.markdown("**" + label + "**")
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
        # INVESTMENT MEMO
        # ──────────────────────────────────────────────────────────────────


# ── Page router ───────────────────────────────────────────────────────────────
if st.session_state.page == "home":
    render_home()
else:
    render_results()
