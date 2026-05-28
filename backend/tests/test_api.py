from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db.connection import get_db_connection
from app.db.manager import init_db
from app.main import app


@pytest.fixture
def test_db_setup(tmp_path, monkeypatch):
    """
    Isolates tests with a clean SQLite database.
    """
    temp_db_file = tmp_path / "test_finally_api.db"
    monkeypatch.setenv("DATABASE_PATH", str(temp_db_file))
    init_db()
    yield temp_db_file
    if temp_db_file.exists():
        try:
            temp_db_file.unlink()
        except OSError:
            pass


@pytest.fixture
def client(test_db_setup, monkeypatch):
    """
    Provides a FastAPI TestClient that cleanly starts/stops app lifespan.
    Enforces LLM_MOCK=true for deterministic tests.
    """
    monkeypatch.setenv("LLM_MOCK", "true")
    # Make sure APP_PASSWORD is empty by default in tests
    monkeypatch.setenv("APP_PASSWORD", "")
    with TestClient(app) as c:
        yield c


# -------------------------------------------------------------
# 1. Watchlist CRUD Tests
# -------------------------------------------------------------

def test_get_watchlist(client):
    """GET /api/watchlist returns the seeded default 10 tickers."""
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 10
    tickers = {item["ticker"] for item in data}
    assert "AAPL" in tickers
    assert "MSFT" in tickers


def test_add_to_watchlist_valid(client):
    """POST /api/watchlist adds a normalized uppercase ticker."""
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 200
    data = response.json()
    tickers = {item["ticker"] for item in data}
    assert "PYPL" in tickers


def test_add_to_watchlist_invalid(client):
    """POST /api/watchlist rejects invalid ticker formats."""
    response = client.post("/api/watchlist", json={"ticker": "INVALIDTICKER"})
    assert response.status_code == 400
    assert "Invalid ticker format" in response.json()["detail"]


def test_delete_from_watchlist_unheld(client):
    """DELETE untracks ticker from watchlist and market feed if not held."""
    # First verify it's there
    client.post("/api/watchlist", json={"ticker": "NFLX"})
    # Delete untracked/unheld ticker
    response = client.delete("/api/watchlist/NFLX")
    assert response.status_code == 200
    tickers = {item["ticker"] for item in response.json()}
    assert "NFLX" not in tickers

    # Ticker should be removed from market active list (app.state.market_data_source)
    market_tickers = client.app.state.market_data_source.get_tickers()
    assert "NFLX" not in market_tickers


def test_delete_from_watchlist_held(client):
    """DELETE removes ticker from watchlist table but keeps it priced if held."""
    # Buy AAPL to establish a position
    trade_res = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 5.0})
    assert trade_res.status_code == 200

    # Delete AAPL from watchlist
    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 200
    watchlist_tickers = {item["ticker"] for item in response.json()}
    assert "AAPL" not in watchlist_tickers

    # Ticker MUST remain in the market data source list because it's still held!
    market_tickers = client.app.state.market_data_source.get_tickers()
    assert "AAPL" in market_tickers


# -------------------------------------------------------------
# 2. Portfolio and Trade Execution Tests
# -------------------------------------------------------------

def test_get_portfolio_empty(client):
    """GET /api/portfolio returns default cash and no positions."""
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["cash_balance_cents"] == 1000000
    assert data["cash_balance"] == 10000.0
    assert len(data["positions"]) == 0
    assert data["total_portfolio_value"] == 10000.0
    assert data["unrealized_p_l"] == 0.0
    assert data["degraded"] is False


