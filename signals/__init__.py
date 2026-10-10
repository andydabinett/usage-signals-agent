"""Usage Signals Agent: real public signals + warehouse-first scoring + cited sales handoffs."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
CONFIG_DIR = ROOT / "config"
SEEDS_DIR = ROOT / "seeds"
SNAPSHOT_DB = ROOT / "snapshot" / "warehouse.duckdb"
EXPECTED_JSON = ROOT / "snapshot" / "expected.json"
DATA_DB = ROOT / "data" / "warehouse.duckdb"
REPO_URL = "https://github.com/andydabinett/usage-signals-agent"
__version__ = "0.1.0"
