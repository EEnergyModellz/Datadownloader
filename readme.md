# Market Data Collector — Ubuntu Headless Setup

Automated collection of S&P 500 equities, macro (FRED), and commodity futures data.
Designed to run headless on Ubuntu, syncing to a Windows GPU workstation via Syncthing.

## Quick Start

```bash
# 1. Clone/copy this folder to your Ubuntu machine
cd ~/market-data-collector

# 2. Run setup (installs deps, creates dirs, sets up cron)
chmod +x setup.sh
./setup.sh

# 3. First run — grab full history (takes ~15 min for equities)
source venv/bin/activate
python scripts/collect_equities.py --full-history
python scripts/collect_macro.py
python scripts/collect_commodities.py --full-history

# 4. Check status
python scripts/status.py
```

After the first run, cron handles daily updates automatically.


## Project Structure

```
~/market-data-collector/
├── setup.sh                  # One-time setup script
├── config/
│   └── settings.conf         # FRED API key, paths
├── scripts/
│   ├── utils.py              # Shared helpers
│   ├── collect_equities.py   # S&P 500 daily OHLCV
│   ├── collect_macro.py      # FRED economic data
│   ├── collect_commodities.py # Futures & commodity ETFs
│   └── status.py             # Health check
├── logs/                     # Cron job output
└── venv/                     # Python virtual environment

~/market-data/                # ← This is what Syncthing syncs
├── equities/daily/           # Per-ticker parquet files
├── macro/                    # FRED series by category
│   ├── rates/
│   ├── inflation/
│   ├── gdp/
│   ├── employment/
│   ├── money/
│   ├── financial/
│   ├── housing/
│   ├── leading/
│   ├── all_macro_combined.parquet
│   └── series_index.csv
├── commodities/              # Futures by category
│   ├── energy/
│   ├── metals/
│   ├── agriculture/
│   ├── livestock/
│   ├── indices/
│   ├── all_commodities_close.parquet
│   └── ticker_reference.csv
├── sp500_members/
│   ├── latest.csv
│   └── 2025-03-25.csv
└── metadata/
    └── collection_log.csv
```


## Syncthing Setup (Ubuntu ↔ Windows)

### On Ubuntu:
```bash
# Syncthing was installed by setup.sh, enable it as a service:
sudo systemctl enable syncthing@$USER
sudo systemctl start syncthing@$USER

# Open the web UI (from another machine on the same network):
# http://<ubuntu-ip>:8384
```

### On Windows:
1. Download Syncthing from https://syncthing.net/downloads/
2. Run it — it opens a browser at http://localhost:8384
3. In the Ubuntu web UI:
   - Click "Actions" → "Show ID" — copy the device ID
4. In the Windows web UI:
   - Click "Add Remote Device" → paste the Ubuntu device ID
5. Back on Ubuntu web UI:
   - Accept the Windows device when it appears
   - Click "Add Folder":
     - Folder Path: `/home/<your-user>/market-data`
     - Share with: your Windows device
6. On Windows, accept the folder share
   - Set the local path to something like `D:\market-data`

That's it. Syncthing will keep both folders in sync whenever both
machines are on. No port forwarding, no cloud, no SSH keys.

**Tip:** Set Syncthing to "Send Only" on Ubuntu and "Receive Only"
on Windows. That way the Ubuntu box is the source of truth and
accidental edits on Windows don't propagate back.


## Cron Schedule

| Job          | Schedule               | Time (UTC) |
|-------------|------------------------|------------|
| Equities    | Mon–Fri                | 22:00      |
| Commodities | Mon–Fri                | 22:30      |
| Macro       | Sunday                 | 10:00      |

Check cron: `crontab -l`
Check logs: `tail -50 ~/market-data-collector/logs/equities.log`


## Loading Data on Windows (or anywhere)

```python
import pandas as pd

# Single stock
aapl = pd.read_parquet("D:/market-data/equities/daily/AAPL.parquet")

# All macro in one dataframe
macro = pd.read_parquet("D:/market-data/macro/all_macro_combined.parquet")

# All commodity close prices
commod = pd.read_parquet("D:/market-data/commodities/all_commodities_close.parquet")

# Current S&P 500 members
members = pd.read_csv("D:/market-data/sp500_members/latest.csv")
```


## Troubleshooting

**yfinance rate limiting:** If you see many errors, Yahoo may be
throttling. The scripts have built-in delays but you can increase
`time.sleep()` in the batch loop.

**FRED key not working:** Verify at https://fred.stlouisfed.org/docs/api/api_key.html
that your key is active. Keys are free but need email verification.

**Cron not running:** Check `systemctl status cron` and make sure
the venv python path in `crontab -l` is correct.

**Disk space:** Run `python scripts/status.py` — full S&P 500
history is roughly 500MB–1GB in Parquet. Macro and commodities
are tiny (~50MB).
