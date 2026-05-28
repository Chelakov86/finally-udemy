import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.chat.agent import handle_chat_message
from app.chat.intent import PendingActionsCache
from app.db.connection import get_db_connection

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Setup logging
logger = logging.getLogger("finally.routers.chat")

# Instantiate the thread-safe pending actions cache
pending_actions_cache = PendingActionsCache()


class ChatMessageRequest(BaseModel):
    message: str


@router.post("")
async def send_chat_message(request: Request, body: ChatMessageRequest):
    """
    POST to send a message to the AI assistant.
    Calls the LLM engineer's intent gating & agent pipelines, which handles
    LiteLLM gemini queries, mock mode, intent classification, and trade executions.
    """
    price_cache = request.app.state.price_cache
    market_data_source = request.app.state.market_data_source

    user_msg = body.message.strip()
    if not user_msg:
        raise HTTPException(status_code=400, detail="Empty chat message.")

    try:
        # Delegate directly to the LLM agent pipeline
        result = await handle_chat_message(
            user_message=user_msg,
            price_cache=price_cache,
            market_data_source=market_data_source,
            pending_actions_cache=pending_actions_cache,
            user_id="default",
        )
        return result
    except Exception as e:
        logger.exception("Error handling chat message in pipeline")
        raise HTTPException(status_code=500, detail=f"Chat execution failed: {str(e)}")


@router.delete("")
async def clear_chat_history(request: Request):
    """
    DELETE to clear the chat message history for the default user.
    """
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM chat_messages WHERE user_id = 'default';")
        # Also clear any pending cached actions
        pending_actions_cache.clear("default")
        return {"message": "Chat history successfully cleared."}
    except Exception as e:
        logger.exception("Error clearing chat history")
        raise HTTPException(status_code=500, detail=f"Failed to clear chat history: {str(e)}")
