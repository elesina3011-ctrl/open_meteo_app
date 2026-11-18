# weather_service.py
import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

WMO_DESCRIPTIONS = {
    0: "Ясно",
    1: "Переважно ясно",
    2: "Мінлива хмарність",
    3: "Похмуро",
    45: "Туман",
    48: "Паморозь / туман",
    51: "Легка мряка",
    53: "Помірна мряка",
    55: "Сильна мряка",
    61: "Невеликий дощ",
    63: "Помірний дощ",
    65: "Сильний дощ",
    71: "Невеликий сніг",
    73: "Помірний сніг",
    75: "Сильний сніг",
    80: "Зливовий дощ",
    95: "Гроза",
}


class ExternalWeatherError(Exception):
    """Помилка звернення до зовнішнього сервісу Open-Meteo."""


def describe_weather_code(code: int | None) -> str:
    if code is None:
        return "Невідомо"
    return WMO_DESCRIPTIONS.get(int(code), f"Код погоди WMO {code}")


def search_weather_by_city(city_name: str, limit: int = 5) -> list[dict]:
    cleaned = city_name.strip()
    if len(cleaned) < 2:
        raise ValueError("Назва міста повинна містити щонайменше 2 символи.")

    try:
        geo_resp = requests.get(
            GEO_URL,
            params={"name": cleaned, "count": limit, "language": "uk", "format": "json"},
            timeout=10,
        )
        geo_resp.raise_for_status()
        geo_data = geo_resp.json()
    except requests.RequestException as exc:
        raise ExternalWeatherError(
            "Сервіс геокодування Open-Meteo тимчасово недоступний."
        ) from exc

    locations = geo_data.get("results") or []
    items: list[dict] = []

    for loc in locations:
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        if lat is None or lon is None:
            continue

        try:
            wx_resp = requests.get(
                FORECAST_URL,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                    "timezone": "auto",
                },
                timeout=10,
            )
            wx_resp.raise_for_status()
            wx_data = wx_resp.json()
        except requests.RequestException as exc:
            raise ExternalWeatherError(
                "Сервіс прогнозу погоди Open-Meteo тимчасово недоступний."
            ) from exc

        current = wx_data.get("current") or {}
        code = current.get("weather_code")
        items.append(
            {
                "external_location_id": loc.get("id"),
                "city": loc.get("name", cleaned),
                "country": loc.get("country", ""),
                "latitude": round(float(lat), 4),
                "longitude": round(float(lon), 4),
                "temperature_c": current.get("temperature_2m"),
                "humidity_pct": current.get("relative_humidity_2m"),
                "wind_speed_kmh": current.get("wind_speed_10m"),
                "weather_code": code,
                "weather_condition": describe_weather_code(code),
                "observed_at": current.get("time", ""),
            }
        )

    return items