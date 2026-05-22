"""
SeoFast Multi-Session Bot v6 - httpx_socks + HTTP/2 (DEFINITIVO)
Testado e confirmado: httpx_socks com http2=True funciona 100%.
requests NÃO funciona (Remote disconnected).
httpx_socks com http2=False NÃO funciona (SSL EOF).
UNICA combinação que funciona: httpx_socks + http2=True.
"""

import hashlib
import json
import os
import random
import re
import string
import threading
import time
from datetime import datetime
from urllib.parse import quote as url_quote

import httpx
from httpx_socks import SyncProxyTransport
from flask import Flask, render_template, request, jsonify, Response

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32).hex()

from werkzeug.middleware.proxy_fix import ProxyFix
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

ALLOWED_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '')

# ===== PROTECAO ANTI-SCRAPING =====
BLOCKED_BOTS = [
    'httrack', 'wget', 'curl', 'saveweb2zip', 'website-downloader',
    'webcopier', 'teleport', 'offline explorer', 'webripper',
    'sitecopy', 'grab', 'scrapy', 'python-requests', 'go-http-client',
    'java/', 'libwww', 'lwp-trivial', 'sitesucker', 'blackwidow',
    'webzip', 'webstripper', 'netspider', 'telesoft', 'linkwalker',
    'phantomjs', 'headlesschrome', 'puppeteer', 'playwright',
    'selenium', 'webdriver', 'archive.org_bot', 'ia_archiver',
    'nutch', 'heritrix', 'httpclient', 'axios/', 'node-fetch',
]

@app.before_request
def anti_scraping_guard():
    ua = (request.headers.get('User-Agent', '') or '').lower()
    for bot in BLOCKED_BOTS:
        if bot in ua:
            return Response('', status=403)
    if not ua or ua == '-':
        return Response('', status=403)
    if request.path.startswith('/api/'):
        origin = (request.headers.get('Origin', '') or '').lower()
        req_ref = (request.headers.get('Referer', '') or '').lower()
        xhr = request.headers.get('X-Requested-With', '')
        if origin or req_ref or xhr == 'XMLHttpRequest':
            pass
        else:
            return Response(json.dumps({'error': 'unauthorized'}), status=401, content_type='application/json')

@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers.pop('Server', None)
    return response

@app.route('/robots.txt')
def robots_txt():
    return Response('User-agent: *\nDisallow: /\n', content_type='text/plain')

# ===== CONFIGURACAO DO BOT =====
BASE_URL = "https://seo-fast.bz/webapp/"
APP_VERSION = "1.1.0"
APP_SECRET = "seo_fast_SFk1gR5h5DGH"
PACKAGE_NAME = "com.example.seofast"

TIMER_MULTIPLIER = 0.60
MAX_TIMER_SECONDS = 60
PROXY_PORT = 824
PROXY_COUNTRY = "br"
IP_ROTATION_INTERVAL = 300  # 5 minutos - rotacao mais frequente = mais videos disponiveis

