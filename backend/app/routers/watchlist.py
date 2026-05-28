import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel

from app.db.connection import get_db_connection

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


class AddTickerRequest(BaseModel):
    ticker: str


def get_watchlist_response(price_cache, tickers: list[str]) -> list[dict]:
    """Helper to format watchlist response with latest price and history."""
    res = []
    for ticker in tickers:
        price_update = price_cache.get(ticker)
        history = price_cache.get_history(ticker)
        res.append({
            "ticker": ticker,
            "price": price_update.price if price_update else None,
            "previous_price": price_update.previous_price if price_update else None,
            "change": price_update.change if price_update else 0.0,
            "change_percent": price_update.change_percent if price_update else 0.0,
            "direction": price_update.direction if price_update else "flat",
            "timestamp": price_update.timestamp if price_update else None,
            "history": [h.price for h in history] if history else [],
        })
    return res


@router.get("")
async def get_watchlist(request: Request):
    """
    GET current watchlist tickers with latest prices and in-memory price history.
    """
    price_cache = request.app.state.price_cache

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker ASC;"
        )
        tickers = [row["ticker"] for row in cursor.fetchall()]

    return get_watchlist_response(price_cache, tickers)


@router.post("")
async def add_to_watchlist(request: Request, body: AddTickerRequest):
    """
    POST to add a new ticker to the watchlist.
    Validates ticker format, updates the DB, and adds it to the active market source.
    """
    price_cache = request.app.state.price_cache
    market_data_source = request.app.state.market_data_source

    ticker = body.ticker.upper().strip()
    if not re.match(r"^[A-Z]{1,5}$", ticker):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: {ticker}. Tickers must be 1 to 5 alphabetical characters.",
        )

    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Check if already exists in watchlist
        cursor.execute(
            "SELECT id FROM watchlist WHERE user_id = 'default' AND ticker = ?;",
            (ticker,),
        )
        exists = cursor.fetchone() is not None

        if not exists:
            entry_id = str(uuid.uuid4())
            now_str = datetime.now(timezone.utc).isoformat()
            cursor.execute(
                """
                INSERT INTO watchlist (id, user_id, ticker, added_at)
                VALUES (?, 'default', ?, ?);
                """,
                (entry_id, ticker, now_str),
            )

    # Let the market data source know to track this ticker
    await market_data_source.add_ticker(ticker)

    # Retrieve updated list
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker ASC;"
        )
        tickers = [row["ticker"] for row in cursor.fetchall()]

    return get_watchlist_response(price_cache, tickers)


@router.delete("/{ticker}")
async def delete_from_watchlist(
    request: Request,
    ticker: str = Path(..., description="The ticker to remove from the watchlist"),
):
    """
    DELETE to remove a ticker from the watchlist.
    If the ticker is currently held, it is removed from the watchlist DB
    but continues to be priced. If it is NOT held, it is removed from the DB
    and also removed from the market data source to stop price tracking.
    """
    price_cache = request.app.state.price_cache
    market_data_source = request.app.state.market_data_source

    ticker = ticker.upper().strip()

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Check if the position exists for the default user
        cursor.execute(
            "SELECT quantity FROM positions WHERE user_id = 'default' AND ticker = ?;",
            (ticker,),
        )
        pos_row = cursor.fetchone()
        is_held = pos_row is not None and pos_row["quantity"] > 0

        # Delete from watchlist table
        cursor.execute(
            "DELETE FROM watchlist WHERE user_id = 'default' AND ticker = ?;",
            (ticker,),
        )

    # If the ticker is not held in portfolio, stop tracking it entirely
    if not is_held:
        await market_data_source.remove_ticker(ticker)
    else:
        # Ticker remains active in simulator, just removed from watchlist table
        pass

    # Retrieve updated list
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker FROM watchlist WHERE user_id = 'default' ORDER BY ticker ASC;"
        )
        tickers = [row["ticker"] for row in cursor.fetchall()]

    return get_watchlist_response(price_cache, tickers)
