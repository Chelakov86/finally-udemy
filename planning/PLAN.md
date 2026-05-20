# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered paper trading workstation that streams live-updating prices, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — simulated live prices or market prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell** — market orders only, entered by shares or dollar amount, instant fill at current price, no fees, no confirmation dialog after explicit user intent, no short selling
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist when explicitly requested or confirmed through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat
- Buying a ticker does not automatically add it to the watchlist; owned tickers are priced for valuation even when they are not watched

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Price source label**: simulator mode displays "Simulated live prices"; Massive mode displays "Market prices"
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: LiteLLM → Google Gemini API using `gemma-4-31b-it`, with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── docker-compose.yml        # Optional convenience wrapper
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend initializes the database during FastAPI lifespan startup - creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: Google Gemini API key for LLM chat functionality
GEMINI_API_KEY=your-google-gemini-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false

# Optional: LiteLLM model identifier. Default is gemma-4-31b-it.
LLM_MODEL=gemma-4-31b-it

# Optional but required before exposing the app on a public URL.
# When set, the backend gates the UI and API behind a simple password check.
APP_PASSWORD=
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- If `LLM_MODEL` is set and non-empty → backend uses that LiteLLM model identifier; otherwise it defaults to `gemma-4-31b-it`
- If `APP_PASSWORD` is set and non-empty → backend requires the configured password before serving the UI or API. Do not deploy the app to a public URL without this or an equivalent auth proxy.
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Runs continuously while the app is running; it does not pause for real-world market hours
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices (e.g., AAPL ~$190, GOOGL ~$175, etc.)
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator
- Reflects provider data availability; if markets are closed or provider data is static, freshness/status handling communicates degraded or stale prices

### Ticker Validation

- User and AI ticker input is case-insensitive and normalized to uppercase
- Valid v1 ticker format is `^[A-Z]{1,5}$`
- Invalid symbols such as `BRK.B`, `BTC-USD`, and `7203.T` are rejected with a clear validation error
- ETFs such as `SPY` and `QQQ` are valid if they match the same format
- In simulator mode, any syntactically valid ticker can be added or traded because the simulator can generate a price
- In Massive mode, adding or trading a ticker requires provider data; if no current price can be obtained, the operation fails with a clear validation error
- Trade execution always requires a current price, regardless of market data source

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- The cache also holds a sliding in-memory history of the most recent 30 price updates per ticker so frontend sparklines can render immediately after page load
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer
- Active market data coverage is the union of watchlist tickers and tickers with active positions, so portfolio valuation continues even if a user removes an owned ticker from the watchlist
- Removing a held ticker from the watchlist is allowed. The ticker remains price-tracked until the position is fully sold; if it is neither watched nor held, market data coverage can stop.
- Cached prices have freshness semantics. Display and portfolio valuation may use stale prices with degraded-state warnings, but trade execution requires a fresh price. Freshness threshold is 5 seconds in simulator mode and 60 seconds in Massive mode.

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- Server pushes price updates for all priced tickers at a regular cadence (~500ms): the union of watchlist tickers and tickers with active positions
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite Initialization

The backend verifies and initializes the SQLite database during the FastAPI `lifespan` startup handler before accepting HTTP traffic. If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically
- Startup initialization avoids concurrent first-request schema creation races
- Schema creation and seed inserts are idempotent
- Every SQLite connection must execute `PRAGMA foreign_keys = ON;`
- If the app is ever run with multiple Uvicorn worker processes, migrations must use a process-safe lock because each worker runs its own startup lifecycle

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration. V1 does not expose users, accounts, profiles, login, or signup in the UI or public API; all behavior assumes one implicit participant.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance_cents` INTEGER (default: `1000000`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` TEXT (decimal string)
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

Positions are long-only. Quantity can never be negative; sell requests that exceed the held quantity are rejected. When a sell reduces a position to exactly zero, the position row is deleted; the trade execution remains in the append-only `trades` table.

Average cost uses weighted-average purchase price per share. Buying more of an existing position recalculates average cost with Python `Decimal` arithmetic and persists the result as a decimal string; partial sells reduce quantity but leave average cost unchanged.

V1 tracks unrealized P&L for active positions and total portfolio value over time. Realized P&L reporting is out of scope.

Total portfolio value is `cash_balance + sum(position.quantity * current_price)`, persisted as integer cents. Held tickers should always be priced tickers. If a current price is missing for a held ticker, portfolio valuation should report a degraded/incomplete state rather than silently using zero or stale data.

