import asyncio
import decimal
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.db.connection import get_db_connection

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    side: str  # "buy" or "sell"
    quantity: Optional[float] = None
    notional_amount: Optional[float] = None
    source: Optional[str] = "manual"


def get_fresh_price(price_cache, market_data_source, ticker: str) -> Decimal:
    """
    Fetches the price from PriceCache.
    If ticker is unpriced, adds it to the market data source and waits briefly.
    Verifies freshness (5s for simulator, 60s for Massive).
    Raises HTTPException on stale or missing prices.
    """
    price_update = price_cache.get(ticker)
    if not price_update:
        # Ticker has no price, add to market data source
        # We can't await inside a non-async function normally, but get_fresh_price
        # is called from our async route, so let's make get_fresh_price async!
        pass


async def fetch_and_validate_fresh_price(price_cache, market_data_source, ticker: str) -> Decimal:
    price_update = price_cache.get(ticker)
    if not price_update:
        await market_data_source.add_ticker(ticker)
        # Loop and sleep for up to 3 seconds waiting for price to populate
        for _ in range(15):
            await asyncio.sleep(0.2)
            price_update = price_cache.get(ticker)
            if price_update:
                break

    if not price_update:
        raise HTTPException(
            status_code=400,
            detail=f"No price available for ticker {ticker}."
        )

    # Check price freshness
    now = time.time()
    age = now - price_update.timestamp
    is_massive = bool(os.environ.get("MASSIVE_API_KEY", "").strip())
    freshness_threshold = 60.0 if is_massive else 5.0

    if age > freshness_threshold:
        raise HTTPException(
            status_code=400,
            detail=f"Price for ticker {ticker} is stale ({age:.1f}s old). Trade rejected."
        )

    return Decimal(str(price_update.price))
