"""
Core LLM chat service using Groq (LangChain).
Supports multiple API keys rotation for rate limits.
"""
from typing import List, Optional
import itertools

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

import config
from app.utils.time_info import get_current_datetime_str
from app.utils.weather import (
    is_weather_or_temperature_query,
    extract_city_from_message,
    get_weather_openweathermap,
)
from app.utils import ops_state


class GroqService:
    """Groq LLM with optional RAG (vector store) and multi-key rotation."""

    _key_cycle = None

    @classmethod
    def _next_api_key(cls) -> Optional[str]:
        if not config.GROQ_API_KEYS:
            return None
        if cls._key_cycle is None:
            cls._key_cycle = itertools.cycle(config.GROQ_API_KEYS)
        return next(cls._key_cycle)

    @classmethod
    def get_llm(cls, api_key: Optional[str] = None) -> ChatGroq:
        """Get ChatGroq instance; uses next key in rotation if api_key not given."""
        key = api_key or cls._next_api_key()
        if not key:
            raise ValueError("No GROQ_API_KEYS or GROQ_API_KEY set in .env")
        ops_state.set_groq_key_used(key)
        return ChatGroq(
            model=config.GROQ_MODEL,
            api_key=key,
            temperature=0.7,
            max_tokens=4096,
        )

    @classmethod
    def get_system_prompt(cls, context_from_rag: str = "", use_rag: bool = True) -> str:
        """Build system prompt with RAG context and user/assistant names."""
        time_info = get_current_datetime_str()
        base = f"""You are {config.ASSISTANT_NAME}, a helpful AI assistant. The user's name is {config.USER_NAME}.
Current date and time: {time_info}.
Be concise, accurate, and friendly.

CRITICAL - For personal facts (user's family, pets, preferences, past events): use ONLY the "Relevant stored knowledge" and the conversation below. Do NOT invent or use names/facts from your training data. If something is not in the provided context, say you don't have that information—never guess names (e.g. pet names, people)."""
        if use_rag and context_from_rag:
            base += f"\n\nRelevant stored knowledge (first = most recent; prefer these when they conflict):\n{context_from_rag}"
        return base

    @classmethod
    def chat_general(
        cls,
        message: str,
        history: List[dict],
        retriever=None,
        stored_context: Optional[str] = None,
        api_key: Optional[str] = None,
    ) -> str:
        """
        General chat: optional RAG from vector store (prefer stored_context with newest-first) + conversation history.
        For weather/temperature queries we add OpenWeatherMap data (do not use Tavily).
        history: list of {"role": "user"|"assistant", "content": "..."}
        When stored_context is provided, it is used (newest conversation memories first); else retriever is used.
        """
        context = stored_context or ""
        if not context and retriever:
            try:
                docs = retriever.invoke(message)
                if docs:
                    context = "\n".join(d.page_content for d in docs)
            except Exception:
                pass

        # For weather/temperature: add OpenWeatherMap data to context
        if is_weather_or_temperature_query(message):
            city = extract_city_from_message(message)
            weather_context = get_weather_openweathermap(city)
            if weather_context:
                context = f"Weather data from OpenWeatherMap (use this for temperature and weather):\n{weather_context}\n\n" + (context or "")

        system_prompt = cls.get_system_prompt(context_from_rag=context, use_rag=bool(context))
        llm = cls.get_llm(api_key=api_key)
        messages = [SystemMessage(content=system_prompt)]
        for h in history:
            if h.get("role") == "user":
                messages.append(HumanMessage(content=h.get("content", "")))
            elif h.get("role") == "assistant":
                messages.append(AIMessage(content=h.get("content", "")))
        messages.append(HumanMessage(content=message))
        response = llm.invoke(messages)
        return response.content if hasattr(response, "content") else str(response)
