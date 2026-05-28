from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/history")
async def get_market_history(request: Request):
    """
    Returns the recent in-memory price history for all tracked tickers.
    Contains at most 30 ticks (default cache size) per ticker.
    """
    price_cache = request.app.state.price_cache
    history = price_cache.get_all_history()

    return {
        ticker: [update.to_dict() for update in updates]
        for ticker, updates in history.items()
    }
