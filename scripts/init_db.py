"""SQLite şemasını oluşturur."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.database.schema import initialise_database


if __name__ == "__main__":
    database_path = PROJECT_ROOT / "data" / "process_risk.db"
    initialise_database(database_path)
    print(f"SQLite veritabanı hazır: {database_path}")
