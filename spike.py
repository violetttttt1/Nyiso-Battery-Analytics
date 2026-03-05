import pandas as pd
import numpy as np

DEFAULT_SPIKE_THRESHOLD = 200  # $/MWh


def identify_spikes(df: pd.DataFrame, threshold: float = DEFAULT_SPIKE_THRESHOLD) -> pd.DataFrame:
    """Add a boolean 'is_spike' column to the dataframe."""
    df = df.copy()
    df["is_spike"] = df["lbmp"] >= threshold
    return df


def spike_summary(df: pd.DataFrame, threshold: float = DEFAULT_SPIKE_THRESHOLD) -> dict:
    """Return high-level spike statistics."""
    df = identify_spikes(df, threshold)
    spikes = df[df["is_spike"]]

    total_hours = len(df)
    spike_hours = len(spikes)

    return {
        "total_hours": total_hours,
        "spike_hours": spike_hours,
        "spike_pct": round(spike_hours / total_hours * 100, 2) if total_hours > 0 else 0,
        "avg_spike_price": round(spikes["lbmp"].mean(), 2) if spike_hours > 0 else 0,
        "max_spike_price": round(spikes["lbmp"].max(), 2) if spike_hours > 0 else 0,
        "avg_normal_price": round(df[~df["is_spike"]]["lbmp"].mean(), 2),
    }


def spikes_by_hour(df: pd.DataFrame, threshold: float = DEFAULT_SPIKE_THRESHOLD) -> pd.DataFrame:
    """Count spikes by hour of day."""
    df = identify_spikes(df, threshold)
    return (
        df[df["is_spike"]]
        .groupby("hour")
        .size()
        .reindex(range(24), fill_value=0)
        .reset_index()
        .rename(columns={"hour": "Hour of Day", 0: "Spike Count"})
    )


def spikes_by_month(df: pd.DataFrame, threshold: float = DEFAULT_SPIKE_THRESHOLD) -> pd.DataFrame:
    """Count spikes by calendar month."""
    df = identify_spikes(df, threshold)
    return (
        df[df["is_spike"]]
        .groupby("month")
        .size()
        .reindex(range(1, 13), fill_value=0)
        .reset_index()
        .rename(columns={"month": "Month", 0: "Spike Count"})
    )


def spike_heatmap_data(df: pd.DataFrame, threshold: float = DEFAULT_SPIKE_THRESHOLD) -> pd.DataFrame:
    """
    Return a pivot table: rows = hour of day, columns = month number.
    Values = average LBMP during spike hours, 0 if no spike.
    """
    df = identify_spikes(df, threshold)
    spikes = df[df["is_spike"]].copy()

    if spikes.empty:
        return pd.DataFrame()

    pivot = spikes.pivot_table(
        values="lbmp",
        index="hour",
        columns="month",
        aggfunc="mean",
        fill_value=0,
    )
    return pivot


def price_duration_curve(df: pd.DataFrame) -> pd.DataFrame:
    """Sort prices descending to build a load duration curve."""
    sorted_prices = df["lbmp"].sort_values(ascending=False).reset_index(drop=True)
    total = len(sorted_prices)
    result = pd.DataFrame({
        "Percentile": [(i / total) * 100 for i in range(total)],
        "Price ($/MWh)": sorted_prices.values,
    })
    return result
