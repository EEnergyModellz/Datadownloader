#!/bin/bash
# ============================================================
# Market Data Collector - Ubuntu Setup
# Run once: chmod +x setup.sh && ./setup.sh
# ============================================================

set -e

echo "=== Market Data Collector Setup ==="
echo ""

# --- 1. System packages ---
echo "[1/5] Installing system packages..."
sudo apt update -qq
sudo apt install -y python3 python3-pip python3-venv cron syncthing

# --- 2. Create data directories ---
echo "[2/5] Creating data directories..."
DATA_DIR="$HOME/market-data"
mkdir -p "$DATA_DIR"/{equities/daily,macro,commodities,metadata,sp500_members}
echo "Data root: $DATA_DIR"

# --- 3. Python virtual environment ---
echo "[3/5] Setting up Python environment..."
VENV_DIR="$HOME/market-data-collector/venv"
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

pip install --upgrade pip -q
pip install \
    yfinance \
    fredapi \
    pandas \
    pyarrow \
    requests \
    schedule \
    -q

echo "Python packages installed in venv."

# --- 4. FRED API key setup ---
echo ""
echo "[4/5] FRED API key setup"
echo "  Get your free key at: https://fred.stlouisfed.org/docs/api/api_key.html"
echo "  (Takes 2 minutes - just sign up and they give you one)"
echo ""

CONFIG_FILE="$HOME/market-data-collector/config/settings.conf"
if [ ! -f "$CONFIG_FILE" ]; then
    read -p "  Enter your FRED API key (or press Enter to skip for now): " FRED_KEY
    cat > "$CONFIG_FILE" <<EOF
# Market Data Collector Configuration
FRED_API_KEY=${FRED_KEY:-PASTE_YOUR_KEY_HERE}
DATA_DIR=$DATA_DIR
LOG_DIR=$HOME/market-data-collector/logs
EOF
    echo "  Config saved to $CONFIG_FILE"
else
    echo "  Config already exists at $CONFIG_FILE"
fi

# --- 5. Install cron jobs ---
echo "[5/5] Setting up cron jobs..."
SCRIPT_DIR="$HOME/market-data-collector/scripts"
VENV_PYTHON="$VENV_DIR/bin/python"

# Remove old entries if re-running setup
(crontab -l 2>/dev/null | grep -v "market-data-collector") | crontab -

# Add new cron entries
# Equities: every weekday at 22:00 UTC (after US market close)
# Macro:    every Sunday at 10:00 UTC (weekly is fine for macro)
# Commodities: every weekday at 22:30 UTC
(crontab -l 2>/dev/null; cat <<EOF
# --- Market Data Collector ---
0 22 * * 1-5  $VENV_PYTHON $SCRIPT_DIR/collect_equities.py >> $HOME/market-data-collector/logs/equities.log 2>&1
0 10 * * 0    $VENV_PYTHON $SCRIPT_DIR/collect_macro.py >> $HOME/market-data-collector/logs/macro.log 2>&1
30 22 * * 1-5 $VENV_PYTHON $SCRIPT_DIR/collect_commodities.py >> $HOME/market-data-collector/logs/commodities.log 2>&1
# --- End Market Data Collector ---
EOF
) | crontab -

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Cron schedule (all times UTC):"
echo "  Equities:    Mon-Fri 22:00"
echo "  Macro:       Sunday  10:00"
echo "  Commodities: Mon-Fri 22:30"
echo ""
echo "Next steps:"
echo "  1. Add your FRED API key to $CONFIG_FILE if you skipped it"
echo "  2. Test the collectors manually:"
echo "     source venv/bin/activate"
echo "     python scripts/collect_equities.py"
echo "     python scripts/collect_macro.py"
echo "     python scripts/collect_commodities.py"
echo "  3. Install Syncthing and point it at $DATA_DIR"
echo "     Open http://localhost:8384 to configure Syncthing"
echo ""
