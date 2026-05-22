"""Teste completo com nova sessão HTTP para cada request."""
import requests, ssl, re, hashlib, time, urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from urllib3.util.retry import Retry

urllib3.disable_warnings()

class TLSAdapter(HTTPAdapter):
    def __init__(self, *a, **kw):
        kw['max_retries'] = Retry(total=3, backoff_factor=2, status_forcelist=[500,502,503,504])
        super().__init__(*a, **kw)
    def init_poolmanager(self, *a, **kw):
        ctx = create_urllib3_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.maximum_version = ssl.TLSVersion.TLSv1_2
        kw['ssl_context'] = ctx
        return super().init_poolmanager(*a, **kw)

def new_session():
    s = requests.Session()
    s.mount('https://', TLSAdapter())
    s.verify = False
    return s

BASE = 'https://seo-fast.bz/webapp/'
UA = 'Mozilla/5.0 (Linux; Android 9; SM-G960N Build/PQ3A.190605.07021633; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/138.0.7204.179 Mobile Safari/537.36 SeoFast-App/1.0'

device_id = 'bluestacks_c8583418d5f071b4'
app_token = hashlib.sha256(f'{device_id}:com.example.seofast:seo_fast_SFk1gR5h5DGH'.encode()).hexdigest()
print(f'Token: {app_token}')

base_headers = {
    'User-Agent': UA,
    'X-Requested-With': 'com.example.seofast',
    'X-App-Token': app_token,
    'X-App-Version': '1.1.0',
    'X-Device-Id': device_id,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'pt-PT,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Accept-Encoding': 'gzip, deflate, br',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Android WebView";v="138"',
    'sec-ch-ua-mobile': '?1',
    'sec-ch-ua-platform': '"Android"',
    'sec-fetch-site': 'none',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-dest': 'document',
}

def do_request(method, url, headers, data=None, max_retries=3):
    """Make request with retry and new session on failure."""
    for attempt in range(max_retries):
        try:
            http = new_session()
            if method == 'GET':
                r = http.get(url, headers=headers, timeout=60)
            else:
                r = http.post(url, headers=headers, data=data, timeout=60)
            http.close()
            return r
        except Exception as e:
            print(f'    [Retry {attempt+1}] {e}')
            time.sleep(2 * (attempt + 1))
    return None

# Step 1: GET /
print('[1] GET / ...')
r = do_request('GET', BASE, base_headers)
phpsessid = None
for c in r.cookies:
    if c.name == 'PHPSESSID':
        phpsessid = c.value
print(f'    PHPSESSID: {phpsessid}')

# Step 2: GET ?pg=login
print('[2] GET ?pg=login ...')
time.sleep(1)
h = base_headers.copy()
h['Cookie'] = f'PHPSESSID={phpsessid}'
r = do_request('GET', BASE + '?pg=login', h)
m = re.search(r"var\s+hash_ajax\s*=\s*['\"]([a-f0-9]+)['\"]", r.text)
hash_ajax = m.group(1) if m else None
print(f'    hash_ajax: {hash_ajax}')

# Step 3: POST login
print('[3] POST login ...')
time.sleep(1)
login_headers = base_headers.copy()
login_headers.update({
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://seo-fast.bz',
    'Referer': 'https://seo-fast.bz/webapp/?pg=login',
    'Cookie': f'PHPSESSID={phpsessid}',
    'Accept': 'text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
})
login_data = {
    'login': 'muriel60herrera@gmail.com',
    'password': '6ecbdd6ec8',
    'hash': hash_ajax,
    'ajax_func': 'login',
}
r = do_request('POST', BASE + 'ajax/ajax_login.php', login_headers, login_data)
if r:
    print(f'    Status: {r.status_code}')
    print(f'    Response: {r.text[:200]}')
else:
    print('    FAILED')

# Step 4: GET ?pg=job
print('[4] GET ?pg=job ...')
time.sleep(2)
h = base_headers.copy()
h['Cookie'] = f'PHPSESSID={phpsessid}'
r = do_request('GET', BASE + '?pg=job', h)
if r:
    m = re.search(r"var\s+hash_ajax\s*=\s*['\"]([a-f0-9]+)['\"]", r.text)
    if m:
        hash_ajax = m.group(1)
        print(f'    hash_ajax: {hash_ajax}')
    else:
        print(f'    NO hash_ajax - checking page...')
        print(f'    URL: {r.url}')
        print(f'    HTML: {r.text[:300]}')

# Step 5: up_data
print('[5] up_data ...')
time.sleep(2)
task_headers = base_headers.copy()
task_headers.update({
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Origin': 'https://seo-fast.bz',
    'Referer': 'https://seo-fast.bz/webapp/?pg=job',
    'Cookie': f'PHPSESSID={phpsessid}',
    'Accept': 'text/javascript, application/javascript, application/ecmascript, application/x-ecmascript, */*; q=0.01',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-mode': 'cors',
    'sec-fetch-dest': 'empty',
})
up_data = {
    'act': 'up_data',
    'hash_ajax': hash_ajax,
    'device_id': device_id,
    'google_email': 'muriel60herrera@gmail.com',
    'is_emulator': 'false',
}
r = do_request('POST', BASE + 'ajax/ajax_data.php', task_headers, up_data)
if r:
    print(f'    Response: {r.text[:200]}')

# Step 6: get_task
print('[6] get_task ...')
time.sleep(2)
task_data = {
    'act': 'get_task',
    'hash_ajax': hash_ajax,
    'device_id': device_id,
}
r = do_request('POST', BASE + 'ajax/ajax_views.php', task_headers, task_data)
if r:
    print(f'    Response: {r.text[:300]}')

print('\n[DONE]')
