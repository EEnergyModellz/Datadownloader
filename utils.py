"""
Shared utilities for all collectors.
"""

import os
import sys
import logging
from datetime import datetime
from pathlib import Path


def load_config():
    """Load settings from config file."""
    config_path = Path(__file__).parent.parent / "config" / "settings.conf"
    config = {}
    with open(config_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, _, value = line.partition("=")
                config[key.strip()] = value.strip()
    return config


def get_data_dir():
    """Return the data root directory."""
    config = load_config()
    return Path(config.get("DATA_DIR", Path.home() / "market-data"))


def get_logger(name: str) -> logging.Logger:
    """Create a logger with timestamp prefix."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
    return logger


def save_parquet(df, path: Path):
    """Save dataframe as parquet, creating dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, engine="pyarrow", compression="snappy")


def write_metadata(data_dir: Path, source: str, status: str, details: str = ""):
    """Append a line to the metadata log for tracking collection runs."""
    meta_file = data_dir / "metadata" / "collection_log.csv"
    meta_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().isoformat()
    header_needed = not meta_file.exists()
    with open(meta_file, "a") as f:
        if header_needed:
            f.write("timestamp,source,status,details\n")
        f.write(f"{timestamp},{source},{status},{details}\n")
