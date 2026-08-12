import base64
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

if len(sys.argv) != 3:
    raise SystemExit('usage: extract_official_supabase.py <official.apk> <output.env>')

apk_path, output_path = sys.argv[1:3]

with zipfile.ZipFile(apk_path) as apk:
    dex_names = [name for name in apk.namelist() if name.endswith('.dex')]
    if not dex_names:
        raise SystemExit('No classes*.dex files found in official APK')
    blob = b'\n'.join(apk.read(name) for name in dex_names)

def unique(items):
    seen = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

keys = []
jwt_pattern = re.compile(rb'eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}')
for match in jwt_pattern.finditer(blob):
    value = match.group(0).decode('ascii', errors='ignore')
    try:
        payload_part = value.split('.')[1]
        payload_part += '=' * (-len(payload_part) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_part).decode('utf-8'))
    except Exception:
        continue
    if payload.get('role') == 'anon':
        keys.append(value)

publishable_pattern = re.compile(rb'sb_publishable_[A-Za-z0-9_-]{16,}')
keys.extend(match.group(0).decode('ascii') for match in publishable_pattern.finditer(blob))
keys = unique(keys)
if not keys:
    raise SystemExit('Could not find a public Supabase anon/publishable key in official APK')

url_pattern = re.compile(rb"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")
bases = []
for match in url_pattern.finditer(blob):
    raw = match.group(0).decode('utf-8', errors='ignore').rstrip('./,;:)\"]}')
    try:
        parsed = urllib.parse.urlsplit(raw)
    except Exception:
        continue
    host = (parsed.hostname or '').lower()
    if not host:
        continue
    if 'supabase' not in host and 'nuvio' not in host:
        continue
    bases.append(f'{parsed.scheme}://{parsed.netloc}'.rstrip('/'))
bases = unique(bases)
if not bases:
    raise SystemExit('Could not find candidate Nuvio/Supabase endpoints in official APK')

working = []
selected_key = None
for key in keys:
    for base in bases:
        request = urllib.request.Request(
            base + '/auth/v1/settings',
            headers={
                'apikey': key,
                'Authorization': 'Bearer ' + key,
                'User-Agent': 'Nuvio-iOS-CI-config-check',
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                if 200 <= response.status < 300:
                    response.read(256)
                    if base not in working:
                        working.append(base)
                    selected_key = key
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
            continue
    if working:
        break

if not working:
    supabase_bases = [base for base in bases if 'supabase.co' in base.lower()]
    if not supabase_bases:
        raise SystemExit('Found config candidates, but none responded as a valid Supabase Auth endpoint')
    working = supabase_bases
    selected_key = keys[0]

primary = working[0]
fallback = working[1] if len(working) > 1 else ''
with open(output_path, 'w', encoding='utf-8') as output:
    output.write(f'NUVIO_SUPABASE_URL={primary}\n')
    output.write(f'NUVIO_SUPABASE_ANON_KEY={selected_key}\n')
    output.write(f'NUVIO_SUPABASE_FALLBACK_URL={fallback}\n')

print('Validated production Supabase config from official APK')
