import pandas as pd
import numpy as np

def run_backtest(
    df: pd.DataFrame,
    power_mw: float = 1.0,
    duration_hrs: float = 4.0,
    roundtrip_efficiency: float = 0.85,
    charge_hours: int = 4,
    discharge_hours: int = 4,
) -> pd.DataFrame:
    """
    Simple price arbitrage backtest for a battery.

    Strategy: Each day, charge during the N cheapest hours,
    discharge during the N most expensive hours.

    Args:
        df: LBMP dataframe with 'date', 'hour', 'lbmp' columns
        power_mw: Battery power rating in MW
        duration_hrs: Battery duration in hours (energy = power * duration)
        roundtrip_efficiency: Round-trip efficiency (e.g. 0.85 = 85%)
        charge_hours: Number of hours to charge per day
        discharge_hours: Number of hours to discharge per day

    Returns:
        DataFrame with daily revenue results.
    """
    results = []
    energy_mwh = power_mw * duration_hrs

    for date, day_df in df.groupby("date"):
        if len(day_df) < 20:  # skip incomplete days
            continue

        day_sorted = day_df.sort_values("lbmp")

        cheap = day_sorted.head(charge_hours)
        expensive = day_sorted.tail(discharge_hours)

        avg_charge_price = cheap["lbmp"].mean()
        avg_discharge_price = expensive["lbmp"].mean()

        # Energy charged (limited by capacity)
        energy_charged = min(power_mw * charge_hours, energy_mwh)
        energy_discharged = energy_charged * roundtrip_efficiency

        charge_cost = energy_charged * avg_charge_price
        discharge_revenue = energy_discharged * avg_discharge_price

        daily_revenue = discharge_revenue - charge_cost

        results.append({
            "date": date,
            "avg_charge_price": round(avg_charge_price, 2),
            "avg_discharge_price": round(avg_discharge_price, 2),
            "price_spread": round(avg_discharge_price - avg_charge_price, 2),
            "energy_charged_mwh": round(energy_charged, 2),
            "energy_discharged_mwh": round(energy_discharged, 2),
            "charge_cost": round(charge_cost, 2),
            "discharge_revenue": round(discharge_revenue, 2),
            "daily_revenue": round(daily_revenue, 2),
        })

    result_df = pd.DataFrame(results)
    if result_df.empty:
        return result_df

    result_df["date"] = pd.to_datetime(result_df["date"])
    result_df["month"] = result_df["date"].dt.to_period("M")
    result_df["cumulative_revenue"] = result_df["daily_revenue"].cumsum()

    return result_df


def monthly_summary(backtest_df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate backtest results by month."""
    if backtest_df.empty:
        return pd.DataFrame()

    monthly = (
        backtest_df.groupby("month")
        .agg(
            revenue=("daily_revenue", "sum"),
            avg_spread=("price_spread", "mean"),
            trading_days=("daily_revenue", "count"),
            positive_days=("daily_revenue", lambda x: (x > 0).sum()),
        )
        .reset_index()
    )
    monthly["month_str"] = monthly["month"].astype(str)
    monthly["revenue"] = monthly["revenue"].round(2)
    monthly["avg_spread"] = monthly["avg_spread"].round(2)
    return monthly


def backtest_summary(backtest_df: pd.DataFrame, power_mw: float, duration_hrs: float) -> dict:
    """Return high-level backtest KPIs."""
    if backtest_df.empty:
        return {}

    total_revenue = backtest_df["daily_revenue"].sum()
    avg_daily = backtest_df["daily_revenue"].mean()
    positive_days = (backtest_df["daily_revenue"] > 0).sum()
    total_days = len(backtest_df)

    return {
        "total_revenue": round(total_revenue, 0),
        "avg_daily_revenue": round(avg_daily, 2),
        "annualized_revenue": round(avg_daily * 365, 0),
        "positive_days_pct": round(positive_days / total_days * 100, 1),
        "best_day": round(backtest_df["daily_revenue"].max(), 2),
        "worst_day": round(backtest_df["daily_revenue"].min(), 2),
        "revenue_per_mw": round(total_revenue / power_mw, 0),
    }
