"""
SeoFast Multi-Session Bot - Web Application (Multi-User)
Flask backend com bot SeoFast integrado.
Usa httpx com HTTP/2 para resolver problemas de TLS/403.
Login automatico + coleta de hash_ajax.
Multiplas sessoes HTTP paralelas com login independente.
CADA USUARIO TEM SEU PROPRIO ESTADO ISOLADO.
CADA SESSAO TEM SEU PROPRIO IP (via proxy), USER-AGENT E DEVICE ID.

v4: Migrado para httpx (HTTP/2) - corrige erro 403 no login.
    IP fixo Brasil. Logs detalhados. Timer otimizado 60%.
"""

import hashlib
import json
import os
import random
import re
import string
import threading
import time
import warnings
from datetime import datetime
from urllib.parse import quote as url_quote

import httpx
import httpx_socks
from flask import Flask, render_template, request, jsonify, Response

warnings.filterwarnings("ignore")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(32).hex()

# ===== RAILWAY / REVERSE PROXY SUPPORT =====
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

BLOCKED_REFERERS = [
    'saveweb2zip.com', 'web2zip.com', 'webarchive', 'archive.org',
]


@app.before_request
def anti_scraping_guard():
    ua = (request.headers.get('User-Agent', '') or '').lower()
    referer = (request.headers.get('Referer', '') or '').lower()

    for bot in BLOCKED_BOTS:
        if bot in ua:
            return Response('', status=403)

    for ref in BLOCKED_REFERERS:
        if ref in referer:
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

# === CONFIGURACOES DE OTIMIZACAO ===
TIMER_MULTIPLIER = 0.60  # Usar 60% do timer (testado e aceito pelo servidor)
MAX_TIMER_SECONDS = 60   # Rejeitar tarefas com timer > 60s
PROXY_PORT = 824         # Porta SOCKS5 do DataImpulse

# === IP FIXO BRASIL ===
PROXY_COUNTRY = "br"  # Usar apenas Brasil

# === ROTACAO DE IP ===
IP_ROTATION_INTERVAL = 900  # Rotacionar IP a cada 15 minutos (900 segundos)


# ===== GERADORES DE IDENTIDADE UNICA POR SESSAO =====

