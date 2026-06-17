"""AI Deal Advisor — Streamlit app entry point."""

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

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Deal Advisor",
    page_icon="💜",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (dark theme) ───────────────────────────────────────────────────
st.markdown(
    """
    <style>
      /* Global background */
      html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
          background-color: #0a0a0f !important;
          color: #e0e0e0 !important;
          font-family: 'Inter', 'Segoe UI', sans-serif !important;
      }
      [data-testid="stSidebar"] {
          background-color: #10101a !important;
          border-right: 1px solid #2a2a3a !important;
      }
      /* Remove default orange everywhere */
      .stSlider > div > div > div > div { background: #7c6af7 !important; }
      .stSelectbox [data-baseweb="select"] > div { background: #16162a !important; border-color: #2a2a3a !important; color: #e0e0e0 !important; }
      .stTextInput > div > div > input { background: #16162a !important; border-color: #2a2a3a !important; color: #e0e0e0 !important; }
      .stNumberInput > div > div > input { background: #16162a !important; border-color: #2a2a3a !important; color: #e0e0e0 !important; }
      /* Tabs */
      [data-testid="stTabs"] [data-baseweb="tab-list"] { background: #10101a !important; border-bottom: 1px solid #2a2a3a !important; gap: 4px; }
      [data-testid="stTabs"] [data-baseweb="tab"] { background: #16162a !important; color: #9090b0 !important; border-radius: 6px 6px 0 0 !important; border: none !important; padding: 10px 20px !important; }
      [data-testid="stTabs"] [aria-selected="true"] { background: #7c6af7 !important; color: #ffffff !important; }
      [data-testid="stTabs"] [data-baseweb="tab-highlight"] { background: #7c6af7 !important; }
      /* Metric cards */
      [data-testid="metric-container"] { background: #16162a !important; border: 1px solid #2a2a3a !important; border-radius: 10px !important; padding: 12px !important; }
      [data-testid="stMetricValue"] { color: #7c6af7 !important; font-size: 1.6rem !important; }
      [data-testid="stMetricLabel"] { color: #9090b0 !important; }
      /* Dataframes */
      [data-testid="stDataFrame"] { border: 1px solid #2a2a3a !important; border-radius: 8px !important; }
      /* Buttons */
      .stButton > button { background: #7c6af7 !important; color: #fff !important; border: none !important; border-radius: 6px !important; }
      .stButton > button:hover { background: #9580ff !important; }
      /* Headers */
      h1, h2, h3 { color: #ffffff !important; }
      h1 { border-bottom: 2px solid #7c6af7; padding-bottom: 8px; }
      /* Divider */
      hr { border-color: #2a2a3a !important; }
      /* Info / success / warning boxes */
      [data-testid="stAlert"] { background: #16162a !important; border-color: #7c6af7 !important; color: #e0e0e0 !important; }
      /* Expander */
      [data-testid="stExpander"] { background: #16162a !important; border: 1px solid #2a2a3a !important; border-radius: 8px !important; }
      /* Plotly chart backgrounds handled via layout */
      .stPlotlyChart { border-radius: 10px !important; overflow: hidden !important; }
      /* Sidebar label */
      .css-1d391kg, [data-testid="stSidebarNav"] { color: #e0e0e0 !important; }
      label, .stMarkdown p { color: #c0c0d0 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

PLOTLY_LAYOUT = dict(
    paper_bgcolor="#10101a",
    plot_bgcolor="#10101a",
    font=dict(color="#e0e0e0", family="Inter, Segoe UI, sans-serif"),
    legend=dict(bgcolor="#16162a", bordercolor="#2a2a3a"),
    margin=dict(l=20, r=20, t=40, b=20),
)

AXIS_STYLE = dict(gridcolor="#1e1e2e", linecolor="#2a2a3a")

PURPLE = "#7c6af7"
PURPLE_LIGHT = "#a89cf7"
PURPLE_DARK = "#5b50c4"


def fmt_gbp(val: float) -> str:
    """Format as £Xm."""
    return f"£{val / 1_000_000:.1f}m"


# ── Sidebar inputs ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Company Profile")
    st.markdown("---")

    company_name = st.text_input("Company Name", value="FinTechX")

    sector = st.selectbox(
        "Sector",
        ["FinTech", "SaaS", "HealthTech", "EdTech", "CleanTech",
         "E-Commerce", "DeepTech", "Cybersecurity", "MarketPlace", "Other"],
        index=0,
    )

    stage = st.selectbox(
        "Stage",
        ["Pre-Seed", "Seed", "Series A", "Series B", "Series C+", "Growth"],
        index=2,
    )

    geography = st.selectbox(
        "Geography",
        ["UK", "Europe", "US", "Asia", "Global", "MENA", "LatAm"],
        index=0,
    )

    st.markdown("---")
    st.markdown("### Financials")

    revenue = st.number_input(
        "Annual Revenue (£)", min_value=0, value=4_000_000, step=100_000,
        format="%d",
    )

    growth_pct = st.slider("Revenue Growth (%)", 0, 300, 80, step=5)
    ebitda_margin = st.slider("EBITDA Margin (%)", -100, 80, 15, step=1)
    cash = st.number_input(
        "Cash on Hand (£)", min_value=0, value=1_500_000, step=100_000,
        format="%d",
    )
    burn = st.number_input(
        "Monthly Burn (£)", min_value=0, value=200_000, step=10_000,
        format="%d",
    )

    runway_months = int(cash / burn) if burn > 0 else 999
    runway_color = "#e05050" if runway_months < 12 else "#50e090"
    st.markdown(
        f"<p style='color:{runway_color};font-size:0.9rem;'>🕐 Runway: "
        f"<b>{runway_months} months</b></p>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    openai_key = st.text_input("OpenAI API Key (optional)", type="password",
                               placeholder="sk-...")

# ── Pre-compute valuations ────────────────────────────────────────────────────
dcf   = dcf_valuation(revenue, growth_pct, ebitda_margin, stage)
comps = comparable_valuation(revenue, sector)
blend = blended_valuation(dcf, comps)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown(
    f"<h1 style='color:#7c6af7;'>AI Deal Advisor</h1>"
    f"<p style='color:#9090b0;margin-top:-8px;'>Analysing <b style='color:#e0e0e0'>{company_name}</b> "
    f"· {sector} · {stage} · {geography}</p>",
    unsafe_allow_html=True,
)

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_val, tab_fund, tab_vc, tab_memo, tab_ma = st.tabs(
    ["📊 Valuation", "💰 Fundraising", "🎯 VC Matching", "📝 Memo", "🤝 M&A"]
)


# ═══════════════════════════════════════════════════════════════════
# TAB 1 — VALUATION
# ═══════════════════════════════════════════════════════════════════
with tab_val:
    st.markdown("## Valuation Analysis")
    st.markdown(f"All figures in GBP · Based on £{revenue/1e6:.1f}m revenue · "
                f"{growth_pct}% growth · {ebitda_margin}% EBITDA margin")

    # ── Key metrics row ──
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Blended (Low)",  fmt_gbp(blend["low"]))
    c2.metric("Blended (Base)", fmt_gbp(blend["base"]))
    c3.metric("Blended (High)", fmt_gbp(blend["high"]))
    c4.metric("Revenue Multiple (Base)",
              f"{comps['base'] / revenue:.1f}x" if revenue > 0 else "N/A")

    st.markdown("---")

    # ── DCF section ──
    col_l, col_r = st.columns(2)

    with col_l:
        st.markdown("### DCF Valuation")
        dcf_df = pd.DataFrame({
            "Scenario": ["🔴 Low", "🟡 Base", "🟢 High"],
            "Value (£m)": [
                round(dcf["low"] / 1e6, 1),
                round(dcf["base"] / 1e6, 1),
                round(dcf["high"] / 1e6, 1),
            ],
        })
        st.dataframe(dcf_df, hide_index=True, use_container_width=True)

        fig_dcf = go.Figure(go.Bar(
            x=["Low", "Base", "High"],
            y=[dcf["low"] / 1e6, dcf["base"] / 1e6, dcf["high"] / 1e6],
            marker_color=[PURPLE_DARK, PURPLE, PURPLE_LIGHT],
            text=[f"£{v/1e6:.1f}m" for v in [dcf["low"], dcf["base"], dcf["high"]]],
            textposition="outside",
        ))
        fig_dcf.update_layout(title="DCF Scenarios (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
        st.plotly_chart(fig_dcf, use_container_width=True)

    with col_r:
        st.markdown("### Comparable Multiples")
        sector_multiples = {
            "FinTech": {"low": 4.0, "base": 7.0, "high": 12.0},
            "SaaS": {"low": 5.0, "base": 9.0, "high": 15.0},
            "HealthTech": {"low": 3.5, "base": 6.0, "high": 10.0},
            "EdTech": {"low": 2.5, "base": 4.5, "high": 8.0},
            "CleanTech": {"low": 3.0, "base": 5.5, "high": 9.0},
            "E-Commerce": {"low": 1.5, "base": 3.0, "high": 5.5},
            "DeepTech": {"low": 4.0, "base": 8.0, "high": 14.0},
            "Cybersecurity": {"low": 5.0, "base": 9.5, "high": 16.0},
            "MarketPlace": {"low": 2.0, "base": 4.0, "high": 7.0},
            "Other": {"low": 2.0, "base": 4.0, "high": 7.0},
        }
        m = sector_multiples.get(sector, sector_multiples["Other"])
        comps_df = pd.DataFrame({
            "Scenario": ["🔴 Low", "🟡 Base", "🟢 High"],
            "EV/Rev Multiple": [m["low"], m["base"], m["high"]],
            "Value (£m)": [
                round(comps["low"] / 1e6, 1),
                round(comps["base"] / 1e6, 1),
                round(comps["high"] / 1e6, 1),
            ],
        })
        st.dataframe(comps_df, hide_index=True, use_container_width=True)

        fig_comps = go.Figure(go.Bar(
            x=["Low", "Base", "High"],
            y=[comps["low"] / 1e6, comps["base"] / 1e6, comps["high"] / 1e6],
            marker_color=[PURPLE_DARK, PURPLE, PURPLE_LIGHT],
            text=[f"£{v/1e6:.1f}m" for v in [comps["low"], comps["base"], comps["high"]]],
            textposition="outside",
        ))
        fig_comps.update_layout(title="Comparable Multiples (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
        st.plotly_chart(fig_comps, use_container_width=True)

    st.markdown("---")
    st.markdown("### Blended Valuation")

    fig_blend = go.Figure()
    scenarios = ["Low", "Base", "High"]
    dcf_vals   = [dcf["low"] / 1e6,   dcf["base"] / 1e6,   dcf["high"] / 1e6]
    comps_vals = [comps["low"] / 1e6, comps["base"] / 1e6, comps["high"] / 1e6]
    blend_vals = [blend["low"] / 1e6, blend["base"] / 1e6, blend["high"] / 1e6]

    fig_blend.add_trace(go.Bar(name="DCF",        x=scenarios, y=dcf_vals,   marker_color=PURPLE_DARK))
    fig_blend.add_trace(go.Bar(name="Comparables", x=scenarios, y=comps_vals, marker_color=PURPLE))
    fig_blend.add_trace(go.Bar(name="Blended",    x=scenarios, y=blend_vals, marker_color=PURPLE_LIGHT))
    fig_blend.update_layout(barmode="group", title="Blended Valuation (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
    st.plotly_chart(fig_blend, use_container_width=True)

    st.markdown("---")
    st.markdown("### 5-Year Projection")

    proj_df = five_year_projection(revenue, growth_pct, ebitda_margin)
    st.dataframe(proj_df, hide_index=True, use_container_width=True)

    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["Revenue (£m)"],
        mode="lines+markers+text",
        name="Revenue",
        line=dict(color=PURPLE, width=3),
        text=[f"£{v}m" for v in proj_df["Revenue (£m)"]],
        textposition="top center",
    ))
    fig_proj.add_trace(go.Scatter(
        x=proj_df["Year"], y=proj_df["EBITDA (£m)"],
        mode="lines+markers+text",
        name="EBITDA",
        line=dict(color=PURPLE_LIGHT, width=2, dash="dot"),
        text=[f"£{v}m" for v in proj_df["EBITDA (£m)"]],
        textposition="bottom center",
    ))
    fig_proj.update_layout(title="5-Year Revenue & EBITDA (£m)", xaxis=AXIS_STYLE, yaxis=AXIS_STYLE, **PLOTLY_LAYOUT)
    st.plotly_chart(fig_proj, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════
# TAB 2 — FUNDRAISING
# ═══════════════════════════════════════════════════════════════════
with tab_fund:
    st.markdown("## Fundraising Analysis")

    # ── Runway gauge ──
    runway_pct = min(runway_months / 24, 1.0)
    gauge_color = "#e05050" if runway_months < 12 else "#50e090" if runway_months >= 18 else "#e0b050"

    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=runway_months,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Runway (Months)", "font": {"color": "#e0e0e0"}},
        gauge={
            "axis": {"range": [0, 36], "tickcolor": "#9090b0"},
            "bar": {"color": gauge_color},
            "bgcolor": "#16162a",
            "bordercolor": "#2a2a3a",
            "steps": [
                {"range": [0, 12],  "color": "#2a0a0a"},
                {"range": [12, 18], "color": "#2a1a0a"},
                {"range": [18, 36], "color": "#0a2a1a"},
            ],
            "threshold": {"line": {"color": PURPLE, "width": 4}, "value": 18},
        },
        number={"font": {"color": gauge_color, "size": 48}},
    ))
    fig_gauge.update_layout(paper_bgcolor="#10101a", font=dict(color="#e0e0e0"), height=300,
                            margin=dict(l=20, r=20, t=40, b=20))
    st.plotly_chart(fig_gauge, use_container_width=True)

    st.markdown("---")

    # ── Recommended raise size ──
    recommended_raise = burn * 18
    dilution_estimate = 0.20 if stage == "Seed" else 0.15 if stage == "Series A" else 0.12

    col1, col2, col3 = st.columns(3)
    col1.metric("Recommended Raise", fmt_gbp(recommended_raise),
                help="18 months of runway at current burn")
    col2.metric("Estimated Dilution", f"{dilution_estimate*100:.0f}%",
                help="Typical dilution for this stage")
    col3.metric("Post-Money (Base)",
                fmt_gbp(blend["base"] + recommended_raise))

    st.markdown("---")

    # ── Use of funds ──
    st.markdown("### Suggested Use of Funds")
    categories = ["Engineering & Product", "Sales & Marketing", "Operations", "G&A / Legal", "Reserve"]
    weights = [0.40, 0.30, 0.15, 0.10, 0.05]
    amounts = [recommended_raise * w for w in weights]

    fig_pie = go.Figure(go.Pie(
        labels=categories,
        values=amounts,
        hole=0.45,
        marker=dict(colors=[PURPLE, PURPLE_LIGHT, PURPLE_DARK, "#4a3a8a", "#2a1a5a"]),
        textinfo="label+percent",
        textfont=dict(color="#e0e0e0"),
    ))
    fig_pie.update_layout(
        title=f"Use of £{recommended_raise/1e6:.1f}m Raise",
        showlegend=False,
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_pie, use_container_width=True)

    uof_df = pd.DataFrame({
        "Category": categories,
        "Allocation": [f"{w*100:.0f}%" for w in weights],
        "Amount (£)": [f"£{a:,.0f}" for a in amounts],
    })
    st.dataframe(uof_df, hide_index=True, use_container_width=True)

    st.markdown("---")

    # ── Burn bridge chart ──
    st.markdown("### Cash Runway Bridge")
    months = list(range(0, runway_months + 1))
    cash_values = [max(cash - burn * m, 0) for m in months]

    fig_burn = go.Figure()
    fig_burn.add_trace(go.Scatter(
        x=months, y=[c / 1e6 for c in cash_values],
        fill="tozeroy",
        mode="lines",
        line=dict(color=PURPLE, width=2),
        fillcolor="rgba(124, 106, 247, 0.15)",
        name="Cash (£m)",
    ))
    fig_burn.add_vline(x=12, line_dash="dot", line_color="#e05050",
                       annotation_text="12-month warning", annotation_font_color="#e05050")
    if runway_months < 36:
        fig_burn.add_vline(x=runway_months, line_dash="dash", line_color="#e0b050",
                           annotation_text=f"Zero cash (M{runway_months})",
                           annotation_font_color="#e0b050")
    fig_burn.update_layout(
        title="Cash Balance Over Time (£m)",
        xaxis=dict(title="Month", **AXIS_STYLE),
        yaxis=dict(title="£m", **AXIS_STYLE),
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_burn, use_container_width=True)

    # ── Fundraising tips ──
    st.markdown("---")
    st.markdown("### Fundraising Readiness Checklist")
    tips = [
        ("Pitch Deck",        runway_months > 6,  "Ready to fundraise" if runway_months > 6 else "Start immediately"),
        ("Runway",            runway_months >= 18, f"{runway_months} months" if runway_months >= 18 else "< 18 months — raise now"),
        ("Revenue Evidence",  revenue > 0,         fmt_gbp(revenue) + " ARR"),
        ("Growth Rate",       growth_pct >= 50,    f"{growth_pct}% YoY"),
        ("EBITDA Visibility", ebitda_margin >= 0,  f"{ebitda_margin}% margin"),
    ]
    for label, ok, note in tips:
        icon = "✅" if ok else "⚠️"
        color = "#50e090" if ok else "#e0b050"
        st.markdown(
            f"<p style='color:{color};'>{icon} <b>{label}</b> — {note}</p>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════
# TAB 3 — VC MATCHING
# ═══════════════════════════════════════════════════════════════════
with tab_vc:
    st.markdown("## VC Matching")
    st.markdown(f"Scoring investors for **{company_name}** · {sector} · {stage} · {geography}")

    csv_path = os.path.join(os.path.dirname(__file__), "data", "vc_database.csv")
    try:
        vc_df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.error(f"VC database not found at {csv_path}")
        st.stop()

    scored = score_investors(vc_df, sector, stage, geography, revenue)
    top10  = scored.head(10).copy()

    st.markdown(f"**{len(scored)} investors** analysed · Showing top 10")
    st.markdown("---")

    # ── Score bars chart ──
    fig_vc = go.Figure(go.Bar(
        x=top10["Score /100"],
        y=top10["Investor"],
        orientation="h",
        marker=dict(
            color=top10["Score /100"],
            colorscale=[[0, PURPLE_DARK], [0.5, PURPLE], [1.0, PURPLE_LIGHT]],
            showscale=False,
        ),
        text=[f"{s}/100" for s in top10["Score /100"]],
        textposition="outside",
    ))
    fig_vc.update_layout(
        title="Top 10 Investor Match Scores",
        xaxis=dict(title="Score /100", **AXIS_STYLE),
        yaxis=dict(autorange="reversed", **AXIS_STYLE),
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_vc, use_container_width=True)

    st.markdown("---")
    st.markdown("### Top 10 Investors")

    display_cols = ["Investor", "Type", "Score /100", "Sector Fit",
                    "Stage Fit", "Geo Fit", "Cheque Fit",
                    "Min Cheque (£m)", "Max Cheque (£m)"]
    st.dataframe(
        top10[display_cols].reset_index(drop=True),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("---")
    st.markdown("### Score Breakdown")
    st.markdown("Scores are out of: Sector Fit **/40** · Stage Fit **/30** · Geo Fit **/20** · Cheque Fit **/10**")

    fig_radar_list = []
    for _, row in top10.head(5).iterrows():
        fig_radar_list.append(go.Scatterpolar(
            r=[row["Sector Fit"], row["Stage Fit"], row["Geo Fit"], row["Cheque Fit"]],
            theta=["Sector (40)", "Stage (30)", "Geo (20)", "Cheque (10)"],
            fill="toself",
            name=row["Investor"],
        ))

    fig_radar = go.Figure(fig_radar_list)
    fig_radar.update_layout(
        polar=dict(
            bgcolor="#10101a",
            radialaxis=dict(visible=True, range=[0, 40], color="#9090b0"),
            angularaxis=dict(color="#9090b0"),
        ),
        title="Score Breakdown — Top 5 Investors",
        xaxis=AXIS_STYLE,
        yaxis=AXIS_STYLE,
        **PLOTLY_LAYOUT,
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # ── Website links ──
    st.markdown("---")
    st.markdown("### Investor Quick Links")
    for _, row in top10.iterrows():
        url = row.get("Website", "")
        if url:
            st.markdown(
                f"[🔗 {row['Investor']}]({url}) — Score: **{row['Score /100']}/100**"
            )


# ═══════════════════════════════════════════════════════════════════
# TAB 4 — MEMO (requires OpenAI key)
# ═══════════════════════════════════════════════════════════════════
with tab_memo:
    st.markdown("## Investment Memo")

    if not openai_key:
        st.markdown(
            """
            <div style='background:#16162a;border:1px solid #7c6af7;border-radius:10px;
                        padding:40px;text-align:center;margin:40px auto;max-width:500px;'>
                <div style='font-size:3rem;'>🔑</div>
                <h3 style='color:#7c6af7;margin:16px 0 8px;'>OpenAI API Key Required</h3>
                <p style='color:#9090b0;'>Add your OpenAI API key to enable AI-generated investment memos.</p>
                <p style='color:#9090b0;font-size:0.85rem;'>Enter your key in the sidebar → <b>OpenAI API Key</b> field.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        try:
            import openai
            from prompts.prompts import MEMO_SYSTEM, MEMO_USER

            if st.button("Generate Investment Memo"):
                with st.spinner("Generating memo with GPT-4o…"):
                    client = openai.OpenAI(api_key=openai_key)
                    prompt = MEMO_USER.format(
                        company_name=company_name, sector=sector, stage=stage,
                        geography=geography, revenue=revenue, growth=growth_pct,
                        ebitda_margin=ebitda_margin, cash=cash, burn=burn,
                        valuation=blend["base"] / 1e6,
                    )
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": MEMO_SYSTEM},
                            {"role": "user",   "content": prompt},
                        ],
                        max_tokens=1200,
                    )
                    memo_text = response.choices[0].message.content
                    st.markdown(memo_text)
        except ImportError:
            st.error("openai package not installed. Run: pip install openai")
        except Exception as e:
            st.error(f"Error: {e}")


