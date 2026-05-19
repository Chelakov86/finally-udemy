# FinAlly Context

FinAlly is a single-context domain for a simulated finance application. This glossary defines the project language used by plans, code, and agent handoffs.

## Language

**FinAlly**:
The paper trading workstation being built for the agentic AI coding course.

**Paper trading workstation**:
A professional-style trading interface where all portfolio activity uses simulated money and carries no real financial risk.
_Avoid_: Trading workstation, AI trading game, brokerage platform

**Portfolio**:
The user's simulated holdings and cash balance inside FinAlly.
_Avoid_: Account, brokerage account, simulated portfolio

**Long Position**:
A positive share holding in one ticker within the Portfolio.
_Avoid_: Short position, negative position

**Average Cost**:
The weighted-average purchase price per share for a Long Position.
_Avoid_: Cost basis, entry price

**Unrealized P&L**:
The gain or loss on an active Long Position based on current price versus Average Cost.
_Avoid_: Realized P&L, profit

**Portfolio Value**:
The Portfolio cash balance plus the current market value of all Long Positions.
_Avoid_: Equity, account value

**Money Amount**:
A dollar-denominated amount stored exactly as integer cents at persistence boundaries.
_Avoid_: Float dollars, REAL money

**Watchlist**:
The user's set of tracked ticker symbols in FinAlly.
_Avoid_: Symbol list, ticker list

**Priced Ticker**:
A ticker whose latest price is maintained for watchlist display or portfolio valuation.
_Avoid_: Watched ticker, active ticker

**Fresh Price**:
A current enough price to allow Trade Execution.
_Avoid_: Latest price, cached price

**Stale Price**:
A cached price old enough that it may be displayed with warning but cannot be used for Trade Execution.
_Avoid_: Invalid price, missing price

**Ticker**:
A normalized uppercase US equity-style symbol from one to five letters.
_Avoid_: Crypto pair, exchange-qualified symbol, dotted share class

**Trade Recommendation**:
A non-executed trading suggestion produced by FinAlly or the AI assistant.
_Avoid_: Signal, order

**Trade Request**:
A user's requested buy or sell expressed as either a share quantity or a dollar amount.
_Avoid_: Order, transaction

**Sell All**:
A Trade Request to sell the full quantity of an existing Long Position.
_Avoid_: Liquidate, close position

**Trade Execution**:
An explicit portfolio change recorded as shares at the execution price after the user asks for or confirms a trade.
_Avoid_: Auto-trade, recommendation

**Watchlist Change**:
An explicit addition to or removal from the Watchlist after the user asks for or confirms it.
_Avoid_: Auto-watch, passive recommendation

## Relationships

- **FinAlly** is a **Paper trading workstation**
- A **Portfolio** is scoped to FinAlly's single implicit participant in v1
- A **Portfolio** contains zero or more **Long Positions**
- A **Long Position** has an **Average Cost**
- A **Long Position** has **Unrealized P&L** while it remains active
- **Portfolio Value** is cash plus current market value of active **Long Positions**
- A persisted **Money Amount** is stored as integer cents
- A **Ticker** must match `^[A-Z]{1,5}$`
- A **Priced Ticker** includes every Watchlist ticker and every ticker with an active Long Position
- In simulator mode, any syntactically valid **Ticker** can become a **Priced Ticker**
- In real market data mode, a **Ticker** can become a **Priced Ticker** only if the provider returns a current price
- A buy **Trade Execution** creates a **Priced Ticker** but does not create a **Watchlist Change**
- Removing a held ticker from the **Watchlist** leaves it as a **Priced Ticker** until the **Long Position** is fully sold
- A **Trade Recommendation** may reference tickers outside the **Watchlist**
- A **Trade Execution** requires a **Fresh Price**
- A **Trade Request** may be expressed in shares or dollars
- **Sell All** maps to the full current quantity of a **Long Position**
- A **Trade Execution** is always recorded in shares at an execution price
- A dollar-based sell **Trade Request** is converted to shares using the current price before validation and execution
- A sell **Trade Request** cannot reduce a **Long Position** below zero
- A fully sold **Long Position** is removed from the **Portfolio**
- A partial sell reduces **Long Position** quantity and does not change **Average Cost**
- A **Trade Recommendation** may become a **Trade Execution** only after explicit user intent
- A **Watchlist Change** may occur after lower-friction explicit intent such as "track this", "add those", or "remove TSLA"

## Example Dialogue

> **Dev:** "Should the buy button place a real market order?"
> **Domain expert:** "No. In the **Paper trading workstation**, every trade changes only the simulated portfolio."

