from datetime import datetime, timedelta, timezone

import pytest

from app.chat.agent import (
    extract_json_content,
    format_portfolio_text,
    get_portfolio_context_data,
    handle_chat_message,
)
from app.chat.intent import PendingActionsCache, PendingActionSet, classify_intent
from app.chat.models import ChatAgentResponse, Recommendation, TradeRequest, WatchlistChangeRequest
from app.db.connection import get_db_connection
from app.db.manager import init_db
from app.market.cache import PriceCache


class MockMarketDataSource:
    def __init__(self):
        self.tracked_tickers = set()

    async def add_ticker(self, ticker: str):
        self.tracked_tickers.add(ticker)

    async def remove_ticker(self, ticker: str):
        self.tracked_tickers.discard(ticker)


@pytest.fixture
def temp_db(monkeypatch, tmp_path):
    """Isolates the DB environment variable for each test case."""
    temp_db_file = tmp_path / "test_finally.db"
    monkeypatch.setenv("DATABASE_PATH", str(temp_db_file))
    yield temp_db_file
    if temp_db_file.exists():
        try:
            temp_db_file.unlink()
        except OSError:
            pass


@pytest.fixture
def price_cache():
    cache = PriceCache()
    # Seed cache with standard prices
    cache.update("AAPL", 190.00)
    cache.update("GOOGL", 175.00)
    cache.update("MSFT", 400.00)
    cache.update("TSLA", 180.00)
    return cache


@pytest.fixture
def market_source():
    return MockMarketDataSource()


@pytest.fixture
def pending_cache():
    cache = PendingActionsCache(expiration_minutes=10)
    yield cache
    cache.stop_loop()