def test_execute_trade_buy_shares(client):
    """POST /api/portfolio/trade buys fractional shares, updates DB, records snapshot."""
    response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10.5})
    assert response.status_code == 200
    data = response.json()

    assert data["trade"]["ticker"] == "AAPL"
    assert data["trade"]["side"] == "buy"
    assert data["trade"]["quantity"] == 10.5
    assert data["trade"]["source"] == "manual"

    # Position is established
    assert data["position"]["ticker"] == "AAPL"
    assert data["position"]["quantity"] == 10.5
    assert Decimal(data["position"]["avg_cost"]) > 0

    # Verify database updates
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Verify cash decreased
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id='default';")
        cash = cursor.fetchone()["cash_balance_cents"]
        assert cash < 1000000

        # Verify trade is logged
        cursor.execute("SELECT ticker, side, quantity FROM trades;")
        trades = cursor.fetchall()
        assert len(trades) == 1
        assert trades[0]["ticker"] == "AAPL"
        assert trades[0]["quantity"] == 10.5

        # Verify immediate snapshot created
        cursor.execute("SELECT count(*) FROM portfolio_snapshots;")
        snaps_count = cursor.fetchone()[0]
        assert snaps_count >= 1


def test_execute_trade_buy_notional(client):
    """POST /api/portfolio/trade buy by notional converts to shares and rounds down."""
    response = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "buy", "notional_amount": 500.0})
    assert response.status_code == 200
    data = response.json()

    assert data["trade"]["ticker"] == "MSFT"
    assert data["trade"]["side"] == "buy"
    # Derives quantity (500 / execution_price) rounded down to 6 decimals
    assert data["trade"]["quantity"] > 0
    assert data["trade"]["notional_amount"] <= 500.0


def test_execute_trade_insufficient_cash(client):
    """POST /api/portfolio/trade rejects buys exceeding cash balance."""
    response = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "side": "buy", "quantity": 10000.0})
    assert response.status_code == 400
    assert "Insufficient cash balance" in response.json()["detail"]


def test_execute_trade_sell_too_much(client):
    """POST /api/portfolio/trade rejects sells exceeding holding quantity."""
    # First buy 5 shares of MSFT
    client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "buy", "quantity": 5.0})

    # Attempt to sell 6 shares
    response = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "sell", "quantity": 6.0})
    assert response.status_code == 400
    assert "Insufficient shares" in response.json()["detail"]


def test_execute_trade_partial_and_full_sell(client):
    """POST /api/portfolio/trade partial sell leaves position; full sell deletes position row."""
    # 1. Buy 5.0 MSFT
    client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "buy", "quantity": 5.0})

    # 2. Sell 2.0 MSFT (partial)
    res_partial = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "sell", "quantity": 2.0})
    assert res_partial.status_code == 200
    assert res_partial.json()["position"]["quantity"] == 3.0

    # 3. Sell 3.0 MSFT (full sell)
    res_full = client.post("/api/portfolio/trade", json={"ticker": "MSFT", "side": "sell", "quantity": 3.0})
    assert res_full.status_code == 200
    assert res_full.json()["position"] is None  # Position deleted from DB

    # Verify positions table is empty for MSFT
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM positions WHERE ticker='MSFT';")
        count = cursor.fetchone()[0]
        assert count == 0


def test_degraded_portfolio_state(client):
    """GET /api/portfolio reports degraded status when a held ticker lacks price cache entry."""
    # 1. Establish position in AMZN
    client.post("/api/portfolio/trade", json={"ticker": "AMZN", "side": "buy", "quantity": 2.0})

    # 2. Mock degraded price feed by removing AMZN from PriceCache
    client.app.state.price_cache.remove("AMZN")

    # 3. Request portfolio status
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    data = response.json()
    assert data["degraded"] is True
    assert data["total_portfolio_value"] is None
    assert data["unrealized_p_l"] is None


# -------------------------------------------------------------
# 3. LLM Chat Integration and Intent Gating Tests
# -------------------------------------------------------------

def test_chat_analysis_intent(client):
    """Chat with analysis intent parses recommendations and caches pending actions without immediate execution."""
    response = client.post("/api/chat", json={"message": "analyze AAPL"})
    assert response.status_code == 200
    data = response.json()

    assert "AAPL" in data["message"]
    assert len(data["recommendations"]) >= 1
    assert data["recommendations"][0]["ticker"] == "AAPL"

    # Verify NO trades were executed (since intent is analysis, it is gated)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM trades;")
        trades_count = cursor.fetchone()[0]
        assert trades_count == 0