> **Dev:** "Should we call this an account?"
> **Domain expert:** "No. Use **Portfolio**; there is no brokerage account or login identity."

> **Dev:** "If the AI recommends buying NVDA, should we execute immediately?"
> **Domain expert:** "No. A **Trade Recommendation** becomes a **Trade Execution** only when the user explicitly asks or confirms."

> **Dev:** "If the user says buy $500 of NVDA, what do we store?"
> **Domain expert:** "The **Trade Request** is dollar-based, but the **Trade Execution** records the resulting share quantity at the current price."

> **Dev:** "If the user says sell $500 of NVDA, is that allowed?"
> **Domain expert:** "Yes. Convert the dollar amount to shares using the current price, then validate against the holding."

> **Dev:** "What does sell all AAPL mean?"
> **Domain expert:** "**Sell All** means sell the full current AAPL **Long Position**."

> **Dev:** "Can the user sell TSLA if they do not own it?"
> **Domain expert:** "No. FinAlly only supports **Long Positions**; no short selling."

> **Dev:** "If the user sells all AAPL, do we keep a zero-share row?"
> **Domain expert:** "No. Remove the **Long Position** and keep the **Trade Execution** in history."

> **Dev:** "If the user sells half their AAPL, does average cost change?"
> **Domain expert:** "No. A partial sell changes quantity only; **Average Cost** stays the same."

> **Dev:** "Should we show realized profit after a sell?"
> **Domain expert:** "Not in v1. Show **Unrealized P&L** for active positions and portfolio value over time."

> **Dev:** "What is total value?"
> **Domain expert:** "**Portfolio Value** is cash plus each **Long Position** valued at its current price."

> **Dev:** "Should cash be stored as 10000.00?"
> **Domain expert:** "No. Persist a **Money Amount** as integer cents and format dollars at the API or UI boundary."

> **Dev:** "If the user removes AAPL from the Watchlist but still owns it, do prices stop?"
> **Domain expert:** "No. AAPL remains a **Priced Ticker** because active **Long Positions** need valuation."

> **Dev:** "If the user buys PYPL, should PYPL appear in the Watchlist?"
> **Domain expert:** "No. PYPL is priced for valuation, but the **Watchlist** changes only after explicit user intent."

> **Dev:** "Can the user remove AAPL from the Watchlist while still owning it?"
> **Domain expert:** "Yes. It leaves the **Watchlist**, but remains a **Priced Ticker** until the **Long Position** is gone."

> **Dev:** "Can the AI recommend a ticker that is not watched?"
> **Domain expert:** "Yes. But a **Trade Execution** needs a current price, and that does not add it to the **Watchlist**."

> **Dev:** "Can we execute a trade using yesterday's cached price?"
> **Domain expert:** "No. A **Stale Price** can be shown with warning, but **Trade Execution** requires a **Fresh Price**."

> **Dev:** "Can the user add BTC-USD or BRK.B?"
> **Domain expert:** "No. In v1, a **Ticker** is one to five uppercase letters only."

> **Dev:** "Can the simulator accept a made-up ticker like ABCDE?"
> **Domain expert:** "Yes, if it is syntactically valid. Real market data mode must require an actual provider price."

> **Dev:** "If the AI suggests watching PYPL, can it add PYPL silently?"
> **Domain expert:** "No. A **Watchlist Change** still needs user intent, but short confirmations like 'add it' are enough."

## Flagged Ambiguities

- "trading workstation" can imply real brokerage execution; resolved: use **Paper trading workstation** unless explicitly discussing visual style.
- "portfolio" is simulated by definition in this project; resolved: use **Portfolio** rather than **Simulated Portfolio** in domain language.
- "auto-execute" was ambiguous; resolved: **Trade Execution** requires explicit user request or confirmation.
- "watchlist recommendation" is distinct from a **Watchlist Change**; resolved: the change needs explicit but low-friction user intent.
- "trade" may refer to either a requested input or a recorded result; resolved: use **Trade Request** for user intent and **Trade Execution** for the portfolio mutation.
- "sell" never means open a short position; resolved: sells only reduce existing **Long Positions**.
- "average cost" is not recalculated on sells; resolved: buys update **Average Cost**, partial sells do not.
- "P&L" means **Unrealized P&L** for active positions unless explicitly qualified; realized P&L is out of scope for v1.
- "watched" and "priced" are different; resolved: **Watchlist** controls display, **Priced Ticker** controls market data coverage.
- "ticker" excludes crypto pairs, dotted share classes, and exchange suffixes in v1; resolved: validate as `^[A-Z]{1,5}$`.