ANDROID_DEVICES = [
    {"brand": "samsung", "model": "SM-A546E", "device": "a54x", "hardware": "exynos1380", "product": "a54xns", "board": "s5e8835", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-G960N", "device": "starlte", "hardware": "exynos9810", "product": "starltexx", "board": "exynos9810", "build": "PQ3A.190605.07021633", "sdk": 28, "release": "9"},
    {"brand": "samsung", "model": "SM-A525F", "device": "a52q", "hardware": "qcom", "product": "a52qnsxx", "board": "atoll", "build": "SP1A.210812.016", "sdk": 31, "release": "12"},
    {"brand": "samsung", "model": "SM-G991B", "device": "o1s", "hardware": "exynos2100", "product": "o1sxeea", "board": "exynos2100", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-A336B", "device": "a33x", "hardware": "exynos1280", "product": "a33xxx", "board": "s5e8825", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "samsung", "model": "SM-G998B", "device": "p3s", "hardware": "exynos2100", "product": "p3sxeea", "board": "exynos2100", "build": "SP2A.220405.004", "sdk": 32, "release": "12L"},
    {"brand": "xiaomi", "model": "Redmi Note 12", "device": "tapas", "hardware": "qcom", "product": "tapas_global", "board": "bengal", "build": "TKQ1.221114.001", "sdk": 33, "release": "13"},
    {"brand": "xiaomi", "model": "POCO X5 Pro", "device": "redwood", "hardware": "qcom", "product": "redwood_global", "board": "taro", "build": "TKQ1.221114.001", "sdk": 33, "release": "13"},
    {"brand": "xiaomi", "model": "Redmi Note 11", "device": "spes", "hardware": "qcom", "product": "spes_global", "board": "bengal", "build": "SKQ1.211019.001", "sdk": 31, "release": "12"},
    {"brand": "google", "model": "Pixel 7", "device": "panther", "hardware": "tensor", "product": "panther", "board": "gs201", "build": "TQ3A.230901.001", "sdk": 34, "release": "14"},
    {"brand": "google", "model": "Pixel 6a", "device": "bluejay", "hardware": "tensor", "product": "bluejay", "board": "gs101", "build": "TQ3A.230705.001", "sdk": 33, "release": "13"},
    {"brand": "oneplus", "model": "CPH2449", "device": "OP5958L1", "hardware": "qcom", "product": "OP5958L1", "board": "taro", "build": "TP1A.220905.001", "sdk": 33, "release": "13"},
    {"brand": "realme", "model": "RMX3630", "device": "RE58B2", "hardware": "mt6833", "product": "RE58B2", "board": "mt6833", "build": "TP1A.220905.001", "sdk": 33, "release": "13"},
    {"brand": "huawei", "model": "MAR-LX1A", "device": "HWMAR", "hardware": "kirin710", "product": "MAR-LX1A", "board": "MAR", "build": "HUAWEIMAR-L21A", "sdk": 29, "release": "10"},
    {"brand": "motorola", "model": "moto g(60)", "device": "hanoip", "hardware": "qcom", "product": "hanoip_retail", "board": "hanoip", "build": "S3RHS32.20-42-6-2", "sdk": 31, "release": "12"},
    {"brand": "oppo", "model": "CPH2387", "device": "OP5961L1", "hardware": "qcom", "product": "OP5961L1", "board": "bengal", "build": "TP1A.220905.001", "sdk": 32, "release": "12"},
    {"brand": "vivo", "model": "V2203", "device": "PD2203F_EX", "hardware": "qcom", "product": "PD2203F_EX", "board": "bengal", "build": "TP1A.220624.014", "sdk": 33, "release": "13"},
    {"brand": "nokia", "model": "Nokia G21", "device": "RGR_sprout", "hardware": "mt6769", "product": "RGR_sprout", "board": "RGR", "build": "SP1A.210812.016", "sdk": 31, "release": "12"},
    {"brand": "asus", "model": "ASUS_I006D", "device": "ASUS_I006D", "hardware": "qcom", "product": "WW_I006D", "board": "lahaina", "build": "SKQ1.210821.001", "sdk": 32, "release": "12"},
    {"brand": "sony", "model": "XQ-CQ72", "device": "pdx225", "hardware": "qcom", "product": "pdx225", "board": "taro", "build": "TQ3A.230901.001", "sdk": 33, "release": "13"},
]

CHROME_VERSIONS = [
    "120.0.6099.144", "121.0.6167.101", "122.0.6261.64", "123.0.6312.99",
    "124.0.6367.82", "125.0.6422.113", "126.0.6478.72", "127.0.6533.88",
    "128.0.6613.127", "129.0.6668.54", "130.0.6723.86", "131.0.6778.39",
    "132.0.6834.15", "133.0.6917.71", "134.0.6998.39", "135.0.7049.38",
    "136.0.7103.60", "137.0.7151.22", "138.0.7204.179",
]


def generate_device_id():
    """Gera um device_id unico aleatorio no formato bluestacks_XXXXXXXX."""
    hex_chars = string.hexdigits[:16]
    random_hex = ''.join(random.choice(hex_chars) for _ in range(16))
    return f"bluestacks_{random_hex}"


def generate_user_agent(device_info):
    """Gera um User-Agent unico baseado no dispositivo."""
    chrome_ver = random.choice(CHROME_VERSIONS)
    android_ver = device_info["release"]
    model = device_info["model"]
    build = device_info["build"]
    return (
        f"Mozilla/5.0 (Linux; Android {android_ver}; {model} Build/{build}; wv) "
        f"AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
        f"Chrome/{chrome_ver} Mobile Safari/537.36 SeoFast-App/1.0"
    )


def generate_session_identity(session_id):
    """Gera identidade unica para uma sessao: device_id, user_agent, device_info."""
    device_info = random.choice(ANDROID_DEVICES)
    device_id = generate_device_id()
    user_agent = generate_user_agent(device_info)
    return {
        "device_id": device_id,
        "user_agent": user_agent,
        "device_info": device_info,
    }


def generate_app_token(device_id):
    raw = f"{device_id}:{PACKAGE_NAME}:{APP_SECRET}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


# ===== MULTI-USER STATE MANAGEMENT =====

users_state = {}
users_lock = threading.Lock()

PERSISTENCE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "active_bots.json")


def save_active_bots(email, password, num_sessions, proxy_config):
    """Salva uma conta ativa no arquivo de persistencia."""
    try:
        data = load_active_bots()
        data[email] = {
            "email": email,
            "password": password,
            "num_sessions": num_sessions,
            "proxy_config": proxy_config,
            "started_at": datetime.now().isoformat(),
        }
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[PERSIST] Erro ao salvar: {e}")


def remove_active_bot(email):
    """Remove uma conta do arquivo de persistencia."""
    try:
        data = load_active_bots()
        data.pop(email, None)
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[PERSIST] Erro ao remover: {e}")


def load_active_bots():
    """Carrega contas ativas do arquivo de persistencia."""
    try:
        if os.path.exists(PERSISTENCE_FILE):
            with open(PERSISTENCE_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"[PERSIST] Erro ao carregar: {e}")
    return {}


def auto_resume_bots():
    """Relanca automaticamente todas as contas ativas apos restart."""
    data = load_active_bots()
    if not data:
        print("[AUTO-RESUME] Nenhuma conta para resumir.")
        return

    print(f"[AUTO-RESUME] Resumindo {len(data)} conta(s) ativas...")
    for email, info in data.items():
        try:
            password = info["password"]
            num_sessions = info.get("num_sessions", 50)
            proxy_config = info.get("proxy_config", {})

            user_state = get_user_state(email)
            active_threads = [t for t in user_state.get("threads", []) if t.is_alive()]
            if active_threads:
                print(f"[AUTO-RESUME] {email} ja esta rodando, pulando.")
                continue

            with online_users_lock:
                online_users[email] = {
                    "started_at": datetime.now().strftime("%H:%M:%S"),
                    "sessions": num_sessions,
                    "last_seen": time.time()
                }

            threading.Thread(
                target=start_bot,
                args=(email, password, num_sessions, proxy_config),
                daemon=True
            ).start()

            print(f"[AUTO-RESUME] {email} iniciado com {num_sessions} sessoes.")
            time.sleep(2)
        except Exception as e:
            print(f"[AUTO-RESUME] Erro ao resumir {email}: {e}")


def get_user_state(email):
    """Obtem ou cria o estado isolado de um usuario."""
    with users_lock:
        if email not in users_state:
            users_state[email] = {
                "running": False,
                "sessions": [],
                "threads": [],
                "total_earned": 0.0,
                "total_views": 0,
                "logs": [],
                "start_time": None,
                "stop_requested": False,
                "lock": threading.Lock(),
            }
        return users_state[email]


def add_log_for_user(email, message, level="info"):
    """Adiciona log ao estado do usuario especifico."""
    state = get_user_state(email)
    with state["lock"]:
        timestamp = datetime.now().strftime("%H:%M:%S")
        state["logs"].append({"time": timestamp, "message": message, "level": level})
        if len(state["logs"]) > 500:
            state["logs"] = state["logs"][-500:]


online_users = {}
online_users_lock = threading.Lock()


# ===== FUNCOES DE PROXY =====

def build_proxy_url(proxy_config, session_id, rotation_id=None):
    """
    Constroi a URL do proxy SOCKS5 para uma sessao especifica.
    Sempre usa Brasil (PROXY_COUNTRY).
    """
    if not proxy_config or not proxy_config.get("enabled"):
        return None

    login = proxy_config.get("login", "")
    password = proxy_config.get("password", "")
    host = proxy_config.get("host", "gw.dataimpulse.com")

    if not login or not password:
        return None

    rot_id = rotation_id or int(time.time()) % 100000
    sessid_value = f"sf{session_id}r{rot_id}"

    # Formato DataImpulse: login__cr.COUNTRY__sd.SESSID
    login_with_params = f"{login}__cr.{PROXY_COUNTRY}__sd.{sessid_value}"

    return f"socks5://{login_with_params}:{password}@{host}:{PROXY_PORT}"


# ===== CLASSE DO BOT (httpx) =====

class SeoFastSession:
    """Sessao individual com httpx - faz login proprio e opera independente."""

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
        self.earned = 0.0
        self.rotation_count = 0
        self.last_rotation_time = time.time()
        self.current_country = PROXY_COUNTRY
        self.views = 0
        self.status = "idle"
        self.current_video = None
        self.current_ip = None
        self.http = None  # httpx.Client
        self._use_http2 = True  # Tenta HTTP/2 primeiro, muda para False se falhar
        # === ESTATISTICAS ===
        self.total_attempts = 0
        self.tasks_found = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.tasks_skipped = 0
        self.no_task_count = 0
        self.consecutive_empty = 0
        self.session_start_time = time.time()
        self.last_task_time = None

    def _get_chrome_major(self):
        if "Chrome/" in self.user_agent:
            return self.user_agent.split("Chrome/")[1].split(".")[0]
        return "138"

    def _get_nav_headers(self):
        """Headers para navegacao WebView (GET pages)."""
        chrome_major = self._get_chrome_major()
        headers = {
            "host": "seo-fast.bz",
            "sec-ch-ua": f'"Not)A;Brand";v="8", "Chromium";v="{chrome_major}", "Android WebView";v="{chrome_major}"',
            "sec-ch-ua-mobile": "?1",
            "sec-ch-ua-platform": '"Android"',
            "upgrade-insecure-requests": "1",
            "user-agent": self.user_agent,
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "x-app-token": self.app_token,
            "x-app-version": APP_VERSION,
            "x-device-id": self.device_id,
            "x-requested-with": PACKAGE_NAME,
            "sec-fetch-site": "none",
            "sec-fetch-mode": "navigate",
            "sec-fetch-user": "?1",
            "sec-fetch-dest": "document",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "priority": "u=0, i",
        }
        if self.phpsessid:
            headers["cookie"] = f"PHPSESSID={self.phpsessid}"
        return headers

    def _get_login_headers(self):
        """Headers para POST login (WebView AJAX form-encoded)."""
        chrome_major = self._get_chrome_major()
        headers = {
            "host": "seo-fast.bz",
            "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
            "x-app-token": self.app_token,
            "sec-ch-ua-platform": '"Android"',
            "x-device-id": self.device_id,
            "sec-ch-ua": f'"Not)A;Brand";v="8", "Chromium";v="{chrome_major}", "Android WebView";v="{chrome_major}"',
            "sec-ch-ua-mobile": "?1",
            "x-app-version": APP_VERSION,
            "x-requested-with": "XMLHttpRequest",
            "accept": "*/*",
            "user-agent": self.user_agent,
            "origin": "https://seo-fast.bz",
            "sec-fetch-site": "same-origin",
            "sec-fetch-mode": "cors",
            "sec-fetch-dest": "empty",
            "referer": "https://seo-fast.bz/webapp/?pg=login",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "priority": "u=1, i",
        }
        if self.phpsessid:
            headers["cookie"] = f"PHPSESSID={self.phpsessid}"
        return headers

    def _get_ajax_headers(self):
        """Headers para AJAX nativo (get_task, complete_task, up_data)."""
        headers = {
            "host": "seo-fast.bz",
            "user-agent": self.user_agent,
            "x-app-token": self.app_token,
            "x-app-version": APP_VERSION,
            "x-device-id": self.device_id,
            "accept": "application/json, text/plain, */*",
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "origin": "https://seo-fast.bz",
            "referer": "https://seo-fast.bz/",
            "x-requested-with": "XMLHttpRequest",
            "content-type": "application/json; charset=utf-8",
            "accept-encoding": "gzip",
        }
        if self.phpsessid:
            headers["cookie"] = f"PHPSESSID={self.phpsessid}"
        return headers

    def _create_http(self, use_http2=True):
        """Cria cliente httpx com proxy SOCKS5. Tenta HTTP/2, fallback para HTTP/1.1."""
        if self.proxy_url:
            transport = httpx_socks.SyncProxyTransport.from_url(
                self.proxy_url, http2=use_http2
            )
            client = httpx.Client(
                transport=transport,
                verify=False,
                timeout=30.0,
                follow_redirects=True,
            )
        else:
            client = httpx.Client(
                http2=use_http2,
                verify=False,
                timeout=30.0,
                follow_redirects=True,
            )
        return client

    def detect_ip(self):
        """Detecta o IP real da sessao via proxy."""
        try:
            r = self.http.get("https://api.ipify.org/?format=json")
            if r.status_code == 200:
                self.current_ip = r.json().get("ip", "?")
        except Exception:
            self.current_ip = "erro"

    def login(self):
        """Faz login e obtem PHPSESSID + hash_ajax usando httpx."""
        self.status = "logging_in"

        # Fechar cliente antigo se existir
        if self.http:
            try:
                self.http.close()
            except Exception:
                pass

        # Tentar HTTP/2 primeiro, fallback para HTTP/1.1
        last_error = None
        for use_h2 in [self._use_http2, not self._use_http2]:
            try:
                self.http = self._create_http(use_http2=use_h2)
                # Detectar IP
                if self.proxy_url:
                    self.detect_ip()
                    if use_h2:
                        add_log_for_user(self.owner_email,
                            f"[S{self.session_id}] IP: {self.current_ip} | UA: {self.device_info['brand']} {self.device_info['model']}",
                            "info")
                # Testar conexao com GET
                headers = self._get_nav_headers()
                r = self.http.get(BASE_URL, headers=headers)
                self._use_http2 = use_h2  # Lembrar qual funcionou
                break  # Sucesso, sair do loop
            except Exception as e:
                last_error = e
                if self.http:
                    try:
                        self.http.close()
                    except Exception:
                        pass
                if not use_h2:
                    # Ambos falharam
                    self.status = "login_failed"
                    err_msg = str(last_error)[:80]
                    add_log_for_user(self.owner_email,
                        f"[S{self.session_id}] Login erro: {err_msg}",
                        "error")
                    return False
                # HTTP/2 falhou, tentar HTTP/1.1
                time.sleep(1)
                continue

        try:

            # Extrair PHPSESSID do header set-cookie
            for key, value in r.headers.multi_items():
                if key.lower() == "set-cookie" and "PHPSESSID" in value:
                    match = re.search(r"PHPSESSID=([^;]+)", value)
                    if match:
                        self.phpsessid = match.value if hasattr(match, 'value') else match.group(1)

            # Tambem verificar cookies do httpx
            for cookie in self.http.cookies.jar:
                if cookie.name == "PHPSESSID":
                    self.phpsessid = cookie.value

            # Buscar hash_ajax na resposta (pode ter sido redirecionado para login)
            m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
            self.hash_ajax = m.group(1) if m else None

            if not self.hash_ajax:
                # Tentar GET ?pg=login explicitamente
                time.sleep(random.uniform(0.3, 0.8))
                headers = self._get_nav_headers()
                r = self.http.get(f"{BASE_URL}?pg=login", headers=headers)
                m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
                self.hash_ajax = m.group(1) if m else None

            if not self.hash_ajax:
                self.status = "login_failed"
                add_log_for_user(self.owner_email,
                    f"[S{self.session_id}] FALHA: hash_ajax nao encontrado (status={r.status_code})",
                    "error")
                return False

            # Step 2: POST login
            time.sleep(random.uniform(0.3, 0.8))
            login_headers = self._get_login_headers()
            login_data = f"login={url_quote(self.email)}&password={url_quote(self.password)}&hash={self.hash_ajax}&ajax_func=login"

            r = self.http.post(
                f"{BASE_URL}ajax/ajax_login.php",
                content=login_data,
                headers=login_headers,
            )

            if "pg=job" not in r.text and "location.replace" not in r.text:
                self.status = "login_failed"
                resp_preview = r.text[:80] if r.text else "vazio"
                add_log_for_user(self.owner_email,
                    f"[S{self.session_id}] Login rejeitado: {resp_preview}",
                    "error")
                return False

            # Step 3: GET ?pg=job para obter hash_ajax atualizado
            time.sleep(random.uniform(0.5, 1.0))
            headers = self._get_nav_headers()
            r = self.http.get(f"{BASE_URL}?pg=job", headers=headers)
            m = re.search(r"var\s+hash_ajax\s*=\s*'([a-f0-9]+)'", r.text)
            if m:
                self.hash_ajax = m.group(1)

            # Atualizar PHPSESSID
            for cookie in self.http.cookies.jar:
                if cookie.name == "PHPSESSID":
                    self.phpsessid = cookie.value

            # Step 4: up_data - registrar dispositivo
            time.sleep(random.uniform(0.5, 1.0))
            up_data_body = json.dumps({
                "ajax_func": "up_data",
                "hash_ajax": self.hash_ajax,
                "id_device": self.device_id,
                "email": self.email,
                "os_version": self.device_info["release"],
                "screen_resolution": "1080x1920",
                "locale_language": "pt",
                "locale_country": "BR",
                "data_json": json.dumps({
                    "device_id": self.device_id,
                    "device_type": "emulator",
                    "is_emulator": True,
                    "is_secure": False,
                    "timestamp": int(time.time() * 1000),
                    "emulator_type": "bluestacks",
                    "emulator_details": {
                        "build_properties": False, "hardware": False, "files": False,
                        "memu": False, "bluestacks": True, "nox": False,
                        "genymotion": False, "google_emulator": False, "masking_detected": True,
                    },
                    "google_email": self.email,
                    "hardware": {
                        "brand": self.device_info["brand"], "model": self.device_info["model"],
                        "device": self.device_info["device"], "hardware": self.device_info["hardware"],
                        "manufacturer": self.device_info["brand"], "product": self.device_info["product"],
                        "board": self.device_info["board"],
                    },
                    "os": {"sdk_int": self.device_info["sdk"], "release": self.device_info["release"], "incremental": self.device_info["build"]},
                    "display": {"width_px": 1080, "height_px": 1920, "density_dpi": 480, "density": 3},
                    "locale": {"language": "pt", "country": "BR", "variant": ""},
                    "timezone": "America/Sao_Paulo",
                    "extra": {
                        "fingerprint": f"Android/aosp_marlin/marlin:{self.device_info['release']}/{self.device_info['build']}/3793265:user/release-keys",
                        "tags": "release-keys", "type": "user", "user": "build", "host": "ubuntu",
                    },
                    "masking_detected": True, "masking_evidence": {},
                }),
            })
            ajax_headers = self._get_ajax_headers()
            self.http.post(f"{BASE_URL}ajax/ajax_data.php", content=up_data_body, headers=ajax_headers)

            self.status = "ready"
            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] LOGIN OK | Hash: {self.hash_ajax[:8]}...",
                "success")
            return True

        except Exception as e:
            self.status = "login_failed"
            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] Login erro: {str(e)[:80]}",
                "error")
            return False

    def _post_json(self, endpoint, body_dict, max_retries=3):
        """Envia POST JSON via httpx."""
        url = BASE_URL + endpoint
        headers = self._get_ajax_headers()
        body = json.dumps(body_dict)

        for attempt in range(1, max_retries + 1):
            try:
                resp = self.http.post(url, content=body, headers=headers)
                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return {"raw": resp.text[:200]}
                elif resp.status_code >= 500:
                    time.sleep(2 * attempt)
                    continue
                else:
                    return None
            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError, httpx.ConnectTimeout):
                # Reconectar
                try:
                    self.http.close()
                except Exception:
                    pass
                self.http = self._create_http(use_http2=self._use_http2)
                time.sleep(2 * attempt)
                continue
            except Exception:
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                    continue
                return None
        return None

    def get_task(self):
        """Busca tarefa usando JSON."""
        self.total_attempts += 1
        body = {
            "ajax_func": "get_task",
            "id_device": self.device_id,
            "hash_ajax": self.hash_ajax,
        }
        return self._post_json("ajax/ajax_views.php", body)

    def complete_task(self, id_status):
        """Completa tarefa usando JSON."""
        device_json = json.dumps({
            "device_id": self.device_id,
            "device_type": "emulator",
            "is_emulator": True,
            "is_secure": False,
            "timestamp": int(time.time() * 1000),
            "emulator_type": "bluestacks",
            "emulator_details": {
                "build_properties": False, "hardware": False, "files": False,
                "memu": False, "bluestacks": True, "nox": False,
                "genymotion": False, "google_emulator": False, "masking_detected": True,
            },
            "google_email": self.email,
            "hardware": {
                "brand": self.device_info["brand"], "model": self.device_info["model"],
                "device": self.device_info["device"], "hardware": self.device_info["hardware"],
                "manufacturer": self.device_info["brand"], "product": self.device_info["product"],
                "board": self.device_info["board"],
            },
            "os": {"sdk_int": self.device_info["sdk"], "release": self.device_info["release"], "incremental": self.device_info["build"]},
            "display": {"width_px": 1080, "height_px": 1920, "density_dpi": 480, "density": 3},
            "locale": {"language": "pt", "country": "BR", "variant": ""},
            "timezone": "America/Sao_Paulo",
            "extra": {
                "fingerprint": f"Android/aosp_marlin/marlin:{self.device_info['release']}/{self.device_info['build']}/3793265:user/release-keys",
                "tags": "release-keys", "type": "user", "user": "build", "host": "ubuntu",
            },
            "masking_detected": True, "masking_evidence": {},
        })
        body = {
            "ajax_func": "complete_task",
            "id_status": str(id_status),
            "id_device": self.device_id,
            "data_json": device_json,
            "hash_ajax": self.hash_ajax,
        }
        return self._post_json("ajax/ajax_views.php", body)

    def rotate_ip(self):
        """Rotaciona o IP gerando novo sessid (novo IP do Brasil)."""
        if not self.proxy_config or not self.proxy_config.get("enabled"):
            return True

        self.rotation_count += 1

        # Gerar novo proxy URL com novo sessid = novo IP
        new_proxy_url = build_proxy_url(
            self.proxy_config,
            self.session_id,
            rotation_id=int(time.time()) % 100000
        )
        self.proxy_url = new_proxy_url
        self.last_rotation_time = time.time()

        # Fechar conexao antiga
        if self.http:
            try:
                self.http.close()
            except Exception:
                pass

        add_log_for_user(self.owner_email,
            f"[S{self.session_id}] Rotacao #{self.rotation_count}: novo IP (BR)",
            "info")

        # Refazer login com novo IP
        return self.login()

    def should_rotate(self):
        """Verifica se esta na hora de rotacionar o IP."""
        elapsed = time.time() - self.last_rotation_time
        return elapsed >= IP_ROTATION_INTERVAL

    def run_cycle(self):
        """Executa um ciclo: buscar tarefa -> assistir -> completar."""
        user_state = get_user_state(self.owner_email)
        self.status = "getting_task"
        result = self.get_task()

        if not result:
            self.status = "error"
            self.no_task_count += 1
            self.consecutive_empty += 1
            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] Erro de conexao ao buscar tarefa",
                "error")
            return False

        # Se veio resposta raw (nao JSON valido)
        if "raw" in result and not result.get("status") and "video_id" not in result:
            raw_text = result.get("raw", "")
            if "войти" in raw_text.lower() or "login" in raw_text.lower() or "Авторизуйтесь" in raw_text:
                self.status = "relogging"
                add_log_for_user(self.owner_email,
                    f"[S{self.session_id}] Sessao expirada, refazendo login...",
                    "warning")
                return self.login()
            self.status = "waiting"
            self.no_task_count += 1
            self.consecutive_empty += 1
            return False

        if not result.get("status") and "mess" in result:
            msg = result.get("mess", "")
            if "войти" in msg.lower() or "Попробуйте" in msg or "Авторизуйтесь" in msg:
                self.status = "relogging"
                add_log_for_user(self.owner_email,
                    f"[S{self.session_id}] Sessao expirada, refazendo login...",
                    "warning")
                return self.login()
            elif "нет заданий" in msg.lower() or "Ожидание" in msg:
                self.status = "no_task"
                self.no_task_count += 1
                self.consecutive_empty += 1
                # Log a cada 10 tentativas vazias para nao poluir
                if self.consecutive_empty % 10 == 1:
                    add_log_for_user(self.owner_email,
                        f"[S{self.session_id}] Sem tarefa ({self.consecutive_empty}x seguidas)",
                        "warning")
            else:
                self.status = "waiting"
                self.consecutive_empty += 1
            return False

        if "video_id" not in result:
            self.status = "no_task"
            self.no_task_count += 1
            self.consecutive_empty += 1
            return False

        # === TAREFA ENCONTRADA! ===
        video_id = result["video_id"]
        timer = int(result.get("timer", 15))
        id_status = result.get("id_status", "")
        self.current_video = video_id
        self.tasks_found += 1
        self.consecutive_empty = 0
        self.last_task_time = time.time()

        # Filtro de tarefas longas
        if timer > MAX_TIMER_SECONDS:
            self.tasks_skipped += 1
            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] SKIP: {video_id} (timer={timer}s > {MAX_TIMER_SECONDS}s)",
                "warning")
            self.current_video = None
            self.status = "skipped"
            return False

        # === ASSISTINDO VIDEO ===
        self.status = "watching"
        optimized_timer = max(int(timer * TIMER_MULTIPLIER), 5)
        time_saved = timer - optimized_timer

        add_log_for_user(self.owner_email,
            f"[S{self.session_id}] ASSISTINDO: {video_id} ({timer}s -> {optimized_timer}s, -{time_saved}s)",
            "info")

        for _ in range(optimized_timer):
            if user_state["stop_requested"]:
                return False
            time.sleep(1)

        # === COMPLETANDO ===
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

            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] GANHOU +{price} R | Saldo: {balance} R | Total sessao: {self.earned:.3f} R",
                "success")
            return True
        else:
            self.tasks_failed += 1
            self.status = "complete_failed"
            err_msg = ""
            if complete_result and "mess" in complete_result:
                err_msg = f" ({complete_result['mess'][:40]})"
            add_log_for_user(self.owner_email,
                f"[S{self.session_id}] FALHA ao completar {video_id}{err_msg}",
                "error")
            return False