@router.get("")
async def get_portfolio(request: Request):
    """
    GET current positions, cash, total portfolio value, and unrealized P&L.
    Enforces exact cents calculations and reports degraded state if prices are missing.
    """
    price_cache = request.app.state.price_cache

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Fetch cash balance
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id = 'default';")
        profile_row = cursor.fetchone()
        if not profile_row:
            raise HTTPException(status_code=500, detail="Default user profile not found.")
        cash_balance_cents = profile_row["cash_balance_cents"]

        # Fetch positions
        cursor.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions WHERE user_id = 'default' ORDER BY ticker ASC;"
        )
        pos_rows = cursor.fetchall()

    cash_balance = float(Decimal(cash_balance_cents) / 100)

    positions = []
    degraded = False
    total_positions_value_cents = 0
    total_avg_cost_cents = 0

    for row in pos_rows:
        ticker = row["ticker"]
        quantity = Decimal(str(row["quantity"]))
        avg_cost = Decimal(row["avg_cost"])

        price_update = price_cache.get(ticker)

        if price_update is None:
            degraded = True
            positions.append({
                "ticker": ticker,
                "quantity": float(quantity),
                "avg_cost": str(avg_cost),
                "avg_cost_float": float(avg_cost),
                "current_price": None,
                "unrealized_p_l": None,
                "unrealized_p_l_cents": None,
                "unrealized_p_l_percent": None,
                "total_value": None,
                "total_value_cents": None,
                "updated_at": row["updated_at"],
            })
        else:
            cur_price = Decimal(str(price_update.price))
            pos_value_cents = int(round(quantity * cur_price * 100))
            avg_cost_val_cents = int(round(quantity * avg_cost * 100))

            total_positions_value_cents += pos_value_cents
            total_avg_cost_cents += avg_cost_val_cents

            unrealized_cents = pos_value_cents - avg_cost_val_cents
            unrealized_p_l = float(Decimal(unrealized_cents) / 100)
            unrealized_percent = float((cur_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0

            positions.append({
                "ticker": ticker,
                "quantity": float(quantity),
                "avg_cost": str(avg_cost),
                "avg_cost_float": float(avg_cost),
                "current_price": float(cur_price),
                "unrealized_p_l": unrealized_p_l,
                "unrealized_p_l_cents": unrealized_cents,
                "unrealized_p_l_percent": unrealized_percent,
                "total_value": float(Decimal(pos_value_cents) / 100),
                "total_value_cents": pos_value_cents,
                "updated_at": row["updated_at"],
            })

    if degraded:
        return {
            "cash_balance": cash_balance,
            "cash_balance_cents": cash_balance_cents,
            "positions": positions,
            "total_portfolio_value": None,
            "total_portfolio_value_cents": None,
            "unrealized_p_l": None,
            "unrealized_p_l_cents": None,
            "unrealized_p_l_percent": None,
            "degraded": True,
        }

    total_value_cents = cash_balance_cents + total_positions_value_cents
    total_value = float(Decimal(total_value_cents) / 100)

    total_unrealized_cents = total_positions_value_cents - total_avg_cost_cents
    total_unrealized_p_l = float(Decimal(total_unrealized_cents) / 100)
    total_unrealized_percent = (
        float(Decimal(total_unrealized_cents) / Decimal(total_avg_cost_cents) * 100)
        if total_avg_cost_cents > 0
        else 0.0
    )

    return {
        "cash_balance": cash_balance,
        "cash_balance_cents": cash_balance_cents,
        "positions": positions,
        "total_portfolio_value": total_value,
        "total_portfolio_value_cents": total_value_cents,
        "unrealized_p_l": total_unrealized_p_l,
        "unrealized_p_l_cents": total_unrealized_cents,
        "unrealized_p_l_percent": total_unrealized_percent,
        "degraded": False,
    }


async def execute_trade_logic(
    body: TradeRequest,
    price_cache,
    market_data_source,
) -> dict:
    """
    Core authoritative trade execution logic.
    Converts dollar notions to shares, validates constraints, recalculates average cost,
    updates DB (cash, positions, trades log), and takes an immediate portfolio snapshot.
    """
    # 1. Basic validation
    ticker = body.ticker.upper().strip()
    if not re.match(r"^[A-Z]{1,5}$", ticker):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ticker format: {ticker}.",
        )

    side = body.side.lower().strip()
    if side not in ("buy", "sell"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid side: {side}. Must be 'buy' or 'sell'.",
        )

    if body.quantity is not None and body.notional_amount is not None:
        raise HTTPException(
            status_code=400,
            detail="Specify either 'quantity' or 'notional_amount', not both.",
        )

    if body.quantity is None and body.notional_amount is None:
        raise HTTPException(
            status_code=400,
            detail="Specify either 'quantity' or 'notional_amount'.",
        )

    # 2. Get fresh price
    execution_price = await fetch_and_validate_fresh_price(price_cache, market_data_source, ticker)

    # 3. Determine quantity and notional amount
    if body.quantity is not None:
        qty_decimal = Decimal(str(body.quantity))
        if qty_decimal <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than zero.",
            )
        # Calculate notional
        notional_cents = int(round(qty_decimal * execution_price * 100))
        if notional_cents < 1:
            raise HTTPException(
                status_code=400,
                detail="Trade amount is too small to execute. Minimum notional is $0.01.",
            )
    else:
        # Notional-based
        notional_amount = body.notional_amount
        if notional_amount < 0.01:
            raise HTTPException(
                status_code=400,
                detail="Trade amount is too small to execute. Minimum notional is $0.01.",
            )
        notional_cents_requested = int(round(Decimal(str(notional_amount)) * 100))
        # Convert to shares: requested_dollars / price
        shares_exact = Decimal(notional_cents_requested) / Decimal(100) / execution_price
        # Round down to 6 decimal places
        qty_decimal = shares_exact.quantize(Decimal("0.000001"), rounding=decimal.ROUND_DOWN)

        if qty_decimal <= 0:
            raise HTTPException(
                status_code=400,
                detail="Trade amount is too small to execute. The rounded quantity is 0 shares.",
            )
        # Recalculate actual notional cents after rounding quantity down
        notional_cents = int(round(qty_decimal * execution_price * 100))
        if notional_cents < 1:
            raise HTTPException(
                status_code=400,
                detail="Trade amount is too small to execute. Minimum notional is $0.01.",
            )

    now_str = datetime.now(timezone.utc).isoformat()
    trade_id = str(uuid.uuid4())

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Fetch cash balance
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id = 'default';")
        cash_row = cursor.fetchone()
        cash_balance_cents = cash_row["cash_balance_cents"]

        # Fetch current position
        cursor.execute(
            "SELECT quantity, avg_cost FROM positions WHERE user_id = 'default' AND ticker = ?;",
            (ticker,),
        )
        pos_row = cursor.fetchone()

        if side == "buy":
            if cash_balance_cents < notional_cents:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient cash balance. Required: ${notional_cents/100:.2f}, Available: ${cash_balance_cents/100:.2f}",
                )

            # Recalculate cash & positions
            new_cash = cash_balance_cents - notional_cents

            if pos_row:
                old_qty = Decimal(str(pos_row["quantity"]))
                old_avg_cost = Decimal(pos_row["avg_cost"])
                new_qty = old_qty + qty_decimal
                new_avg_cost = ((old_qty * old_avg_cost) + (qty_decimal * execution_price)) / new_qty

                cursor.execute(
                    """
                    UPDATE positions
                    SET quantity = ?, avg_cost = ?, updated_at = ?
                    WHERE user_id = 'default' AND ticker = ?;
                    """,
                    (float(new_qty), str(new_avg_cost), now_str, ticker),
                )
                position_res = {
                    "ticker": ticker,
                    "quantity": float(new_qty),
                    "avg_cost": str(new_avg_cost),
                    "avg_cost_float": float(new_avg_cost),
                    "updated_at": now_str,
                }
            else:
                cursor.execute(
                    """
                    INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
                    VALUES (?, 'default', ?, ?, ?, ?);
                    """,
                    (str(uuid.uuid4()), ticker, float(qty_decimal), str(execution_price), now_str),
                )
                position_res = {
                    "ticker": ticker,
                    "quantity": float(qty_decimal),
                    "avg_cost": str(execution_price),
                    "avg_cost_float": float(execution_price),
                    "updated_at": now_str,
                }

        else:  # sell
            if not pos_row:
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot sell ticker {ticker}: you do not hold any shares.",
                )

            old_qty = Decimal(str(pos_row["quantity"]))
            if qty_decimal > old_qty:
                raise HTTPException(
                    status_code=400,
                    detail=f"Insufficient shares. Held: {float(old_qty)}, Requested: {float(qty_decimal)}",
                )

            new_cash = cash_balance_cents + notional_cents
            new_qty = old_qty - qty_decimal

            if new_qty <= Decimal("1e-9"):  # fully sold
                cursor.execute(
                    "DELETE FROM positions WHERE user_id = 'default' AND ticker = ?;",
                    (ticker,),
                )
                position_res = None
            else:
                # Average cost remains unchanged on partial sells
                avg_cost = Decimal(pos_row["avg_cost"])
                cursor.execute(
                    """
                    UPDATE positions
                    SET quantity = ?, updated_at = ?
                    WHERE user_id = 'default' AND ticker = ?;
                    """,
                    (float(new_qty), now_str, ticker),
                )
                position_res = {
                    "ticker": ticker,
                    "quantity": float(new_qty),
                    "avg_cost": str(avg_cost),
                    "avg_cost_float": float(avg_cost),
                    "updated_at": now_str,
                }

        # Update cash balance
        cursor.execute(
            "UPDATE users_profile SET cash_balance_cents = ? WHERE id = 'default';",
            (new_cash,),
        )

        # Log trade execution
        cursor.execute(
            """
            INSERT INTO trades (id, user_id, ticker, side, quantity, execution_price, notional_amount_cents, source, executed_at)
            VALUES (?, 'default', ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                trade_id,
                ticker,
                side,
                float(qty_decimal),
                str(execution_price),
                notional_cents,
                body.source or "manual",
                now_str,
            ),
        )

        # 4. Immediate portfolio snapshot calculation
        cursor.execute("SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = 'default';")
        all_positions = cursor.fetchall()

        total_positions_cents = 0
        for pos in all_positions:
            pos_ticker = pos["ticker"]
            pos_qty = Decimal(str(pos["quantity"]))
            pos_price = Decimal(str(price_cache.get_price(pos_ticker) or pos["avg_cost"]))
            total_positions_cents += int(round(pos_qty * pos_price * 100))

        snapshot_val_cents = new_cash + total_positions_cents
        cursor.execute(
            """
            INSERT INTO portfolio_snapshots (id, user_id, total_value_cents, recorded_at)
            VALUES (?, 'default', ?, ?);
            """,
            (str(uuid.uuid4()), snapshot_val_cents, now_str),
        )

    # Return response payload
    return {
        "trade": {
            "id": trade_id,
            "ticker": ticker,
            "side": side,
            "quantity": float(qty_decimal),
            "execution_price": str(execution_price),
            "notional_amount_cents": notional_cents,
            "notional_amount": float(Decimal(notional_cents) / 100),
            "source": body.source or "manual",
            "executed_at": now_str,
        },
        "position": position_res,
    }


@router.post("/trade")
async def execute_trade(request: Request, body: TradeRequest):
    """
    POST to execute a trade. Authoritative trade execution path.
    """
    price_cache = request.app.state.price_cache
    market_data_source = request.app.state.market_data_source
    return await execute_trade_logic(body, price_cache, market_data_source)



@router.get("/history")
async def get_portfolio_history(request: Request, range: str = "ALL"):
    """
    GET downsampled historical portfolio snapshots.
    Supports range=1D|1W|1M|ALL and returns at most 200 points.
    """
    now = datetime.now(timezone.utc)
    cutoff = None

    range_str = range.upper().strip()
    if range_str == "1D":
        cutoff = now - timedelta(days=1)
    elif range_str == "1W":
        cutoff = now - timedelta(days=7)
    elif range_str == "1M":
        cutoff = now - timedelta(days=30)

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if cutoff:
            cursor.execute(
                """
                SELECT total_value_cents, recorded_at
                FROM portfolio_snapshots
                WHERE user_id = 'default' AND recorded_at >= ?
                ORDER BY recorded_at ASC;
                """,
                (cutoff.isoformat(),),
            )
        else:
            cursor.execute(
                """
                SELECT total_value_cents, recorded_at
                FROM portfolio_snapshots
                WHERE user_id = 'default'
                ORDER BY recorded_at ASC;
                """,
            )
        rows = cursor.fetchall()

    snapshots = [
        {
            "total_value_cents": row["total_value_cents"],
            "total_value": float(Decimal(row["total_value_cents"]) / 100),
            "recorded_at": row["recorded_at"],
        }
        for row in rows
    ]

    # Downsample to maximum 200 points
    max_points = 200
    if len(snapshots) <= max_points:
        return snapshots

    indices = [int(round(i * (len(snapshots) - 1) / (max_points - 1))) for i in range(max_points)]
    seen = set()
    deduped_indices = []
    for idx in indices:
        if idx not in seen:
            seen.add(idx)
            deduped_indices.append(idx)

    return [snapshots[i] for i in deduped_indices]