def test_prompt_context_building(temp_db, price_cache):
    """Verifies that the portfolio context data matches what is in the DB and cache."""
    init_db()

    # 1. Verify get_portfolio_context_data returns seeded values
    data = get_portfolio_context_data(price_cache)
    assert data["cash_balance"] == 10000.00
    assert len(data["positions"]) == 0
    assert len(data["watchlist"]) == 10

    # 2. Check AAPL price is retrieved successfully from cache
    aapl_watchlist_item = next(item for item in data["watchlist"] if item["ticker"] == "AAPL")
    assert aapl_watchlist_item["price"] == 190.00

    # 3. Add a position manually to test positions context
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at)
            VALUES ('pos-id', 'default', 'AAPL', 10.0, '180.00', '2026-05-27T00:00:00Z');
            """
        )

    data = get_portfolio_context_data(price_cache)
    assert len(data["positions"]) == 1
    aapl_pos = data["positions"][0]
    assert aapl_pos["ticker"] == "AAPL"
    assert aapl_pos["quantity"] == 10.0
    assert aapl_pos["avg_cost"] == 180.00
    assert aapl_pos["current_price"] == 190.00
    assert aapl_pos["total_value"] == 1900.00
    assert aapl_pos["unrealized_p_l"] == 100.00
    assert aapl_pos["unrealized_p_l_percent"] == pytest.approx(5.5555, abs=1e-3)

    # 4. Check total portfolio value
    # cash ($10,000) - manually inserted positions did not deduct cash, so cash is still $10,000.
    # Total portfolio value = $10,000 + $1,900 = $11,900.00
    assert data["total_portfolio_value"] == 11900.00

    # 5. Check format_portfolio_text formatting
    pos_text, wl_text = format_portfolio_text(data)
    assert (
        "AAPL: 10.0000 shares @ Avg Cost $180.00 (Current: $190.00, P&L: +$100.00 (+5.56%))"
        in pos_text
    )
    assert "AAPL: $190.00" in wl_text


def test_json_robust_extraction():
    """Verifies that extract_json_content correctly retrieves json blocks."""
    # Tagged block
    raw_1 = 'Sure! Here is the JSON:\n```json\n{"message": "hello"}\n```\nHope it helps!'
    assert extract_json_content(raw_1) == '{"message": "hello"}'

    # Untagged block
    raw_2 = '```\n{"message": "world"}\n```'
    assert extract_json_content(raw_2) == '{"message": "world"}'

    # Raw JSON
    raw_3 = '{"message": "raw"}'
    assert extract_json_content(raw_3) == '{"message": "raw"}'

    # Text surrounding JSON without backticks
    raw_4 = 'Analysis details: {"message": "test"} hope you like it'
    assert extract_json_content(raw_4) == '{"message": "test"}'


def test_pydantic_structured_models():
    """Verifies that the structured Pydantic models validate successfully and reject bad entries."""
    # 1. Valid responses
    resp = ChatAgentResponse(
        message="Ok",
        recommendations=[Recommendation(type="trade", ticker="AAPL", side="buy", rationale="Nice")],
        trades=[TradeRequest(ticker="MSFT", side="buy", quantity=10.0)],
        watchlist_changes=[WatchlistChangeRequest(ticker="NVDA", action="add")],
    )
    assert resp.trades[0].ticker == "MSFT"
    assert resp.trades[0].quantity == 10.0

    # 2. Invalid ticker formatting
    with pytest.raises(ValueError) as exc:
        Recommendation(type="trade", ticker="INVALID_TICKER", side="buy", rationale="Nice")
    assert "Invalid ticker format" in str(exc.value)

    # 3. Invalid trades (both quantity and notional)
    with pytest.raises(ValueError) as exc:
        TradeRequest(ticker="AAPL", side="buy", quantity=10.0, notional_amount=500.0)
    assert "Only one of 'quantity' or 'notional_amount' can be provided" in str(exc.value)

    # 4. Invalid trades (neither quantity nor notional)
    with pytest.raises(ValueError) as exc:
        TradeRequest(ticker="AAPL", side="buy")
    assert "Exactly one of 'quantity' or 'notional_amount' must be provided" in str(exc.value)


def test_intent_gating_classification():
    """Verifies that classify_intent maps queries to correct intent states."""
    # Analysis cases
    assert classify_intent("What is my active P&L?") == "analysis"
    assert classify_intent("Should I buy AAPL or sell TSLA?") == "analysis"
    assert classify_intent("What is your analysis on MSFT?") == "analysis"

    # Execution cases
    assert classify_intent("Buy 10 shares of AAPL") == "execution"
    assert classify_intent("sell all NFLX") == "execution"
    assert classify_intent("Add MSFT to my watchlist") == "execution"
    assert classify_intent("untrack TSLA") == "execution"

    # Confirmation cases
    assert classify_intent("yes") == "confirmation"
    assert classify_intent("do it") == "confirmation"
    assert classify_intent("go ahead") == "confirmation"
    assert classify_intent("confirm the trade") == "confirmation"
    assert classify_intent("yes, please do that") == "confirmation"


def test_pending_actions_cache(pending_cache):
    """Verifies thread-safe caching, retrieval, manual expiration, and cleaning."""
    user_id = "default"

    # 1. Caching and retrieving
    action_set = PendingActionSet(
        user_id=user_id,
        trades=[TradeRequest(ticker="AAPL", side="buy", quantity=10.0)],
        watchlist_changes=[],
        timestamp=datetime.now(timezone.utc),
        message_id="msg-1",
    )
    pending_cache.set(user_id, action_set)

    cached = pending_cache.get(user_id)
    assert cached is not None
    assert cached.message_id == "msg-1"
    assert cached.trades[0].ticker == "AAPL"

    # 2. Expiration (manual injection of old timestamp)
    action_set_old = PendingActionSet(
        user_id=user_id,
        trades=[TradeRequest(ticker="AAPL", side="buy", quantity=10.0)],
        watchlist_changes=[],
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=11),
        message_id="msg-old",
    )
    pending_cache.set(user_id, action_set_old)

    # Should expire on retrieval
    assert pending_cache.get(user_id) is None

    # 3. Cache clearing
    pending_cache.set(user_id, action_set)
    pending_cache.clear(user_id)
    assert pending_cache.get(user_id) is None


@pytest.mark.asyncio
async def test_mock_chat_execution_loop(
    temp_db, price_cache, market_source, pending_cache, monkeypatch
):
    """
    Tests the complete conversational paper-trading loop in mock mode:
    1. Direct trade execution (explicit user intent).
    2. Suggestion and caching (analysis intent).
    3. Unambiguous confirmation (confirmation intent) that triggers the cached trade.
    """
    init_db()
    monkeypatch.setenv("LLM_MOCK", "true")

    # --- PHASE 1: DIRECT EXECUTION ---
    # User sends "buy AAPL"
    res1 = await handle_chat_message(
        user_message="buy AAPL",
        price_cache=price_cache,
        market_data_source=market_source,
        pending_actions_cache=pending_cache,
    )

    # Verify execution details
    assert "Successfully bought 10.0 shares of AAPL" in res1["message"]
    assert len(res1["actions"]["trades"]) == 1
    trade_audit = res1["actions"]["trades"][0]
    assert trade_audit["status"] == "success"
    assert trade_audit["details"]["ticker"] == "AAPL"
    assert trade_audit["details"]["quantity"] == 10.0

    # Verify DB mutations: cash decreases from $10,000 by 10 * $190 = $1,900
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id='default';")
        cash_cents = cursor.fetchone()["cash_balance_cents"]
        # Expected cash cents: 1000000 - 190000 = 810000 ($8,100.00)
        assert cash_cents == 810000

        # Verify position was updated
        cursor.execute("SELECT quantity, avg_cost FROM positions WHERE ticker='AAPL';")
        pos = cursor.fetchone()
        assert pos["quantity"] == 10.0
        assert float(pos["avg_cost"]) == 190.00

    # --- PHASE 2: ANALYSIS & CACHING ---
    # User asks "What is your recommendation on AAPL?"
    res2 = await handle_chat_message(
        user_message="What is your recommendation on AAPL?",
        price_cache=price_cache,
        market_data_source=market_source,
        pending_actions_cache=pending_cache,
    )

    # Verify it does NOT mutate portfolio state immediately, but returns recommendations and caches actions
    assert "AAPL looks solid" in res2["message"]
    # Check that recommendations are returned
    assert (
        len(res2["recommendations"]) == 2
    )  # 1 from recommendations, 1 mapped from trades proposal
    assert res2["recommendations"][0]["ticker"] == "AAPL"
    assert res2["recommendations"][0]["type"] == "trade"

    # Check that actions are cached
    cached_set = pending_cache.get("default")
    assert cached_set is not None
    assert len(cached_set.trades) == 1
    assert cached_set.trades[0].ticker == "AAPL"
    assert cached_set.trades[0].side == "buy"

    # Cash balance and position should remain unchanged
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id='default';")
        assert cursor.fetchone()["cash_balance_cents"] == 810000
        cursor.execute("SELECT quantity FROM positions WHERE ticker='AAPL';")
        assert cursor.fetchone()["quantity"] == 10.0

    # --- PHASE 3: CONFIRMATION ---
    # User says "yes, do that"
    res3 = await handle_chat_message(
        user_message="yes, do that",
        price_cache=price_cache,
        market_data_source=market_source,
        pending_actions_cache=pending_cache,
    )

    # Verify execution of cached trade
    assert "Executed trade: successfully bought 10.0 shares of AAPL" in res3["message"]
    assert len(res3["actions"]["trades"]) == 1
    assert res3["actions"]["trades"][0]["status"] == "success"

    # Verify DB mutations: cash decreases again from $8,100 by $1,900 to $6,200 ($6,200.00)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id='default';")
        assert cursor.fetchone()["cash_balance_cents"] == 620000

        # Position should increase from 10 to 20 shares
        cursor.execute("SELECT quantity FROM positions WHERE ticker='AAPL';")
        assert cursor.fetchone()["quantity"] == 20.0

    # Cache should be cleared
    assert pending_cache.get("default") is None
