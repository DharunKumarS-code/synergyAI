
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from knowledge_base.rag_chatbot import answer_question, gemini_client

from knowledge_base.rag_chatbot import (
    answer_question,
    gemini_client,
)


# ============================================================
# 1. LOGGING CONFIGURATION
# ============================================================

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("synergyai")


# ============================================================
# 2. APPLICATION LIFECYCLE
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting SynergyAI backend...")

    yield

    logger.info("Shutting down SynergyAI backend...")

    try:
        gemini_client.close()
        logger.info("Gemini client closed successfully.")
    except Exception:
        logger.exception("Could not close the Gemini client.")


# ============================================================
# 3. CREATE FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="SynergyAI API",
    description=(
        "A Retrieval-Augmented Generation (RAG) chatbot "
        "for answering questions using indexed Synergy Marine "
        "Group website content."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# 4. CORS CONFIGURATION
# ============================================================

# Development configuration for the local React frontend.
# Restrict this list to trusted origins in production.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# ============================================================
# 5. REQUEST AND RESPONSE MODELS
# ============================================================

class ChatRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Question about Synergy Marine Group.",
    )


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list)


# ============================================================
# 6. ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "application": "SynergyAI",
        "message": "Welcome to the SynergyAI API!",
        "status": "running",
        "documentation": "/docs",
    }


# ============================================================
# 7. HEALTH CHECK ENDPOINT
# ============================================================

@app.get("/health")
def health_check():
    return {
        "application": "SynergyAI",
        "status": "healthy",
    }


# ============================================================
# 8. NORMALIZE SOURCE DATA
# ============================================================

def normalize_sources(raw_sources: Any) -> list[str]:
    """
    Ensure sources is returned as a list of HTTP/HTTPS URLs.

    Supports:
      - A list of URLs
      - A single URL string
      - None or unexpected data types
    """

    if raw_sources is None:
        return []

    if isinstance(raw_sources, str):
        raw_sources = [raw_sources]

    if not isinstance(raw_sources, (list, tuple, set)):
        logger.warning(
            "Unexpected sources type: %s",
            type(raw_sources).__name__,
        )
        return []

    normalized = []

    for source in raw_sources:
        if not isinstance(source, str):
            continue

        source = source.strip()

        if source.startswith(("https://", "http://")):
            if source not in normalized:
                normalized.append(source)

    return normalized


# ============================================================
# 9. CHAT ENDPOINT
# ============================================================

@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty.",
        )

    logger.info("Received a chat request.")

    try:
        # Run the RAG pipeline.
        result = answer_question(question)

        # Validate the result returned by rag_chatbot.py.
        if not isinstance(result, dict):
            logger.error(
                "answer_question() returned %s instead of a dictionary.",
                type(result).__name__,
            )

            raise HTTPException(
                status_code=500,
                detail="The chatbot returned an unexpected response.",
            )

        # Extract the generated answer.
        answer = result.get("answer")

        if not isinstance(answer, str) or not answer.strip():
            answer = (
                "I couldn't generate an answer from the "
                "available website content. Please try again."
            )

        # Normalize sources to prevent Pydantic validation errors.
        sources = normalize_sources(result.get("sources", []))

        # Return the expected JSON structure.
        response = ChatResponse(
            answer=answer.strip(),
            sources=sources,
        )

        logger.info("Chat request completed successfully.")

        return response

    except HTTPException:
        raise

    except Exception:
        logger.exception("Unexpected error while answering the question.")

        raise HTTPException(
            status_code=500,
            detail=(
                "An unexpected error occurred while processing "
                "your question. Please try again."
            ),
        )


# ============================================================
# 10. RUN THE APPLICATION DIRECTLY
# ============================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "api:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
