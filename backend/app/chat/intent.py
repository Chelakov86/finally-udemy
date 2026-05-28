import logging
import re
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.chat.models import TradeRequest, WatchlistChangeRequest

# Setup logger
logger = logging.getLogger("finally.chat.intent")


class PendingActionSet(BaseModel):
    user_id: str
    trades: List[TradeRequest] = Field(default_factory=list)
    watchlist_changes: List[WatchlistChangeRequest] = Field(default_factory=list)
    timestamp: datetime
    message_id: str


class PendingActionsCache:
    """
    Thread-safe in-memory cache for pending actionable recommendations.
    Expires entries after 10 minutes or clears them on unrelated user messages.
    """

    def __init__(self, expiration_minutes: int = 10):
        self._cache: Dict[str, PendingActionSet] = {}
        self._lock = threading.Lock()
        self._expiration_delta = timedelta(minutes=expiration_minutes)

        # Expiration loop thread
        self._stop_event = threading.Event()
        self._loop_thread = threading.Thread(target=self._expiration_loop, daemon=True)
        self._loop_thread.start()

    def _expiration_loop(self) -> None:
        """Periodic loop to clear expired cache entries."""
        while not self._stop_event.is_set():
            time.sleep(10)  # check every 10 seconds for test responsiveness
            self.clean_expired()

    def stop_loop(self) -> None:
        """Stop the background expiration loop."""
        self._stop_event.set()

    def set(self, user_id: str, action_set: PendingActionSet) -> None:
        """Store a pending action set for a user."""
        with self._lock:
            self._cache[user_id] = action_set
            logger.info(
                f"Cached pending actions for user '{user_id}' with message_id '{action_set.message_id}'"
            )

    def get(self, user_id: str) -> Optional[PendingActionSet]:
        """Retrieve a non-expired pending action set for a user."""
        with self._lock:
            action_set = self._cache.get(user_id)
            if not action_set:
                return None

            # Check expiration manually on retrieval for safety
            if datetime.now(timezone.utc) - action_set.timestamp > self._expiration_delta:
                self._cache.pop(user_id, None)
                logger.info(f"Expired pending action set for user '{user_id}' on retrieval.")
                return None
            return action_set

    def clear(self, user_id: str) -> None:
        """Clear a pending action set for a user."""
        with self._lock:
            self._cache.pop(user_id, None)
            logger.info(f"Cleared pending actions cache for user '{user_id}'")

    def clean_expired(self) -> None:
        """Scan cache and remove expired pending actions."""
        with self._lock:
            now = datetime.now(timezone.utc)
            to_remove = []
            for uid, action_set in list(self._cache.items()):
                if now - action_set.timestamp > self._expiration_delta:
                    to_remove.append(uid)

            for uid in to_remove:
                self._cache.pop(uid, None)
                logger.info(f"Background thread expired pending action set for user '{uid}'.")


def is_confirmation(message: str) -> bool:
    """
    Heuristic check to determine if a message is an unambiguous confirmation.
    E.g. 'yes', 'do it', 'go ahead', 'confirm', 'make the trade'.
    """
    cleaned = re.sub(r"[^\w\s]", "", message.lower().strip())

    # Standard short confirmation words
    confirmation_keywords = {
        "yes",
        "do it",
        "go ahead",
        "sure",
        "ok",
        "confirm",
        "proceed",
        "execute",
        "agree",
        "buy them",
        "sell them",
        "make the trade",
        "do that",
        "that sounds good",
        "please do",
        "yup",
        "yeah",
        "ok buy",
        "ok sell",
        "ok add",
        "go",
        "approved",
        "approve",
    }

    if cleaned in confirmation_keywords:
        return True

    # Check if starts with a confirmation keyword followed by minimal confirmation
    words = cleaned.split()
    if words and words[0] in {"yes", "sure", "ok", "y", "confirm", "approve"}:
        # Ensure it doesn't contain negation or question (e.g. "yes but actually no" or "ok but should i?")
        if not any(neg in cleaned for neg in ["but", "not", "no", "dont", "should i", "should we"]):
            return True

    return False


def classify_intent(message: str) -> str:
    """
    Determine if the user's message is:
    - "confirmation": unambiguous confirmation of a pending recommendation.
    - "execution": explicit request to trade or mutate watchlist.
    - "analysis": non-mutating query or general analysis.
    """
    message_lower = message.lower().strip()

    # 1. Confirmation check
    if is_confirmation(message_lower):
        return "confirmation"

    # 2. Execution check
    execution_keywords = {
        "buy",
        "sell",
        "trade",
        "add",
        "remove",
        "track",
        "untrack",
        "delete",
        "purchase",
        "liquidate",
        "dispose",
        "clear history",
        "sell all",
    }

    # Check if a question/speculative context is present, which overrides execution
    is_analysis_question = any(
        q in message_lower
        for q in [
            "should i",
            "would you",
            "recommend",
            "opinion",
            "analysis",
            "what do you think",
            "is it a good time",
            "why did",
            "what is",
            "how is",
            "tell me about",
            "view",
            "show me",
            "explain",
            "do you think",
        ]
    )

    words = re.findall(r"\b\w+\b", message_lower)
    has_execution_word = any(w in execution_keywords for w in words)

    if has_execution_word and not is_analysis_question:
        return "execution"

    return "analysis"
