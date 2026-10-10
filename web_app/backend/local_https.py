"""Private-LAN HTTPS with a short-lived CA and a public-only iPad setup page.

Does not install certificates in Windows or change firewall/trust settings.
The iPad owner installs/trusts the root explicitly in Settings.
"""
import argparse
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import threading
from urllib.parse import urlsplit
import uuid

WEB_ROOT = Path(__file__).resolve().parents[1]
RUNTIME = WEB_ROOT / '.runtime/ipad-https'


def openssl_path():
    candidates = [shutil.which('openssl'), r'C:\Program Files\Git\usr\bin\openssl.exe']
    for path in candidates:
        if path and Path(path).is_file():
            return str(path)
    raise RuntimeError('OpenSSL is required. Use the OpenSSL supplied with Git for Windows.')


def run_openssl(binary, *args):
    result = subprocess.run([binary, *map(str,args)], capture_output=True, text=True, check=False)
    if result.returncode:
        raise RuntimeError('Certificate command failed: ' + result.stderr[-1200:])
    return result.stdout.strip()


def prepare_certificates(host):
    address = ipaddress.ip_address(host)
    if address.version != 4 or not address.is_private or address.is_unspecified or address.is_loopback:
        raise ValueError('Use the computer private Wi-Fi IPv4 address, e.g. 192.168.1.195.')
    binary = openssl_path()
    directory = RUNTIME / str(address)
    directory.mkdir(parents=True,exist_ok=True)
    metadata_file = directory/'metadata.json'
    files = ['ca.pem','server.pem','server.key','chain.pem','sawuai-ipad.mobileconfig','ca.cer']
    if metadata_file.is_file() and all((directory/name).is_file() for name in files):
        check = subprocess.run([binary,'x509','-checkend','86400','-noout','-in',str(directory/'server.pem')],
                               capture_output=True)
        if check.returncode == 0:
            run_openssl(binary,'verify','-CAfile',directory/'ca.pem','-verify_ip',host,directory/'server.pem')
            return directory,json.loads(metadata_file.read_text(encoding='utf-8'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d') + '-' + uuid.uuid4().hex[:8]
    name = 'SawULearn Local CA ' + stamp
    # Private keys stay outside dist and are never served by the setup handler.
    (directory/'ca.cnf').write_text(f'''[req]
prompt = no
distinguished_name = dn
x509_extensions = v3_ca
[dn]
CN = {name}
O = SawULearn Local Development
[v3_ca]
basicConstraints = critical,CA:TRUE,pathlen:0
keyUsage = critical,keyCertSign,cRLSign
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always
nameConstraints = critical,permitted;IP:{host}/255.255.255.255,permitted;IP:127.0.0.1/255.255.255.255,excluded;DNS:.
''',encoding='ascii')
    (directory/'server.cnf').write_text(f'''[req]
prompt = no
distinguished_name = dn
[dn]
CN = {host}
O = SawULearn Local Development
[server]
basicConstraints = critical,CA:FALSE
keyUsage = critical,digitalSignature,keyEncipherment
extendedKeyUsage = serverAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
subjectAltName = IP:{host},IP:127.0.0.1
''',encoding='ascii')
    run_openssl(binary,'req','-new','-x509','-newkey','rsa:2048','-noenc','-sha256','-days','30',
                '-config',directory/'ca.cnf','-keyout',directory/'ca.key','-out',directory/'ca.pem')
    run_openssl(binary,'req','-new','-newkey','rsa:2048','-noenc','-sha256','-config',directory/'server.cnf',
                '-keyout',directory/'server.key','-out',directory/'server.csr')
    run_openssl(binary,'x509','-req','-in',directory/'server.csr','-CA',directory/'ca.pem',
                '-CAkey',directory/'ca.key','-set_serial','0x'+uuid.uuid4().hex,'-days','29','-sha256',
                '-extfile',directory/'server.cnf','-extensions','server','-out',directory/'server.pem')
    run_openssl(binary,'verify','-CAfile',directory/'ca.pem','-verify_ip',host,'-purpose','sslserver',directory/'server.pem')
    run_openssl(binary,'x509','-in',directory/'ca.pem','-outform','DER','-out',directory/'ca.cer')
    payload_uuid = str(uuid.uuid4()).upper()
    profile = {
        'PayloadType':'Configuration','PayloadVersion':1,'PayloadUUID':str(uuid.uuid4()).upper(),
        'PayloadIdentifier':'local.sawuai.ipad.'+stamp,'PayloadDisplayName':'SawULearn Local HTTPS '+stamp,
        'PayloadDescription':'Local development certificate created on your SawULearn computer. Valid for 30 days.',
        'PayloadOrganization':'SawULearn Local Development','PayloadRemovalDisallowed':False,
        'PayloadContent':[{
            'PayloadType':'com.apple.security.root','PayloadVersion':1,'PayloadUUID':payload_uuid,
            'PayloadIdentifier':'local.sawuai.certificate.'+stamp,'PayloadDisplayName':name,
            'PayloadCertificateFileName':'sawuai-local-ca.cer','PayloadContent':(directory/'ca.cer').read_bytes(),
        }],
    }
    (directory/'sawuai-ipad.mobileconfig').write_bytes(plistlib.dumps(profile))
    (directory/'chain.pem').write_bytes((directory/'server.pem').read_bytes()+(directory/'ca.pem').read_bytes())
    metadata = {'host':host,'ca_name':name,'created_at':datetime.now(timezone.utc).isoformat(),
                'fingerprint_sha256':run_openssl(binary,'x509','-in',directory/'ca.pem','-noout','-fingerprint','-sha256').split('=',1)[1],
                'ca_expiry':run_openssl(binary,'x509','-in',directory/'ca.pem','-noout','-enddate').split('=',1)[1]}
    metadata_file.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return directory,metadata


def setup_page(metadata, https_port):
    name=html.escape(metadata['ca_name']); host=metadata['host']
    url=f'https://{host}:{https_port}/#practice'
    return f'''<!doctype html><html lang="th"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SawULearn · เปิดกล้องบน iPad</title><style>
body{{background:#f4f3ef;color:#403223;font-family:system-ui,sans-serif;line-height:1.8;margin:0;padding:24px}}
main{{max-width:680px;margin:24px auto;background:white;border:1px solid #ddd7cd;border-radius:12px;padding:28px}}
h1{{font-size:26px;line-height:1.5}}h2{{font-size:18px}}a{{color:#365d3f}}.button{{display:block;text-align:center;text-decoration:none;background:#403223;color:white;padding:12px;border-radius:6px;margin:20px 0}}
.secondary{{background:#e8eee3;color:#365d3f}}li{{margin:18px 0}}code{{overflow-wrap:anywhere}}small{{color:#786c5e}}details{{margin-top:20px}}.name{{padding:12px;background:#f4f3ef;overflow-wrap:anywhere}}
</style><main><small>SAWULEARN · LOCAL WI-FI</small><h1>เปิดกล้องบน iPad</h1>
<p>ใช้ Safari เปิดหน้านี้บน iPad แล้วตั้งค่าใบรับรองครั้งเดียว เพื่อให้เว็บ HTTPS ขอใช้กล้องได้</p>
<p class="name">ใบรับรองที่สร้างบนคอมของคุณ: <strong>{name}</strong><br>มีอายุ 30 วัน</p>
<ol><li><a class="button" href="/sawuai-ipad.mobileconfig">1. ดาวน์โหลดโปรไฟล์ใบรับรอง</a>เมื่อ Safari ถาม ให้เลือก <b>อนุญาต / Allow</b></li>
<li>เปิด <b>การตั้งค่า / Settings → โปรไฟล์ที่ดาวน์โหลด / Profile Downloaded</b><br>
หรือ <b>ทั่วไป / General → VPN และการจัดการอุปกรณ์ / VPN &amp; Device Management</b><br>
เลือก <b>SawULearn Local HTTPS</b> แล้วกด <b>ติดตั้ง / Install</b></li>
<li>ไปที่ <b>ทั่วไป / General → เกี่ยวกับ / About → การตั้งค่าความเชื่อถือใบรับรอง / Certificate Trust Settings</b><br>
เปิดความเชื่อถือให้ <b>{name}</b><br><small>ขั้นตอนนี้ทำให้ iPad ยอมรับใบรับรองที่ CA นี้ลงนาม คุณเป็นผู้เลือกเปิดความเชื่อถือเอง</small></li>
<li><a class="button secondary" href="{url}">4. เปิดเว็บ HTTPS เพื่อเริ่มฝึก</a>
กด <b>เปิดกล้องเริ่มฝึก</b> แล้วเลือก <b>อนุญาต / Allow</b></li></ol>
<p>หาก Safari ยังแจ้งว่าใบรับรองไม่น่าเชื่อถือ ให้กลับไปตรวจข้อ 2–3 ก่อนใช้งาน</p>
<p><small>เมื่อเลิกใช้ ให้ลบโปรไฟล์ SawULearn Local HTTPS ใน VPN &amp; Device Management<br>
ถ้า IP คอมเปลี่ยนหรือใบรับรองหมดอายุ ให้เริ่มเซิร์ฟเวอร์ด้วย IP ใหม่แล้วติดตั้งโปรไฟล์ใหม่</small></p>
<details><summary>รายละเอียดใบรับรอง</summary><p>หมดอายุ: {html.escape(metadata['ca_expiry'])}</p>
<p>SHA-256: <code>{html.escape(metadata['fingerprint_sha256'])}</code></p></details>
<p><small><a href="https://support.apple.com/102390">วิธีเปิดความเชื่อถือใบรับรองจาก Apple</a></small></p>
</main></html>'''.encode('utf-8')


def setup_handler(directory, metadata, https_port):
    public_files = {'/sawuai-ipad.mobileconfig':('application/x-apple-aspen-config',directory/'sawuai-ipad.mobileconfig'),
                    '/sawuai-local-ca.cer':('application/pkix-cert',directory/'ca.cer')}
    class SetupHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            path=urlsplit(self.path).path
            if path=='/':
                mime,body='text/html; charset=utf-8',setup_page(metadata,https_port)
            elif path in public_files:
                mime,file=public_files[path];body=file.read_bytes()
            else:
                self.send_error(404);return
            self.send_response(200);self.send_header('Content-Type',mime)
            self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(body)))
            self.send_header('X-Content-Type-Options','nosniff')
            if path in public_files:
                self.send_header('Content-Disposition','attachment; filename="'+Path(path).name+'"')
            self.end_headers()
            if not head:self.wfile.write(body)
    return SetupHandler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--https-port',type=int,default=8443)
    parser.add_argument('--setup-port',type=int,default=8002)
    parser.add_argument('--prepare-only',action='store_true')
    args=parser.parse_args()
    directory,metadata=prepare_certificates(args.host)
    print('Certificate:',metadata['ca_name'],flush=True)
    print('iPad setup:',f'http://{args.host}:{args.setup_port}/',flush=True)
    print('Practice:',f'https://{args.host}:{args.https_port}/#practice',flush=True)
    if args.prepare_only:return
    # Do not serve the directory: it contains private keys.
    setup=ThreadingHTTPServer((args.host,args.setup_port),setup_handler(directory,metadata,args.https_port))
    setup.daemon_threads=True
    worker=threading.Thread(target=setup.serve_forever,daemon=True);worker.start()
    os.environ.setdefault('MPLCONFIGDIR',str(WEB_ROOT.parent/'training/.venv/matplotlib-cache'))
    import uvicorn
    try:
        uvicorn.run('web_app.backend.app:app',host=args.host,port=args.https_port,
                    ssl_keyfile=str(directory/'server.key'),ssl_certfile=str(directory/'chain.pem'))
    finally:
        setup.shutdown();setup.server_close()


if __name__=='__main__':main()
