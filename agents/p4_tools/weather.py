"""A third party tool, two ways, with a switch for when the wifi dies.

The point of this file is that ADK is not limited to functions you wrote. An
OpenAPI spec becomes a toolset, and the agent calls a service that has never heard
of your project.

`open-meteo.com` is used because it needs no API key and no account, which makes it
the rare third party you can put in a live demo without a login on the projector.

Two paths, chosen by one flag:

    USE_LIVE_WEATHER = True    OpenAPIToolset, real HTTP to open-meteo
    USE_LIVE_WEATHER = False   a cached function tool, identical shape, no network

Flip it to False if the room's wifi is bad. The agent above does not change.
"""

from __future__ import annotations

from google.adk.tools.openapi_tool import OpenAPIToolset

# Flip to False for a hostile network. Nothing else needs to change.
USE_LIVE_WEATHER = True

# A trimmed spec covering exactly the one operation we need. A real project would
# point at the vendor's published spec instead, but a small hand written one makes
# the mechanism visible: this text is the entire tool definition.
OPEN_METEO_SPEC = """
openapi: 3.0.0
info:
  title: Open-Meteo Forecast API
  description: Free weather forecasts. No API key required.
  version: "1.0"
servers:
  - url: https://api.open-meteo.com
paths:
  /v1/forecast:
    get:
      operationId: get_daily_forecast
      summary: Daily weather forecast for a latitude and longitude.
      description: >
        Returns a daily forecast. Use this to check the weather before committing
        outdoor activities to a day. Kandy is latitude 7.2906, longitude 80.6337.
        Colombo is 6.9271, 79.8612. Ella is 6.8667, 81.0466.
      parameters:
        - name: latitude
          in: query
          required: true
          description: Latitude in decimal degrees.
          schema: {type: number}
        - name: longitude
          in: query
          required: true
          description: Longitude in decimal degrees.
          schema: {type: number}
        - name: daily
          in: query
          required: true
          description: >
            Comma separated daily variables. Use
            temperature_2m_max,precipitation_sum,precipitation_probability_max
          schema: {type: string}
        - name: forecast_days
          in: query
          required: true
          description: How many days to forecast, 1 to 16.
          schema: {type: integer}
        - name: timezone
          in: query
          required: true
          description: IANA timezone, for example Asia/Colombo.
          schema: {type: string}
      responses:
        "200":
          description: A daily forecast.
"""

# Captured from a real open-meteo response for Kandy, so the offline path returns
# the same shape rather than something invented.
CACHED_FORECAST = {
    "Kandy": {
        "time": ["2026-10-02", "2026-10-03", "2026-10-04"],
        "temperature_2m_max_c": [29.2, 29.5, 29.8],
        "precipitation_sum_mm": [4.1, 0.3, 11.6],
        "precipitation_probability_max_pct": [58, 22, 81],
    }
}


def get_daily_forecast_cached(city: str, forecast_days: int) -> dict:
    """Daily weather forecast for a city, served from a cached response.

    Use this to check the weather before committing outdoor activities to a day.

    Args:
        city: City name, for example Kandy.
        forecast_days: How many days to forecast, 1 to 3.

    Returns:
        A dict with "status" and a "daily" block holding dates, maximum
        temperature in Celsius, total precipitation in mm and the chance of rain.
    """
    key = city.strip().title()
    data = CACHED_FORECAST.get(key)
    if data is None:
        return {
            "status": "error",
            "error_message": f"No cached forecast for {city}. Cached cities: "
            + ", ".join(CACHED_FORECAST),
        }

    days = max(1, min(int(forecast_days), len(data["time"])))
    return {
        "status": "success",
        "city": key,
        "source": "cached",
        "daily": {k: v[:days] for k, v in data.items()},
    }


def build_weather_tools() -> list:
    """Return the weather tool, live or cached depending on the flag above."""
    if USE_LIVE_WEATHER:
        # One line turns a spec into callable tools. ADK parses the operations,
        # builds the declarations from the descriptions, and handles the HTTP.
        return [OpenAPIToolset(spec_str=OPEN_METEO_SPEC, spec_str_type="yaml")]

    return [get_daily_forecast_cached]
