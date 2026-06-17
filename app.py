"""AI Deal Advisor — Streamlit app entry point."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import os

from modules.valuation import (
    CompanyInputs,
    dcf_valuation,
    comparable_valuation,
    blended_valuation,
    five_year_projection,
)
from modules.vc_matching import score_investors

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Deal Advisor",
    page_icon="⚡",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── CSS — light theme ─────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
      /* Hide Streamlit chrome */
      #MainMenu, footer, header { visibility: hidden; }
      [data-testid="stSidebar"] { display: none !important; }

      /* Page background */
      html, body,
      [data-testid="stAppViewContainer"],
      [data-testid="stApp"],
      [data-testid="stAppViewBlockContainer"],
      .main { background-color: #F8FAFC !important; }

      /* Global font + colour */
      * { font-family: 'Inter', 'Segoe UI', sans-serif !important; color: #0F172A; }

      /* Headings */
      h1, h2, h3 { font-weight: 500 !important; color: #0F172A !important; }

      /* Bordered card containers */
      [data-testid="stVerticalBlockBorderWrapper"] > div:first-child {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
      }

      /* Text inputs / number inputs */
      .stTextInput > div > div > input,
      .stNumberInput > div > div > input {
        background: #F1F5F9 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
        font-size: 14px !important;
      }
      .stTextInput > div > div > input:focus,
      .stNumberInput > div > div > input:focus {
        border-color: #1D4ED8 !important;
        box-shadow: 0 0 0 3px rgba(29,78,216,0.12) !important;
      }

      /* Selectboxes */
      .stSelectbox [data-baseweb="select"] > div {
        background: #F1F5F9 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        color: #0F172A !important;
        font-size: 14px !important;
      }

      /* Labels */
      label, .stMarkdown p { color: #0F172A !important; font-size: 13px !important; }

      /* Buttons (primary) */
      .stButton > button {
        background: #1D4ED8 !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        padding: 10px 32px !important;
        letter-spacing: 0.02em !important;
        transition: background 0.15s ease !important;
      }
      .stButton > button:hover { background: #1E40AF !important; }

      /* Tabs */
      [data-testid="stTabs"] [data-baseweb="tab-list"] {
        background: transparent !important;
        border-bottom: 1px solid #E2E8F0 !important;
        gap: 4px !important;
        padding-bottom: 0 !important;
      }
      [data-testid="stTabs"] [data-baseweb="tab"] {
        background: #FFFFFF !important;
        color: #64748B !important;
        border: 1px solid #E2E8F0 !important;
        border-bottom: none !important;
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 18px !important;
        font-size: 13px !important;
        font-weight: 400 !important;
      }
      [data-testid="stTabs"] [aria-selected="true"] {
        background: #1D4ED8 !important;
        color: #ffffff !important;
        border-color: #1D4ED8 !important;
      }
      [data-testid="stTabs"] [data-baseweb="tab-highlight"] {
        background: transparent !important;
        height: 0 !important;
      }

      /* Metric cards */
      [data-testid="metric-container"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 16px !important;
      }
      [data-testid="stMetricValue"] {
        color: #0F172A !important;
        font-size: 22px !important;
        font-weight: 500 !important;
      }
      [data-testid="stMetricLabel"] {
        color: #94A3B8 !important;
        font-size: 11px !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
      }

      /* DataFrames */
      [data-testid="stDataFrame"] {
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
      }

      /* Divider */
      hr { border-color: #E2E8F0 !important; margin: 1.25rem 0 !important; }

      /* Expanders */
      [data-testid="stExpander"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
      }

      /* Spinner */
      [data-testid="stSpinner"] { color: #1D4ED8 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Design tokens ─────────────────────────────────────────────────────────────
BLUE       = "#1D4ED8"
BLUE_LIGHT = "#93C5FD"
BLUE_DARK  = "#1E40AF"
GREEN      = "#22C55E"
AMBER      = "#F59E0B"
RED        = "#EF4444"

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#FFFFFF",
    plot_bgcolor="#FFFFFF",
    font=dict(color="#0F172A", family="Inter, Segoe UI, sans-serif"),
    legend=dict(bgcolor="#FFFFFF", bordercolor="#E2E8F0"),
    margin=dict(l=20, r=20, t=40, b=20),
)
AXIS_STYLE = dict(gridcolor="#F1F5F9", linecolor="#E2E8F0", tickcolor="#94A3B8", color="#64748B")


# ── Helper functions ──────────────────────────────────────────────────────────
def fmt_gbp(val: float) -> str:
    return f"£{val / 1_000_000:.1f}m"


def overline(text: str) -> None:
    st.markdown(
        f"<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
        f"color:#64748B;margin:0 0 10px;font-weight:400;'>{text}</p>",
        unsafe_allow_html=True,
    )


def callout(text: str, kind: str = "info") -> None:
    border_map = {"info": BLUE, "warning": AMBER, "danger": RED, "success": GREEN}
    bc = border_map.get(kind, BLUE)
    st.markdown(
        f"<div style='background:#F8FAFC;border-left:3px solid {bc};border-radius:0 8px 8px 0;"
        f"padding:14px 18px;margin:10px 0;'>"
        f"<p style='font-size:14px;color:#0F172A;margin:0;line-height:1.6;'>{text}</p>"
        f"</div>",
        unsafe_allow_html=True,
    )


def valuation_cards_html(low: float, base: float, high: float) -> str:
    def card(label, val, primary=False):
        border  = f"2px solid {BLUE}" if primary else "1px solid #E2E8F0"
        lc = BLUE if primary else "#94A3B8"
        vc = BLUE if primary else "#64748B"
        return (
            f"<div style='background:#FFFFFF;border:{border};border-radius:12px;"
            f"padding:20px 16px;text-align:center;'>"
            f"<p style='font-size:11px;color:{lc};margin:0;text-transform:uppercase;"
            f"letter-spacing:0.06em;font-weight:400;'>{label}</p>"
            f"<p style='font-size:22px;font-weight:500;color:{vc};margin:6px 0 0;'>{fmt_gbp(val)}</p>"
            f"</div>"
        )
    return (
        "<div style='display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin:16px 0;'>"
        + card("Conservative", low)
        + card("Base case", base, primary=True)
        + card("Optimistic", high)
        + "</div>"
    )


# ── Session state defaults ────────────────────────────────────────────────────
_DEFAULTS = {
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
    "analysis_run": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


def _load_preset(name: str) -> None:
    presets = {
        "FinTechX": dict(inp_company="FinTechX",  inp_sector="FinTech",    inp_stage="Series A",
                         inp_geo="UK", inp_revenue=4_000_000,  inp_growth=80,  inp_ebitda=15),
        "CloudBase": dict(inp_company="CloudBase", inp_sector="SaaS",       inp_stage="Series B",
                          inp_geo="UK", inp_revenue=12_000_000, inp_growth=55,  inp_ebitda=8),
        "HealthOS":  dict(inp_company="HealthOS",  inp_sector="HealthTech", inp_stage="Seed",
                          inp_geo="UK", inp_revenue=800_000,   inp_growth=120, inp_ebitda=-30),
    }
    for k, v in presets[name].items():
        st.session_state[k] = v
    st.session_state.analysis_run = False  # reset so user clicks Run again


# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
st.markdown(
    f"<div style='text-align:center;padding:32px 0 20px;border-bottom:1px solid #E2E8F0;"
    f"margin-bottom:24px;'>"
    f"<div style='display:inline-flex;align-items:center;gap:10px;'>"
    f"<span style='font-size:24px;'>⚡</span>"
    f"<span style='font-size:28px;font-weight:500;color:#0F172A;'>AI Deal Advisor</span>"
    f"</div>"
    f"<p style='font-size:14px;color:#64748B;margin:6px 0 0;font-size:13px;'>"
    f"Institutional-grade analysis at junior analyst speed</p>"
    f"</div>",
    unsafe_allow_html=True,
)

# ── Demo company buttons ──────────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
    "color:#94A3B8;text-align:center;margin:0 0 8px;'>Quick-load demo company</p>",
    unsafe_allow_html=True,
)
_d1, _d2, _d3 = st.columns(3)
_d1.button("⚡ FinTechX",  on_click=_load_preset, args=("FinTechX",),  use_container_width=True)
_d2.button("☁️ CloudBase", on_click=_load_preset, args=("CloudBase",), use_container_width=True)
_d3.button("🏥 HealthOS",  on_click=_load_preset, args=("HealthOS",),  use_container_width=True)

st.markdown("<div style='margin-bottom:20px;'></div>", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════
# SECTION 1 — COMPANY PROFILE
# ═══════════════════════════════════════════════════════════════════
with st.container(border=True):
    overline("🏢  Company profile")
    _c1, _c2, _c3, _c4 = st.columns(4)
    company_name = _c1.text_input("Company name",  key="inp_company")
    sector       = _c2.selectbox("Sector",
        ["FinTech", "SaaS", "HealthTech", "EdTech", "CleanTech",
         "E-Commerce", "DeepTech", "Cybersecurity", "MarketPlace", "Other"],
        key="inp_sector",
    )
    stage        = _c3.selectbox("Stage",
        ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Growth"],
        key="inp_stage",
    )
    geography    = _c4.selectbox("Geography",
        ["UK", "Europe", "US", "Asia", "Global", "MENA", "LatAm"],
        key="inp_geo",
    )

# ═══════════════════════════════════════════════════════════════════
# SECTION 2 — FINANCIALS
# ═══════════════════════════════════════════════════════════════════
with st.container(border=True):
    overline("📊  Financials")
    _f1, _f2, _f3 = st.columns(3)
    revenue      = _f1.number_input("Annual Revenue (£)", min_value=0,    key="inp_revenue", step=100_000, format="%d")
    growth_pct   = _f2.number_input("Revenue Growth (%)", min_value=-100, key="inp_growth",  step=5)
    ebitda_margin= _f3.number_input("EBITDA Margin (%)",  min_value=-100, key="inp_ebitda",  step=1)

# ═══════════════════════════════════════════════════════════════════
# SECTION 3 — OPTIONAL: RUNWAY & CAPITAL STRUCTURE
# ═══════════════════════════════════════════════════════════════════
with st.expander("Optional: Runway & Capital Structure"):
    overline("💰  Cash & debt")
    _o1, _o2, _o3, _o4 = st.columns(4)
    cash       = _o1.number_input("Cash on hand (£)",  min_value=0, key="inp_cash",  step=100_000,  format="%d")
    burn       = _o2.number_input("Monthly burn (£)",  min_value=0, key="inp_burn",  step=10_000,   format="%d")
    total_debt = _o3.number_input("Total debt (£)",    min_value=0, key="inp_debt",  step=50_000,   format="%d")
    cost_of_debt=_o4.number_input("Cost of debt (%)",  min_value=1, key="inp_cod",   step=1, max_value=20)
    st.markdown(
        "<p style='font-size:12px;color:#94A3B8;margin:4px 0 0;'>"
        "Leave debt at £0 if the company has no meaningful debt — equity-only assumption will apply.</p>",
        unsafe_allow_html=True,
    )

# ═══════════════════════════════════════════════════════════════════
# SECTION 4 — SETTINGS
# ═══════════════════════════════════════════════════════════════════
with st.expander("Settings"):
    overline("🔑  API keys")
    openai_key = st.text_input(
        "OpenAI API Key (enables Memo & M&A tabs)",
        key="inp_openai",
        type="password",
        placeholder="sk-...",
    )

st.markdown("<div style='margin:12px 0;'></div>", unsafe_allow_html=True)

# ── Derived sidebar-equivalent values ────────────────────────────────────────
runway_months = int(cash / burn) if burn > 0 else 999

# ── Run Analysis button ───────────────────────────────────────────────────────
_btn_l, _btn_m, _btn_r = st.columns([1, 2, 1])
with _btn_m:
    if st.button("⚡  Run analysis", use_container_width=True):
        st.session_state.analysis_run = True
    if st.session_state.analysis_run:
        st.markdown(
            "<p style='font-size:11px;color:#94A3B8;text-align:center;margin:4px 0 0;'>"
            "Results auto-update as you change inputs above</p>",
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════════
# RESULTS (shown only after Run Analysis)
# ═══════════════════════════════════════════════════════════════════
if not st.session_state.analysis_run:
    st.stop()

# ── Compute valuations ────────────────────────────────────────────────────────
company_inputs = CompanyInputs(
    stage=stage,
    total_debt_gbp=float(total_debt) if total_debt > 0 else None,
    cost_of_debt_pct=float(cost_of_debt),
)
dcf   = dcf_valuation(revenue, growth_pct, ebitda_margin, company_inputs)
comps = comparable_valuation(revenue, sector)
blend = blended_valuation(dcf, comps)

st.markdown("<hr/>", unsafe_allow_html=True)

# ── Headline valuation cards ──────────────────────────────────────────────────
st.markdown(
    "<p style='font-size:11px;letter-spacing:0.08em;text-transform:uppercase;"
    f"color:{BLUE};margin:0 0 4px;font-weight:400;'>📈  Results — Blended valuation</p>",
    unsafe_allow_html=True,
)
st.markdown(
    valuation_cards_html(blend["low"], blend["base"], blend["high"]),
    unsafe_allow_html=True,
)

# ── DCF + Comparables summary row ─────────────────────────────────────────────
_s1, _s2 = st.columns(2)
with _s1:
    st.markdown(
        f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;padding:16px;'>"
        f"<p style='font-size:11px;color:#94A3B8;margin:0;text-transform:uppercase;letter-spacing:0.06em;'>DCF valuation</p>"
        f"<p style='font-size:20px;font-weight:500;color:#0F172A;margin:6px 0 4px;'>{fmt_gbp(dcf['base'])}</p>"
        f"<p style='font-size:12px;color:#64748B;margin:0;'>WACC {blend['wacc']*100:.1f}% · 5yr projection</p>"
        f"</div>",
        unsafe_allow_html=True,
    )
with _s2:
    sector_multiples = {
        "FinTech": 7.0, "SaaS": 9.0, "HealthTech": 6.0, "EdTech": 4.5,
        "CleanTech": 5.5, "E-Commerce": 3.0, "DeepTech": 8.0,
        "Cybersecurity": 9.5, "MarketPlace": 4.0, "Other": 4.0,
    }
    mult = sector_multiples.get(sector, 4.0)
    st.markdown(
        f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;padding:16px;'>"
        f"<p style='font-size:11px;color:#94A3B8;margin:0;text-transform:uppercase;letter-spacing:0.06em;'>Comparable multiples</p>"
        f"<p style='font-size:20px;font-weight:500;color:#0F172A;margin:6px 0 4px;'>{fmt_gbp(comps['base'])}</p>"
        f"<p style='font-size:12px;color:#64748B;margin:0;'>{mult:.1f}x EV/Rev · {sector} sector</p>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin:16px 0;'></div>", unsafe_allow_html=True)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_val, tab_fund, tab_vc, tab_memo, tab_ma = st.tabs(
    ["Valuation", "Fundraising", "VC matching", "Investment memo", "M&A analysis"]
)


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — VALUATION
# ═══════════════════════════════════════════════════════════════════
with tab_val:
    st.markdown(f"<h2 style='font-size:20px;margin:16px 0 4px;'>Valuation analysis</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='font-size:14px;color:#64748B;margin:0 0 16px;'>"
        f"£{revenue/1e6:.1f}m revenue · {growth_pct}% growth · {ebitda_margin}% EBITDA margin</p>",
        unsafe_allow_html=True,
    )

    # WACC callout
    wacc_kind = "info" if "equity-only" in blend["wacc_method"].lower() else "success"
    callout(f"⚙️ <b>WACC: {blend['wacc']*100:.1f}%</b> — {blend['wacc_method']}", kind=wacc_kind)

    st.markdown("---")

    # DCF + Comps charts
    col_l, col_r = st.columns(2)

    with col_l:
        overline("DCF valuation — three scenarios")
        dcf_df = pd.DataFrame({
            "Scenario": ["🔴 Conservative", "🟡 Base", "🟢 Optimistic"],
            "Value (£m)": [round(dcf["low"]/1e6,1), round(dcf["base"]/1e6,1), round(dcf["high"]/1e6,1)],
        })
        st.dataframe(dcf_df, hide_index=True, use_container_width=True)

        fig_dcf = go.Figure(go.Bar(
            x=["Conservative", "Base", "Optimistic"],
            y=[dcf["low"]/1e6, dcf["base"]/1e6, dcf["high"]/1e6],
            marker_color=[BLUE_LIGHT, BLUE, BLUE_DARK],
            text=[f"£{v/1e6:.1f}m" for v in [dcf["low"], dcf["base"], dcf["high"]]],
            textposition="outside",
        ))
        fig_dcf.update_layout(title="DCF Scenarios (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
        st.plotly_chart(fig_dcf, use_container_width=True)

    with col_r:
        overline("Comparable multiples — three scenarios")
        sector_mult_table = {
            "FinTech": {"low":4.0,"base":7.0,"high":12.0}, "SaaS": {"low":5.0,"base":9.0,"high":15.0},
            "HealthTech": {"low":3.5,"base":6.0,"high":10.0}, "EdTech": {"low":2.5,"base":4.5,"high":8.0},
            "CleanTech": {"low":3.0,"base":5.5,"high":9.0}, "E-Commerce": {"low":1.5,"base":3.0,"high":5.5},
            "DeepTech": {"low":4.0,"base":8.0,"high":14.0}, "Cybersecurity": {"low":5.0,"base":9.5,"high":16.0},
            "MarketPlace": {"low":2.0,"base":4.0,"high":7.0}, "Other": {"low":2.0,"base":4.0,"high":7.0},
        }
        m = sector_mult_table.get(sector, sector_mult_table["Other"])
        comps_df = pd.DataFrame({
            "Scenario": ["🔴 Conservative", "🟡 Base", "🟢 Optimistic"],
            "EV/Rev": [m["low"], m["base"], m["high"]],
            "Value (£m)": [round(comps["low"]/1e6,1), round(comps["base"]/1e6,1), round(comps["high"]/1e6,1)],
        })
        st.dataframe(comps_df, hide_index=True, use_container_width=True)

        fig_comps = go.Figure(go.Bar(
            x=["Conservative", "Base", "Optimistic"],
            y=[comps["low"]/1e6, comps["base"]/1e6, comps["high"]/1e6],
            marker_color=[BLUE_LIGHT, BLUE, BLUE_DARK],
            text=[f"£{v/1e6:.1f}m" for v in [comps["low"], comps["base"], comps["high"]]],
            textposition="outside",
        ))
        fig_comps.update_layout(title="Comparable Multiples (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
        st.plotly_chart(fig_comps, use_container_width=True)

    st.markdown("---")
    overline("Blended valuation — DCF 50% / Comparables 50%")

    fig_blend = go.Figure()
    scenarios = ["Conservative", "Base", "Optimistic"]
    fig_blend.add_trace(go.Bar(name="DCF",          x=scenarios, y=[dcf["low"]/1e6,   dcf["base"]/1e6,   dcf["high"]/1e6],   marker_color=BLUE_LIGHT))
    fig_blend.add_trace(go.Bar(name="Comparables",  x=scenarios, y=[comps["low"]/1e6, comps["base"]/1e6, comps["high"]/1e6], marker_color=BLUE))
    fig_blend.add_trace(go.Bar(name="Blended",      x=scenarios, y=[blend["low"]/1e6, blend["base"]/1e6, blend["high"]/1e6], marker_color=BLUE_DARK))
    fig_blend.update_layout(barmode="group", title="Blended Valuation (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
    st.plotly_chart(fig_blend, use_container_width=True)

    st.markdown("---")
    overline("5-year projection")

    proj_df = five_year_projection(revenue, growth_pct, ebitda_margin)
    st.dataframe(proj_df, hide_index=True, use_container_width=True)

    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["Revenue (£m)"],
        mode="lines+markers+text", name="Revenue",
        line=dict(color=BLUE, width=3),
        text=[f"£{v}m" for v in proj_df["Revenue (£m)"]],
        textposition="top center",
    ))
    fig_proj.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["EBITDA (£m)"],
        mode="lines+markers+text", name="EBITDA",
        line=dict(color=BLUE_LIGHT, width=2, dash="dot"),
        text=[f"£{v}m" for v in proj_df["EBITDA (£m)"]],
        textposition="bottom center",
    ))
    fig_proj.update_layout(title="5-Year Revenue & EBITDA (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
    st.plotly_chart(fig_proj, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — FUNDRAISING
# ═══════════════════════════════════════════════════════════════════
with tab_fund:
    st.markdown("<h2 style='font-size:20px;margin:16px 0 16px;'>Fundraising analysis</h2>", unsafe_allow_html=True)

    # Runway gauge
    gauge_color = RED if runway_months < 12 else GREEN if runway_months >= 18 else AMBER
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=runway_months,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Runway (months)", "font": {"color": "#64748B", "size": 14}},
        gauge={
            "axis": {"range": [0, 36], "tickcolor": "#94A3B8", "tickfont": {"color": "#94A3B8"}},
            "bar": {"color": gauge_color},
            "bgcolor": "#F1F5F9",
            "bordercolor": "#E2E8F0",
            "steps": [
                {"range": [0, 12],  "color": "#FEE2E2"},
                {"range": [12, 18], "color": "#FEF3C7"},
                {"range": [18, 36], "color": "#DCFCE7"},
            ],
            "threshold": {"line": {"color": BLUE, "width": 3}, "value": 18},
        },
        number={"font": {"color": gauge_color, "size": 48}},
    ))
    fig_gauge.update_layout(paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
                            font=dict(color="#0F172A"), height=280,
                            margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("---")

    recommended_raise  = burn * 18
    dilution_estimate  = 0.20 if stage == "Seed" else 0.15 if stage == "Series A" else 0.12
    post_money         = blend["base"] + recommended_raise

    _m1, _m2, _m3 = st.columns(3)
    _m1.metric("Recommended raise", fmt_gbp(recommended_raise), help="18 months runway at current burn")
    _m2.metric("Estimated dilution", f"{dilution_estimate*100:.0f}%", help="Typical for this stage")
    _m3.metric("Post-money (base)",  fmt_gbp(post_money))

    st.markdown("---")
    overline("Suggested use of funds")

    categories = ["Engineering & Product", "Sales & Marketing", "Operations", "G&A / Legal", "Reserve"]
    weights    = [0.40, 0.30, 0.15, 0.10, 0.05]
    amounts    = [recommended_raise * w for w in weights]

    fig_pie = go.Figure(go.Pie(
        labels=categories, values=amounts, hole=0.45,
        marker=dict(colors=[BLUE, BLUE_LIGHT, BLUE_DARK, "#60A5FA", "#BFDBFE"]),
        textinfo="label+percent", textfont=dict(color="#0F172A", size=12),
    ))
    fig_pie.update_layout(title=f"Use of {fmt_gbp(recommended_raise)} raise",
                          showlegend=False, **PLOTLY_LAYOUT)
    st.plotly_chart(fig_pie, use_container_width=True)

    uof_df = pd.DataFrame({
        "Category":   categories,
        "Allocation": [f"{w*100:.0f}%" for w in weights],
        "Amount (£)": [f"£{a:,.0f}" for a in amounts],
    })
    st.dataframe(uof_df, hide_index=True, use_container_width=True)

    st.markdown("---")
    overline("Cash runway bridge")

    _months     = list(range(0, min(runway_months + 1, 37)))
    _cash_vals  = [max(cash - burn * mo, 0) for mo in _months]
    fig_burn = go.Figure()
    fig_burn.add_trace(go.Scatter(
        x=_months, y=[c/1e6 for c in _cash_vals],
        fill="tozeroy", mode="lines",
        line=dict(color=BLUE, width=2),
        fillcolor="rgba(29,78,216,0.08)",
        name="Cash (£m)",
    ))
    fig_burn.add_vline(x=12, line_dash="dot", line_color=RED,
                       annotation_text="12-month warning", annotation_font_color=RED)
    if runway_months < 36:
        fig_burn.add_vline(x=runway_months, line_dash="dash", line_color=AMBER,
                           annotation_text=f"Zero cash (M{runway_months})",
                           annotation_font_color=AMBER)
    fig_burn.update_layout(
        title="Cash balance over time (£m)",
        xaxis=dict(title="Month", **AXIS_STYLE),
        yaxis=dict(title="£m", **AXIS_STYLE),
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_burn, use_container_width=True)

    st.markdown("---")
    overline("Fundraising readiness checklist")
    tips = [
        ("Pitch deck ready",     runway_months > 6,   "Start fundraise now" if runway_months > 6 else "Start immediately"),
        ("Runway > 18 months",   runway_months >= 18, f"{runway_months} months remaining" if runway_months >= 18 else f"Only {runway_months} months — raise urgently"),
        ("Revenue traction",     revenue > 0,         fmt_gbp(revenue) + " ARR"),
        ("High growth rate",     growth_pct >= 50,    f"{growth_pct}% YoY growth"),
        ("EBITDA visibility",    ebitda_margin >= 0,  f"{ebitda_margin}% margin"),
    ]
    for label, ok, note in tips:
        icon  = "✅" if ok else "⚠️"
        kind  = "success" if ok else "warning"
        callout(f"{icon} <b>{label}</b> — {note}", kind=kind)


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — VC MATCHING
# ═══════════════════════════════════════════════════════════════════
with tab_vc:
    st.markdown(f"<h2 style='font-size:20px;margin:16px 0 4px;'>VC matching</h2>", unsafe_allow_html=True)
    st.markdown(
        f"<p style='font-size:14px;color:#64748B;margin:0 0 16px;'>"
        f"Scoring investors for <b style='color:#0F172A;'>{company_name}</b> · {sector} · {stage} · {geography}</p>",
        unsafe_allow_html=True,
    )

    csv_path = os.path.join(os.path.dirname(__file__), "data", "vc_database.csv")
    try:
        vc_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.error(f"VC database not found at {csv_path}")
        st.stop()

    scored = score_investors(vc_df, sector, stage, geography, revenue)
    top10  = scored.head(10).copy()

    callout(f"<b>{len(scored)} investors</b> analysed · Showing top 10 matches", kind="info")

    st.markdown("---")
    overline("Match scores — top 10")

    fig_vc = go.Figure(go.Bar(
        x=top10["Score /100"],
        y=top10["Investor"],
        orientation="h",
        marker=dict(
            color=top10["Score /100"],
            colorscale=[[0, BLUE_LIGHT], [1.0, BLUE_DARK]],
            showscale=False,
        ),
        text=[f"{s}/100" for s in top10["Score /100"]],
        textposition="outside",
    ))
    fig_vc.update_layout(
        title="Top 10 investor match scores",
        xaxis=dict(title="Score /100", **AXIS_STYLE),
        yaxis=dict(autorange="reversed", **AXIS_STYLE),
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_vc, use_container_width=True)

    st.markdown("---")
    overline("Investor detail table")
    display_cols = ["Investor", "Type", "Score /100", "Sector Fit",
                    "Stage Fit", "Geo Fit", "Cheque Fit",
                    "Min Cheque (£m)", "Max Cheque (£m)"]
    st.dataframe(top10[display_cols].reset_index(drop=True),
                 hide_index=True, use_container_width=True)

    st.markdown("---")
    overline("Score breakdown — top 5 investors")
    st.markdown(
        "<p style='font-size:12px;color:#64748B;margin:0 0 12px;'>"
        "Sector <b>/40</b> · Stage <b>/30</b> · Geography <b>/20</b> · Cheque size <b>/10</b></p>",
        unsafe_allow_html=True,
    )

    radar_traces = []
    _colors = [BLUE, BLUE_LIGHT, BLUE_DARK, "#60A5FA", "#BFDBFE"]
    for i, (_, row) in enumerate(top10.head(5).iterrows()):
        radar_traces.append(go.Scatterpolar(
            r=[row["Sector Fit"], row["Stage Fit"], row["Geo Fit"], row["Cheque Fit"]],
            theta=["Sector (40)", "Stage (30)", "Geo (20)", "Cheque (10)"],
            fill="toself", name=row["Investor"],
            line=dict(color=_colors[i]),
            fillcolor=_colors[i].replace("#", "rgba(").replace(")", ",0.08)") if False else "rgba(0,0,0,0)",
        ))

    fig_radar = go.Figure(radar_traces)
    fig_radar.update_layout(
        polar=dict(
            bgcolor="#F8FAFC",
            radialaxis=dict(visible=True, range=[0, 40], color="#94A3B8", gridcolor="#E2E8F0"),
            angularaxis=dict(color="#64748B", gridcolor="#E2E8F0"),
        ),
        title="Score breakdown — top 5 investors",
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("---")
    overline("Quick links")
    for _, row in top10.iterrows():
        url = row.get("Website", "")
        if url:
            st.markdown(
                f"[🔗 {row['Investor']}]({url}) — **{row['Score /100']}/100**"
            )


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — MEMO
# ═══════════════════════════════════════════════════════════════════
with tab_memo:
    st.markdown("<h2 style='font-size:20px;margin:16px 0 16px;'>Investment memo</h2>", unsafe_allow_html=True)

    if not openai_key:
        st.markdown(
            f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;"
            f"padding:48px 32px;text-align:center;margin:24px 0;'>"
            f"<div style='font-size:40px;'>🔑</div>"
            f"<h3 style='font-size:18px;font-weight:500;color:#1D4ED8;margin:16px 0 8px;'>OpenAI API key required</h3>"
            f"<p style='font-size:14px;color:#64748B;margin:0;'>Add your OpenAI API key to enable AI-generated investment memos.</p>"
            f"<p style='font-size:13px;color:#94A3B8;margin:8px 0 0;'>Open the <b>Settings</b> expander above and enter your key.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        try:
            import openai
            from prompts.prompts import MEMO_SYSTEM, MEMO_USER
            if st.button("Generate investment memo"):
                with st.spinner("Generating with GPT-4o…"):
                    client = openai.OpenAI(api_key=openai_key)
                    prompt = MEMO_USER.format(
                        company_name=company_name, sector=sector, stage=stage,
                        geography=geography, revenue=revenue, growth=growth_pct,
                        ebitda_margin=ebitda_margin, cash=cash, burn=burn,
                        valuation=blend["base"]/1e6,
                    )
                    resp = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": MEMO_SYSTEM},
                                  {"role": "user",   "content": prompt}],
                        max_tokens=1200,
                    )
                    st.markdown(resp.choices[0].message.content)
        except ImportError:
            st.error("openai package not installed. Run: pip install openai")
        except Exception as e:
            st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════════════
# TAB 5 — M&A
# ═══════════════════════════════════════════════════════════════════
with tab_ma:
    st.markdown("<h2 style='font-size:20px;margin:16px 0 16px;'>M&A analysis</h2>", unsafe_allow_html=True)

    if not openai_key:
        st.markdown(
            f"<div style='background:#FFFFFF;border:1px solid #E2E8F0;border-radius:12px;"
            f"padding:48px 32px;text-align:center;margin:24px 0;'>"
            f"<div style='font-size:40px;'>🔑</div>"
            f"<h3 style='font-size:18px;font-weight:500;color:#1D4ED8;margin:16px 0 8px;'>OpenAI API key required</h3>"
            f"<p style='font-size:14px;color:#64748B;margin:0;'>Add your OpenAI API key to enable AI-powered M&A analysis.</p>"
            f"<p style='font-size:13px;color:#94A3B8;margin:8px 0 0;'>Open the <b>Settings</b> expander above and enter your key.</p>"
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        try:
            import openai
            from prompts.prompts import MA_SYSTEM, MA_USER
            if st.button("Generate M&A analysis"):
                with st.spinner("Generating with GPT-4o…"):
                    client = openai.OpenAI(api_key=openai_key)
                    prompt = MA_USER.format(
                        company_name=company_name, sector=sector, stage=stage,
                        revenue=revenue, growth=growth_pct,
                        ebitda_margin=ebitda_margin, valuation=blend["base"]/1e6,
                    )
                    resp = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[{"role": "system", "content": MA_SYSTEM},
                                  {"role": "user",   "content": prompt}],
                        max_tokens=1200,
                    )
                    st.markdown(resp.choices[0].message.content)
        except ImportError:
            st.error("openai package not installed. Run: pip install openai")
        except Exception as e:
            st.error(f"Error: {e}")
