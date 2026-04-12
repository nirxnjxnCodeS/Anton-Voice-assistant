"""
Weather tools — current conditions and 5-day forecasts via OpenWeatherMap.
"""

import httpx
from collections import defaultdict
from datetime import date as date_cls, datetime

from anton.config import config

BASE_URL = "https://api.openweathermap.org/data/2.5"


def register(mcp):

    @mcp.tool()
    async def get_current_weather(city: str) -> str:
        """
        Get current weather conditions for a city: temperature, feels-like,
        condition, humidity, and wind speed.
        Use when the user asks 'What's the weather in X?' or 'Is it hot outside?'
        """
        if not config.OPENWEATHER_API_KEY:
            return "Weather service is offline, sir. OPENWEATHER_API_KEY is not configured."

        params = {
            "q": city,
            "appid": config.OPENWEATHER_API_KEY,
            "units": "metric",
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{BASE_URL}/weather", params=params)

            if response.status_code == 404:
                return f"I couldn't locate '{city}' in the weather grid, sir. Please verify the city name."
            if response.status_code == 401:
                return "Weather service authentication failed, sir. The API key appears to be invalid."
            response.raise_for_status()

            data = response.json()
            temp = round(data["main"]["temp"])
            feels_like = round(data["main"]["feels_like"])
            humidity = data["main"]["humidity"]
            condition = data["weather"][0]["description"].capitalize()
            wind_kph = round(data["wind"]["speed"] * 3.6)  # m/s → km/h
            city_name = data["name"]
            country = data["sys"]["country"]

            return (
                f"Currently {temp}°C in {city_name}, {country} — feels like {feels_like}°C. "
                f"{condition}, humidity at {humidity}%, winds at {wind_kph} km/h."
            )

        except httpx.TimeoutException:
            return "The weather service timed out, sir. Try again in a moment."
        except Exception as e:
            return f"Weather retrieval failed: {str(e)}"

    @mcp.tool()
    async def get_weekly_forecast(city: str) -> str:
        """
        Get a 5-day weather forecast for a city, summarised by day with high/low
        temperatures and dominant conditions.
        Use when the user asks 'What's the weather like this week?' or 'Will it rain tomorrow?'
        """
        if not config.OPENWEATHER_API_KEY:
            return "Weather service is offline, sir. OPENWEATHER_API_KEY is not configured."

        params = {
            "q": city,
            "appid": config.OPENWEATHER_API_KEY,
            "units": "metric",
            "cnt": 40,  # 5 days × 8 three-hour slots
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{BASE_URL}/forecast", params=params)

            if response.status_code == 404:
                return f"I couldn't locate '{city}' in the weather grid, sir. Please verify the city name."
            if response.status_code == 401:
                return "Weather service authentication failed, sir. The API key appears to be invalid."
            response.raise_for_status()

            data = response.json()
            city_name = data["city"]["name"]
            country = data["city"]["country"]

            # Group 3-hour slots by date, collect temps and conditions per day
            days: dict[str, dict] = defaultdict(lambda: {"temps": [], "conditions": []})
            for slot in data["list"]:
                date_str = slot["dt_txt"].split(" ")[0]  # "2024-04-14 12:00:00" → "2024-04-14"
                days[date_str]["temps"].append(slot["main"]["temp"])
                days[date_str]["conditions"].append(slot["weather"][0]["description"])

            today_str = date_cls.today().isoformat()
            lines = [f"5-day forecast for {city_name}, {country}:\n"]
            count = 0

            for date_str, info in sorted(days.items()):
                if date_str == today_str:
                    continue  # today is covered by get_current_weather
                if count >= 5:
                    break

                lo = round(min(info["temps"]))
                hi = round(max(info["temps"]))
                dominant = max(set(info["conditions"]), key=info["conditions"].count).capitalize()
                label = datetime.strptime(date_str, "%Y-%m-%d").strftime("%a %d %b")
                lines.append(f"  • {label}: {lo}–{hi}°C, {dominant}")
                count += 1

            return "\n".join(lines)

        except httpx.TimeoutException:
            return "The weather service timed out, sir. Try again in a moment."
        except Exception as e:
            return f"Forecast retrieval failed: {str(e)}"
