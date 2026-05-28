import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from app.chat.intent import PendingActionsCache, PendingActionSet, classify_intent
from app.chat.models import ChatAgentResponse, Recommendation, TradeRequest, WatchlistChangeRequest
from app.db.connection import get_db_connection
from app.routers.portfolio import TradeRequest as RouterTradeRequest
from app.routers.portfolio import execute_trade_logic

# Setup logger
logger = logging.getLogger("finally.chat.agent")


def get_portfolio_context_data(price_cache, user_id: str = "default") -> dict:
    """
    Fetches the current portfolio data (cash, positions, watchlist, total value)
    to be injected into the LLM system prompt.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # 1. Cash Balance
        cursor.execute("SELECT cash_balance_cents FROM users_profile WHERE id = ?;", (user_id,))
        profile = cursor.fetchone()
        cash_balance_cents = profile["cash_balance_cents"] if profile else 1000000
        cash_balance = float(cash_balance_cents) / 100.0

        # 2. Positions
        cursor.execute(
            "SELECT ticker, quantity, avg_cost FROM positions WHERE user_id = ? ORDER BY ticker ASC;",
            (user_id,),
        )
        positions = []
        total_positions_value_cents = 0
        for row in cursor.fetchall():
            ticker = row["ticker"]
            quantity = float(row["quantity"])
            avg_cost = float(row["avg_cost"])

            price_update = price_cache.get(ticker)
            if price_update:
                current_price = price_update.price
                total_value = quantity * current_price
                unrealized_p_l = total_value - (quantity * avg_cost)
                unrealized_p_l_percent = (
                    ((current_price - avg_cost) / avg_cost * 100) if avg_cost > 0 else 0.0
                )
            else:
                current_price = None
                total_value = 0.0
                unrealized_p_l = 0.0
                unrealized_p_l_percent = 0.0

            positions.append(
                {
                    "ticker": ticker,
                    "quantity": quantity,
                    "avg_cost": avg_cost,
                    "current_price": current_price,
                    "total_value": total_value,
                    "unrealized_p_l": unrealized_p_l,
                    "unrealized_p_l_percent": unrealized_p_l_percent,
                }
            )
            total_positions_value_cents += int(round(total_value * 100))

        total_portfolio_value_cents = cash_balance_cents + total_positions_value_cents
        total_portfolio_value = float(total_portfolio_value_cents) / 100.0

        # 3. Watchlist
        cursor.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY ticker ASC;", (user_id,)
        )
        watchlist = []
        for row in cursor.fetchall():
            ticker = row["ticker"]
            price_update = price_cache.get(ticker)
            watchlist.append(
                {"ticker": ticker, "price": price_update.price if price_update else None}
            )

    return {
        "cash_balance": cash_balance,
        "positions": positions,
        "watchlist": watchlist,
        "total_portfolio_value": total_portfolio_value,
    }


def format_portfolio_text(context_data: dict) -> tuple[str, str]:
    """Formats positions and watchlist data as a readable text block for the system prompt."""
    pos_lines = []
    for pos in context_data["positions"]:
        cur_price_str = (
            f"${pos['current_price']:.2f}" if pos["current_price"] is not None else "N/A"
        )
        pnl_sign = "+" if pos["unrealized_p_l"] >= 0 else ""
        pnl_str = f"{pnl_sign}${pos['unrealized_p_l']:.2f} ({pnl_sign}{pos['unrealized_p_l_percent']:.2f}%)"
        pos_lines.append(
            f"- {pos['ticker']}: {pos['quantity']:.4f} shares @ Avg Cost ${pos['avg_cost']:.2f} "
            f"(Current: {cur_price_str}, P&L: {pnl_str})"
        )
    positions_text = "\n".join(pos_lines) if pos_lines else "- No active long positions."

    wl_lines = []
    for wl in context_data["watchlist"]:
        price_str = f"${wl['price']:.2f}" if wl["price"] is not None else "N/A"
        wl_lines.append(f"- {wl['ticker']}: {price_str}")
    watchlist_text = "\n".join(wl_lines) if wl_lines else "- Watchlist is empty."

    return positions_text, watchlist_text


def load_chat_history(conn, limit: int = 20) -> list[dict]:
    """Loads the bounded chat history for the default user."""
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT role, content
        FROM chat_messages
        WHERE user_id = 'default'
        ORDER BY created_at DESC
        LIMIT ?;
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    # Reverse to restore chronological order (oldest first)
    rows.reverse()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_chat_message(role: str, content: str, actions: Optional[dict] = None) -> str:
    """Saves a single chat message and associated executed actions audit JSON."""
    message_id = str(uuid.uuid4())
    now_str = datetime.now(timezone.utc).isoformat()
    actions_json = json.dumps(actions) if actions is not None else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO chat_messages (id, user_id, role, content, actions, created_at)
            VALUES (?, 'default', ?, ?, ?, ?);
            """,
            (message_id, role, content, actions_json, now_str),
        )
    return message_id


