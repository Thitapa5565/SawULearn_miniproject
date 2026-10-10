"""Run all three submitted notebooks in the current environment without retraining."""
import json
import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'training'))
from src.training import combined_experts as ce

before = ce.web_fingerprints()
output = ROOT/'.runtime/verification/notebooks'
output.mkdir(parents=True, exist_ok=True)
results = []
for path in sorted((ROOT/'training/notebooks/15_combined_experts').glob('*.ipynb')):
    print('Executing:', path.name, flush=True)
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    NotebookClient(notebook, timeout=600, kernel_name='python3',
                   resources={'metadata': {'path': str(ROOT)}}, record_timing=False).execute()
    errors = [item for cell in notebook.cells for item in cell.get('outputs', []) if item.output_type=='error']
    assert not errors, errors
    nbformat.write(notebook, output/path.name)
    results.append({'notebook': path.name, 'code_cells': sum(c.cell_type=='code' for c in notebook.cells), 'errors': 0})
    print('Passed:', path.name, flush=True)
assert before == ce.web_fingerprints(), 'Notebook changed the deployed model'
(output.parent/'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
print('All notebooks passed; deployment hashes unchanged', flush=True)
