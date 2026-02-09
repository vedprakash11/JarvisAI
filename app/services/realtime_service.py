"""
Realtime chat: web search (Tavily) + LLM for up-to-date answers.
For weather/temperature queries we use OpenWeatherMap API instead of Tavily.
"""
from typing import List, Optional

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

import re

import config
from app.utils.time_info import get_current_datetime_str, get_current_date_natural, get_today_phrase
from app.utils.weather import (
    is_weather_or_temperature_query,
    extract_city_from_message,
    get_weather_openweathermap,
)
from app.utils.recent_query import needs_recent_data
from app.services.groq_service import GroqService

# Words that suggest the user means "current date" for search and answers
_TODAY_PATTERN = re.compile(
    r"\b(today|this\s+morning|this\s+afternoon|this\s+evening|tonight)\b",
    re.IGNORECASE,
)


def search_tavily(query: str, max_results: int = 5) -> str:
    """Run Tavily web search and return concatenated snippets as context."""
    if not config.TAVILY_API_KEY:
        return ""
    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=config.TAVILY_API_KEY)
        response = client.search(query=query, max_results=max_results)
        results = getattr(response, "results", None) or (response.get("results", []) if isinstance(response, dict) else [])
        parts = []
        for r in results:
            if isinstance(r, dict):
                content = r.get("content") or r.get("snippet") or r.get("body", "")
            else:
                content = getattr(r, "content", None) or getattr(r, "snippet", "") or str(r)
            if content:
                parts.append(content)
        return "\n\n".join(parts) if parts else ""
    except Exception:
        return ""


class RealtimeService:
    """Realtime chatbot: Tavily search + vector store (RAG) + Groq LLM."""

    @classmethod
    def chat(
        cls,
        message: str,
        history: List[dict],
        api_key: Optional[str] = None,
        search_query: Optional[str] = None,
        stored_context: Optional[str] = None,
    ) -> tuple[str, str]:
        """
        Search web with Tavily or OpenWeatherMap when applicable, then answer with Groq.
        Returns (reply, tool_used) where tool_used is "openweather" | "tavily" | "llm answer"
        based on what was actually used for this request.
        history: list of {"role": "user"|"assistant", "content": "..."}
        stored_context: pre-built context from vector_store.get_memory_context_for_query.
        """
        query_to_search = search_query if search_query else message
        date_natural = get_current_date_natural()
        if _TODAY_PATTERN.search(message):
            query_to_search = f"{query_to_search} {date_natural}"

        weather_context = ""
        is_weather_query = is_weather_or_temperature_query(message)
        if is_weather_query:
            city = extract_city_from_message(message)
            weather_context = get_weather_openweathermap(city)

        # Use Tavily only when query needs recent data (news, today, latest, etc.); else LLM only to save cost
        if is_weather_query and weather_context:
            web_context = ""
        elif needs_recent_data(message):
            web_context = search_tavily(query_to_search)
        else:
            web_context = ""

        # Tool actually used: openweather if we got weather data, tavily if we got search results, else llm answer
        if weather_context:
            tool_used = "openweather"
        elif web_context:
            tool_used = "tavily"
        else:
            tool_used = "llm answer"

        stored_context = stored_context or ""
        time_info = get_current_datetime_str()
        today_phrase = get_today_phrase()
        system_prompt = f"""You are {config.ASSISTANT_NAME}, a helpful AI assistant. The user's name is {config.USER_NAME}.
Current date and time: {time_info}. When the user says "today" they mean {today_phrase}.

CRITICAL - Personal facts (user's name, family, pets, preferences, past events they shared):
- Use ONLY the "Stored knowledge" and the conversation history below. Do NOT use names, facts, or details from your training data.
- If the user asks about something personal (e.g. "what was my dog's name?") and it is not in Stored knowledge or this conversation, say you don't have that information or ask them to tell you. Never guess or invent names (e.g. do not say a pet name like "Itus" or any name unless the user or the stored knowledge explicitly states it).
- The first entries in Stored knowledge are the most recent things the user told you—prefer those when they conflict with later entries.

For current events or general web knowledge, use the "Search results" below.
When the user asks about "today" (e.g. today's match, today's news), interpret it as {today_phrase}. Phrase your answer naturally, e.g. "Today, Afghanistan scored..." or "In today's match (8 February 2025), ..." so it is clear you are referring to the current date. If search results do not clearly match today's date, say so and give the most relevant recent information with the date it refers to."""
        if stored_context:
            system_prompt += f"\n\nStored knowledge about the user (from past chats and profile):\n{stored_context}"
        if weather_context:
            system_prompt += f"\n\nWeather data from OpenWeatherMap (use this for temperature and weather—do not use search results for temp):\n{weather_context}"
        if web_context:
            system_prompt += f"\n\nSearch results (for up-to-date or general info):\n{web_context}"
        if not stored_context and not web_context and not weather_context:
            system_prompt += "\n\nNo search results or stored knowledge for this query. Answer from the conversation history and general knowledge."
        llm = GroqService.get_llm(api_key=api_key)
        messages = [SystemMessage(content=system_prompt)]
        for h in history:
            if h.get("role") == "user":
                messages.append(HumanMessage(content=h.get("content", "")))
            elif h.get("role") == "assistant":
                messages.append(AIMessage(content=h.get("content", "")))
        messages.append(HumanMessage(content=message))
        response = llm.invoke(messages)
        reply = response.content if hasattr(response, "content") else str(response)
        return reply, tool_used
