"""Run the explicitly synthetic browser regression with prepared, verified tooling."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import base64,hashlib,json,subprocess,urllib.request
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from scripts.kubernetes_local import *
safety()
tool='leadforge-browser-tool:5h-l-local'
locked=json.loads(run([executable('docker'),'run','--rm','--network=none',tool,'cat','/tmp/leadforge-browser/package-lock.json']).stdout)
for name in ('playwright','playwright-core'):
    with urllib.request.urlopen('https://registry.npmjs.org/'+name+'/1.58.2',timeout=15) as response:metadata=json.load(response)
    assert locked['packages']['node_modules/'+name]['integrity']==metadata['dist']['integrity']
cert=x509.load_pem_x509_certificate((PRIVATE/'fullchain.pem').read_bytes())
spki=base64.b64encode(hashlib.sha256(cert.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)).digest()).decode()
ip=json.loads(kubectl('get','service','local-ingress','-o','json').stdout)['spec']['clusterIP']
# No package manager or external code download runs with the synthetic QA mount.
args=[executable('docker'),'run','--rm','--network=container:desktop-control-plane','--cap-drop=ALL','--security-opt=no-new-privileges:true','--shm-size=256m',
    '-v',str(ROOT/'scripts/kubernetes_browser_smoke.mjs')+':/check.mjs:ro',
    '-v',str(OUTPUT)+':/evidence',
    '-v',str(PRIVATE/'qa_password')+':/qa/password:ro',
    '-e','LF_INGRESS_IP='+ip,'-e','LF_LOCAL_CERT_SPKI='+spki,
    tool,'node','/check.mjs']
result=subprocess.run(args,capture_output=True,text=True,timeout=180)
if (PRIVATE/'qa_password').read_text().strip() in result.stdout+result.stderr:raise RuntimeError('Browser credential in output; withheld')
print(result.stdout);print(result.stderr[-2500:]);raise SystemExit(result.returncode)
