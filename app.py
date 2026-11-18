# app.py
from flask import Flask, jsonify, redirect, render_template, request, url_for

from database import (
    add_search_history,
    create_forecast,
    delete_forecast,
    get_forecast_by_id,
    get_forecasts_stats,
    get_recent_searches,
    init_db,
    query_forecasts,
    update_forecast,
)
from weather_service import ExternalWeatherError, search_weather_by_city

app = Flask(__name__)
init_db()


@app.route("/", methods=["GET"])
def index():
    city = request.args.get("city", "").strip()
    results = []
    error = None

    if "city" in request.args:
        if not city:
            error = "Введіть назву міста для пошуку погоди."
        else:
            try:
                results = search_weather_by_city(city)
                add_search_history(city)
                if not results:
                    error = f"За запитом «{city}» населених пунктів не знайдено."
            except ValueError as exc:
                error = str(exc)
            except ExternalWeatherError as exc:
                error = str(exc)

    recent_searches = get_recent_searches(limit=6)
    return render_template(
        "index.html",
        city=city,
        results=results,
        error=error,
        recent_searches=recent_searches,
    )


@app.route("/save", methods=["POST"])
def save_item():
    try:
        forecast_id = create_forecast(
            {
                "external_location_id": request.form.get("external_location_id") or None,
                "city": request.form.get("city", ""),
                "country": request.form.get("country", ""),
                "latitude": request.form.get("latitude", 0),
                "longitude": request.form.get("longitude", 0),
                "temperature_c": request.form.get("temperature_c", 0),
                "humidity_pct": request.form.get("humidity_pct", 0),
                "wind_speed_kmh": request.form.get("wind_speed_kmh", 0),
                "weather_condition": request.form.get("weather_condition", "Невідомо"),
                "user_note": request.form.get("user_note", ""),
                "observed_at": request.form.get("observed_at", ""),
            }
        )
        return redirect(url_for("saved_page", saved_id=forecast_id))
    except (ValueError, KeyError):
        return redirect(url_for("index"))


@app.route("/saved", methods=["GET"])
def saved_page():
    city_filter = request.args.get("city", "").strip()
    min_temp_raw = request.args.get("min_temp", "").strip()
    filter_error = None
    min_temp = None

    if min_temp_raw:
        try:
            min_temp = float(min_temp_raw)
        except ValueError:
            filter_error = "Мінімальна температура має бути числовим значенням."

    records = query_forecasts(city=city_filter, min_temp=min_temp)
    stats = get_forecasts_stats()
    return render_template(
        "saved.html",
        records=records,
        stats=stats,
        city_filter=city_filter,
        min_temp_raw=min_temp_raw,
        filter_error=filter_error,
    )


@app.route("/saved/<int:forecast_id>/update", methods=["POST"])
def update_saved(forecast_id: int):
    city = request.form.get("city", "").strip()
    note = request.form.get("user_note", "").strip()
    if not city:
        return redirect(url_for("saved_page"))
    update_forecast(forecast_id, {"city": city, "user_note": note})
    return redirect(url_for("saved_page"))


@app.route("/saved/<int:forecast_id>/delete", methods=["POST"])
def delete_saved(forecast_id: int):
    delete_forecast(forecast_id)
    return redirect(url_for("saved_page"))


# --- Власний REST API ---

def _parse_min_temp_arg():
    raw = request.args.get("min_temp")
    if raw is None or raw.strip() == "":
        return None, None
    try:
        return float(raw), None
    except ValueError:
        return None, "Параметр 'min_temp' повинен бути числом"


@app.route("/api/forecasts/stats", methods=["GET"])
def api_forecasts_stats():
    return jsonify(get_forecasts_stats()), 200


@app.route("/api/forecasts", methods=["GET"])
def api_list_forecasts():
    city = request.args.get("city", "").strip()
    min_temp, err = _parse_min_temp_arg()
    if err:
        return jsonify({"error": err}), 400

    items = query_forecasts(city=city, min_temp=min_temp)
    return jsonify(items), 200


@app.route("/api/forecasts/<int:forecast_id>", methods=["GET"])
def api_get_forecast(forecast_id: int):
    item = get_forecast_by_id(forecast_id)
    if not item:
        return jsonify({"error": f"Запис із id={forecast_id} не знайдено"}), 404
    return jsonify(item), 200


@app.route("/api/forecasts", methods=["POST"])
def api_create_forecast():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Очікується валідний JSON-об'єкт"}), 400

    required_fields = [
        "city",
        "latitude",
        "longitude",
        "temperature_c",
        "humidity_pct",
        "wind_speed_kmh",
        "weather_condition",
    ]
    missing = [f for f in required_fields if f not in payload or payload[f] in (None, "")]
    if missing:
        return jsonify({"error": f"Відсутні обов'язкові поля: {', '.join(missing)}"}), 400

    try:
        new_id = create_forecast(payload)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Некоректні значення полів: {exc}"}), 400

    created = get_forecast_by_id(new_id)
    return jsonify(created), 201


@app.route("/api/forecasts/<int:forecast_id>", methods=["PATCH"])
def api_patch_forecast(forecast_id: int):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "Очікується валідний JSON-об'єкт"}), 400

    if get_forecast_by_id(forecast_id) is None:
        return jsonify({"error": f"Запис із id={forecast_id} не знайдено"}), 404

    if "city" in payload and not str(payload["city"]).strip():
        return jsonify({"error": "Поле 'city' не може бути порожнім"}), 400

    try:
        updated = update_forecast(forecast_id, payload)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Некоректні значення для оновлення: {exc}"}), 400

    return jsonify(updated), 200


@app.route("/api/forecasts/<int:forecast_id>", methods=["DELETE"])
def api_delete_forecast(forecast_id: int):
    deleted = delete_forecast(forecast_id)
    if not deleted:
        return jsonify({"error": f"Запис із id={forecast_id} не знайдено"}), 404
    return jsonify({"deleted": True, "id": forecast_id}), 200


if __name__ == "__main__":
    app.run(debug=True)