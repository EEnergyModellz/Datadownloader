#!/usr/bin/env python3
"""
Collect commodity futures data via Yahoo Finance.

Covers: energy, metals, agriculture, and key commodity indices.

Run manually:  python collect_commodities.py
               python collect_commodities.py --full-history
"""

import argparse
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

from utils import get_data_dir, get_logger, save_parquet, write_metadata

log = get_logger("commodities")


# ── Commodity tickers (Yahoo Finance format) ──────────────────
# Continuous front-month futures contracts

COMMODITIES = {
    # --- Energy ---
    "CL=F":  {"name": "Crude Oil WTI",       "category": "energy"},
    "BZ=F":  {"name": "Brent Crude",          "category": "energy"},
    "NG=F":  {"name": "Natural Gas",           "category": "energy"},
    "HO=F":  {"name": "Heating Oil",           "category": "energy"},
    "RB=F":  {"name": "RBOB Gasoline",         "category": "energy"},

    # --- Precious metals ---
    "GC=F":  {"name": "Gold",                  "category": "metals"},
    "SI=F":  {"name": "Silver",                "category": "metals"},
    "PL=F":  {"name": "Platinum",              "category": "metals"},
    "PA=F":  {"name": "Palladium",             "category": "metals"},

    # --- Industrial metals ---
    "HG=F":  {"name": "Copper",                "category": "metals"},

    # --- Agriculture ---
    "ZC=F":  {"name": "Corn",                  "category": "agriculture"},
    "ZW=F":  {"name": "Wheat",                 "category": "agriculture"},
    "ZS=F":  {"name": "Soybeans",              "category": "agriculture"},
    "KC=F":  {"name": "Coffee",                "category": "agriculture"},
    "SB=F":  {"name": "Sugar",                 "category": "agriculture"},
    "CC=F":  {"name": "Cocoa",                 "category": "agriculture"},
    "CT=F":  {"name": "Cotton",                "category": "agriculture"},

    # --- Livestock ---
    "LE=F":  {"name": "Live Cattle",           "category": "livestock"},
    "HE=F":  {"name": "Lean Hogs",             "category": "livestock"},

    # --- Commodity indices / ETFs (for benchmarking) ---
    "DBA":   {"name": "Agriculture ETF",       "category": "indices"},
    "DBC":   {"name": "Commodity Index ETF",   "category": "indices"},
    "USO":   {"name": "US Oil Fund",           "category": "indices"},
    "GLD":   {"name": "Gold ETF",              "category": "indices"},
    "SLV":   {"name": "Silver ETF",            "category": "indices"},
}


def download_commodities(data_dir: Path, full_history: bool = False):
    """Download OHLCV for all commodity futures."""
    out_dir = data_dir / "commodities"
    out_dir.mkdir(parents=True, exist_ok=True)

    period = "max" if full_history else "5d"
    success = 0
    errors = []

    all_close = {}  # for combined file

    for ticker, info in COMMODITIES.items():
        name = info["name"]
        category = info["category"]

        try:
            df = yf.download(
                ticker, period=period, interval="1d", progress=False
            )
            if df.empty:
                log.warning(f"  {ticker:8s} ({name}): no data")
                continue

            # Flatten columns if multi-level
            if hasattr(df.columns, "levels"):
                df.columns = df.columns.get_level_values(0)

            df = df.reset_index()

            # Save per-ticker in category subdirectory
            safe_name = ticker.replace("=", "_")
            cat_dir = out_dir / category
            parquet_path = cat_dir / f"{safe_name}.parquet"

            # Merge with existing
            if parquet_path.exists() and not full_history:
                existing = pd.read_parquet(parquet_path)
                df = pd.concat([existing, df]).drop_duplicates(
                    subset=["Date"], keep="last"
                )
                df = df.sort_values("Date").reset_index(drop=True)

            save_parquet(df, parquet_path)
            success += 1

            # Collect close prices for combined file
            close_df = df.set_index("Date")["Close"]
            all_close[ticker] = close_df

            log.info(f"  {ticker:8s} ({name:20s}): {len(df)} bars")

        except Exception as e:
            errors.append(ticker)
            log.warning(f"  {ticker:8s} ({name}): FAILED - {e}")

        time.sleep(0.5)  # be polite

    # Save combined close prices
    if all_close:
        combined = pd.DataFrame(all_close)
        combined.index.name = "Date"
        combined = combined.reset_index()
        save_parquet(combined, out_dir / "all_commodities_close.parquet")
        log.info(f"Combined file: {len(combined)} rows, {len(all_close)} tickers")

    # Save ticker reference
    ref = pd.DataFrame(
        [(t, i["name"], i["category"]) for t, i in COMMODITIES.items()],
        columns=["ticker", "name", "category"],
    )
    ref.to_csv(out_dir / "ticker_reference.csv", index=False)

    return success, errors


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-history", action="store_true")
    args = parser.parse_args()

    data_dir = get_data_dir()
    log.info(f"Data directory: {data_dir}")
    log.info(f"Collecting {len(COMMODITIES)} commodity tickers...")

    success, errors = download_commodities(data_dir, args.full_history)

    log.info(f"Done: {success} tickers saved, {len(errors)} errors")

    write_metadata(
        data_dir,
        source="commodities",
        status="ok" if not errors else "partial",
        details=f"{success} ok / {len(errors)} errors",
    )


if __name__ == "__main__":
    main()