def test_chat_confirmation_intent(client):
    """Chat message matching 'yes' confirms and executes previously cached recommendations."""
    # 1. Ask for analysis first (caches pending recommendation to buy 10 shares of AAPL)
    client.post("/api/chat", json={"message": "analyze AAPL"})

    # 2. Say "yes" to confirm the action
    response = client.post("/api/chat", json={"message": "yes"})
    assert response.status_code == 200
    data = response.json()

    assert "Executed" in data["message"] or "confirmed" in data["message"] or "success" in data["message"]
    assert len(data["actions"]["trades"]) == 1
    assert data["actions"]["trades"][0]["ticker"] == "AAPL"
    assert data["actions"]["trades"][0]["status"] == "success"

    # Verify trade was successfully logged in DB
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT ticker, side, quantity FROM trades;")
        trades = cursor.fetchall()
        assert len(trades) == 1
        assert trades[0]["ticker"] == "AAPL"
        assert trades[0]["quantity"] == 10.0


def test_chat_analysis_returns_proposed_actions(client):
    """Chat message in analysis mode returns the proposed trades and watchlist changes to client."""
    response = client.post("/api/chat", json={"message": "analyze AAPL"})
    assert response.status_code == 200
    data = response.json()

    assert len(data["trades"]) == 1
    assert data["trades"][0]["ticker"] == "AAPL"
    assert data["trades"][0]["side"] == "buy"
    assert data["trades"][0]["quantity"] == 10.0
    assert data["actions"] is None


def test_chat_execution_intent(client):
    """Chat message with direct instruction immediately executes the trade or watchlist update."""
    response = client.post("/api/chat", json={"message": "buy 10 shares of AAPL"})
    assert response.status_code == 200
    data = response.json()

    assert len(data["actions"]["trades"]) == 1
    assert data["actions"]["trades"][0]["ticker"] == "AAPL"
    assert data["actions"]["trades"][0]["status"] == "success"

    # Verify positions and trades
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT quantity FROM positions WHERE ticker='AAPL';")
        qty = cursor.fetchone()["quantity"]
        assert qty == 10.0


def test_clear_chat_history(client):
    """DELETE /api/chat clears all persisted chat logs."""
    # Send a message to log something
    client.post("/api/chat", json={"message": "hello"})

    # Verify log exists
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM chat_messages;")
        assert cursor.fetchone()[0] > 0

    # Delete history
    response = client.delete("/api/chat")
    assert response.status_code == 200

    # Verify history is empty
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM chat_messages;")
        assert cursor.fetchone()[0] == 0


# -------------------------------------------------------------
# 4. APP_PASSWORD Authentication Gate Tests
# -------------------------------------------------------------

def test_app_password_gate_inactive(client):
    """When APP_PASSWORD is empty, all routes are accessible without authorization."""
    response = client.get("/api/watchlist")
    assert response.status_code == 200


def test_app_password_gate_active(client, monkeypatch):
    """When APP_PASSWORD is configured, gates API requests unless valid authorization is provided."""
    # 1. Configure password
    monkeypatch.setenv("APP_PASSWORD", "supersecret123")

    # 2. Attempt unauthorized request (no headers) -> Rejected with 401
    response = client.get("/api/watchlist")
    assert response.status_code == 401
    assert "Unauthorized" in response.json()["detail"]

    # 3. Attempt authorized request with X-App-Password header -> Accepted
    res_header = client.get("/api/watchlist", headers={"X-App-Password": "supersecret123"})
    assert res_header.status_code == 200

    # 4. Attempt authorized request with Bearer Authorization header -> Accepted
    res_bearer = client.get("/api/watchlist", headers={"Authorization": "Bearer supersecret123"})
    assert res_bearer.status_code == 200

    # 5. Attempt authorized request with cookie -> Accepted
    client.cookies.set("app_password", "supersecret123")
    res_cookie = client.get("/api/watchlist")
    assert res_cookie.status_code == 200
