import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sys
import os

sys.path.append(os.path.dirname(__file__))
from fetch_data import fetch_date_range, ZONES
from spike import (
    identify_spikes,
    spike_summary,
    spikes_by_hour,
    spikes_by_month,
    price_duration_curve,
)
from backtest import run_backtest, monthly_summary, backtest_summary

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="NYISO Battery Analytics",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stMetric [data-testid="metric-container"] {
        background: #1e2130;
        border-radius: 8px;
        padding: 12px;
    }
    .insight-box {
        background: #eef4fb;
        border-left: 4px solid #2e7abf;
        border-radius: 0 8px 8px 0;
        padding: 13px 17px;
        margin: 8px 0 18px 0;
        font-size: 0.9rem;
        color: #1a2f45;
        line-height: 1.7;
    }
    .insight-box b { color: #0d1f30; }
    .investment-card {
        background: #f0f7ff;
        border: 1px solid #b3d4f0;
        border-radius: 10px;
        padding: 22px 26px;
        margin-bottom: 24px;
        color: #0d1f30;
    }
    .investment-card h4 {
        color: #1a5fa8;
        margin-top: 0;
        font-size: 1.05rem;
    }
    .investment-card p { color: #1c2e40; line-height: 1.8; margin: 0 0 12px 0; }
    .investment-card .note { color: #5a7a99; font-size: 0.83rem; }
    .takeaway-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 12px;
        margin-top: 8px;
        margin-bottom: 24px;
    }
    .takeaway-item {
        background: #eef4fb;
        border-radius: 8px;
        padding: 15px 17px;
        font-size: 0.88rem;
        color: #1c2e40;
        line-height: 1.6;
    }
    .takeaway-item strong {
        display: block;
        color: #0d1f30;
        margin-bottom: 5px;
        font-size: 0.92rem;
    }
    h1 { color: #f0f0f0; }
    h2, h3 { color: #d0d0d0; }
</style>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("⚡ NYISO Battery Analytics")
    st.caption("Configure your parameters below, then click **Fetch & Analyze** to run the analysis.")

    st.divider()
    st.subheader("📅 Time Range")
    year_options = [2021, 2022, 2023, 2024]
    start_year = st.selectbox("Start Year", year_options, index=1)
    start_month = st.selectbox("Start Month", range(1, 13), index=0,
                               format_func=lambda m: pd.Timestamp(2024, m, 1).strftime("%B"))
    end_year = st.selectbox("End Year", year_options, index=3)
    end_month = st.selectbox("End Month", range(1, 13), index=11,
                             format_func=lambda m: pd.Timestamp(2024, m, 1).strftime("%B"))

    st.divider()
    st.subheader("🗺️ Zone")
    zone_options = list(ZONES.keys())
    zone_labels = [f"{v} ({k})" for k, v in ZONES.items()]
    selected_zone_idx = st.selectbox("Select Zone", range(len(zone_options)), index=8,
                                     format_func=lambda i: zone_labels[i])
    selected_zone = zone_options[selected_zone_idx]

    st.divider()
    st.subheader("🔋 Battery Parameters")
    st.caption("Define the size and efficiency of the battery asset you want to model.")
    power_mw = st.slider("Power Rating (MW)", 0.5, 20.0, 1.0, 0.5,
                         help="How much power the battery can charge or discharge at once.")
    duration_hrs = st.slider("Duration (hours)", 1.0, 8.0, 4.0, 0.5,
                             help="How many hours the battery can sustain full output. Energy = Power × Duration.")
    efficiency = st.slider("Round-trip Efficiency", 0.70, 0.95, 0.85, 0.01,
                           help="Energy lost in the charge/discharge cycle. 0.85 is typical for Li-ion.")
    cycle_hours = st.slider("Trading Hours per Cycle", 2, 6, 4,
                            help="Hours per day the battery charges (and discharges). Kept equal to respect energy capacity limits.")

    st.divider()
    st.subheader("📊 High Price Filter")
    st.caption("Flag hours above a price threshold to analyse when the market is most valuable. You can skip this and analyse all hours instead.")

    use_filter = st.toggle("Enable High Price Filter", value=True)
    spike_threshold = None

    if use_filter:
        st.info("After fetching data, the chart will show your dataset's price distribution to help you choose a meaningful threshold.")
        spike_threshold = st.slider(
            "Flag hours above ($/MWh)",
            min_value=50, max_value=500, value=100, step=25,
            help="Hours above this price are highlighted as high-value events. The average NYISO real-time price is typically $30–$70/MWh, so $100+ already represents an elevated market."
        )

    st.divider()
    fetch_btn = st.button("🚀 Fetch & Analyze", type="primary", use_container_width=True)

# ── Welcome screen ────────────────────────────────────────────────────────────
if not fetch_btn and "df" not in st.session_state:
    st.markdown("## ⚡ NYISO Battery Analytics")
    st.markdown(
        "Understand electricity price dynamics and model battery storage revenue "
        "in New York's wholesale electricity market — using real NYISO data."
    )
    st.divider()
    col_a, col_b = st.columns([1, 1], gap="large")
    with col_a:
        st.markdown("#### What this tool does")
        st.markdown("""
- Visualises historical **real-time electricity prices** across NYISO zones
- Identifies **high-price patterns** by hour of day and month
- Runs a **battery arbitrage backtest** — how much could a battery have earned buying cheap and selling expensive?
- Generates an **investment summary** with plain-language, actionable conclusions
        """)
        st.markdown(
            "**Data source:** [NYISO Market Information System](https://mis.nyiso.com/public/) "
            "— public real-time LBMP data, no API key required."
        )
    with col_b:
        st.markdown("#### How to get started")
        st.markdown("""
1. **👈 Use the sidebar on the left** to set your parameters
2. Choose a **time range** (e.g. Jan 2022 – Dec 2024)
3. Pick a **NYISO zone** (New York City is a good default)
4. Set your **battery size** and trading assumptions
5. Scroll down and click **🚀 Fetch & Analyze**
        """)
        st.info("💡 Fetching 1–2 years of data typically takes 10–20 seconds.")
    st.stop()

# ── Fetch data ────────────────────────────────────────────────────────────────
if fetch_btn or "df" in st.session_state:
    if fetch_btn:
        with st.spinner(f"Fetching NYISO data ({start_year}-{start_month:02d} → {end_year}-{end_month:02d})..."):
            try:
                raw_df = fetch_date_range(start_year, start_month, end_year, end_month)
                df = raw_df[raw_df["zone"] == selected_zone].copy()
                if df.empty:
                    st.error(f"No data found for zone '{selected_zone}'. Try a different zone.")
                    st.stop()
                st.session_state["df"] = df
                st.session_state["zone"] = selected_zone
            except Exception as e:
                st.error(f"Failed to fetch data: {e}")
                st.stop()
    else:
        df = st.session_state["df"]
        selected_zone = st.session_state.get("zone", selected_zone)

    # ── Compute everything ────────────────────────────────────────────────────
    # Auto-compute price context from actual data
    p50 = df["lbmp"].median()
    p75 = df["lbmp"].quantile(0.75)
    p90 = df["lbmp"].quantile(0.90)
    p95 = df["lbmp"].quantile(0.95)

    # If filter is off, use p90 as a silent threshold for spike-related analytics
    effective_threshold = spike_threshold if (use_filter and spike_threshold is not None) else int(p90)

    df_spikes = identify_spikes(df, effective_threshold)
    summary = spike_summary(df, effective_threshold)
    bt = run_backtest(df, power_mw, duration_hrs, efficiency, cycle_hours, cycle_hours)
    bt_sum = backtest_summary(bt, power_mw, duration_hrs)
    monthly = monthly_summary(bt)
    zone_display = ZONES.get(selected_zone, selected_zone)
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    # ── Helper functions ──────────────────────────────────────────────────────
    def peak_spike_hour(df, threshold):
        h = spikes_by_hour(df, threshold)
        if h["Spike Count"].sum() == 0:
            return "N/A"
        peak = int(h.loc[h["Spike Count"].idxmax(), "Hour of Day"])
        return f"{peak:02d}:00–{peak+1:02d}:00"

    def peak_spike_month(df, threshold):
        m = spikes_by_month(df, threshold)
        if m["Spike Count"].sum() == 0:
            return "N/A"
        peak = int(m.loc[m["Spike Count"].idxmax(), "Month"])
        return month_names[peak - 1]

    def second_spike_month(df, threshold):
        m = spikes_by_month(df, threshold)
        if m["Spike Count"].sum() == 0:
            return "N/A"
        sorted_m = m.sort_values("Spike Count", ascending=False)
        if len(sorted_m) < 2:
            return "N/A"
        second = int(sorted_m.iloc[1]["Month"])
        return month_names[second - 1]

    def spike_revenue_share(bt, df_spikes, threshold):
        if bt.empty:
            return 0
        spike_days = df_spikes[df_spikes["lbmp"] >= threshold]["date"].unique()
        spike_rev = bt[bt["date"].isin(spike_days)]["daily_revenue"].sum()
        total = bt["daily_revenue"].sum()
        if total == 0:
            return 0
        return round(spike_rev / total * 100, 0)

    ph = peak_spike_hour(df, effective_threshold)
    pm = peak_spike_month(df, effective_threshold)
    pm2 = second_spike_month(df, effective_threshold)
    srs = spike_revenue_share(bt, df_spikes, effective_threshold)
    best_month_rev = monthly.loc[monthly["revenue"].idxmax(), "month_str"] if not monthly.empty else "N/A"
    worst_month_rev = monthly.loc[monthly["revenue"].idxmin(), "month_str"] if not monthly.empty else "N/A"
    above_threshold_pct = round((df["lbmp"] >= effective_threshold).mean() * 100, 1)

    # ── Header ────────────────────────────────────────────────────────────────
    st.title(f"⚡ NYISO — {zone_display} Zone")
    filter_label = f"High price filter: ${effective_threshold}/MWh" if use_filter else f"No filter (using p90 = ${effective_threshold:.0f}/MWh for spike analytics)"
    st.caption(
        f"{start_year}-{start_month:02d} to {end_year}-{end_month:02d}  ·  "
        f"{power_mw} MW / {duration_hrs}h battery  ·  {filter_label}"
    )

    tab1, tab2, tab3 = st.tabs(["📈 Price Overview", "⚡ High Price Analysis", "🔋 Battery Backtest"])

    # ════════════════════════════════════════════════════════════════════════
    # Tab 1: Price Overview
    # ════════════════════════════════════════════════════════════════════════
    with tab1:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Median Price", f"${p50:.1f}/MWh")
        c2.metric("90th Percentile", f"${p90:.0f}/MWh")
        c3.metric("Max Price", f"${df['lbmp'].max():.0f}/MWh")
        c4.metric("High-Price Hours", f"{summary['spike_hours']:,} ({summary['spike_pct']}%)")

        # Show price context if filter is enabled
        if use_filter and spike_threshold is not None:
            percentile_of_threshold = round((df["lbmp"] < spike_threshold).mean() * 100, 0)
            st.markdown(
                f'<div class="insight-box">📊 <b>Your threshold in context:</b> In this dataset, '
                f'the median price is <b>${p50:.0f}/MWh</b>, the 75th percentile is <b>${p75:.0f}/MWh</b>, '
                f'and the 90th percentile is <b>${p90:.0f}/MWh</b>. '
                f'Your filter of <b>${spike_threshold}/MWh</b> sits at the <b>{percentile_of_threshold:.0f}th percentile</b> — '
                f'meaning only the top <b>{100 - percentile_of_threshold:.0f}%</b> of hours are flagged. '
                f'If you want to focus on truly extreme events, try raising the threshold closer to ${p95:.0f}/MWh (95th percentile).</div>',
                unsafe_allow_html=True
            )

        st.subheader("Hourly Price Timeline")
        plot_df = df_spikes.copy()
        if len(plot_df) > 5000:
            plot_df = plot_df.sample(5000).sort_values("timestamp")

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df[~plot_df["is_spike"]]["timestamp"],
            y=plot_df[~plot_df["is_spike"]]["lbmp"],
            mode="lines", name="Normal hours",
            line=dict(color="#4c78a8", width=1), opacity=0.7,
        ))
        if use_filter:
            fig.add_trace(go.Scatter(
                x=plot_df[plot_df["is_spike"]]["timestamp"],
                y=plot_df[plot_df["is_spike"]]["lbmp"],
                mode="markers", name=f"High-price hours (>${effective_threshold})",
                marker=dict(color="#e45756", size=5),
            ))
            fig.add_hline(y=effective_threshold, line_dash="dash", line_color="orange",
                          annotation_text=f"Filter: ${effective_threshold}/MWh")
        fig.update_layout(height=400, template="plotly_dark",
                          xaxis_title="Date", yaxis_title="LBMP ($/MWh)",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            f'<div class="insight-box">💡 <b>What to do with this:</b> If you see spikes clustering in summer months, '
            f'prioritise battery availability during June–August and avoid scheduling maintenance then. '
            f'If spikes are spread year-round, a consistent daily trading strategy makes more sense than a seasonal one. '
            f'Flat periods with no spikes are low-revenue stretches — factor these into your cash flow projections.</div>',
            unsafe_allow_html=True
        )

        st.subheader("Price Duration Curve")
        pdc = price_duration_curve(df)
        fig2 = px.line(
            pdc.iloc[::max(1, len(pdc)//1000)],
            x="Percentile", y="Price ($/MWh)",
            template="plotly_dark",
        )
        if use_filter:
            fig2.add_hline(y=effective_threshold, line_dash="dash", line_color="orange",
                           annotation_text=f"${effective_threshold} filter")
        fig2.add_hline(y=p90, line_dash="dot", line_color="#aaa",
                       annotation_text=f"p90 ${p90:.0f}")
        fig2.update_layout(height=350, xaxis_title="% of Hours (left = most expensive)")
        st.plotly_chart(fig2, use_container_width=True)

        st.markdown(
            f'<div class="insight-box">💡 <b>How to use this curve:</b> The steep drop on the left means a small number of hours '
            f'are worth dramatically more than the rest. Only <b>{above_threshold_pct}%</b> of hours exceeded '
            f'${effective_threshold}/MWh. In practical terms: a battery that misses even a handful of those hours '
            f'through an outage or poor scheduling can lose a meaningful share of annual revenue. '
            f'Build in redundancy and prioritise uptime during known high-risk periods.</div>',
            unsafe_allow_html=True
        )

    # ════════════════════════════════════════════════════════════════════════
    # Tab 2: High Price Analysis
    # ════════════════════════════════════════════════════════════════════════
    with tab2:
        if not use_filter:
            st.info(f"High Price Filter is off. Showing analysis based on the automatic p90 threshold (${effective_threshold:.0f}/MWh) to identify high-value hours. Enable the filter in the sidebar to set your own threshold.")

        c1, c2, c3 = st.columns(3)
        c1.metric("High-Price Hours", f"{summary['spike_hours']:,}")
        c2.metric("Avg High-Price Level", f"${summary['avg_spike_price']}/MWh")
        c3.metric("Peak Price", f"${summary['max_spike_price']:,}/MWh")

        cl, cr = st.columns(2)

        with cl:
            st.subheader("High-Price Hours by Time of Day")
            hourly = spikes_by_hour(df, effective_threshold)
            fig3 = px.bar(hourly, x="Hour of Day", y="Spike Count",
                          template="plotly_dark", color="Spike Count",
                          color_continuous_scale="Reds")
            fig3.update_layout(height=320, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig3, use_container_width=True)
            st.markdown(
                f'<div class="insight-box">💡 <b>Action:</b> High prices peak around <b>{ph}</b>. '
                f'Program your battery to hold charge through the morning and early afternoon, '
                f'and discharge specifically into this window. '
                f'Avoid letting the battery run low before {ph.split("–")[0]} — '
                f'that is when the revenue opportunity is highest.</div>',
                unsafe_allow_html=True
            )

        with cr:
            st.subheader("High-Price Hours by Month")
            monthly_spikes = spikes_by_month(df, effective_threshold)
            monthly_spikes["Month Name"] = monthly_spikes["Month"].apply(lambda m: month_names[m-1])
            fig4 = px.bar(monthly_spikes, x="Month Name", y="Spike Count",
                          template="plotly_dark", color="Spike Count",
                          color_continuous_scale="Oranges")
            fig4.update_layout(height=320, showlegend=False, coloraxis_showscale=False)
            st.plotly_chart(fig4, use_container_width=True)
            st.markdown(
                f'<div class="insight-box">💡 <b>Action:</b> <b>{pm}</b> and <b>{pm2}</b> are your highest-risk months. '
                f'Do not schedule battery maintenance, firmware upgrades, or grid interconnection tests during these periods. '
                f'If you are underwriting a project, stress-test your revenue model against scenarios where '
                f'the battery is offline for 2 weeks in {pm} — that outage cost is likely larger than any other month combined.</div>',
                unsafe_allow_html=True
            )

        st.subheader("Price Distribution: Normal vs High-Price Hours")
        fig5 = go.Figure()
        fig5.add_trace(go.Histogram(
            x=df_spikes[~df_spikes["is_spike"]]["lbmp"],
            name="Normal Hours", marker_color="#4c78a8", opacity=0.7, nbinsx=60,
        ))
        fig5.add_trace(go.Histogram(
            x=df_spikes[df_spikes["is_spike"]]["lbmp"],
            name="High-Price Hours", marker_color="#e45756", opacity=0.7, nbinsx=60,
        ))
        fig5.update_layout(barmode="overlay", template="plotly_dark", height=320,
                           xaxis_title="LBMP ($/MWh)", yaxis_title="Count")
        st.plotly_chart(fig5, use_container_width=True)
        st.markdown(
            f'<div class="insight-box">💡 <b>What the spread tells you:</b> The wide tail on the red distribution means '
            f'high-price hours vary enormously — some are modestly elevated, others are extreme. '
            f'If you are building a revenue model, do not just use the average high-price level: '
            f'model the distribution, and include a sensitivity case where the top 1% of extreme hours do not occur. '
            f'That gives you a conservative floor for your investment case.</div>',
            unsafe_allow_html=True
        )

    # ════════════════════════════════════════════════════════════════════════
    # Tab 3: Battery Backtest
    # ════════════════════════════════════════════════════════════════════════
    with tab3:
        if bt.empty:
            st.warning("Not enough data to run backtest. Try expanding the date range.")
            st.stop()

        energy_mwh = power_mw * duration_hrs
        ann_rev = bt_sum["annualized_revenue"]
        rev_per_mw = bt_sum["revenue_per_mw"]
        pos_pct = bt_sum["positive_days_pct"]
        avg_daily = bt_sum["avg_daily_revenue"]

        if rev_per_mw > 80000:
            rev_signal, rev_color = "strong", "#1a7a3a"
        elif rev_per_mw > 40000:
            rev_signal, rev_color = "moderate", "#a05a00"
        else:
            rev_signal, rev_color = "limited", "#a02020"

        # ── Investment Summary ─────────────────────────────────────────────
        st.markdown(
            f"""
            <div class="investment-card">
                <h4>📋 Investment Summary</h4>
                <p>
                A <b>{power_mw} MW / {energy_mwh:.0f} MWh</b> battery in the <b>{zone_display}</b> zone
                would have earned approximately
                <b style="color:#1a5fa8">${ann_rev:,.0f}/year</b> from energy arbitrage alone,
                based on {start_year}–{end_year} market data.
                That works out to <b>${rev_per_mw:,.0f} per MW</b> of installed capacity —
                a <b style="color:{rev_color}">{rev_signal}</b> arbitrage signal for this zone and period.
                </p>
                <p>
                The battery was profitable on <b>{pos_pct}%</b> of trading days, averaging
                <b>${avg_daily:,.2f}/day</b>. Revenue is heavily concentrated:
                <b>{best_month_rev}</b> was the strongest month, and approximately
                <b>{srs:.0f}%</b> of total revenue came from days with at least one high-price event.
                This means <b>availability during extreme price hours is the single biggest driver of returns</b> —
                more important than marginal improvements to your dispatch algorithm.
                </p>
                <p>
                <b>Practical recommendation:</b>
                {"Energy arbitrage alone appears sufficient to support a strong investment case in this zone. Before committing capital, cross-check against NYISO's ICAP (capacity market) revenues and frequency regulation — both can add meaningfully to this baseline." if rev_signal == "strong" else
                 "Energy arbitrage alone may not justify the project on its own in this configuration. Consider whether a larger battery (longer duration or higher power) improves the economics, and factor in ancillary service revenues — particularly frequency regulation, which NYISO rewards batteries well for — before making a final investment decision." if rev_signal == "moderate" else
                 "Energy arbitrage revenue in this configuration is limited. The project economics likely depend heavily on ancillary service revenues and/or capacity payments. Revisit the battery size, zone selection, or time period before drawing conclusions — or model the full revenue stack including ICAP and regulation to see if the project is viable."}
                </p>
                <p class="note">
                ⚠️ This backtest assumes perfect daily price foresight (upper bound on arbitrage revenue) and models energy arbitrage only.
                Real-world revenue would include ancillary services and capacity markets, which can materially change the picture.
                Cycle degradation and O&amp;M costs are not modelled.
                </p>
            </div>
            """,
            unsafe_allow_html=True
        )

        # ── KPIs ──────────────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Revenue", f"${bt_sum['total_revenue']:,.0f}")
        c2.metric("Annualized Revenue", f"${ann_rev:,.0f}/yr")
        c3.metric("Revenue per MW", f"${rev_per_mw:,.0f}/MW")
        c4.metric("Profitable Days", f"{pos_pct}%")

        c1b, c2b = st.columns(2)
        c1b.metric("Best Single Day", f"${bt_sum['best_day']:,.2f}")
        c2b.metric("Worst Single Day", f"${bt_sum['worst_day']:,.2f}")

        # ── Monthly revenue ───────────────────────────────────────────────
        st.subheader("Monthly Arbitrage Revenue")
        if not monthly.empty:
            fig6 = px.bar(
                monthly, x="month_str", y="revenue",
                template="plotly_dark",
                color="revenue",
                color_continuous_scale=["#e45756", "#f58518", "#54a24b"],
                labels={"month_str": "Month", "revenue": "Revenue ($)"},
            )
            fig6.add_hline(y=0, line_color="white", line_width=1)
            fig6.update_layout(height=360, coloraxis_showscale=False, xaxis_tickangle=-45)
            st.plotly_chart(fig6, use_container_width=True)

        st.markdown(
            f'<div class="insight-box">💡 <b>Action:</b> <b>{best_month_rev}</b> was the strongest month — '
            f'this is when your battery earns the most and when any downtime is most costly. '
            f'<b>{worst_month_rev}</b> was the weakest. If you have flexibility on maintenance windows, '
            f'schedule them in {worst_month_rev} to minimise lost revenue. '
            f'Red bars (negative months) mean spread was too thin to cover charging costs — '
            f'in a real system you would simply not trade on those days, so actual losses would be lower than shown.</div>',
            unsafe_allow_html=True
        )

        # ── Cumulative revenue ────────────────────────────────────────────
        st.subheader("Cumulative Revenue Over Time")
        fig7 = px.area(bt, x="date", y="cumulative_revenue",
                       template="plotly_dark",
                       labels={"date": "Date", "cumulative_revenue": "Cumulative Revenue ($)"},
                       color_discrete_sequence=["#54a24b"])
        fig7.update_layout(height=320)
        st.plotly_chart(fig7, use_container_width=True)

        st.markdown(
            f'<div class="insight-box">💡 <b>What to look for:</b> A steadily rising curve with steep jumps '
            f'during peak months is healthy — it means the battery earns consistently but captures outsized '
            f'returns when the market is stressed. A flat curve for long stretches signals revenue risk: '
            f'your project cash flows could be volatile, and debt service coverage in quiet periods '
            f'should be stress-tested in your financial model.</div>',
            unsafe_allow_html=True
        )

        # ── Daily distribution ────────────────────────────────────────────
        st.subheader("Daily Revenue Distribution")
        fig8 = px.histogram(bt, x="daily_revenue", nbins=60,
                            template="plotly_dark",
                            color_discrete_sequence=["#4c78a8"],
                            labels={"daily_revenue": "Daily Revenue ($)"})
        fig8.add_vline(x=0, line_color="white", line_dash="dash")
        fig8.update_layout(height=300)
        st.plotly_chart(fig8, use_container_width=True)

        # ── Key Takeaways ─────────────────────────────────────────────────
        st.subheader("Key Takeaways")
        st.markdown(
            f"""
            <div class="takeaway-grid">
                <div class="takeaway-item">
                    🕐 <strong>When to discharge</strong>
                    High prices cluster around <b>{ph}</b>. Program your battery to hold capacity
                    until this window. Do not let automated dispatch drain the battery in the morning
                    at $40/MWh when $200+/MWh opportunities arrive in the afternoon.
                </div>
                <div class="takeaway-item">
                    📅 <strong>Protect your peak months</strong>
                    <b>{pm}</b> and <b>{pm2}</b> generate a disproportionate share of annual revenue.
                    Lock in maintenance windows for off-peak months now.
                    A two-week outage in {pm} could cost more than the rest of the year's revenue combined.
                </div>
                <div class="takeaway-item">
                    💰 <strong>Uptime beats optimisation</strong>
                    ~<b>{srs:.0f}%</b> of revenue comes from high-price days.
                    Investing in battery reliability and grid connection uptime will deliver
                    better returns than fine-tuning your dispatch algorithm.
                    Prioritise availability above all else.
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        with st.expander("📋 Raw Daily Data"):
            st.dataframe(
                bt[["date","avg_charge_price","avg_discharge_price","price_spread",
                    "daily_revenue","cumulative_revenue"]].rename(columns={
                    "date": "Date",
                    "avg_charge_price": "Avg Charge Price ($/MWh)",
                    "avg_discharge_price": "Avg Discharge Price ($/MWh)",
                    "price_spread": "Spread ($/MWh)",
                    "daily_revenue": "Daily Revenue ($)",
                    "cumulative_revenue": "Cumulative Revenue ($)",
                }),
                use_container_width=True,
                height=300,
            )
