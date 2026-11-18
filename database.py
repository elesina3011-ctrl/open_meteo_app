# database.py
import sqlite3

DB_PATH = "weather_app.db"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS forecasts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    external_location_id INTEGER,
    city TEXT NOT NULL CHECK (length(trim(city)) > 0),
    country TEXT NOT NULL DEFAULT '',
    latitude REAL NOT NULL CHECK (latitude BETWEEN -90.0 AND 90.0),
    longitude REAL NOT NULL CHECK (longitude BETWEEN -180.0 AND 180.0),
    temperature_c REAL NOT NULL,
    humidity_pct INTEGER NOT NULL CHECK (humidity_pct BETWEEN 0 AND 100),
    wind_speed_kmh REAL NOT NULL CHECK (wind_speed_kmh >= 0),
    weather_condition TEXT NOT NULL,
    user_note TEXT NOT NULL DEFAULT '',
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL CHECK (length(trim(query)) > 0),
    searched_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_SQL)
        conn.commit()


def create_forecast(data: dict) -> int:
    sql = """
    INSERT INTO forecasts (
        external_location_id, city, country, latitude, longitude,
        temperature_c, humidity_pct, wind_speed_kmh, weather_condition,
        user_note, observed_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        data.get("external_location_id"),
        data["city"].strip(),
        data.get("country", "").strip(),
        float(data["latitude"]),
        float(data["longitude"]),
        float(data["temperature_c"]),
        int(data["humidity_pct"]),
        float(data["wind_speed_kmh"]),
        data["weather_condition"].strip(),
        data.get("user_note", "").strip(),
        data.get("observed_at", ""),
    )
    with get_connection() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return int(cur.lastrowid)


def query_forecasts(city: str = "", min_temp: float | None = None) -> list[dict]:
    sql = """
    SELECT id, external_location_id, city, country, latitude, longitude,
           temperature_c, humidity_pct, wind_speed_kmh, weather_condition,
           user_note, observed_at, created_at
    FROM forecasts
    WHERE 1=1
    """
    params: list = []

    if city.strip():
        sql += " AND LOWER(city) LIKE LOWER(?)"
        params.append(f"%{city.strip()}%")

    if min_temp is not None:
        sql += " AND temperature_c >= ?"
        params.append(min_temp)

    sql += " ORDER BY id DESC"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def get_forecast_by_id(forecast_id: int) -> dict | None:
    sql = """
    SELECT id, external_location_id, city, country, latitude, longitude,
           temperature_c, humidity_pct, wind_speed_kmh, weather_condition,
           user_note, observed_at, created_at
    FROM forecasts
    WHERE id = ?
    """
    with get_connection() as conn:
        row = conn.execute(sql, (forecast_id,)).fetchone()
    return dict(row) if row else None


def update_forecast(forecast_id: int, updates: dict) -> dict | None:
    allowed_fields = {
        "city": lambda v: str(v).strip(),
        "country": lambda v: str(v).strip(),
        "temperature_c": lambda v: float(v),
        "humidity_pct": lambda v: int(v),
        "wind_speed_kmh": lambda v: float(v),
        "weather_condition": lambda v: str(v).strip(),
        "user_note": lambda v: str(v).strip(),
    }

    set_clauses = []
    params = []
    for field, caster in allowed_fields.items():
        if field in updates and updates[field] is not None:
            set_clauses.append(f"{field} = ?")
            params.append(caster(updates[field]))

    if not set_clauses:
        return get_forecast_by_id(forecast_id)

    params.append(forecast_id)
    sql = f"UPDATE forecasts SET {', '.join(set_clauses)} WHERE id = ?"

    with get_connection() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        if cur.rowcount == 0:
            return None
    return get_forecast_by_id(forecast_id)


def delete_forecast(forecast_id: int) -> bool:
    sql = "DELETE FROM forecasts WHERE id = ?"
    with get_connection() as conn:
        cur = conn.execute(sql, (forecast_id,))
        conn.commit()
        return cur.rowcount > 0


def get_forecasts_stats() -> dict:
    sql = """
    SELECT
        COUNT(*) AS total_count,
        ROUND(AVG(temperature_c), 1) AS avg_temp,
        MIN(temperature_c) AS min_temp,
        MAX(temperature_c) AS max_temp,
        ROUND(AVG(humidity_pct), 0) AS avg_humidity,
        ROUND(AVG(wind_speed_kmh), 1) AS avg_wind
    FROM forecasts
    """
    with get_connection() as conn:
        row = conn.execute(sql).fetchone()
    return dict(row) if row else {
        "total_count": 0,
        "avg_temp": None,
        "min_temp": None,
        "max_temp": None,
        "avg_humidity": None,
        "avg_wind": None,
    }


def add_search_history(query: str) -> None:
    cleaned = query.strip()
    if not cleaned:
        return
    with get_connection() as conn:
        conn.execute("INSERT INTO search_history (query) VALUES (?)", (cleaned,))
        conn.commit()


def get_recent_searches(limit: int = 6) -> list[str]:
    sql = """
    SELECT query
    FROM search_history
    GROUP BY LOWER(query)
    ORDER BY MAX(id) DESC
    LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (limit,)).fetchall()
    return [row["query"] for row in rows]