# ═══════════════════════════════════════════════════════════════════
# TAB 5 — M&A (requires OpenAI key)
# ═══════════════════════════════════════════════════════════════════
with tab_ma:
    st.markdown("## M&A Analysis")

    if not openai_key:
        st.markdown(
            """
            <div style='background:#16162a;border:1px solid #7c6af7;border-radius:10px;
                        padding:40px;text-align:center;margin:40px auto;max-width:500px;'>
                <div style='font-size:3rem;'>🔑</div>
                <h3 style='color:#7c6af7;margin:16px 0 8px;'>OpenAI API Key Required</h3>
                <p style='color:#9090b0;'>Add your OpenAI API key to enable AI-powered M&A analysis.</p>
                <p style='color:#9090b0;font-size:0.85rem;'>Enter your key in the sidebar → <b>OpenAI API Key</b> field.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        try:
            import openai
            from prompts.prompts import MA_SYSTEM, MA_USER

            if st.button("Generate M&A Analysis"):
                with st.spinner("Generating M&A analysis with GPT-4o…"):
                    client = openai.OpenAI(api_key=openai_key)
                    prompt = MA_USER.format(
                        company_name=company_name, sector=sector, stage=stage,
                        revenue=revenue, growth=growth_pct,
                        ebitda_margin=ebitda_margin,
                        valuation=blend["base"] / 1e6,
                    )
                    response = client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": MA_SYSTEM},
                            {"role": "user",   "content": prompt},
                        ],
                        max_tokens=1200,
                    )
                    ma_text = response.choices[0].message.content
                    st.markdown(ma_text)
        except ImportError:
            st.error("openai package not installed. Run: pip install openai")
        except Exception as e:
            st.error(f"Error: {e}")
