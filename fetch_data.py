import requests
import pandas as pd
import zipfile
import io
from datetime import datetime, timedelta
import os

NYISO_BASE_URL = "https://mis.nyiso.com/public/csv/realtime"

ZONES = {
    "CAPITL": "Capital",
    "CENTRL": "Central",
    "DUNWOD": "Dunwoodie",
    "GENESE": "Genesee",
    "HUD VL": "Hudson Valley",
    "LONGIL": "Long Island",
    "MHK VL": "Mohawk Valley",
    "MILLWD": "Millwood",
    "N.Y.C.": "New York City",
    "NORTH": "North",
    "WEST": "West",
}

def fetch_nyiso_lbmp(year: int, month: int) -> pd.DataFrame:
    """
    Fetch NYISO real-time LBMP data for a given month.
    NYISO stores data as monthly zip files containing daily CSVs.
    """
    date_str = f"{year}{month:02d}01"
    url = f"{NYISO_BASE_URL}/{date_str}realtime_zone_csv.zip"

    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        raise ValueError(f"Failed to fetch data for {year}-{month:02d}: HTTP {response.status_code}")

    dfs = []
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        for filename in z.namelist():
            if filename.endswith(".csv"):
                with z.open(filename) as f:
                    df = pd.read_csv(f)
                    dfs.append(df)

    if not dfs:
        raise ValueError(f"No CSV files found in zip for {year}-{month:02d}")

    combined = pd.concat(dfs, ignore_index=True)
    return _clean_lbmp(combined)


def _clean_lbmp(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and standardize NYISO LBMP dataframe."""
    df.columns = df.columns.str.strip()

    # Rename columns
    col_map = {
        "Time Stamp": "timestamp",
        "Name": "zone",
        "LBMP ($/MWHr)": "lbmp",
        "Marginal Cost Losses ($/MWHr)": "mc_losses",
        "Marginal Cost Congestion ($/MWHr)": "mc_congestion",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["lbmp"] = pd.to_numeric(df["lbmp"], errors="coerce")
    df = df.dropna(subset=["timestamp", "lbmp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Add time features
    df["hour"] = df["timestamp"].dt.hour
    df["month"] = df["timestamp"].dt.month
    df["date"] = df["timestamp"].dt.date
    df["month_name"] = df["timestamp"].dt.strftime("%b %Y")

    return df


def fetch_date_range(start_year: int, start_month: int, end_year: int, end_month: int) -> pd.DataFrame:
    """Fetch multiple months of LBMP data."""
    dfs = []
    current = datetime(start_year, start_month, 1)
    end = datetime(end_year, end_month, 1)

    while current <= end:
        try:
            df = fetch_nyiso_lbmp(current.year, current.month)
            dfs.append(df)
            print(f"Fetched {current.year}-{current.month:02d}")
        except Exception as e:
            print(f"Warning: could not fetch {current.year}-{current.month:02d}: {e}")

        if current.month == 12:
            current = datetime(current.year + 1, 1, 1)
        else:
            current = datetime(current.year, current.month + 1, 1)

    if not dfs:
        raise ValueError("No data could be fetched.")

    return pd.concat(dfs, ignore_index=True)


def get_zone_display_name(zone_code: str) -> str:
    return ZONES.get(zone_code, zone_code)
