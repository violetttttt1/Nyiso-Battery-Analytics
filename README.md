# ⚡ NYISO Battery Analytics

A Streamlit app that helps battery asset owners and investors understand electricity price dynamics and model storage arbitrage revenue in New York's wholesale electricity market — using real, publicly available NYISO data.

**Live demo:** https://nyiso-battery-analytics-4pzqbyczeuxrb68tjm63ek.streamlit.app/

---

## The Problem

Before committing capital to a battery storage project, investors need to answer one question:

> **"How much revenue can this asset realistically earn, and where does that revenue come from?"**

Energy arbitrage — charging when prices are low, discharging when they are high — is the most fundamental revenue stream for a battery in a wholesale market. But the answer is not obvious without looking at actual historical price data. This tool makes that analysis accessible without requiring a data engineering team or proprietary software.

## What This Tool Does

Three tabs, each building on the last:

**Price Overview** — Hourly LBMP timeline with high-price events highlighted, a price duration curve showing how often any given price level is exceeded, and a dataset context panel that shows where your chosen threshold sits relative to the actual distribution (median, p75, p90, p95).

**High Price Analysis** — Which hours of the day and which months see the most elevated prices. Each chart is paired with a plain-language action: when to discharge, when not to schedule maintenance, how to think about revenue risk.

**Battery Backtest** — Simulates a daily arbitrage strategy across the selected period. Charges during the N cheapest hours, discharges during the N most expensive. Outputs monthly revenue, cumulative revenue, daily distribution, and a full Investment Summary with a strong / moderate / limited signal rating and a specific recommendation for each case.

## Design Choices

**Why perfect-foresight arbitrage?** It is the upper bound on energy-only revenue — the best a battery could have done with full knowledge of that day's prices. This is the right baseline for an investment case. Real dispatch layers in forecast error on top, but you need this number first.

**Why NYISO?** Publicly available real-time LBMP data, well-structured, no API key required, and one of the more volatile wholesale markets in the US.

**Why Streamlit?** The goal was to put something in front of a user quickly. Streamlit deploys directly from GitHub, runs in the browser with no installation, and handles interactive controls natively. For a decision-support tool, frictionless access matters.

**Why include explicit investment recommendations?** A chart showing monthly revenue is useful. A sentence that says "a two-week outage in July costs more than the rest of the year combined" is actionable. The tool is designed to support decisions, not just display data.

## Data Source

[NYISO Market Information System (MIS)](https://mis.nyiso.com/public/) — real-time zonal LBMP data, 5-minute resolution, aggregated to hourly. No API key required. Data is fetched directly from NYISO's public CSV archive.

## Running Locally

```bash
git clone https://github.com/yourusername/nyiso-battery-analytics
cd nyiso-battery-analytics
pip install -r requirements.txt
streamlit run app.py
```

## Project Structure

```
nyiso-battery-analytics/
├── app.py              # Streamlit UI, layout, and all chart logic
├── fetch_data.py       # NYISO data fetching, zip extraction, and cleaning
├── spike.py            # High-price hour identification and statistics
├── backtest.py         # Daily arbitrage simulation and revenue calculations
├── requirements.txt
└── README.md
```

## Limitations & Next Steps

- Backtest assumes perfect daily price foresight — real dispatch would require a day-ahead price forecast
- Models energy arbitrage only — ancillary services (frequency regulation, ICAP capacity payments) are not included and can materially increase total revenue
- Cycle degradation and O&M costs are not modelled
- A natural next step is building a full revenue stack view: energy arbitrage + regulation + capacity, which is how most BESS projects are actually underwritten
