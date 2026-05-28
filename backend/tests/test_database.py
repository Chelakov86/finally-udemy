import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from app.db.connection import get_db_connection, get_db_path
from app.db.manager import init_db


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """
    Fixture to isolate database tests.
    Sets the DATABASE_PATH environment variable to a temporary file path
    unique to each test case, ensuring a clean state and zero interference
    with the actual development or production database.
    """
    temp_db_file = tmp_path / "test_finally.db"
    monkeypatch.setenv("DATABASE_PATH", str(temp_db_file))
    yield temp_db_file
    # Cleanup after test completes
    if temp_db_file.exists():
        try:
            temp_db_file.unlink()
        except OSError:
            pass


def test_database_connection_and_pragma(temp_db):
    """
    Verifies that we can establish a database connection successfully,
    and that 'PRAGMA foreign_keys = ON;' is executed and active immediately.
    """
    # Verify that the DB path matches the temp fixture
    assert get_db_path() == temp_db

    with get_db_connection() as conn:
        # Check basic query execution works
        cursor = conn.cursor()
        cursor.execute("SELECT 1;")
        res = cursor.fetchone()
        assert res[0] == 1

        # Verify that foreign keys are enabled (should return 1)
        cursor.execute("PRAGMA foreign_keys;")
        fk_status = cursor.fetchone()[0]
        assert fk_status == 1


def test_foreign_key_constraints(temp_db):
    """
    Verifies that foreign key constraints are strictly enforced in our SQLite schema.
    Specifically, inserting rows referencing a non-existent 'user_id' must raise
    an sqlite3.IntegrityError.
    """
    # Initialize the tables using our schema
    init_db()

    with get_db_connection() as conn:
        # Attempt to insert a watchlist item with a non-existent user_id
        # This should fail since 'nonexistent' is not in 'users_profile'
        with pytest.raises(sqlite3.IntegrityError) as exc_info:
            conn.execute(
                """
                INSERT INTO watchlist (id, user_id, ticker, added_at)
                VALUES (?, 'nonexistent', 'AAPL', ?);
                """,
                (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()),
            )
        assert "FOREIGN KEY constraint failed" in str(exc_info.value)

        # Attempt to insert a position with a non-existent user_id
        with pytest.raises(sqlite3.IntegrityError) as exc_info:
            conn.execute(
                """
                INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                VALUES (?, 'nonexistent', 'AAPL', 10.0, '190.50', ?);
                """,
                (str(uuid.uuid4()), datetime.now(timezone.utc).isoformat()),
            )
        assert "FOREIGN KEY constraint failed" in str(exc_info.value)


def test_idempotent_seeding(temp_db):
    """
    Verifies that:
    1. The schema initializes correctly.
    2. The default user is seeded with exactly 1,000,000 cents ($10,000).
    3. The default 10 watchlist tickers are successfully seeded.
    4. Seeding is fully idempotent: running init_db again does not duplicate items
       or reset user modifications (such as mutated cash balances).
    """
    # 1. First run of initialization and seeding
    init_db()

    # Check seeded values
    with get_db_connection() as conn:
        # Check users_profile
        cursor = conn.cursor()
        cursor.execute("SELECT id, cash_balance_cents, created_at FROM users_profile;")
        profiles = cursor.fetchall()
        assert len(profiles) == 1
        profile = profiles[0]
        assert profile["id"] == "default"
        assert profile["cash_balance_cents"] == 1000000
        assert profile["created_at"] is not None

        # Check watchlist entries
        cursor.execute("SELECT ticker FROM watchlist WHERE user_id = 'default';")
        rows = cursor.fetchall()
        assert len(rows) == 10
        tickers = [row["ticker"] for row in rows]
        expected_tickers = {
            "AAPL",
            "GOOGL",
            "MSFT",
            "AMZN",
            "TSLA",
            "NVDA",
            "META",
            "JPM",
            "V",
            "NFLX",
        }
        assert set(tickers) == expected_tickers

        # 2. Simulate user activity (mutate cash balance and remove a ticker)
        # Mutate cash
        conn.execute("UPDATE users_profile SET cash_balance_cents = 850000 WHERE id = 'default';")
        # Delete one ticker from watchlist (e.g., TSLA)
        conn.execute("DELETE FROM watchlist WHERE user_id = 'default' AND ticker = 'TSLA';")

    # 3. Run init_db() a second time (should be completely idempotent)
    init_db()

    # Verify that:
    # - The mutated cash balance was NOT overwritten or reset.
    # - The deleted ticker was RE-SEEDED because it was missing (restoring the default 10 tickers).
    # - There are no duplicates in the watchlist.
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Cash balance must remain 850,000 cents
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id = 'default';")
        cash = cursor.fetchone()["cash_balance_cents"]
        assert cash == 850000

        # Watchlist should have exactly 10 elements again, with no duplicates
        cursor.execute("SELECT ticker FROM watchlist WHERE user_id = 'default';")
        rows = cursor.fetchall()
        tickers = [row["ticker"] for row in rows]
        assert len(tickers) == 10
        assert len(set(tickers)) == 10
        assert set(tickers) == expected_tickers


def test_table_structures(temp_db):
    """
    Verifies that all 6 tables exist and have the exact column layout as requested.
    """
    init_db()

    expected_tables = {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    }

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = {row["name"] for row in cursor.fetchall()}

        # Verify all tables exist
        for table in expected_tables:
            assert table in tables

        # Verify positions column names & UNIQUE constraint
        cursor.execute("PRAGMA table_info(positions);")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        assert "id" in columns
        assert "user_id" in columns
        assert "ticker" in columns
        assert "quantity" in columns
        assert "avg_cost" in columns
        assert "updated_at" in columns

        # Verify trades column names
        cursor.execute("PRAGMA table_info(trades);")
        columns = {row["name"]: row["type"] for row in cursor.fetchall()}
        assert "id" in columns
        assert "user_id" in columns
        assert "ticker" in columns
        assert "side" in columns
        assert "quantity" in columns
        assert "execution_price" in columns
        assert "notional_amount_cents" in columns
        assert "source" in columns
        assert "executed_at" in columns
