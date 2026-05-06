"""Weather integration via Yr.no (Norwegian Meteorological Institute).

Free, no API key needed, ideal for Norwegian users.
Used to swap outdoor sessions to indoor when weather is bad.

Bergen coordinates: 60.39, 5.32
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from urllib import request


YR_API = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
USER_AGENT = "TrainingOptimization/0.1 (github.com/andreassendev/Training-Optimization)"


@dataclass(frozen=True)
class WeatherForecast:
    when: datetime
    temp_c: float
    wind_speed_ms: float
    precip_mm_next_hour: float | None
    cloud_pct: float | None
    symbol: str | None  # e.g. "rain", "clearsky", "cloudy"

    @property
    def is_bad_for_outdoor(self) -> bool:
        """Heuristic: rain > 2mm/h, wind > 12 m/s, or cold + wet."""
        if self.precip_mm_next_hour and self.precip_mm_next_hour > 2:
            return True
        if self.wind_speed_ms > 12:
            return True
        if self.temp_c < 0 and self.precip_mm_next_hour and self.precip_mm_next_hour > 0:
            return True
        return False

    @property
    def is_great_for_outdoor(self) -> bool:
        """Sunny, light wind, mild."""
        if self.precip_mm_next_hour and self.precip_mm_next_hour > 0:
            return False
        if self.wind_speed_ms > 8:
            return False
        if not (5 <= self.temp_c <= 22):
            return False
        return True

    @property
    def summary(self) -> str:
        precip = f", {self.precip_mm_next_hour:.1f}mm regn" if self.precip_mm_next_hour else ""
        return f"{self.temp_c:.0f}°C, vind {self.wind_speed_ms:.0f} m/s{precip}"


def fetch_forecast(
    lat: float = 60.39, lon: float = 5.32, hours_ahead: int = 24
) -> list[WeatherForecast]:
    """Fetch weather forecast from Yr.no.

    Default coordinates: Bergen, Norway.
    Returns hourly forecasts up to hours_ahead.
    """
    url = f"{YR_API}?lat={lat}&lon={lon}"
    req = request.Request(url, headers={"User-Agent": USER_AGENT})
    with request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)

    forecasts: list[WeatherForecast] = []
    for entry in data["properties"]["timeseries"][:hours_ahead]:
        when = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
        details = entry["data"]["instant"]["details"]
        next_1h = entry["data"].get("next_1_hours", {})
        next_summary = next_1h.get("summary", {})
        next_details = next_1h.get("details", {})

        forecasts.append(
            WeatherForecast(
                when=when,
                temp_c=details.get("air_temperature", 0),
                wind_speed_ms=details.get("wind_speed", 0),
                precip_mm_next_hour=next_details.get("precipitation_amount"),
                cloud_pct=details.get("cloud_area_fraction"),
                symbol=next_summary.get("symbol_code"),
            )
        )
    return forecasts


def forecast_for_date(target: date, lat: float = 60.39, lon: float = 5.32) -> WeatherForecast | None:
    """Get the forecast closest to noon on a given date."""
    forecasts = fetch_forecast(lat, lon, hours_ahead=72)
    target_noon = datetime(target.year, target.month, target.day, 12)
    if not forecasts:
        return None

    # Find closest to noon
    target_aware = target_noon.replace(tzinfo=forecasts[0].when.tzinfo)
    return min(forecasts, key=lambda f: abs((f.when - target_aware).total_seconds()))


def adjust_workout_for_weather(workout_sport: str, weather: WeatherForecast) -> tuple[str, str]:
    """Suggest workout adjustment based on weather.

    Returns (suggested_sport, note).
    """
    if not weather.is_bad_for_outdoor:
        return workout_sport, ""

    # Bad weather alternatives
    swaps = {
        "bike": ("bike_indoor", "Dårlig vær - kjør på rulle/spinningssykkel"),
        "run": ("run_treadmill", "Dårlig vær - vurder mølle eller bytt til svømming"),
        "brick": ("brick_indoor", "Dårlig vær - rulle + mølle eller flytt økten"),
    }
    if workout_sport in swaps:
        new_sport, note = swaps[workout_sport]
        return new_sport, f"{note} ({weather.summary})"
    return workout_sport, weather.summary