# ===== WORKER =====

def session_worker(session_obj):
    user_state = get_user_state(session_obj.owner_email)

    if not session_obj.login():
        add_log_for_user(session_obj.owner_email,
            f"[S{session_obj.session_id}] Login falhou! Tentando novamente em 10s...",
            "error")
        # Retry login 3 vezes
        for retry in range(3):
            time.sleep(10)
            if user_state["stop_requested"]:
                session_obj.status = "stopped"
                return
            if session_obj.login():
                break
        else:
            session_obj.status = "login_failed"
            add_log_for_user(session_obj.owner_email,
                f"[S{session_obj.session_id}] Login falhou 3x, sessao encerrada.",
                "error")
            return

    while not user_state["stop_requested"]:
        try:
            # === ROTACAO AUTOMATICA DE IP ===
            if session_obj.should_rotate():
                session_obj.status = "rotating"
                if not session_obj.rotate_ip():
                    add_log_for_user(session_obj.owner_email,
                        f"[S{session_obj.session_id}] Falha na rotacao, tentando novamente...",
                        "error")
                    time.sleep(5)
                    if not session_obj.rotate_ip():
                        # Se falhar 2x, esperar mais
                        time.sleep(15)
                    continue
                session_obj.consecutive_empty = 0

            success = session_obj.run_cycle()
            if not success:
                if session_obj.status == "login_failed":
                    # Tentar re-login
                    time.sleep(10)
                    if not session_obj.login():
                        break

                # Espera adaptativa
                if session_obj.consecutive_empty <= 3:
                    delay = random.uniform(2, 4)
                elif session_obj.consecutive_empty <= 10:
                    delay = random.uniform(4, 7)
                elif session_obj.consecutive_empty <= 20:
                    delay = random.uniform(7, 12)
                else:
                    # Forcar rotacao de IP apos muitas tentativas vazias
                    add_log_for_user(session_obj.owner_email,
                        f"[S{session_obj.session_id}] {session_obj.consecutive_empty}x sem tarefa, forcando rotacao...",
                        "warning")
                    session_obj.last_rotation_time = 0
                    session_obj.consecutive_empty = 0
                    delay = 2

                for _ in range(int(delay)):
                    if user_state["stop_requested"]:
                        break
                    time.sleep(1)
            else:
                # Apos sucesso, espera curta
                delay = random.uniform(1, 2)
                for _ in range(int(delay)):
                    if user_state["stop_requested"]:
                        break
                    time.sleep(1)
        except Exception as e:
            add_log_for_user(session_obj.owner_email,
                f"[S{session_obj.session_id}] Erro: {str(e)[:60]}",
                "error")
            time.sleep(5)

    session_obj.status = "stopped"
    if session_obj.http:
        try:
            session_obj.http.close()
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

    proxy_status = "COM PROXY (BR)" if (proxy_config and proxy_config.get("enabled")) else "SEM PROXY"
    add_log_for_user(email, f"Iniciando {num_sessions} sessoes ({proxy_status})...", "info")

    threads = []
    for i in range(num_sessions):
        identity = generate_session_identity(i + 1)
        proxy_url = build_proxy_url(proxy_config, i + 1)

        session_obj = SeoFastSession(
            session_id=i + 1,
            email=email,
            password=password,
            owner_email=email,
            identity=identity,
            proxy_url=proxy_url,
            proxy_config=proxy_config,
        )

        with user_state["lock"]:
            user_state["sessions"].append({
                "id": i + 1,
                "device_id": identity["device_id"],
                "device_name": f"{identity['device_info']['brand']} {identity['device_info']['model']}",
                "status": "starting",
                "obj": session_obj,
            })

        t = threading.Thread(target=session_worker, args=(session_obj,), daemon=True)
        t.start()
        threads.append(t)

        # Espacar inicializacoes para nao sobrecarregar
        time.sleep(random.uniform(1.5, 3.0))

    with user_state["lock"]:
        user_state["threads"] = threads

    add_log_for_user(email, f"Todas as {num_sessions} sessoes iniciadas!", "success")


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
        return jsonify({"error": "Seu bot ja esta rodando! Clique PARAR primeiro."}), 400

    with user_state["lock"]:
        user_state["running"] = False
        user_state["stop_requested"] = False
        user_state["sessions"] = []
        user_state["threads"] = []

    with online_users_lock:
        online_users[email] = {
            "started_at": datetime.now().strftime("%H:%M:%S"),
            "sessions": num_sessions,
            "last_seen": time.time()
        }

    threading.Thread(target=start_bot, args=(email, password, num_sessions, proxy_config), daemon=True).start()

    save_active_bots(email, password, num_sessions, proxy_config)

    return jsonify({"status": "started", "sessions": num_sessions})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    data = request.json or {}
    email = data.get("email", "").strip()

    if not email:
        return jsonify({"error": "Email necessario para identificar usuario"}), 400

    user_state = get_user_state(email)

    with user_state["lock"]:
        user_state["stop_requested"] = True
        user_state["running"] = False

    with online_users_lock:
        online_users.pop(email, None)

    remove_active_bot(email)

    add_log_for_user(email, "Parando todas as sessoes...", "warning")
    return jsonify({"status": "stopping"})