# ===== DISPOSITIVOS ANDROID =====
ANDROID_DEVICES = [
    {"brand": "samsung", "model": "SM-A546E", "device": "a54x", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-G960N", "device": "starlte", "build": "PQ3A.190605.07021633", "sdk": 28, "release": "9"},
    {"brand": "samsung", "model": "SM-A525F", "device": "a52q", "build": "SP1A.210812.016", "sdk": 31, "release": "12"},
    {"brand": "samsung", "model": "SM-G991B", "device": "o1s", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-A336B", "device": "a33x", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-G998B", "device": "p3s", "build": "SP2A.220405.004", "sdk": 32, "release": "12L"},
    {"brand": "xiaomi", "model": "Redmi Note 12", "device": "tapas", "build": "TKQ1.221114.001", "sdk": 33, "release": "13"},
    {"brand": "xiaomi", "model": "POCO X5 Pro", "device": "redwood", "build": "TKQ1.221114.001", "sdk": 33, "release": "13"},
    {"brand": "xiaomi", "model": "Redmi Note 11", "device": "spes", "build": "SKQ1.211019.001", "sdk": 31, "release": "12"},
    {"brand": "google", "model": "Pixel 7", "device": "panther", "build": "TQ3A.230901.001", "sdk": 34, "release": "14"},
    {"brand": "google", "model": "Pixel 6a", "device": "bluejay", "build": "TQ3A.230705.001", "sdk": 33, "release": "13"},
    {"brand": "oneplus", "model": "CPH2449", "device": "OP5958L1", "build": "TP1A.220905.001", "sdk": 33, "release": "13"},
    {"brand": "realme", "model": "RMX3630", "device": "RE58B2", "build": "TP1A.220905.001", "sdk": 33, "release": "13"},
    {"brand": "motorola", "model": "moto g(60)", "device": "hanoip", "build": "S3RHS32.20-42-6-2", "sdk": 31, "release": "12"},
    {"brand": "oppo", "model": "CPH2387", "device": "OP5961L1", "build": "TP1A.220905.001", "sdk": 32, "release": "12"},
    {"brand": "nokia", "model": "Nokia G21", "device": "RGR_sprout", "build": "SP1A.210812.016", "sdk": 31, "release": "12"},
    {"brand": "asus", "model": "ASUS_I006D", "device": "ASUS_I006D", "build": "SKQ1.210821.001", "sdk": 32, "release": "12"},
    {"brand": "sony", "model": "XQ-CQ72", "device": "pdx225", "build": "TQ3A.230901.001", "sdk": 33, "release": "13"},
]

CHROME_VERSIONS = [
    "120.0.6099.144", "121.0.6167.101", "122.0.6261.64", "123.0.6312.99",
    "124.0.6367.82", "125.0.6422.113", "126.0.6478.72", "127.0.6533.88",
    "128.0.6613.127", "129.0.6668.54", "130.0.6723.86", "131.0.6778.39",
    "132.0.6834.15", "133.0.6917.71", "134.0.6998.39",
]

def generate_device_id():
    return f"bluestacks_{''.join(random.choice(string.hexdigits[:16]) for _ in range(16))}"

def generate_user_agent(device_info):
    chrome_ver = random.choice(CHROME_VERSIONS)
    return (
        f"Mozilla/5.0 (Linux; Android {device_info['release']}; {device_info['model']} "
        f"Build/{device_info['build']}; wv) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Version/4.0 Chrome/{chrome_ver} Mobile Safari/537.36 SeoFast-App/1.0"
    )

def generate_app_token(device_id):
    return hashlib.sha256(f"{device_id}:{PACKAGE_NAME}:{APP_SECRET}".encode('utf-8')).hexdigest()

# ===== MULTI-USER STATE =====
users_state = {}
users_lock = threading.Lock()
PERSISTENCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_bots.json")

def save_active_bots(email, password, num_sessions, proxy_config):
    try:
        data = load_active_bots()
        data[email] = {"email": email, "password": password, "num_sessions": num_sessions, "proxy_config": proxy_config, "started_at": datetime.now().isoformat()}
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[PERSIST] Erro ao salvar: {e}")

def remove_active_bot(email):
    try:
        data = load_active_bots()
        data.pop(email, None)
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_active_bots():
    try:
        if os.path.exists(PERSISTENCE_FILE):
            with open(PERSISTENCE_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def auto_resume_bots():
    data = load_active_bots()
    if not data:
        print("[AUTO-RESUME] Nenhuma conta para resumir.")
        return
    print(f"[AUTO-RESUME] Resumindo {len(data)} conta(s)...")
    for email, info in data.items():
        try:
            user_state = get_user_state(email)
            active_threads = [t for t in user_state.get("threads", []) if t.is_alive()]
            if active_threads:
                continue
            with online_users_lock:
                online_users[email] = {"started_at": datetime.now().strftime("%H:%M:%S"), "sessions": info.get("num_sessions", 50), "last_seen": time.time()}
            threading.Thread(target=start_bot, args=(email, info["password"], info.get("num_sessions", 50), info.get("proxy_config", {})), daemon=True).start()
            print(f"[AUTO-RESUME] {email} iniciado.")
            time.sleep(2)
        except Exception as e:
            print(f"[AUTO-RESUME] Erro: {e}")

def get_user_state(email):
    with users_lock:
        if email not in users_state:
            users_state[email] = {"running": False, "sessions": [], "threads": [], "total_earned": 0.0, "total_views": 0, "logs": [], "start_time": None, "stop_requested": False, "lock": threading.Lock()}
        return users_state[email]

def add_log(email, message, level="info"):
    state = get_user_state(email)
    with state["lock"]:
        timestamp = datetime.now().strftime("%H:%M:%S")
        state["logs"].append({"time": timestamp, "message": message, "level": level})
        if len(state["logs"]) > 500:
            state["logs"] = state["logs"][-500:]

online_users = {}
online_users_lock = threading.Lock()

# ===== PROXY =====
def build_proxy_url(proxy_config, session_id, rotation_id=None):
    if not proxy_config or not proxy_config.get("enabled"):
        return None
    login = proxy_config.get("login", "")
    password = proxy_config.get("password", "")
    host = proxy_config.get("host", "gw.dataimpulse.com")
    if not login or not password:
        return None
    rot_id = rotation_id or int(time.time()) % 100000
    sessid_value = f"sf{session_id}r{rot_id}"
    login_with_params = f"{login}__cr.{PROXY_COUNTRY}__sd.{sessid_value}"
    return f"socks5://{login_with_params}:{password}@{host}:{PROXY_PORT}"

# ===== BOT SESSION =====
class SeoFastSession:
    def __init__(self, session_id, email, password, owner_email, identity, proxy_url=None, proxy_config=None):
        self.session_id = session_id
        self.email = email
        self.password = password
        self.owner_email = owner_email
        self.device_id = identity["device_id"]
        self.user_agent = identity["user_agent"]
        self.device_info = identity["device_info"]
        self.proxy_url = proxy_url
        self.proxy_config = proxy_config
        self.app_token = generate_app_token(self.device_id)
        self.phpsessid = None
        self.hash_ajax = None
        self.client = None
        self.earned = 0.0
        self.views = 0
        self.rotation_count = 0
        self.last_rotation_time = time.time()
        self.status = "idle"
        self.current_video = None
        self.current_ip = None
        self.consecutive_empty = 0
        self.total_attempts = 0
        self.tasks_found = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_skipped = 0

    def _create_client(self):
        """Criar httpx client com HTTP/2 via SOCKS5 proxy"""
        if self.client:
            try:
                self.client.close()
            except Exception:
                pass
        if self.proxy_url:
            transport = SyncProxyTransport.from_url(self.proxy_url, http2=True, verify=False)
            self.client = httpx.Client(transport=transport, timeout=25.0, follow_redirects=True)
        else:
            self.client = httpx.Client(http2=True, verify=False, timeout=25.0, follow_redirects=True)

    def _nav_headers(self):
        h = {
            "User-Agent": self.user_agent,
            "X-App-Token": self.app_token,
            "X-App-Version": APP_VERSION,
            "X-Device-Id": self.device_id,
            "X-Requested-With": PACKAGE_NAME,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        if self.phpsessid:
            h["Cookie"] = f"PHPSESSID={self.phpsessid}"
        return h

    def _login_headers(self):
        h = {
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "X-App-Token": self.app_token,
            "X-Device-Id": self.device_id,
            "X-App-Version": APP_VERSION,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "User-Agent": self.user_agent,
            "Origin": "https://seo-fast.bz",
            "Referer": "https://seo-fast.bz/webapp/?pg=login",
        }
        if self.phpsessid:
            h["Cookie"] = f"PHPSESSID={self.phpsessid}"
        return h

    def _ajax_headers(self):
        h = {
            "User-Agent": self.user_agent,
            "X-App-Token": self.app_token,
            "X-App-Version": APP_VERSION,
            "X-Device-Id": self.device_id,
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://seo-fast.bz",
            "Referer": "https://seo-fast.bz/webapp/?pg=job",
            "X-Requested-With": "XMLHttpRequest",
            "Content-Type": "application/json; charset=utf-8",
        }
        if self.phpsessid:
            h["Cookie"] = f"PHPSESSID={self.phpsessid}"
        return h

    def detect_ip(self):
        try:
            r = self.client.get("https://api.ipify.org/?format=json")
            if r.status_code == 200:
                self.current_ip = r.json().get("ip", "?")
        except Exception:
            self.current_ip = "?"

    def login(self):
        self.status = "logging_in"
        try:
            self._create_client()

            # Detectar IP
            if self.proxy_url:
                self.detect_ip()
                add_log(self.owner_email,
                    f"[S{self.session_id}] IP: {self.current_ip} | UA: {self.device_info['brand']} {self.device_info['model']}",
                    "info")

            # Step 1: GET /webapp/
            r = self.client.get(BASE_URL, headers=self._nav_headers())

            # Extrair PHPSESSID
            for name, value in r.headers.multi_items():
                if name.lower() == "set-cookie" and "PHPSESSID" in value:
                    self.phpsessid = value.split("PHPSESSID=")[1].split(";")[0]
            if not self.phpsessid:
                for cookie in self.client.cookies.jar:
                    if cookie.name == "PHPSESSID":
                        self.phpsessid = cookie.value

            # Extrair hash_ajax
            m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
            self.hash_ajax = m.group(1) if m else None

            if not self.hash_ajax:
                time.sleep(0.5)
                r = self.client.get(f"{BASE_URL}?pg=login", headers=self._nav_headers())
                for cookie in self.client.cookies.jar:
                    if cookie.name == "PHPSESSID":
                        self.phpsessid = cookie.value
                m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
                self.hash_ajax = m.group(1) if m else None

            if not self.hash_ajax:
                self.status = "login_failed"
                add_log(self.owner_email, f"[S{self.session_id}] FALHA: hash_ajax nao encontrado", "error")
                return False

            # Step 2: POST login
            time.sleep(random.uniform(0.3, 0.8))
            login_data = f"login={url_quote(self.email)}&password={url_quote(self.password)}&hash={self.hash_ajax}&ajax_func=login"
            r = self.client.post(f"{BASE_URL}ajax/ajax_login.php",
                content=login_data, headers=self._login_headers())

            if "pg=job" not in r.text and "location.replace" not in r.text:
                self.status = "login_failed"
                add_log(self.owner_email, f"[S{self.session_id}] Login rejeitado: {r.text[:60]}", "error")
                return False

            # Step 3: GET ?pg=job para hash_ajax atualizado
            time.sleep(random.uniform(0.5, 1.0))
            r = self.client.get(f"{BASE_URL}?pg=job", headers=self._nav_headers())
            m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
            if m:
                self.hash_ajax = m.group(1)

            # Step 4: up_data
            time.sleep(0.3)
            up_body = json.dumps({
                "ajax_func": "up_data",
                "hash_ajax": self.hash_ajax,
                "id_device": self.device_id,
                "email": self.email,
                "os_version": self.device_info["release"],
                "screen_resolution": "1080x1920",
                "locale_language": "pt",
                "locale_country": "BR",
                "data_json": json.dumps({
                    "device_id": self.device_id, "device_type": "emulator",
                    "is_emulator": True, "timestamp": int(time.time() * 1000),
                    "google_email": self.email,
                }),
            })
            try:
                self.client.post(f"{BASE_URL}ajax/ajax_data.php",
                    content=up_body, headers=self._ajax_headers())
            except Exception:
                pass

            self.status = "ready"
            add_log(self.owner_email, f"[S{self.session_id}] LOGIN OK | Hash: {self.hash_ajax[:8]}...", "success")
            return True

        except Exception as e:
            self.status = "login_failed"
            add_log(self.owner_email, f"[S{self.session_id}] Login erro: {str(e)[:80]}", "error")
            return False

    def _post_json(self, endpoint, body_dict):
        url = BASE_URL + endpoint
        body = json.dumps(body_dict)
        for attempt in range(3):
            try:
                r = self.client.post(url, content=body, headers=self._ajax_headers())
                if r.status_code == 200:
                    try:
                        return r.json()
                    except Exception:
                        return {"raw": r.text[:200]}
                elif r.status_code >= 500:
                    time.sleep(2)
                    continue
                else:
                    return None
            except Exception as e:
                if attempt < 2:
                    try:
                        self._create_client()
                    except Exception:
                        pass
                    time.sleep(2)
        return None

    def get_task(self):
        self.total_attempts += 1
        return self._post_json("ajax/ajax_views.php", {
            "ajax_func": "get_task",
            "id_device": self.device_id,
            "hash_ajax": self.hash_ajax,
        })

    def complete_task(self, id_status):
        return self._post_json("ajax/ajax_views.php", {
            "ajax_func": "complete_task",
            "id_status": str(id_status),
            "id_device": self.device_id,
            "data_json": json.dumps({"device_id": self.device_id, "device_type": "emulator", "is_emulator": True, "timestamp": int(time.time() * 1000), "google_email": self.email}),
            "hash_ajax": self.hash_ajax,
        })

    def rotate_ip(self):
        if not self.proxy_config or not self.proxy_config.get("enabled"):
            return True
        self.rotation_count += 1
        self.proxy_url = build_proxy_url(self.proxy_config, self.session_id, rotation_id=int(time.time()) % 100000 + self.rotation_count)
        self.last_rotation_time = time.time()
        # Apenas reconectar com novo proxy, mantendo PHPSESSID e hash_ajax
        try:
            self._create_client()
            self.detect_ip()
            add_log(self.owner_email, f"[S{self.session_id}] Rotacao #{self.rotation_count}: IP {self.current_ip} (BR)", "info")
            return True
        except Exception as e:
            add_log(self.owner_email, f"[S{self.session_id}] Erro na rotacao: {str(e)[:50]}", "error")
            return False

    def should_rotate(self):
        return (time.time() - self.last_rotation_time) >= IP_ROTATION_INTERVAL

    def run_cycle(self):
        user_state = get_user_state(self.owner_email)
        self.status = "getting_task"
        result = self.get_task()

        if not result:
            self.status = "error"
            self.consecutive_empty += 1
            return False

        # Resposta raw (não JSON)
        if "raw" in result:
            raw_text = result.get("raw", "")
            if "войти" in raw_text.lower() or "Авторизуйтесь" in raw_text:
                add_log(self.owner_email, f"[S{self.session_id}] Sessao expirada, relogin...", "warning")
                return self.login()
            self.status = "waiting"
            self.consecutive_empty += 1
            return False

        # Sem tarefa
        if not result.get("status") and "mess" in result:
            msg = result.get("mess", "")
            if "войти" in msg.lower() or "Попробуйте" in msg:
                add_log(self.owner_email, f"[S{self.session_id}] Sessao expirada, relogin...", "warning")
                return self.login()
            self.status = "no_task"
            self.consecutive_empty += 1
            if self.consecutive_empty % 15 == 1:
                add_log(self.owner_email, f"[S{self.session_id}] Sem tarefa ({self.consecutive_empty}x seguidas)", "warning")
            return False

        if "video_id" not in result:
            self.status = "no_task"
            self.consecutive_empty += 1
            return False

        # TAREFA ENCONTRADA!
        video_id = result["video_id"]
        timer = int(result.get("timer", 15))
        id_status = result.get("id_status", "")
        self.current_video = video_id
        self.tasks_found += 1
        self.consecutive_empty = 0

        # Filtrar tarefas longas
        if timer > MAX_TIMER_SECONDS:
            self.tasks_skipped += 1
            add_log(self.owner_email, f"[S{self.session_id}] SKIP: {video_id} (timer={timer}s > {MAX_TIMER_SECONDS}s)", "warning")
            self.current_video = None
            self.status = "skipped"
            return False

        # ASSISTINDO
        self.status = "watching"
        optimized_timer = max(int(timer * TIMER_MULTIPLIER), 4)
        time_saved = timer - optimized_timer
        add_log(self.owner_email, f"[S{self.session_id}] ASSISTINDO: {video_id} ({timer}s -> {optimized_timer}s, -{time_saved}s)", "info")

        for _ in range(optimized_timer):
            if user_state["stop_requested"]:
                return False
            time.sleep(1)

        # COMPLETANDO
        self.status = "completing"
        complete_result = self.complete_task(id_status)

        if complete_result and complete_result.get("status"):
            price = complete_result.get("price", 0)
            balance = complete_result.get("balance", "0")
            self.earned += float(price) if price else 0
            self.views += 1
            self.tasks_completed += 1
            self.status = "completed"
            self.current_video = None
            with user_state["lock"]:
                user_state["total_earned"] += float(price) if price else 0
                user_state["total_views"] += 1
            add_log(self.owner_email, f"[S{self.session_id}] GANHOU +{price} R | Saldo: {balance} R | Total sessao: {self.earned:.3f} R", "success")
            return True
        else:
            self.tasks_failed += 1
            self.status = "complete_failed"
            err = ""
            if complete_result and "mess" in complete_result:
                err = f" ({complete_result['mess'][:40]})"
            add_log(self.owner_email, f"[S{self.session_id}] FALHA completar {video_id}{err}", "error")
            return False


# ===== WORKER =====
def session_worker(session_obj):
    user_state = get_user_state(session_obj.owner_email)

    # Login com retry INFINITO (troca IP a cada tentativa)
    logged_in = False
    attempt = 0
    while not user_state["stop_requested"]:
        attempt += 1
        if session_obj.login():
            logged_in = True
            break
        # Trocar IP antes de tentar novamente (novo sessid)
        if session_obj.proxy_config and session_obj.proxy_config.get("enabled"):
            session_obj.proxy_url = build_proxy_url(
                session_obj.proxy_config, session_obj.session_id,
                rotation_id=int(time.time() * 1000) % 1000000 + attempt
            )
            add_log(session_obj.owner_email, f"[S{session_obj.session_id}] Trocando IP (tentativa {attempt})...", "warning")
        # Backoff curto: 3s nas primeiras 5, depois 10s, depois 30s
        if attempt <= 5:
            time.sleep(3)
        elif attempt <= 10:
            time.sleep(10)
        else:
            time.sleep(30)
    if not logged_in:
        session_obj.status = "stopped"
        return

    # Loop principal
    while not user_state["stop_requested"]:
        try:
            # Rotacao de IP
            if session_obj.should_rotate():
                session_obj.status = "rotating"
                if not session_obj.rotate_ip():
                    time.sleep(10)
                    if not session_obj.rotate_ip():
                        time.sleep(30)
                        continue
                session_obj.consecutive_empty = 0

            # Forcar rotacao se muitas tentativas vazias
            if session_obj.consecutive_empty >= 10:
                add_log(session_obj.owner_email, f"[S{session_obj.session_id}] {session_obj.consecutive_empty}x sem tarefa, forcando rotacao...", "warning")
                session_obj.last_rotation_time = 0
                session_obj.consecutive_empty = 0
                continue

            # Executar ciclo
            success = session_obj.run_cycle()

            if success:
                time.sleep(random.uniform(1, 2))
            else:
                if session_obj.consecutive_empty <= 3:
                    delay = random.uniform(2, 4)
                elif session_obj.consecutive_empty <= 10:
                    delay = random.uniform(4, 7)
                else:
                    delay = random.uniform(7, 12)
                for _ in range(int(delay)):
                    if user_state["stop_requested"]:
                        break
                    time.sleep(1)

        except Exception as e:
            err_msg = str(e)[:80]
            add_log(session_obj.owner_email, f"[S{session_obj.session_id}] Erro: {err_msg}", "error")
            # Se erro de conexao/SSL, trocar IP e re-logar
            if "SSL" in err_msg or "EOF" in err_msg or "disconnect" in err_msg.lower() or "timeout" in err_msg.lower():
                add_log(session_obj.owner_email, f"[S{session_obj.session_id}] Reconectando com novo IP...", "warning")
                if session_obj.proxy_config and session_obj.proxy_config.get("enabled"):
                    session_obj.proxy_url = build_proxy_url(
                        session_obj.proxy_config, session_obj.session_id,
                        rotation_id=int(time.time() * 1000) % 1000000
                    )
                time.sleep(3)
                # Re-login com novo IP
                for retry in range(5):
                    if user_state["stop_requested"]:
                        break
                    if session_obj.login():
                        session_obj.consecutive_empty = 0
                        break
                    if session_obj.proxy_config and session_obj.proxy_config.get("enabled"):
                        session_obj.proxy_url = build_proxy_url(
                            session_obj.proxy_config, session_obj.session_id,
                            rotation_id=int(time.time() * 1000) % 1000000 + retry
                        )
                    time.sleep(5)
            else:
                time.sleep(5)

    session_obj.status = "stopped"
    if session_obj.client:
        try:
            session_obj.client.close()
        except Exception:
            pass


def start_bot(email, password, num_sessions, proxy_config=None):
    user_state = get_user_state(email)
    with user_state["lock"]:
        user_state["running"] = True
        user_state["stop_requested"] = False
        user_state["sessions"] = []
        user_state["threads"] = []
        user_state["total_earned"] = 0.0
        user_state["total_views"] = 0
        user_state["logs"] = []
        user_state["start_time"] = datetime.now().strftime("%H:%M:%S")

    proxy_status = "COM PROXY (BR, HTTP/2)" if (proxy_config and proxy_config.get("enabled")) else "SEM PROXY"
    add_log(email, f"Iniciando {num_sessions} sessoes ({proxy_status})...", "info")

    threads = []
    for i in range(num_sessions):
        if user_state["stop_requested"]:
            break
        device_info = random.choice(ANDROID_DEVICES)
        device_id = generate_device_id()
        user_agent = generate_user_agent(device_info)
        identity = {"device_id": device_id, "user_agent": user_agent, "device_info": device_info}
        proxy_url = build_proxy_url(proxy_config, i + 1)

        session_obj = SeoFastSession(
            session_id=i + 1, email=email, password=password,
            owner_email=email, identity=identity,
            proxy_url=proxy_url, proxy_config=proxy_config,
        )
        with user_state["lock"]:
            user_state["sessions"].append({"id": i + 1, "obj": session_obj})

        t = threading.Thread(target=session_worker, args=(session_obj,), daemon=True)
        t.start()
        threads.append(t)
        # Escalonar inicio para nao sobrecarregar proxy (5-8s entre cada)
        time.sleep(random.uniform(5, 8))

    with user_state["lock"]:
        user_state["threads"] = threads
    add_log(email, f"Todas as {num_sessions} sessoes iniciadas!", "success")


# ===== ROTAS FLASK =====
@app.route("/")
def index():
    return render_template("index.html", allowed_domain=ALLOWED_DOMAIN)

@app.route("/api/start", methods=["POST"])
def api_start():
    data = request.json
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()
    num_sessions = int(data.get("num_sessions", 50))
    proxy_config = {
        "enabled": data.get("proxy_enabled", False),
        "login": data.get("proxy_login", "").strip(),
        "password": data.get("proxy_password", "").strip(),
        "host": data.get("proxy_host", "gw.dataimpulse.com").strip(),
        "country": data.get("proxy_country", "br").strip().lower(),
    }
    if not email or not password:
        return jsonify({"error": "Email e senha sao obrigatorios!"}), 400
    if num_sessions < 1 or num_sessions > 200:
        return jsonify({"error": "Numero de sessoes deve ser entre 1 e 200"}), 400
    user_state = get_user_state(email)
    active_threads = [t for t in user_state.get("threads", []) if t.is_alive()]
    if active_threads:
        # Se ja tem threads ativas, parar as antigas antes de iniciar novas
        add_log(email, f"Parando {len(active_threads)} sessoes antigas antes de reiniciar...", "warning")
        with user_state["lock"]:
            user_state["stop_requested"] = True
        # Aguardar ate 10s para as threads pararem
        timeout_stop = time.time() + 10
        while time.time() < timeout_stop:
            still_alive = [t for t in user_state.get("threads", []) if t.is_alive()]
            if not still_alive:
                break
            time.sleep(0.5)
        # Resetar estado
        with user_state["lock"]:
            user_state["stop_requested"] = False
            user_state["threads"] = []
            user_state["sessions"] = []
    with online_users_lock:
        online_users[email] = {"started_at": datetime.now().strftime("%H:%M:%S"), "sessions": num_sessions, "last_seen": time.time()}
    threading.Thread(target=start_bot, args=(email, password, num_sessions, proxy_config), daemon=True).start()
    save_active_bots(email, password, num_sessions, proxy_config)
    return jsonify({"status": "started", "sessions": num_sessions})

@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.json or {}
    email = data.get("email", "").strip()
    if not email:
        return jsonify({"error": "Email necessario"}), 400
    user_state = get_user_state(email)
    with user_state["lock"]:
        user_state["stop_requested"] = True
        user_state["running"] = False
    with online_users_lock:
        online_users.pop(email, None)
    remove_active_bot(email)
    add_log(email, "Parando todas as sessoes...", "warning")
    return jsonify({"status": "stopping"})

@app.route("/api/status")
def api_status():
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"running": False, "total_earned": 0.0, "total_views": 0, "sessions": [], "logs": [], "start_time": None, "active_threads": 0})
    user_state = get_user_state(email)
    with user_state["lock"]:
        active_threads = [t for t in user_state.get("threads", []) if t.is_alive()]
        is_running = len(active_threads) > 0
        active_sessions = []
        for s in user_state["sessions"]:
            obj = s["obj"]
            active_sessions.append({
                "id": s["id"],
                "device_name": f"{obj.device_info['brand']} {obj.device_info['model']}",
                "status": obj.status,
                "earned": round(obj.earned, 4),
                "views": obj.views,
                "current_video": obj.current_video,
                "ip": obj.current_ip or "-",
                "country": "BR",
                "rotations": obj.rotation_count,
            })
        return jsonify({
            "running": is_running,
            "total_earned": round(user_state["total_earned"], 4),
            "total_views": user_state["total_views"],
            "sessions": active_sessions,
            "logs": user_state["logs"][-100:],
            "start_time": user_state["start_time"],
            "active_threads": len(active_threads),
        })

@app.route("/api/online")
def api_online():
    users_list = []
    with online_users_lock:
        for email, info in list(online_users.items()):
            has_activity = False
            if email in users_state:
                ustate = users_state[email]
                active_threads = [t for t in ustate.get("threads", []) if t.is_alive()]
                if active_threads or ustate.get("sessions"):
                    has_activity = True
            if not has_activity:
                active = load_active_bots()
                if email in active:
                    has_activity = True
            if not has_activity:
                continue
            user_earned = 0.0
            user_views = 0
            if email in users_state:
                ustate = users_state[email]
                user_earned = round(ustate.get("total_earned", 0.0), 4)
                user_views = ustate.get("total_views", 0)
            users_list.append({"email": email, "started_at": info.get("started_at", "-"), "sessions": info.get("sessions", 0), "earned": user_earned, "views": user_views})
    return jsonify({"online_count": len(users_list), "users": users_list})

@app.route("/api/heartbeat", methods=["POST"])
def api_heartbeat():
    data = request.json or {}
    email = data.get("email", "").strip()
    if email:
        with online_users_lock:
            if email in online_users:
                online_users[email]["last_seen"] = time.time()
    return jsonify({"ok": True})

# === AUTO-RESUME ===
def _delayed_auto_resume():
    time.sleep(10)
    auto_resume_bots()

threading.Thread(target=_delayed_auto_resume, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
