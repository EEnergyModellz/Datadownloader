#!/usr/bin/env python3
"""
Quick status check — shows what data is collected and freshness.
Run:  python scripts/status.py
"""

import os
from datetime import datetime
from pathlib import Path

from utils import get_data_dir


def human_size(nbytes):
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def dir_stats(path: Path):
    """Count files and total size in a directory tree."""
    files = list(path.rglob("*.parquet"))
    total = sum(f.stat().st_size for f in files)
    newest = max((f.stat().st_mtime for f in files), default=0)
    return len(files), total, newest


def main():
    data_dir = get_data_dir()
    print(f"\n{'='*60}")
    print(f"  Market Data Status  —  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Data root: {data_dir}")
    print(f"{'='*60}\n")

    sections = [
        ("Equities (S&P 500)", "equities"),
        ("Macro (FRED)",       "macro"),
        ("Commodities",        "commodities"),
    ]

    total_files = 0
    total_size = 0

    for label, subdir in sections:
        path = data_dir / subdir
        if not path.exists():
            print(f"  {label:30s}  — not collected yet")
            continue

        nfiles, size, newest = dir_stats(path)
        total_files += nfiles
        total_size += size

        if newest > 0:
            last = datetime.fromtimestamp(newest).strftime("%Y-%m-%d %H:%M")
        else:
            last = "never"

        print(f"  {label:30s}  {nfiles:4d} files  {human_size(size):>10s}  last: {last}")

    # SP500 member list
    members_dir = data_dir / "sp500_members"
    latest = members_dir / "latest.csv"
    if latest.exists():
        import pandas as pd
        n = len(pd.read_csv(latest))
        print(f"\n  S&P 500 members: {n} tickers (list updated {datetime.fromtimestamp(latest.stat().st_mtime):%Y-%m-%d})")

    # Collection log
    meta = data_dir / "metadata" / "collection_log.csv"
    if meta.exists():
        import pandas as pd
        log = pd.read_csv(meta)
        last5 = log.tail(5)
        print(f"\n  Recent collection runs:")
        for _, row in last5.iterrows():
            print(f"    {row['timestamp'][:19]}  {row['source']:15s}  {row['status']:8s}  {row.get('details','')}")

    print(f"\n  {'TOTAL':30s}  {total_files:4d} files  {human_size(total_size):>10s}")

    # Disk space
    stat = os.statvfs(str(data_dir))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024**3)
    print(f"  Disk free: {free_gb:.1f} GB")
    print()


if __name__ == "__main__":
    main()
