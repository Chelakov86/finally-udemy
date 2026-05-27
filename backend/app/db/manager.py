import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.connection import get_db_connection

# Configure logging
logger = logging.getLogger("finally.db.manager")
if not logger.handlers:
    # Basic logging setup if not already configured
    logging.basicConfig(level=logging.INFO)


def init_db() -> None:
    """
    Initializes the database schema and seeds default data.
    Runs idempotently:
    - Checks if the tables are initialized (by looking for 'users_profile').
    - If missing, reads and executes 'schema.sql'.
    - Seeds default user and watchlist entries if not already present.
    """
    schema_path = Path(__file__).parent / "schema.sql"
    if not schema_path.exists():
        logger.error(f"Schema file not found at: {schema_path}")
        raise FileNotFoundError(f"Schema file not found at: {schema_path}")

    logger.info("Initializing database...")

    with get_db_connection() as conn:
        # Check if users_profile table exists
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users_profile';"
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            logger.info("Database tables not found. Creating schema...")
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()

            # executescript allows executing multiple SQL statement statements
            conn.executescript(schema_sql)
            logger.info("Database schema successfully created.")
        else:
            logger.info("Database tables already exist. Skipping schema creation.")

        # Seed default data (idempotently)
        seed_db(conn)


def seed_db(conn) -> None:
    """
    Idempotently seeds default data if the database is empty or missing defaults.
    - Default User Profile: 'default' with cash_balance_cents=1000000 ($10,000.00).
    - Default Watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX.
    """
    # 1. Seed User Profile
    # First check if the default user exists to avoid changing their existing cash_balance
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users_profile WHERE id = 'default';")
    default_user_exists = cursor.fetchone() is not None

    if not default_user_exists:
        logger.info("Seeding default user profile...")
        now_str = datetime.now(timezone.utc).isoformat()
        cursor.execute(
            """
            INSERT INTO users_profile (id, cash_balance_cents, created_at)
            VALUES ('default', 1000000, ?);
            """,
            (now_str,),
        )
        logger.info("Default user profile seeded.")
    else:
        logger.info("Default user profile already exists. Skipping user seeding.")

    # 2. Seed Watchlist Entries
    # Seed individual default tickers if they don't already exist for user 'default'
    default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]

    seeded_count = 0
    now_str = datetime.now(timezone.utc).isoformat()

    for ticker in default_tickers:
        # Check if this ticker is already in the watchlist for the default user
        cursor.execute(
            "SELECT id FROM watchlist WHERE user_id = 'default' AND ticker = ?;", (ticker,)
        )
        if cursor.fetchone() is None:
            # Not in watchlist, so add it
            entry_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO watchlist (id, user_id, ticker, added_at)
                VALUES (?, 'default', ?, ?);
                """,
                (entry_id, ticker, now_str),
            )
            seeded_count += 1

    if seeded_count > 0:
        logger.info(f"Seeded {seeded_count} default tickers to watchlist.")
    else:
        logger.info("Default watchlist tickers already present. Skipping watchlist seeding.")
