"""
Weather via OpenWeatherMap API. Use for temperature/weather queries instead of Tavily.
"""
import re
import urllib.parse
import urllib.request
import json
import logging

import config

logger = logging.getLogger(__name__)

# Patterns to extract city from user message (e.g. "weather in Mumbai", "temperature in Paris")
_CITY_PATTERNS = [
    re.compile(r"(?:weather|temp(?:erature)?|forecast)\s+in\s+([A-Za-z\s\-']+)", re.IGNORECASE),
    re.compile(r"in\s+([A-Za-z\s\-']+?)\s+(?:weather|temp|forecast)", re.IGNORECASE),
    re.compile(r"(?:what(?:'s| is)\s+)?(?:the\s+)?(?:weather|temp(?:erature)?)\s+(?:in|at)\s+([A-Za-z\s\-']+)", re.IGNORECASE),
    re.compile(r"([A-Za-z\s\-']+)\s+weather", re.IGNORECASE),
]

# Words that indicate user is asking for weather/temperature (so we use OpenWeatherMap, not Tavily)
WEATHER_INTENT_PATTERN = re.compile(
    r"\b(weather|temperature|temp|forecast|how\s+(?:hot|cold)|degrees?\s+(?:celsius|fahrenheit|outside)|humidity|feels\s+like)\b",
    re.IGNORECASE,
)


def extract_city_from_message(message: str) -> str | None:
    """Try to extract a city name from the user message. Returns None if not found."""
    for pat in _CITY_PATTERNS:
        m = pat.search(message)
        if m:
            city = m.group(1).strip()
            if city and len(city) > 1:
                return city
    return None


def is_weather_or_temperature_query(message: str) -> bool:
    """True if the message is likely asking for weather or temperature (use OpenWeatherMap, not Tavily)."""
    return bool(WEATHER_INTENT_PATTERN.search(message))


def get_weather_openweathermap(city: str | None = None) -> str:
    """
    Fetch current weather from OpenWeatherMap API.
    Uses OPENWEATHERMAP_API_KEY and OPENWEATHERMAP_DEFAULT_CITY from config.
    Returns a short text summary for the LLM, or empty string on error/missing key.
    """
    if not config.OPENWEATHERMAP_API_KEY:
        return ""
    location = (city or "").strip() or config.OPENWEATHERMAP_DEFAULT_CITY
    if not location:
        return ""
    try:
        params = {
            "q": location,
            "appid": config.OPENWEATHERMAP_API_KEY,
            "units": "metric",
        }
        url = "https://api.openweathermap.org/data/2.5/weather?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        # Build a concise summary
        name = data.get("name") or location
        main = data.get("main") or {}
        temp = main.get("temp")
        feels = main.get("feels_like")
        humidity = main.get("humidity")
        weather_list = data.get("weather") or []
        desc = weather_list[0].get("description", "") if weather_list else ""
        wind = data.get("wind") or {}
        wind_speed = wind.get("speed")
        parts = [f"Location: {name}"]
        if temp is not None:
            parts.append(f"Temperature: {temp}°C")
        if feels is not None:
            parts.append(f"Feels like: {feels}°C")
        if desc:
            parts.append(f"Conditions: {desc}")
        if humidity is not None:
            parts.append(f"Humidity: {humidity}%")
        if wind_speed is not None:
            parts.append(f"Wind speed: {wind_speed} m/s")
        return "\n".join(parts)
    except Exception as e:
        logger.warning("OpenWeatherMap request failed: %s", e)
        return ""
