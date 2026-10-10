"""Verify model hashes, environment compatibility and prepared CSV identities."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT/'training'))
from web_app.backend.inference import ModelService
from src.training import combined_experts as ce

service = ModelService()
summary, manifests = ce.verify_prepared_data()
assert (ROOT/'web_app/dist/index.html').is_file(), 'Missing built website: run npm ci and npm run build in web_app'
for example in json.loads((ROOT/'web_app/backend/examples.json').read_text(encoding='utf-8')):
    assert (ROOT/'web_app/public/examples'/(example['id']+'.jpg')).is_file()
print(json.dumps({'status': 'ready', 'run': service.active_run,
                  'models': list(service.combined['bundles']),
                  'source_clips': summary['source_clips'], 'prepared_datasets': list(manifests),
                  'scikit_learn': ce.sklearn.__version__}, indent=2))
service.close()
