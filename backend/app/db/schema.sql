-- Database Schema for FinAlly (Finance Ally)
-- V1 Schema definition with single-user defaults, designed for future multi-user support

-- Enable foreign keys (though this needs to be run per-connection, having it here is good practice)
PRAGMA foreign_keys = ON;

-- 1. users_profile: User state and cash balance
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY DEFAULT 'default',
    cash_balance_cents INTEGER NOT NULL DEFAULT 1000000, -- Default: $10,000.00
    created_at TEXT NOT NULL                             -- ISO 8601 timestamp
);

-- 2. watchlist: Tickers the user is tracking
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,                                -- Uppercase ticker symbol (e.g. AAPL)
    added_at TEXT NOT NULL,                              -- ISO 8601 timestamp
    UNIQUE(user_id, ticker),
    FOREIGN KEY(user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

-- 3. positions: Active asset holdings (long-only)
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,                                -- Uppercase ticker symbol
    quantity REAL NOT NULL,                              -- Fractional shares supported
    avg_cost TEXT NOT NULL,                              -- Exact decimal string representation
    updated_at TEXT NOT NULL,                            -- ISO 8601 timestamp
    UNIQUE(user_id, ticker),
    FOREIGN KEY(user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

-- 4. trades: Historical log of executed trades (append-only)
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,                                -- Uppercase ticker symbol
    side TEXT NOT NULL CHECK(side IN ('buy', 'sell')),   -- Transaction type
    quantity REAL NOT NULL,                              -- Quantity traded
    execution_price TEXT NOT NULL,                       -- Exact execution price as decimal string
    notional_amount_cents INTEGER NOT NULL,              -- Derivation: quantity * execution_price rounded to cents
    source TEXT NOT NULL CHECK(source IN ('manual', 'ai')), -- Origin of trade trigger
    executed_at TEXT NOT NULL,                           -- ISO 8601 timestamp
    FOREIGN KEY(user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

-- 5. portfolio_snapshots: Total portfolio value recorded over time (for P&L charts)
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value_cents INTEGER NOT NULL,                  -- cash_balance_cents + sum(quantity * current_price)
    recorded_at TEXT NOT NULL,                           -- ISO 8601 timestamp
    FOREIGN KEY(user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);

-- 6. chat_messages: LLM interaction history
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')), -- Sender role
    content TEXT NOT NULL,                                -- Message content text
    actions TEXT,                                        -- JSON string auditing executed actions, or NULL
    created_at TEXT NOT NULL,                            -- ISO 8601 timestamp
    FOREIGN KEY(user_id) REFERENCES users_profile(id) ON DELETE CASCADE
);
