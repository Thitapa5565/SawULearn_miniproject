"""Check the exact submitted files before rerunning notebooks or rebuilding the UI."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT/'submission_manifest.json').read_text(encoding='utf-8'))
failures = []
for name, expected in manifest['files'].items():
    path = (ROOT/name).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        failures.append(name)
        continue
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected['sha256']:
        failures.append(name)
print(json.dumps({'checked_files': len(manifest['files']), 'changed_or_missing': failures}, indent=2))
if failures:
    raise SystemExit(1)
