"""
LMU Lap Comparator — App principale v2
- Parse CarClass + CarType (marque) par pilote
- Fenetre config Windows native
- Serveur local silencieux
"""
import os, sys, json, re, threading, time, webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import xml.etree.ElementTree as ET
import urllib.request
import tkinter as tk
from tkinter import filedialog

if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
    APP_DIR  = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    APP_DIR  = BASE_DIR

CONFIG_FILE  = os.path.join(APP_DIR, "lmu_config.json")
SERVER_URL   = "https://lmu-comparator-server.onrender.com"
DEFAULT_PATH = r"H:\SteamLibrary\steamapps\common\Le Mans Ultimate\UserData\Log\Results"
PORT         = 5731

RE_SCORE = re.compile(r"^(.+?)\(\d+\)\s+lap=\d+\s+point=(\d+)\s+t=([\d\.]+)", re.I)

def fmt(s):
    if s is None: return "—"
    m = int(s // 60); sec = s - m * 60
    return f"{m:02d}:{sec:06.3f}"

def extract_brand(car_type):
    if not car_type: return ""
    brands = ["Lamborghini","Ferrari","Porsche","BMW","McLaren","Aston Martin",
              "Mercedes","Ford","Chevrolet","Nissan","Toyota","Peugeot",
              "Glickenhaus","Cadillac","Alpine","Oreca","Ligier","Dallara",
              "Genesis","Vanwall","Isotta Fraschini"]
    for b in brands:
        if b.lower() in car_type.lower(): return b
    return car_type.split()[0]

def parse_folder(folder, my_name):
    best = {}
    try:
        for fp in sorted(Path(folder).glob("*.xml"), key=lambda x: x.stat().st_mtime):
            try:
                root = ET.parse(str(fp)).getroot()
                circ = cfg = ""
                for e in root.iter("TrackVenue"):
                    if e.text: circ = e.text.strip(); break
                for e in root.iter("TrackCourse"):
                    if e.text: cfg = e.text.strip(); break
                if not circ: continue
                if cfg == circ: cfg = "WEC"
                driver_info = {}
                for drv in root.iter("Driver"):
                    name_el  = drv.find("Name")
                    class_el = drv.find("CarClass")
                    type_el  = drv.find("CarType")
                    if name_el is not None and name_el.text:
                        dn = name_el.text.strip().lower()
                        ct = type_el.text.strip() if type_el is not None and type_el.text else ""
                        cc = class_el.text.strip() if class_el is not None and class_el.text else "Unknown"
                        driver_info[dn] = {"car_class": cc, "car_type": ct, "brand": extract_brand(ct)}
                for sc in root.iter("Score"):
                    m = RE_SCORE.match((sc.text or "").strip())
                    if not m: continue
                    driver = m.group(1).strip()
                    if driver.lower() != my_name.lower(): continue
                    if int(m.group(2)) == 0 and float(m.group(3)) > 0:
                        t    = float(m.group(3))
                        info = driver_info.get(driver.lower(), {})
                        cc   = info.get("car_class", "Unknown")
                        ct   = info.get("car_type", "")
                        br   = info.get("brand", "")
                        k    = f"{circ}|{cfg}|{cc}"
                        if k not in best or t < best[k]["time_sec"]:
                            best[k] = {"time_sec": t, "time_str": fmt(t), "car_class": cc, "car_type": ct, "brand": br}
            except: pass
    except: pass
    return best

def api_push(name, times):
    try:
        body = json.dumps({"pilot": name, "times": times}).encode()
        req  = urllib.request.Request(SERVER_URL + "/push", data=body,
               headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r: return json.loads(r.read())
    except: return None

def load_config():
    try:
        with open(CONFIG_FILE) as f: return json.load(f)
    except: return {}

def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f: json.dump(cfg, f)
    except: pass

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path in ("/", "/index.html"): self._serve("index.html", "text/html; charset=utf-8")
        elif self.path == "/api/config": self._json(load_config())
        elif self.path == "/api/sync":
            cfg = load_config(); name = cfg.get("name",""); folder = cfg.get("folder","")
            result = {"ok": False, "pilots": 0, "times": 0, "error": ""}
            if name and folder:
                times = parse_folder(folder, name); api_push(name, times); result["times"] = len(times)
            try:
                with urllib.request.urlopen(SERVER_URL + "/all", timeout=15) as r:
                    all_data = json.loads(r.read())
                result["ok"] = True; result["pilots"] = len(all_data)
            except Exception as e: result["error"] = str(e)
            self._json(result)
        else: self.send_error(404)
    def do_POST(self):
        if self.path == "/api/config":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            cfg = load_config(); cfg.update(body); save_config(cfg)
            name = cfg.get("name",""); folder = cfg.get("folder","")
            if name and folder:
                times = parse_folder(folder, name); api_push(name, times)
            self._json({"ok": True})
        else: self.send_error(404)
    def do_OPTIONS(self): self.send_response(200); self._cors(); self.end_headers()
    def _serve(self, filename, ctype):
        fp = os.path.join(BASE_DIR, filename)
        if not os.path.exists(fp): self.send_error(404); return
        with open(fp, "rb") as f: data = f.read()
        self.send_response(200); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", len(data)); self._cors(); self.end_headers(); self.wfile.write(data)
    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body)); self._cors(); self.end_headers(); self.wfile.write(body)
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