def extract_json_content(raw_content: str) -> str:
    """Extracts a raw JSON string from a text block, ignoring surrounding markdown tags."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_content, re.DOTALL)
    if match:
        return match.group(1)
    start = raw_content.find("{")
    end = raw_content.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw_content[start : end + 1]
    return raw_content


async def execute_trade_from_ai(trade: TradeRequest, price_cache, market_data_source) -> dict:
    """Runs a single AI-generated trade through the authoritative backend execution path."""
    router_req = RouterTradeRequest(
        ticker=trade.ticker,
        side=trade.side,
        quantity=trade.quantity,
        notional_amount=trade.notional_amount,
        source="ai",
    )
    try:
        res = await execute_trade_logic(router_req, price_cache, market_data_source)
        return {
            "ticker": trade.ticker,
            "side": trade.side,
            "requested": {"quantity": trade.quantity, "notional_amount": trade.notional_amount},
            "status": "success",
            "details": res["trade"],
        }
    except Exception as e:
        logger.error(f"AI trade execution failed for {trade}: {e}")
        return {
            "ticker": trade.ticker,
            "side": trade.side,
            "requested": {"quantity": trade.quantity, "notional_amount": trade.notional_amount},
            "status": "failed",
            "error": str(getattr(e, "detail", str(e))),
        }


async def execute_watchlist_change_from_ai(
    change: WatchlistChangeRequest, price_cache, market_data_source
) -> dict:
    """Applies an AI-generated watchlist change to the database and market data tracking."""
    ticker = change.ticker.upper().strip()
    action = change.action

    try:
        is_held = False
        with get_db_connection() as conn:
            cursor = conn.cursor()

            if action == "add":
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
            else:  # remove
                cursor.execute(
                    "SELECT quantity FROM positions WHERE user_id = 'default' AND ticker = ?;",
                    (ticker,),
                )
                pos_row = cursor.fetchone()
                is_held = pos_row is not None and pos_row["quantity"] > 0

                cursor.execute(
                    "DELETE FROM watchlist WHERE user_id = 'default' AND ticker = ?;",
                    (ticker,),
                )

        if action == "add":
            await market_data_source.add_ticker(ticker)
        elif not is_held:
            await market_data_source.remove_ticker(ticker)

        return {"ticker": ticker, "action": action, "status": "success"}
    except Exception as e:
        logger.error(f"AI watchlist change failed for {change}: {e}")
        return {"ticker": ticker, "action": action, "status": "failed", "error": str(e)}


async def handle_chat_message(
    user_message: str,
    price_cache,
    market_data_source,
    pending_actions_cache: PendingActionsCache,
    user_id: str = "default",
) -> dict:
    """
    Primary chat entry point:
    1. Persists message.
    2. Gates/classifies intent.
    3. Handles confirmations or requests new analysis/execution from LiteLLM / mock.
    4. Applies intent validation & performs authoritative mutations or caches pending options.
    5. Saves conversational response and returns complete JSON block.
    """
    # 1. Save user message to database
    save_chat_message("user", user_message)

    # 2. Determine intent
    intent = classify_intent(user_message)
    logger.info(f"Classified message intent: {intent}")

    executed_actions = {"trades": [], "watchlist_changes": []}

    # 3. Handle confirmation intent
    if intent == "confirmation":
        # Try to retrieve from cache
        pending_set = pending_actions_cache.get(user_id)
        if pending_set:
            # Let's check if the message specifies a particular ticker
            message_lower = user_message.lower()
            matching_trades = []
            matching_changes = []

            has_specific_ticker = False
            for t in pending_set.trades:
                if t.ticker.lower() in message_lower:
                    matching_trades.append(t)
                    has_specific_ticker = True
            for w in pending_set.watchlist_changes:
                if w.ticker.lower() in message_lower:
                    matching_changes.append(w)
                    has_specific_ticker = True

            if has_specific_ticker:
                trades_to_execute = matching_trades
                changes_to_execute = matching_changes
            else:
                # Generic confirmation: check if multiple independent items exist
                total_items = len(pending_set.trades) + len(pending_set.watchlist_changes)
                if total_items > 1:
                    # Ambiguous generic confirmation: ask for clarification
                    response_msg = (
                        "I have multiple pending recommendations. "
                        "Please specify which one you'd like to proceed with "
                        "(e.g., 'buy AAPL' or 'track MSFT')."
                    )
                    save_chat_message("assistant", response_msg, actions=None)
                    return {
                        "message": response_msg,
                        "recommendations": [],
                        "trades": [],
                        "watchlist_changes": [],
                        "actions": None,
                    }
                else:
                    trades_to_execute = pending_set.trades
                    changes_to_execute = pending_set.watchlist_changes

            # Execute them!
            for trade in trades_to_execute:
                res = await execute_trade_from_ai(trade, price_cache, market_data_source)
                executed_actions["trades"].append(res)
            for change in changes_to_execute:
                res = await execute_watchlist_change_from_ai(
                    change, price_cache, market_data_source
                )
                executed_actions["watchlist_changes"].append(res)

            # Clear the cache
            pending_actions_cache.clear(user_id)

            # Create a response summarizing the actions
            summary_parts = []
            for t in executed_actions["trades"]:
                status = "successfully bought" if t["side"] == "buy" else "successfully sold"
                if t["status"] == "success":
                    summary_parts.append(
                        f"Executed trade: {status} {t['details']['quantity']} shares of "
                        f"{t['ticker']} at ${float(t['details']['execution_price']):.2f}."
                    )
                else:
                    summary_parts.append(
                        f"Failed to execute trade for {t['ticker']}: {t['error']}."
                    )
            for w in executed_actions["watchlist_changes"]:
                action_word = "Added" if w["action"] == "add" else "Removed"
                if w["status"] == "success":
                    summary_parts.append(f"{action_word} {w['ticker']} to/from watchlist.")
                else:
                    summary_parts.append(
                        f"Failed watchlist change for {w['ticker']}: {w['error']}."
                    )

            response_msg = " ".join(summary_parts) if summary_parts else "No action executed."
            save_chat_message("assistant", response_msg, actions=executed_actions)
            return {
                "message": response_msg,
                "recommendations": [],
                "trades": [],
                "watchlist_changes": [],
                "actions": executed_actions,
            }
        else:
            # No pending actions or expired
            response_msg = "No pending trade or watchlist recommendations were found to confirm, or they have expired."
            save_chat_message("assistant", response_msg, actions=None)
            return {
                "message": response_msg,
                "recommendations": [],
                "trades": [],
                "watchlist_changes": [],
                "actions": None,
            }

    # 4. For analysis or explicit execution, we call the LLM / Mock
    portfolio_data = get_portfolio_context_data(price_cache, user_id)
    positions_text, watchlist_text = format_portfolio_text(portfolio_data)

    with get_db_connection() as conn:
        history = load_chat_history(conn, limit=20)

    is_mock = os.environ.get("LLM_MOCK", "false").lower() == "true"

    if is_mock:
        from app.chat.mock import generate_mock_response

        ai_response = generate_mock_response(user_message)
    else:
        # Construct messages list for LiteLLM
        system_prompt = f"""You are FinAlly, a professional, data-driven AI trading assistant for a paper trading workstation.
