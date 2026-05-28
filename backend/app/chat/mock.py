from app.chat.models import ChatAgentResponse, Recommendation, TradeRequest, WatchlistChangeRequest


def generate_mock_response(user_message: str) -> ChatAgentResponse:
    """
    Generates a deterministic ChatAgentResponse based on the user's message.
    Used for CI/CD tests and running without an API key when LLM_MOCK=true.
    """
    msg_lower = user_message.lower().strip()

    # 1. "buy AAPL" or "buy 10 shares of AAPL" or "buy $500 of AAPL"
    if "buy" in msg_lower and "aapl" in msg_lower:
        # Check if they specified a dollar amount
        if "$500" in msg_lower or "500 dollars" in msg_lower or "500 notional" in msg_lower:
            return ChatAgentResponse(
                message="I've prepared a trade request to buy $500.00 worth of AAPL.",
                recommendations=[],
                trades=[TradeRequest(ticker="AAPL", side="buy", notional_amount=500.0)],
                watchlist_changes=[],
            )
        else:
            return ChatAgentResponse(
                message="I've prepared a trade request to buy 10 shares of AAPL.",
                recommendations=[],
                trades=[TradeRequest(ticker="AAPL", side="buy", quantity=10.0)],
                watchlist_changes=[],
            )

    # 2. "sell AAPL" or "sell 10 shares of AAPL"
    elif "sell" in msg_lower and "aapl" in msg_lower:
        return ChatAgentResponse(
            message="I've prepared a trade request to sell 10 shares of AAPL.",
            recommendations=[],
            trades=[TradeRequest(ticker="AAPL", side="sell", quantity=10.0)],
            watchlist_changes=[],
        )

    # 3. "track MSFT" or "add MSFT to watchlist"
    elif ("add" in msg_lower and "msft" in msg_lower) or "track msft" in msg_lower:
        return ChatAgentResponse(
            message="I've prepared a request to add MSFT to your watchlist.",
            recommendations=[],
            trades=[],
            watchlist_changes=[WatchlistChangeRequest(ticker="MSFT", action="add")],
        )

    # 4. "untrack TSLA" or "remove TSLA from watchlist"
    elif ("remove" in msg_lower and "tsla" in msg_lower) or "untrack tsla" in msg_lower:
        return ChatAgentResponse(
            message="I've prepared a request to remove TSLA from your watchlist.",
            recommendations=[],
            trades=[],
            watchlist_changes=[WatchlistChangeRequest(ticker="TSLA", action="remove")],
        )

    # 5. "what do you think of AAPL?" (analysis suggestion)
    elif (
        "think of aapl" in msg_lower or "analyze aapl" in msg_lower or "recommendation" in msg_lower
    ):
        return ChatAgentResponse(
            message="AAPL looks solid with a strong balance sheet and high cash generation.",
            recommendations=[
                Recommendation(
                    type="trade",
                    ticker="AAPL",
                    side="buy",
                    rationale="AAPL is a high-quality stock with stable earnings.",
                )
            ],
            trades=[TradeRequest(ticker="AAPL", side="buy", quantity=10.0)],
            watchlist_changes=[],
        )

    # Default message analysis
    else:
        return ChatAgentResponse(
            message="Hello! I am FinAlly, your trading assistant. How can I help you today?",
            recommendations=[],
            trades=[],
            watchlist_changes=[],
        )