**trades** — Trade execution history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `execution_price` TEXT (decimal string)
- `notional_amount_cents` INTEGER (derived from `quantity * price` and rounded to cents)
- `source` TEXT (`"manual"` or `"ai"`)
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each successful trade execution.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value_cents` INTEGER
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — action results for attempted trades and watchlist changes, including success/failure status; null for user messages)
- `created_at` TEXT (ISO timestamp)

Chat history persists in SQLite across container restarts. The UI may display persisted history, but LLM prompts should include only a bounded recent window, defaulting to the most recent 20 messages. Portfolio context is always loaded fresh from current state, not inferred from chat history.

### Default Seed Data

- One user profile: `id="default"`, `cash_balance_cents=1000000`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |
| GET | `/api/market/history` | Recent in-memory price history for tracked tickers, defaulting to the latest 30 ticks per ticker |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade request: `{ticker, side, quantity}` or `{ticker, side, notional_amount}`. Returns the executed `Trade` record and the updated `Position` record, or a validation error without mutation |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart). Supports `range=1D|1W|1M|ALL` and returns at most 200 downsampled points by default |

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}`. Returns the updated watchlist with cached prices and recent price history |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker. Returns the updated watchlist with cached prices and recent price history |

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |
| DELETE | `/api/chat` | Clear persisted chat history for the default user |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use LiteLLM with Google Gemini via the `GEMINI_API_KEY` environment variable. Structured outputs should be used to interpret the results.

There is a `GEMINI_API_KEY` in the `.env` file in the project root.

Use `gemma-4-31b-it` as the default LLM model. The actual LiteLLM model identifier must be read from `LLM_MODEL` so deployments can adjust provider routing or model availability without code changes.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads a bounded recent conversation window from the `chat_messages` table, defaulting to the most recent 20 messages
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM via LiteLLM → Google Gemini using the configured `LLM_MODEL`, requesting structured output with the strongest mechanism supported by the configured model
5. Parses and validates the complete structured JSON response with Pydantic
6. Classifies the user's message intent as analysis, execution, or confirmation
7. Executes trades and watchlist changes only when backend intent gating allows execution or mutation
8. Stores the message and attempted action results in `chat_messages`
9. Returns the complete JSON response to the frontend

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "recommendations": [
    {"type": "trade", "ticker": "AAPL", "side": "buy", "rationale": "Diversifies the portfolio with a profitable mega-cap position"},
    {"type": "watchlist", "ticker": "PYPL", "rationale": "Useful payments-sector comparison for V"}
  ],
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10},
    {"ticker": "NVDA", "side": "buy", "notional_amount": 500}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `recommendations` (optional): Array of non-mutating suggestions. Recommendations never change portfolio or watchlist state by themselves.
- `trades` (optional): Array of trade requests to execute only after explicit user request or confirmation. Each trade must include exactly one of `quantity` or `notional_amount`. Dollar-based buy and sell requests are converted to share quantity at the current price before recording the execution. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares or holding value for sells)
- `watchlist_changes` (optional): Array of watchlist modifications to apply only after explicit user request or confirmation. Lower-friction confirmations such as "add it", "track those", or "remove TSLA" are sufficient.

The backend must gracefully handle malformed JSON, schema validation failures, and provider-side structured-output errors. Invalid model output should produce a user-facing assistant error response and must not execute trades or mutate the watchlist.

### Execution Intent

Trades specified by the LLM execute without an additional confirmation dialog only when the user has explicitly requested execution or confirmed a prior recommendation. This is a deliberate design choice:
- Analysis requests should produce recommendations, not trades
- Execution requests should produce validated trades
- Confirmation phrases like "yes, do that" can execute the prior recommendation
- It preserves a fluid demo while keeping user intent unambiguous

Backend intent gating is authoritative. The LLM may propose `recommendations`, `trades`, and `watchlist_changes`, but only the backend decides whether executable arrays are applied. If the user's message is analysis-only, executable arrays are ignored or converted into non-mutating recommendations in the response. This same rule applies in mock mode.

Confirmation intent applies only to the most recent pending actionable recommendation set, and only when unambiguous. Short confirmations such as "yes", "do it", or "go ahead" can execute the latest actionable recommendation set if it was presented as one explicit plan. If the latest assistant response contains multiple independent recommendations, a generic confirmation is ambiguous and should ask the user to clarify. Specific confirmations such as "buy the NVDA one" may execute the matching recommendation. Pending recommendations expire after a new unrelated user message or after 10 minutes.

Pending executable recommendation state is not persisted across container restarts. Chat messages and recommendation text remain in history, but after restart a generic confirmation such as "yes, do it" must not execute an old recommendation.

Pending executable recommendations are stored in a thread-safe in-memory `PendingActionsCache` with a periodic expiration loop. The cache stores explicit typed state:

```python
class PendingActionSet(BaseModel):
    user_id: str
    trades: list[TradeRequest]
    watchlist_changes: list[WatchlistChangeRequest]
    timestamp: datetime
    message_id: str
```

Entries expire after 10 minutes and are cleared when a new unrelated user message makes the prior recommendation stale.

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

Trade requests may be share-based or dollar-based. Dollar-based buys and sells are converted to fractional shares at a fresh current price before validation and execution. Executed trades are always recorded as fractional shares at the execution price, with notional amount stored as derived audit data. Short selling is not supported; sells can only reduce existing long positions and position quantity can never become negative.

