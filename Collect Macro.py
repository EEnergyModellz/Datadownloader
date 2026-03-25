#!/usr/bin/env python3
"""
Collect macroeconomic data from FRED (Federal Reserve Economic Data).

Covers: yield curve, rates, GDP, inflation, employment, money supply,
        financial conditions, housing, and leading indicators.

Requires a free FRED API key in config/settings.conf.
Get one at: https://fred.stlouisfed.org/docs/api/api_key.html

Run manually:  python collect_macro.py
"""

import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from utils import load_config, get_data_dir, get_logger, save_parquet, write_metadata

log = get_logger("macro")


# ── FRED series to collect ────────────────────────────────────
# Format: (series_id, human_readable_name, category)

FRED_SERIES = [
    # --- Interest rates & yield curve ---
    ("DFF",       "Fed Funds Rate",                 "rates"),
    ("DGS2",     "2Y Treasury Yield",               "rates"),
    ("DGS5",     "5Y Treasury Yield",               "rates"),
    ("DGS10",    "10Y Treasury Yield",              "rates"),
    ("DGS30",    "30Y Treasury Yield",              "rates"),
    ("T10Y2Y",   "10Y-2Y Spread",                   "rates"),
    ("T10Y3M",   "10Y-3M Spread",                   "rates"),
    ("BAMLH0A0HYM2", "HY OAS Spread",              "rates"),

    # --- Inflation ---
    ("CPIAUCSL",  "CPI All Urban",                  "inflation"),
    ("CPILFESL",  "Core CPI (ex Food/Energy)",      "inflation"),
    ("PCEPI",     "PCE Price Index",                "inflation"),
    ("T5YIE",     "5Y Breakeven Inflation",         "inflation"),
    ("T10YIE",    "10Y Breakeven Inflation",        "inflation"),
    ("MICH",      "UMich Inflation Expectations",   "inflation"),

    # --- GDP & output ---
    ("GDP",       "Nominal GDP",                    "gdp"),
    ("GDPC1",    "Real GDP",                        "gdp"),
    ("INDPRO",   "Industrial Production",           "gdp"),

    # --- Employment ---
    ("UNRATE",    "Unemployment Rate",              "employment"),
    ("PAYEMS",    "Nonfarm Payrolls",               "employment"),
    ("ICSA",      "Initial Jobless Claims",         "employment"),
    ("CCSA",      "Continued Claims",               "employment"),

    # --- Money & credit ---
    ("M2SL",      "M2 Money Supply",                "money"),
    ("WALCL",     "Fed Balance Sheet",              "money"),
    ("TOTRESNS",  "Total Reserves",                 "money"),

    # --- Financial conditions ---
    ("VIXCLS",    "VIX",                            "financial"),
    ("NFCI",      "Chicago Fed NFCI",               "financial"),
    ("STLFSI4",   "StL Fed Financial Stress",       "financial"),
    ("DTWEXBGS",  "Trade-Weighted USD",             "financial"),

    # --- Housing ---
    ("MORTGAGE30US", "30Y Mortgage Rate",           "housing"),
    ("HOUST",        "Housing Starts",              "housing"),
    ("CSUSHPISA",    "Case-Shiller Home Price",     "housing"),

    # --- Leading indicators ---
    ("UMCSENT",      "Consumer Sentiment",          "leading"),
    ("PERMIT",       "Building Permits",            "leading"),
    ("AWHMAN",       "Avg Weekly Hours Mfg",        "leading"),
    ("NEWORDER",     "ISM New Orders",              "leading"),
]


def collect_fred_data(api_key: str, data_dir: Path):
    """Download all FRED series and save as parquet files."""
    from fredapi import Fred

    fred = Fred(api_key=api_key)
    out_dir = data_dir / "macro"
    out_dir.mkdir(parents=True, exist_ok=True)

    success = 0
    errors = []

    # Also build a combined wide-format dataframe
    all_series = {}

    for series_id, name, category in FRED_SERIES:
        try:
            s = fred.get_series(series_id)
            if s is None or s.empty:
                log.warning(f"  {series_id} ({name}): empty")
                continue

            df = s.to_frame(name=series_id)
            df.index.name = "Date"
            df = df.reset_index()

            # Save individual series
            cat_dir = out_dir / category
            save_parquet(df, cat_dir / f"{series_id}.parquet")

            # Add to combined
            all_series[series_id] = s

            success += 1
            log.info(f"  {series_id:20s} ({name}): {len(df)} observations")

        except Exception as e:
            errors.append(series_id)
            log.warning(f"  {series_id} ({name}): FAILED - {e}")

    # Save combined file (wide format, useful for correlation analysis)
    if all_series:
        combined = pd.DataFrame(all_series)
        combined.index.name = "Date"
        combined = combined.reset_index()
        save_parquet(combined, out_dir / "all_macro_combined.parquet")
        log.info(f"Combined macro file: {len(combined)} rows, {len(all_series)} series")

    # Save a human-readable index of what we collected
    index_df = pd.DataFrame(FRED_SERIES, columns=["series_id", "name", "category"])
    index_df.to_csv(out_dir / "series_index.csv", index=False)

    return success, errors


# ── Main ──────────────────────────────────────────────────────

def main():
    data_dir = get_data_dir()
    config = load_config()
    api_key = config.get("FRED_API_KEY", "")

    if not api_key or api_key == "PASTE_YOUR_KEY_HERE":
        log.error("No FRED API key configured!")
        log.error("Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html")
        log.error("Then add it to config/settings.conf")
        sys.exit(1)

    log.info(f"Data directory: {data_dir}")
    log.info(f"Collecting {len(FRED_SERIES)} FRED series...")

    success, errors = collect_fred_data(api_key, data_dir)

    log.info(f"Done: {success} series saved, {len(errors)} errors")

    write_metadata(
        data_dir,
        source="macro",
        status="ok" if not errors else "partial",
        details=f"{success} ok / {len(errors)} errors",
    )


if __name__ == "__main__":
    main()
