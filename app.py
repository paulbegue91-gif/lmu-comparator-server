"""
LMU Lap Comparator — Backend Server v4
Utilise /data si disque persistant disponible, sinon /tmp
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
import json, os
from datetime import datetime

app = Flask(__name__)
CORS(app)

if os.path.isdir('/data') and os.access('/data', os.W_OK):
    DATA_FILE = "/data/lmu_data.json"
else:
    DATA_FILE = "/tmp/lmu_data.json"

print(f"[INFO] Stockage : {DATA_FILE}")

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: pass
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route("/", methods=["GET"])
def index():
    data = load_data()
    return jsonify({"status": "LMU Lap Comparator API", "pilots": list(data.keys()), "total_pilots": len(data), "storage": DATA_FILE})

@app.route("/push", methods=["POST"])
def push():
    body = request.get_json(force=True, silent=True)
    if not body: return jsonify({"error": "Invalid JSON"}), 400
    pilot = (body.get("pilot") or "").strip()
    times = body.get("times") or {}
    if not pilot: return jsonify({"error": "pilot required"}), 400
    if not times: return jsonify({"error": "times required"}), 400
    data = load_data()
    existing = data.get(pilot, {})
    existing_times = existing.get("times", {})
    for key, rec in times.items():
        if key not in existing_times or rec["time_sec"] < existing_times[key]["time_sec"]:
            existing_times[key] = rec
    data[pilot] = {"updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "times": existing_times}
    save_data(data)
    return jsonify({"status": "ok", "pilot": pilot, "circuits_stored": len(existing_times)})

@app.route("/all", methods=["GET"])
def get_all():
    return jsonify(load_data())

@app.route("/pilots", methods=["GET"])
def get_pilots():
    data = load_data()
    return jsonify(sorted([{"name": p, "updated_at": i.get("updated_at",""), "circuits": len(i.get("times",{}))} for p,i in data.items()], key=lambda x: x["name"]))

@app.route("/delete/<name>", methods=["GET","DELETE"])
def delete_pilot(name):
    data = load_data()
    if name in data:
        del data[name]; save_data(data)
        return jsonify({"status": "deleted", "pilot": name})
    return jsonify({"error": "Not found"}), 404

@app.route("/reset", methods=["GET"])
def reset():
    save_data({})
    return jsonify({"status": "reset", "message": "Toutes les donnees effacees"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
