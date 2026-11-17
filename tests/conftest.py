import os
import sys
from pathlib import Path

# Ensure isolated test database for all pytest executions
TEST_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = TEST_ROOT.parent
TEST_DB_PATH = TEST_ROOT / "test_aura.db"

# Force test database URL into environment before any backend module is loaded
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Initialize test database tables and triggers
from backend.db.init_db import init_database
from backend.db.session import engine, Base

# Clean prior test DB if present
if TEST_DB_PATH.exists():
    try:
        TEST_DB_PATH.unlink()
    except Exception:
        pass

init_database()
