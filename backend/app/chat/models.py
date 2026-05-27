import re
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def validate_ticker_symbol(v: str) -> str:
    v = v.strip().upper()
    if not re.match(r"^[A-Z]{1,5}$", v):
        raise ValueError(f"Invalid ticker format: '{v}'. Must be 1 to 5 uppercase letters.")
    return v


class Recommendation(BaseModel):
    type: Literal["trade", "watchlist"]
    ticker: str
    side: Optional[Literal["buy", "sell"]] = None
    rationale: str

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return validate_ticker_symbol(v)


class TradeRequest(BaseModel):
    ticker: str
    side: Literal["buy", "sell"]
    quantity: Optional[float] = None
    notional_amount: Optional[float] = None

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return validate_ticker_symbol(v)

    @model_validator(mode="after")
    def validate_quantity_or_notional(self) -> "TradeRequest":
        qty = self.quantity
        notional = self.notional_amount
        if qty is None and notional is None:
            raise ValueError("Exactly one of 'quantity' or 'notional_amount' must be provided.")
        if qty is not None and notional is not None:
            raise ValueError("Only one of 'quantity' or 'notional_amount' can be provided.")
        if qty is not None and qty <= 0:
            raise ValueError("Quantity must be greater than zero.")
        if notional is not None and notional <= 0:
            raise ValueError("Notional amount must be greater than zero.")
        return self


class WatchlistChangeRequest(BaseModel):
    ticker: str
    action: Literal["add", "remove"]

    @field_validator("ticker")
    @classmethod
    def validate_ticker(cls, v: str) -> str:
        return validate_ticker_symbol(v)


class ChatAgentResponse(BaseModel):
    message: str
    recommendations: List[Recommendation] = Field(default_factory=list)
    trades: List[TradeRequest] = Field(default_factory=list)
    watchlist_changes: List[WatchlistChangeRequest] = Field(default_factory=list)
