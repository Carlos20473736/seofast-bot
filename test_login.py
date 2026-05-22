"""Teste completo do fluxo login → get_task com retry."""
import requests, ssl, re, hashlib, time
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from urllib3.util.retry import Retry

urllib3.disable_warnings()

class TLSAdapter(HTTPAdapter):
    def __init__(self, *args, **kwargs):
        retry = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
        kwargs["max_retries"] = retry
        super().__init__(*args, **kwargs)

    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

http = requests.Session()
http.mount('https://', TLSAdapter())
http.verify = False

BASE = 'https://seo-fast.bz/webapp/'
UA = 'Mozilla/5.0 (Linux; Android 9; SM-G960N Build/PQ3A.190605.07021633; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.179 Mobile Safari/537.36 SeoFast-App/1.0'

# Step 1: GET page
print("[1] Acessando página...")
headers = {'User-Agent': UA, 'X-Requested-With': 'com.example.seofast'}
r = http.get(BASE, headers=headers, timeout=60)
phpsessid = None
for c in http.cookies:
    if c.name == 'PHPSESSID':
        phpsessid = c.value
print(f"    PHPSESSID: {phpsessid}")

m = re.search(r"var\s+hash_ajax\s*=\s*['\"]([a-f0-9]+)['\"]", r.text)
hash_ajax = m.group(1) if m else None
print(f"    hash_ajax: {hash_ajax}")

# Step 2: Login
print("\n[2] Fazendo login...")
login_headers = {
    'User-Agent': UA,
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://seo-fast.bz',
    'Referer': 'https://seo-fast.bz/webapp/?pg=login',
    'Cookie': f'PHPSESSID={phpsessid}',
}
login_data = {
    'login': 'muriel60herrera@gmail.com',
    'password': '6ecbdd6ec8',
    'hash': hash_ajax,
    'ajax_func': 'login',
}

try:
    r = http.post(BASE + 'ajax/ajax_login.php', headers=login_headers, data=login_data, timeout=60)
    print(f"    Status: {r.status_code}")
    print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    ERRO login: {e}")
    # Retry
    time.sleep(3)
    http2 = requests.Session()
    http2.mount('https://', TLSAdapter())
    http2.verify = False
    r = http2.post(BASE + 'ajax/ajax_login.php', headers=login_headers, data=login_data, timeout=60)
    print(f"    Retry Status: {r.status_code}")
    print(f"    Retry Response: {r.text[:200]}")

# Step 3: Get job page
print("\n[3] Acessando página de trabalho...")
time.sleep(2)
try:
    job_headers = {'User-Agent': UA, 'X-Requested-With': 'com.example.seofast', 'Cookie': f'PHPSESSID={phpsessid}'}
    r = http.get(BASE + '?pg=job', headers=job_headers, timeout=60)
    m = re.search(r"var\s+hash_ajax\s*=\s*['\"]([a-f0-9]+)['\"]", r.text)
    if m:
        hash_ajax = m.group(1)
        print(f"    hash_ajax atualizado: {hash_ajax}")
    else:
        print(f"    hash_ajax NÃO encontrado no HTML")
        # Check if redirected to login
        if 'pg=login' in r.text[:500] or 'login' in r.url:
            print("    REDIRECIONADO PARA LOGIN - sessão não autenticada!")
        print(f"    URL: {r.url}")
        print(f"    HTML snippet: {r.text[:300]}")
except Exception as e:
    print(f"    ERRO: {e}")

# Step 4: up_data + get_task
print("\n[4] Registrando device e buscando tarefa...")
device_id = 'samsung_galaxy_a54_a1b2c3d4e5f6a7b8'
app_token = hashlib.sha256(f'{device_id}:com.example.seofast:seo_fast_SFk1gR5h5DGH'.encode()).hexdigest()

task_headers = {
    'User-Agent': UA,
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'X-App-Token': app_token,
    'X-App-Version': '1.1.0',
    'X-Device-Id': device_id,
    'Origin': 'https://seo-fast.bz',
    'Referer': 'https://seo-fast.bz/webapp/?pg=job',
    'Cookie': f'PHPSESSID={phpsessid}',
}

time.sleep(2)
try:
    up_data = {
        'act': 'up_data',
        'hash_ajax': hash_ajax,
        'device_id': device_id,
        'google_email': 'muriel60herrera@gmail.com',
        'is_emulator': 'false',
    }
    r = http.post(BASE + 'ajax/ajax_data.php', headers=task_headers, data=up_data, timeout=60)
    print(f"    up_data: {r.text[:200]}")
except Exception as e:
    print(f"    up_data ERRO: {e}")

time.sleep(2)
try:
    task_data = {
        'act': 'get_task',
        'hash_ajax': hash_ajax,
        'device_id': device_id,
    }
    r = http.post(BASE + 'ajax/ajax_views.php', headers=task_headers, data=task_data, timeout=60)
    print(f"    get_task: {r.text[:300]}")
except Exception as e:
    print(f"    get_task ERRO: {e}")

print("\n[DONE]")