@app.route("/api/status")
def api_status():
    email = request.args.get("email", "").strip()

    if not email:
        return jsonify({
            "running": False,
            "total_earned": 0.0,
            "total_views": 0,
            "sessions": [],
            "logs": [],
            "start_time": None,
            "active_threads": 0,
        })

    user_state = get_user_state(email)

    with user_state["lock"]:
        active_threads = [t for t in user_state.get("threads", []) if t.is_alive()]
        is_running = len(active_threads) > 0

        if user_state["running"] and not is_running:
            user_state["running"] = False

        active_sessions = []
        for s in user_state["sessions"]:
            obj = s["obj"]
            active_sessions.append({
                "id": s["id"],
                "device_id": obj.device_id[:16] + "...",
                "device_name": f"{obj.device_info['brand']} {obj.device_info['model']}",
                "status": obj.status,
                "earned": round(obj.earned, 4),
                "views": obj.views,
                "current_video": obj.current_video,
                "ip": obj.current_ip or "-",
                "country": "BR",
                "rotations": obj.rotation_count,
                "attempts": obj.total_attempts,
                "found": obj.tasks_found,
                "completed": obj.tasks_completed,
                "failed": obj.tasks_failed,
                "skipped": obj.tasks_skipped,
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
    """Retorna lista de usuarios online."""
    with online_users_lock:
        actually_running = []
        for email, info in list(online_users.items()):
            if email in users_state:
                ustate = users_state[email]
                active_threads = [t for t in ustate.get("threads", []) if t.is_alive()]
                if not active_threads and not ustate.get("running"):
                    del online_users[email]
                    continue
            actually_running.append(email)

        users_list = []
        for email in actually_running:
            info = online_users.get(email, {})
            user_earned = 0.0
            user_views = 0
            if email in users_state:
                ustate = users_state[email]
                user_earned = round(ustate.get("total_earned", 0.0), 4)
                user_views = ustate.get("total_views", 0)
            users_list.append({
                "email": email,
                "started_at": info.get("started_at", "-"),
                "sessions": info.get("sessions", 0),
                "earned": user_earned,
                "views": user_views,
            })

    return jsonify({
        "online_count": len(users_list),
        "users": users_list
    })


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