V1 supports `sell all` for owned tickers, mapping to the full current position quantity. V1 does not support a manual `buy max` shortcut; AI requests such as "buy as much as possible" should ask for clarification or a dollar amount unless a later decision defines buy-max semantics.

Trade quantity precision is 6 decimal places. Dollar-based trade requests convert to shares using the fresh current price and round the resulting share quantity down to 6 decimal places before validation and execution. Persisted money values use integer cents; API/UI responses may expose dollar numbers for presentation. Persisted trade execution prices use decimal strings, and trade execution math uses decimal arithmetic. The price cache may use floats for streaming/display, but execution converts prices to decimals before validation and persistence. The UI may show up to 6 share decimals while trimming trailing zeros.

API responses should expose exact money fields in cents and may also include display-friendly dollar fields. For example, return `cash_balance_cents` plus `cash_balance`, and `total_value_cents` plus `total_value`. Request payloads may accept dollar amounts for user-entered notionals and convert them at the backend boundary.

Frontend money formatting should use cents fields as authoritative when present. Dollar fields are convenience values and should not be used for precise frontend calculations. The frontend must not calculate portfolio state from formatted strings.

Dollar-based buys never overspend cash or the requested notional amount. Executed notional is derived from the rounded-down share quantity and execution price; any remainder stays as cash.

Dollar-based sells never exceed the requested notional amount or the held share quantity. Executed notional is derived from the rounded-down share quantity and execution price; any unsold remainder stays in the long position.

Trade requests are rejected if the requested quantity is less than or equal to zero, the rounded executable quantity is zero, or the executed notional amount is less than $0.01. The validation error should state that the trade amount is too small to execute.

The AI may recommend or be asked to trade tickers outside the current watchlist. Before executing a trade for an unpriced ticker, the backend must make it a priced ticker and obtain a current price. If no price is available, the trade is rejected with a clear error. This does not add the ticker to the watchlist unless separately requested.

Manual trade bar submissions and AI-requested trades must use the same backend trade execution path. That path owns ticker validation, current price lookup, share/dollar conversion, cash and holding validation, no-short-selling enforcement, position updates, trade history persistence, and portfolio snapshot creation. Executed trades record `source` as `"manual"` or `"ai"`.

Successful trade executions create an immediate portfolio snapshot. Failed trade requests and watchlist changes do not create portfolio snapshots.

Periodic snapshots should be written only when total portfolio value changed from the last snapshot by at least $0.01, or when no previous snapshot exists. Successful trade executions always create a snapshot even if the value change is below this threshold.

Attempted AI actions are persisted with result status. Successful actions include execution or watchlist details. Failed actions include a clear error reason and do not mutate portfolio or watchlist state. Assistant messages should summarize failures in plain language.

Watchlist changes follow the same intent rule with a lower-friction interpretation: short commands such as "track PYPL", "add those", or "remove TSLA" are sufficient, but analysis-only prompts should not silently mutate the watchlist.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades only when the user explicitly asks or agrees
- Recommend watchlist changes proactively, but apply them only when the user explicitly asks or agrees
- Recommend tickers outside the current watchlist when relevant
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling Google Gemini. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

Mock mode replaces only the model call. Deterministic mock responses must still pass through the normal intent checks, schema parsing, trade validation, watchlist validation, execution, and persistence pipeline.

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watchlist tickers with: ticker symbol, current price (flashing green/red on change), daily change %, and a sparkline mini-chart seeded from cached price history and then updated from SSE
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of active long positions: ticker, quantity, avg cost, current price, unrealized P&L, % change
- **Trade bar** — simple input area: ticker field, shares-or-dollar amount input, buy button, sell button, and sell-all shortcut for owned tickers. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value (updating live), connection status indicator, cash balance

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Heatmaps and treemaps must render within explicit container bounds. Prefer canvas-based rendering or a dedicated React treemap component with fixed width/height containment to avoid resize distortion in the dense terminal layout.
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

FastAPI must register API and static asset routes before a final catch-all route. The catch-all serves the exported `index.html` for non-API, non-asset paths so client-side routing survives browser refreshes on subroutes.

> [!WARNING]
> **CRITICAL SECURITY RISK:** V1 has no signup and assumes one implicit user. Never deploy the Docker container directly to a public cloud URL unless access is protected by `APP_PASSWORD` or an external authentication proxy such as Nginx Basic Auth or Cloudflare Access. Without authentication, anyone with the URL can view portfolio/chat history, execute paper trades, and consume Gemini API quota.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

Public cloud deployment is only acceptable when protected by `APP_PASSWORD` or an external authentication proxy. The default local-first configuration must not be exposed directly to the internet.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade request validation, trade execution logic, share-based and dollar-based order conversion, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: Support two E2E modes:
- Local host mode: run Playwright on the developer machine against an already running app server. This is the default for active development because it is faster and avoids browser-driver friction.
- Containerized CI mode: a separate `docker-compose.test.yml` in `test/` spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image and provides isolated CI runs.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection
