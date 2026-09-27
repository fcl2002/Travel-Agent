from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode
from datetime import date, timedelta
import httpx

@tool
def get_weather(city: str, date_string: str) -> str:
    """
    Get the weather forecast for a city on a specific future date.
    
    Args: 
        city: City name, for example "Amsterdam".
        date_string: Future date in YYYY-MM-DD format.

        Note: If the user's date is ambiguous or does not
        include enough information to determine the year,
        ask the user for clarification instead of guessing.
    """

    # Open-Meteo constraint
    requested_date = date.fromisoformat(date_string)
    max_forecast_date = date.today() + timedelta(days=16)

    if requested_date < date.today():
        return "The requested date is in the past. Please provide a future date."
    
    if requested_date > max_forecast_date:
        return "We cannot forecast weather more than 16 days in advance."

    geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"

    geocoding_response = httpx.get(
        geocoding_url,
        params={
            "name": city,
            "count": 1
        }
    )

    geocoding_response.raise_for_status()
    geocoding_data = geocoding_response.json()

    if not geocoding_data.get("results"):
        return f"Could not find the city '{city}'."

    results = geocoding_data["results"][0]
    latitude = results["latitude"]
    longitude = results["longitude"]

    weather_url = "https://api.open-meteo.com/v1/forecast"

    weather_response = httpx.get(
        weather_url,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "daily": [
                "temperature_2m_max",
                "temperature_2m_min",
                "precipitation_probability_max",
                "weather_code"
            ],
            "timezone": "auto",
            "start_date": date_string,
            "end_date": date_string,
        }
    )

    weather_response.raise_for_status()
    weather_data = weather_response.json()
    daily = weather_data["daily"]

    return (
        f"Weather in {city} on {date_string}: "
        f"min {daily['temperature_2m_min'][0]}°C, "
        f"max {daily['temperature_2m_max'][0]}°C, "
        f"precipitation probability "
        f"{daily['precipitation_probability_max'][0]}%."
    )

tools = [get_weather]
tool_node = ToolNode(tools)
