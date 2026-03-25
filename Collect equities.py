#!/usr/bin/env python3
"""
Collect S&P 500 daily OHLCV data.

Strategy:
  - Fetch current S&P 500 member list from Wikipedia
  - Download daily bars for all members (last 5 days to catch gaps)
  - Save per-ticker parquet files (append-safe, deduplicated)
  - Also save a combined "universe" file for quick loading

Run manually:  python collect_equities.py
               python collect_equities.py --full-history   (first run, grabs max history)
"""

import sys
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from utils import get_data_dir, get_logger, save_parquet, write_metadata

log = get_logger("equities")


# ── S&P 500 member list ──────────────────────────────────────

def fetch_sp500_tickers() -> list[str]:
    """Pull current S&P 500 tickers from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    tables = pd.read_html(url)
    df = tables[0]
    tickers = df["Symbol"].str.replace(".", "-", regex=False).tolist()
    return sorted(tickers)


def save_member_list(tickers: list[str], data_dir: Path):
    """Persist the current member list with a datestamp."""
    out = data_dir / "sp500_members" / f"{datetime.utcnow():%Y-%m-%d}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"ticker": tickers}).to_csv(out, index=False)
    # Also overwrite a "latest" copy for easy loading
    latest = data_dir / "sp500_members" / "latest.csv"
    pd.DataFrame({"ticker": tickers}).to_csv(latest, index=False)
    log.info(f"Saved {len(tickers)} tickers to {out}")


# ── Data download ─────────────────────────────────────────────

def download_equities(tickers: list[str], data_dir: Path, full_history: bool = False):
    """
    Download OHLCV for each ticker and save as parquet.
    - full_history: grab max available data (first run)
    - incremental: last 5 trading days
    """
    out_dir = data_dir / "equities" / "daily"
    out_dir.mkdir(parents=True, exist_ok=True)

    if full_history:
        period = "max"
        log.info("Full history mode — downloading max available data")
    else:
        period = "5d"

    success = 0
    errors = []

    # Download in batches to be polite to Yahoo
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        batch_str = " ".join(batch)
        log.info(f"Batch {i // batch_size + 1}: downloading {len(batch)} tickers...")

        try:
            data = yf.download(
                batch_str,
                period=period,
                interval="1d",
                group_by="ticker",
                threads=True,
                progress=False,
            )
        except Exception as e:
            log.error(f"Batch download failed: {e}")
            errors.extend(batch)
            continue

        for ticker in batch:
            try:
                if len(batch) == 1:
                    df = data.copy()
                else:
                    df = data[ticker].copy()

                df = df.dropna(how="all")
                if df.empty:
                    continue

                # Flatten multi-level columns if present
                if hasattr(df.columns, "levels"):
                    df.columns = df.columns.get_level_values(-1)

                df = df.reset_index()

                # Merge with existing data if any
                parquet_path = out_dir / f"{ticker}.parquet"
                if parquet_path.exists() and not full_history:
                    existing = pd.read_parquet(parquet_path)
                    df = pd.concat([existing, df]).drop_duplicates(
                        subset=["Date"], keep="last"
                    )
                    df = df.sort_values("Date").reset_index(drop=True)

                save_parquet(df, parquet_path)
                success += 1

            except Exception as e:
                errors.append(ticker)
                log.warning(f"  {ticker}: {e}")

        # Small delay between batches
        time.sleep(2)

    log.info(f"Done: {success} tickers saved, {len(errors)} errors")
    if errors:
        log.warning(f"Failed tickers: {errors[:20]}{'...' if len(errors) > 20 else ''}")

    return success, errors


# ── Main ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Download max available history (use on first run)",
    )
    args = parser.parse_args()

    data_dir = get_data_dir()
    log.info(f"Data directory: {data_dir}")

    # 1. Get current S&P 500 members
    log.info("Fetching S&P 500 member list...")
    try:
        tickers = fetch_sp500_tickers()
        save_member_list(tickers, data_dir)
    except Exception as e:
        log.error(f"Failed to fetch ticker list: {e}")
        # Fall back to latest saved list
        latest = data_dir / "sp500_members" / "latest.csv"
        if latest.exists():
            tickers = pd.read_csv(latest)["ticker"].tolist()
            log.info(f"Using cached list: {len(tickers)} tickers")
        else:
            log.error("No cached ticker list. Aborting.")
            sys.exit(1)

    # 2. Download data
    success, errors = download_equities(tickers, data_dir, args.full_history)

    # 3. Log metadata
    write_metadata(
        data_dir,
        source="equities",
        status="ok" if not errors else "partial",
        details=f"{success} ok / {len(errors)} errors",
    )


if __name__ == "__main__":
    main()
