import asyncio
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.db.connection import get_db_connection
from app.db.manager import init_db
from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.stream import create_stream_router
from app.routers.chat import router as chat_router
from app.routers.market import router as market_router
from app.routers.portfolio import router as portfolio_router
from app.routers.watchlist import router as watchlist_router

# Configure logging
logger = logging.getLogger("finally.main")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

# Background snapshot task reference
snapshot_task: Optional[asyncio.Task] = None


async def periodic_snapshot_loop(app: FastAPI):
    """
    Background worker that runs every 30 seconds.
    Calculates total portfolio value and writes snapshot if value has changed
    by at least $0.01 (1 cent) since the last snapshot.
    """
    price_cache = app.state.price_cache
    logger.info("Periodic portfolio snapshot loop started.")

    while True:
        try:
            await asyncio.sleep(30)

            with get_db_connection() as conn:
                cursor = conn.cursor()

                # Fetch cash balance
                cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id = 'default';")
                profile_row = cursor.fetchone()
                if not profile_row:
                    continue
                cash_balance_cents = profile_row["cash_balance_cents"]

                # Fetch positions
                cursor.execute("SELECT ticker, quantity FROM positions WHERE user_id = 'default';")
                positions = cursor.fetchall()

                # Value portfolio
                degraded = False
                total_positions_cents = 0
                for pos in positions:
                    ticker = pos["ticker"]
                    qty = Decimal(str(pos["quantity"]))
                    price_update = price_cache.get(ticker)
                    if price_update is None:
                        degraded = True
                        break
                    cur_price = Decimal(str(price_update.price))
                    total_positions_cents += int(round(qty * cur_price * 100))

                if degraded:
                    # Skip snapshot if price feed is degraded
                    logger.warning("Periodic snapshot skipped: portfolio valuation is degraded (missing prices).")
                    continue

                total_value_cents = cash_balance_cents + total_positions_cents

                # Compare with the most recent snapshot
                cursor.execute(
                    """
                    SELECT total_value_cents FROM portfolio_snapshots
                    WHERE user_id = 'default'
                    ORDER BY recorded_at DESC LIMIT 1;
                    """
                )
                last_snap = cursor.fetchone()

                should_record = False
                if not last_snap:
                    should_record = True
                else:
                    last_val = last_snap["total_value_cents"]
                    if abs(total_value_cents - last_val) >= 1:  # at least 1 cent difference
                        should_record = True

                if should_record:
                    now_str = datetime.now(timezone.utc).isoformat()
                    cursor.execute(
                        """
                        INSERT INTO portfolio_snapshots (id, user_id, total_value_cents, recorded_at)
                        VALUES (?, 'default', ?, ?);
                        """,
                        (str(uuid.uuid4()), total_value_cents, now_str),
                    )
                    logger.info(f"Recorded periodic snapshot: ${total_value_cents/100:.2f}")

        except asyncio.CancelledError:
            logger.info("Periodic portfolio snapshot loop stopped (cancelled).")
            break
        except Exception as e:
            logger.error(f"Error in periodic snapshot loop: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan Startup and Shutdown handler.
    Initializes DB, starts price feeds (Sim/Massive), runs background tasks,
    and cleanly stops everything on shutdown.
    """
    global snapshot_task

    # --- STARTUP ---
    logger.info("Starting up FinAlly backend...")

    # 1. Initialize SQLite Database (Idempotent schema creation + seed data)
    init_db()

    # 2. Create the shared global PriceCache
    price_cache = app.state.price_cache

    # 3. Retrieve the union of all watchlist and position tickers from the DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker FROM watchlist UNION SELECT ticker FROM positions;")
        tickers = [row["ticker"] for row in cursor.fetchall()]

    logger.info(f"Initial priced set union from DB: {tickers}")

    # 4. Create and start the authoritative Market Data Source
    market_data_source = create_market_data_source(price_cache)
    app.state.market_data_source = market_data_source

    await market_data_source.start(tickers)

    # 5. Start the periodic portfolio snapshot loop in the background
    snapshot_task = asyncio.create_task(
        periodic_snapshot_loop(app), name="periodic-snapshot-worker"
    )

    yield

    # --- SHUTDOWN ---
    logger.info("Shutting down FinAlly backend...")

    # 1. Stop periodic snapshot loop
    if snapshot_task:
        snapshot_task.cancel()
        try:
            await snapshot_task
        except asyncio.CancelledError:
            pass

    # 2. Stop the Market Data Source price updates
    if hasattr(app.state, "market_data_source"):
        await app.state.market_data_source.stop()

    logger.info("Shutdown completed.")


# -------------------------------------------------------------
# FastAPI Application Setup
# -------------------------------------------------------------

app = FastAPI(
    title="FinAlly API",
    description="Finance Ally Core REST APIs and real-time SSE stream",
    version="0.1.0",
    lifespan=lifespan,
)
app.state.price_cache = PriceCache()

# Enable CORS for local cross-origin frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------------------------------------------
# Simple APP_PASSWORD Protection Middleware
# -------------------------------------------------------------

@app.middleware("http")
async def app_password_gate(request: Request, call_next):
    # Exclude basic system/auth endpoints from password requirement
    path = request.url.path
    if path == "/api/health" or path == "/api/auth/login":
        return await call_next(request)

    app_password = os.getenv("APP_PASSWORD", "").strip()
    if not app_password:
        return await call_next(request)

    # 1. Verify custom X-App-Password header
    x_password = request.headers.get("X-App-Password", "")
    if x_password == app_password:
        return await call_next(request)

    # 2. Verify standard Authorization bearer / plain token
    auth_header = request.headers.get("Authorization", "")
    if auth_header:
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
            if token == app_password:
                return await call_next(request)
        elif auth_header.strip() == app_password:
            return await call_next(request)

    # 3. Verify app_password cookie
    cookie_password = request.cookies.get("app_password", "")
    if cookie_password == app_password:
        return await call_next(request)

    # If auth validation fails, reject with 401 Unauthorized
    return JSONResponse(
        status_code=401,
        content={"detail": "Unauthorized: Invalid or missing APP_PASSWORD."},
    )


# -------------------------------------------------------------
# Auth & Health Endpoints
# -------------------------------------------------------------

class LoginRequest(BaseModel):
    password: str


@app.post("/api/auth/login")
async def auth_login(body: LoginRequest):
    """
    Simple POST endpoint to verify password and return status.
    Allows clients to fetch/validate credentials before configuring request headers.
    """
    app_password = os.getenv("APP_PASSWORD", "").strip()
    if not app_password or body.password == app_password:
        return {"success": True}
    raise HTTPException(status_code=401, detail="Invalid password.")


@app.get("/api/health")
async def health_check():
    """
    System health check. Used by Docker/orchestration health checkers.
    """
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


# -------------------------------------------------------------
# Register Routers
# -------------------------------------------------------------

# Register core business endpoints
app.include_router(market_router)
app.include_router(watchlist_router)
app.include_router(portfolio_router)
app.include_router(chat_router)
app.include_router(create_stream_router(app.state.price_cache))


# -------------------------------------------------------------
# Catch-all Static File Serving
# -------------------------------------------------------------

static_dir = Path(__file__).resolve().parent.parent / "static"


@app.get("/{catchall:path}")
async def serve_static_or_index(catchall: str):
    """
    Catch-all route that serves Next.js exported static assets.
    If the requested path represents a file (e.g. JS/CSS/image), it is served directly.
    Otherwise, index.html is served to support clean client-side dynamic routing.
    """
    # 1. Look for matching file inside backend/static/
    file_path = static_dir / catchall
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # 2. Otherwise serve index.html (Next.js fallback)
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    # 3. Local dev fallback when frontend static build hasn't run yet
    return JSONResponse(
        content={
            "message": "FinAlly Core API is running. Static files directory 'static/' not found."
        }
    )