def start_server():
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()

class ConfigWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LMU Lap Comparator"); self.geometry("480x340")
        self.resizable(False, False); self.configure(bg="#0D1117")
        self.cfg = load_config()
        self.update_idletasks()
        x = (self.winfo_screenwidth()-480)//2; y = (self.winfo_screenheight()-340)//2
        self.geometry(f"480x340+{x}+{y}"); self._build()
    def _build(self):
        tk.Frame(self, bg="#E8003D", height=4).pack(fill="x")
        logo = tk.Frame(self, bg="#0D1117", pady=20); logo.pack(fill="x", padx=28)
        tk.Label(logo, text="🏎  LMU LAP COMPARATOR", font=("Segoe UI",14,"bold"), bg="#0D1117", fg="white").pack(anchor="w")
        tk.Label(logo, text="Configuration — à faire une seule fois", font=("Segoe UI",9), bg="#0D1117", fg="#5A6A80").pack(anchor="w", pady=(2,0))
        form = tk.Frame(self, bg="#0D1117", padx=28); form.pack(fill="x")
        tk.Label(form, text="VOTRE PSEUDO LMU", font=("Segoe UI",8,"bold"), bg="#0D1117", fg="#5A6A80").pack(anchor="w", pady=(0,4))
        self.v_name = tk.StringVar(value=self.cfg.get("name",""))
        tk.Entry(form, textvariable=self.v_name, font=("Segoe UI",11), bg="#161B22", fg="white", insertbackground="white", relief="flat", highlightbackground="#30363D", highlightthickness=1).pack(fill="x", ipady=8)
        tk.Label(form, text="DOSSIER RESULTS LMU", font=("Segoe UI",8,"bold"), bg="#0D1117", fg="#5A6A80").pack(anchor="w", pady=(16,4))
        row = tk.Frame(form, bg="#0D1117"); row.pack(fill="x")
        self.v_folder = tk.StringVar(value=self.cfg.get("folder", DEFAULT_PATH))
        tk.Entry(row, textvariable=self.v_folder, font=("Segoe UI",9), bg="#161B22", fg="white", insertbackground="white", relief="flat", highlightbackground="#30363D", highlightthickness=1).pack(side="left", fill="x", expand=True, ipady=7)
        tk.Button(row, text="...", command=self._browse, bg="#21262D", fg="white", font=("Segoe UI",9), relief="flat", padx=10, cursor="hand2", bd=0).pack(side="left", padx=(6,0), ipady=7)
        btns = tk.Frame(self, bg="#0D1117", padx=28, pady=20); btns.pack(fill="x")
        tk.Button(btns, text="OUVRIR L'INTERFACE →", command=self._open, bg="#E8003D", fg="white", font=("Segoe UI",10,"bold"), relief="flat", padx=20, pady=10, cursor="hand2", bd=0, activebackground="#C00030", activeforeground="white").pack(side="right")
        tk.Button(btns, text="Sauvegarder", command=self._save, bg="#21262D", fg="white", font=("Segoe UI",9), relief="flat", padx=16, pady=10, cursor="hand2", bd=0).pack(side="right", padx=(0,8))
        self.v_status = tk.StringVar(value="")
        tk.Label(self, textvariable=self.v_status, font=("Segoe UI",8), bg="#0D1117", fg="#5A6A80").pack(side="bottom", pady=8)
    def _browse(self):
        d = filedialog.askdirectory(title="Dossier Results LMU")
        if d: self.v_folder.set(d)
    def _save(self):
        name = self.v_name.get().strip(); folder = self.v_folder.get().strip()
        if not name: self.v_status.set("⚠ Entrez votre pseudo LMU"); return
        self.cfg["name"] = name; self.cfg["folder"] = folder
        save_config(self.cfg); self.v_status.set("✓ Sauvegardé")
        def push():
            if folder:
                times = parse_folder(folder, name); api_push(name, times)
        threading.Thread(target=push, daemon=True).start()
    def _open(self): self._save(); webbrowser.open(f"http://localhost:{PORT}")

if __name__ == "__main__":
    threading.Thread(target=start_server, daemon=True).start()
    time.sleep(0.3)
    ConfigWindow().mainloop()