Your tone is concise, analytical, and objective (like a Bloomberg terminal assistant).

Current Portfolio State:
- Cash Balance: ${portfolio_data["cash_balance"]:.2f}
- Total Portfolio Value: ${portfolio_data["total_portfolio_value"]:.2f}
- Active Long Positions:
{positions_text}
- Watchlist Symbols with Live Prices:
{watchlist_text}

Rules:
1. Recommend trades with clear rationales.
2. Recommend watchlist changes proactively.
3. You can recommend tickers outside the current watchlist when relevant.
4. DO NOT make actual trades or modify the watchlist directly; return them as "trades" and "watchlist_changes" in your JSON response. The backend's intent gating will decide when to execute them based on user explicit requests.
5. In each trade proposal, you MUST specify exactly one of "quantity" (number of shares) or "notional_amount" (dollar amount), never both. Sells are long-only; you cannot short sell, meaning you can only sell what the user holds.
6. Tickers must be 1 to 5 uppercase letters.
7. Be extremely concise in your conversational "message" field. Avoid fluff. Provide data-driven reasoning.

You MUST respond with a single valid JSON object matching the schema below. Do not wrap it in anything else, do not add markdown block markers like ```json.

Response JSON Schema:
{{
  "message": "Your concise conversational response analyzing positions, P&L, or addressing the user's query.",
  "recommendations": [
    {{
      "type": "trade" or "watchlist",
      "ticker": "uppercase ticker symbol",
      "side": "buy" or "sell" or null,
      "rationale": "reason for the recommendation"
    }}
  ],
  "trades": [
    {{
      "ticker": "uppercase ticker symbol",
      "side": "buy" or "sell",
      "quantity": 10 or null,
      "notional_amount": 500 or null
    }}
  ],
  "watchlist_changes": [
    {{
      "ticker": "uppercase ticker symbol",
      "action": "add" or "remove"
    }}
  ]
}}
"""
        messages = [{"role": "system", "content": system_prompt}]
        for hist in history:
            messages.append({"role": hist["role"], "content": hist["content"]})

        messages.append({"role": "user", "content": user_message})

        # Call LiteLLM
        model = os.environ.get("LLM_MODEL", "gemini/gemma-4-31b-it")
        if "/" not in model:
            model = f"gemini/{model}"
        gemini_api_key = os.environ.get("GEMINI_API_KEY")

        try:
            import litellm

            completion_args = {
                "model": model,
                "messages": messages,
                "timeout": 30,
                "num_retries": 3,
            }
            if gemini_api_key:
                completion_args["api_key"] = gemini_api_key

            response = litellm.completion(**completion_args)
            raw_content = response.choices[0].message.content

            cleaned_json = extract_json_content(raw_content)
            ai_response = ChatAgentResponse.model_validate_json(cleaned_json)
        except Exception as e:
            logger.error(f"LiteLLM completion or validation failed: {e}")
            error_msg = f"Sorry, I encountered an error while processing your request: {str(e)}"
            save_chat_message("assistant", error_msg, actions=None)
            return {
                "message": error_msg,
                "recommendations": [],
                "trades": [],
                "watchlist_changes": [],
                "actions": None,
            }

    # Apply backend intent gating
    if intent == "execution":
        # Execute trades and watchlist changes directly
        for trade in ai_response.trades:
            res = await execute_trade_from_ai(trade, price_cache, market_data_source)
            executed_actions["trades"].append(res)
        for change in ai_response.watchlist_changes:
            res = await execute_watchlist_change_from_ai(change, price_cache, market_data_source)
            executed_actions["watchlist_changes"].append(res)

        # Clear cache since we performed execution
        pending_actions_cache.clear(user_id)

        # Update conversational message with details
        summary_parts = []
        for t in executed_actions["trades"]:
            status = "bought" if t["side"] == "buy" else "sold"
            if t["status"] == "success":
                summary_parts.append(
                    f"Successfully {status} {t['details']['quantity']} shares of "
                    f"{t['ticker']} at ${float(t['details']['execution_price']):.2f}."
                )
            else:
                summary_parts.append(f"Failed to execute trade for {t['ticker']}: {t['error']}.")
        for w in executed_actions["watchlist_changes"]:
            action_word = "Added" if w["action"] == "add" else "Removed"
            if w["status"] == "success":
                summary_parts.append(f"{action_word} {w['ticker']} to/from watchlist.")
            else:
                summary_parts.append(f"Failed watchlist change for {w['ticker']}: {w['error']}.")

        final_message = ai_response.message
        if summary_parts:
            final_message += " " + " ".join(summary_parts)

        save_chat_message("assistant", final_message, actions=executed_actions)
        return {
            "message": final_message,
            "recommendations": [r.model_dump() for r in ai_response.recommendations],
            "trades": [],
            "watchlist_changes": [],
            "actions": executed_actions,
        }

    else:  # intent == "analysis"
        # Analysis mode: do NOT execute actions.
        # Cache them in PendingActionsCache and convert them to recommendations!
        all_recommendations = list(ai_response.recommendations)

        for trade in ai_response.trades:
            side_str = "buy" if trade.side == "buy" else "sell"
            qty_part = (
                f"{trade.quantity} shares"
                if trade.quantity is not None
                else f"${trade.notional_amount} notional"
            )
            rationale_str = f"Suggested trade to {side_str} {qty_part}."
            all_recommendations.append(
                Recommendation(
                    type="trade", ticker=trade.ticker, side=trade.side, rationale=rationale_str
                )
            )

        for change in ai_response.watchlist_changes:
            action_str = "add to watchlist" if change.action == "add" else "remove from watchlist"
            all_recommendations.append(
                Recommendation(
                    type="watchlist",
                    ticker=change.ticker,
                    side=None,
                    rationale=f"Suggested {action_str}.",
                )
            )

        # Store in PendingActionsCache
        if ai_response.trades or ai_response.watchlist_changes:
            temp_msg_id = str(uuid.uuid4())
            pending_set = PendingActionSet(
                user_id=user_id,
                trades=ai_response.trades,
                watchlist_changes=ai_response.watchlist_changes,
                timestamp=datetime.now(timezone.utc),
                message_id=temp_msg_id,
            )
            pending_actions_cache.set(user_id, pending_set)
        else:
            # Unrelated message - clear prior pending actions cache
            pending_actions_cache.clear(user_id)

        save_chat_message("assistant", ai_response.message, actions=None)
        return {
            "message": ai_response.message,
            "recommendations": [r.model_dump() for r in all_recommendations],
            "trades": [t.model_dump() for t in ai_response.trades],
            "watchlist_changes": [w.model_dump() for w in ai_response.watchlist_changes],
            "actions": None,
        }

