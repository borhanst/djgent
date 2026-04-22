"""Weather tool using Open-Meteo API (free, no API key)."""

import httpx

from djgent.tools.base import Tool


class WeatherTool(Tool):
    """
    Get current weather for any city using Open-Meteo API.

    Free, no API key required. Uses geocoding to find city coordinates.
    """

    name = "weather"
    description = (
        "Get current weather for a city. Use for weather questions like "
        "'What is the weather in Dhaka?'"
    )

    def _run(self, city: str) -> str:
        """
        Get weather for a city.

        Args:
            city: The city name

        Returns:
            Current weather information including temperature, conditions, etc.
        """
        try:
            # First, geocode the city to get coordinates
            geocode_url = "https://geocoding-api.open-meteo.com/v1/search"
            geocode_params = {
                "name": city,
                "count": 1,
                "language": "en",
                "format": "json",
            }

            with httpx.Client(timeout=10) as client:
                # Get city coordinates
                geo_response = client.get(geocode_url, params=geocode_params)
                geo_data = geo_response.json()

                if not geo_data.get("results"):
                    return f"Could not find city: {city}"

                location = geo_data["results"][0]
                lat = location["latitude"]
                lon = location["longitude"]
                city_name = location["name"]
                country = location.get("country", "")

                # Get weather data
                weather_url = "https://api.open-meteo.com/v1/forecast"
                weather_params = {
                    "latitude": lat,
                    "longitude": lon,
                    "current": [
                        "temperature_2m",
                        "relative_humidity_2m",
                        "apparent_temperature",
                        "weather_code",
                        "wind_speed_10m",
                    ],
                    "timezone": "auto",
                }

                weather_response = client.get(weather_url, params=weather_params)
                weather_data = weather_response.json()

                if "current" not in weather_data:
                    return f"Could not get weather data for {city}"

                current = weather_data["current"]
                temp = current["temperature_2m"]
                feels_like = current["apparent_temperature"]
                humidity = current["relative_humidity_2m"]
                wind_speed = current["wind_speed_10m"]
                weather_code = current["weather_code"]

                # Interpret weather code
                weather_condition = self._interpret_weather_code(weather_code)

                return (
                    f"Weather in {city_name}, {country}:\n"
                    f"🌡️ Temperature: {temp}°C (feels like {feels_like}°C)\n"
                    f"☁️ Condition: {weather_condition}\n"
                    f"💧 Humidity: {humidity}%\n"
                    f"💨 Wind: {wind_speed} km/h"
                )

        except httpx.TimeoutException:
            return "Weather service timeout. Please try again."
        except Exception as e:
            return f"Weather error: {str(e)}"

    def _interpret_weather_code(self, code: int) -> str:
        """Interpret WMO weather code."""
        codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Foggy",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return codes.get(code, "Unknown")
