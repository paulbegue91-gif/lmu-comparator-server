"""
LMU Lap Comparator — Backend Server
Déployez gratuitement sur Render.com
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import time
from datetime import datetime

app = Flask(__name__)
CORS(app)

DATA_FILE = "lmu_data.json"

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# Structure stockée :
# {
#   "Paul Begue": {
#     "updated_at": "2026-04-17 21:00",
#     "times": {
#       "Autodromo Nazionale Monza|WEC": {"time_sec": 110.49, "time_str": "01:50.490"},
#       ...
#     }
#   }
# }

@app.route("/", methods=["GET"])
def index():
    data = load_data()
    return jsonify({
        "status": "LMU Lap Comparator API",
        "pilots": list(data.keys()),
        "total_pilots": len(data)
    })

@app.route("/push", methods=["POST"])
def push():
    """
    Reçoit les meilleurs temps d'un pilote.
    Body JSON: { "pilot": "Paul Begue", "times": {"Circuit|Config": {"time_sec": 110.5, "time_str": "01:50.5"}, ...} }
    """
    body = request.get_json(force=True, silent=True)
    if not body:
        return jsonify({"error": "Invalid JSON"}), 400

    pilot = (body.get("pilot") or "").strip()
    times = body.get("times") or {}

    if not pilot:
        return jsonify({"error": "pilot required"}), 400
    if not times:
        return jsonify({"error": "times required"}), 400

    data = load_data()
    
    # Merge : on garde le meilleur temps par circuit
    existing = data.get(pilot, {})
    existing_times = existing.get("times", {})

    for key, rec in times.items():
        if key not in existing_times or rec["time_sec"] < existing_times[key]["time_sec"]:
            existing_times[key] = rec

    data[pilot] = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "times": existing_times
    }
    save_data(data)

    return jsonify({
        "status": "ok",
        "pilot": pilot,
        "circuits_stored": len(existing_times)
    })

@app.route("/all", methods=["GET"])
def get_all():
    """Retourne tous les temps de tous les pilotes."""
    return jsonify(load_data())

@app.route("/pilot/<name>", methods=["GET"])
def get_pilot(name):
    """Retourne les temps d'un pilote spécifique."""
    data = load_data()
    if name not in data:
        return jsonify({"error": "Pilot not found"}), 404
    return jsonify(data[name])

@app.route("/pilots", methods=["GET"])
def get_pilots():
    """Liste des pilotes enregistrés."""
    data = load_data()
    result = []
    for pilot, info in data.items():
        result.append({
            "name": pilot,
            "updated_at": info.get("updated_at", ""),
            "circuits": len(info.get("times", {}))
        })
    return jsonify(sorted(result, key=lambda x: x["name"]))

@app.route("/delete/<name>", methods=["DELETE"])
def delete_pilot(name):
    """Supprime un pilote (pour nettoyage)."""
    data = load_data()
    if name in data:
        del data[name]
        save_data(data)
        return jsonify({"status": "deleted", "pilot": name})
    return jsonify({"error": "Not found"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
