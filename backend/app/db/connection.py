import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

# Global thread lock to ensure safe concurrent access in multi-threaded environments like FastAPI/Uvicorn
db_lock = threading.Lock()


def get_db_path() -> Path:
    """
    Resiliently resolves the path to the SQLite database file.
    Order of precedence:
    1. DATABASE_PATH environment variable
    2. Container volume path '/app/db/finally.db'
    3. Workspace root relative 'db/finally.db'
    4. Local fallback 'db/finally.db' relative to current working directory
    """
    # 1. Check environment variable
    env_path = os.getenv("DATABASE_PATH")
    if env_path:
        return Path(env_path)

    # 2. Check if running inside docker container (custom target /app/db/)
    if os.path.exists("/app/db"):
        return Path("/app/db/finally.db")

    # 3. Local development - attempt relative navigation to find project-level 'db/' directory
    try:
        # __file__ is: backend/app/db/connection.py
        # parents[3] is the project root directory
        proj_root = Path(__file__).resolve().parents[3]
        proj_db_dir = proj_root / "db"
        if proj_db_dir.exists() or (proj_root / "backend").exists():
            return proj_db_dir / "finally.db"
    except IndexError:
        pass

    # 4. Fallback relative to current working directory
    return Path("db/finally.db")


@contextmanager
def get_db_connection():
    """
    Context manager that yields a thread-safe and configured sqlite3.Connection.
    Enforces SQLite foreign key constraints and sets row_factory to sqlite3.Row.
    Automatically handles rollbacks on exceptions and serializes database access
    via a thread lock to eliminate 'database is locked' errors under concurrency.
    """
    db_path = get_db_path()

    # Ensure the parent directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with db_lock:
        # Establish connection with a 30-second timeout for extra safety
        conn = sqlite3.connect(str(db_path), timeout=30.0)

        # Configure row factory to return Row objects supporting name-based lookup
        conn.row_factory = sqlite3.Row

        # Immediately enable foreign key constraint enforcement
        conn.execute("PRAGMA foreign_keys = ON;")

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
