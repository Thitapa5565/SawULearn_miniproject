import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from web_app.backend.app import app, service, ASSETS
from training.src.training import combined_experts as ce

ROOT = Path(__file__).resolve().parents[1]
RUN = 'combined_experts_20261007_211339_512861'


class SubmissionTests(unittest.TestCase):
    def test_only_latest_classifiers_are_loaded_and_immutable(self):
        self.assertEqual(service.active_run, RUN)
        self.assertEqual(set(service.combined['bundles']), set(ce.TASKS))
        for task, expected in service.combined['config']['model_sha256'].items():
            path = ROOT/'training/models'/RUN/'final'/f'{task}.joblib'
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected)
        self.assertEqual({p.name for p in (ROOT/'training/models').iterdir()}, {RUN, 'pretrained'})

    def test_prepared_data_has_no_split_leakage_and_matches_original_hashes(self):
        summary, manifests = ce.verify_prepared_data()
        self.assertTrue(summary['data_ready'])
        self.assertEqual(summary['source_clips'], 64)
        self.assertEqual(len(manifests), 3)

    def test_selected_models_reproduce_all_saved_test_predictions(self):
        for task, bundle in service.combined['bundles'].items():
            frame = ce.load_split(task, 'test')
            actual = bundle['model'].predict(frame[bundle['feature_columns']]).astype(str)
            saved = pd.read_csv(ROOT/'training/reports'/RUN/'test/selected'/f'{task}_predictions.csv')
            saved['prediction'] = saved['prediction'].astype(str)
            lookup = saved.set_index('frame_path')['prediction']
            np.testing.assert_array_equal(actual, frame.frame_path.map(lookup).to_numpy())

    def test_web_and_real_image_detection_work_without_raw_clips_or_old_models(self):
        with TestClient(app) as client:
            for path in ['/', '/api/health', '/api/models', '/api/lessons', '/api/examples', '/media/lessons/posture.jpg']:
                self.assertEqual(client.get(path).status_code, 200, path)
            image = ASSETS['posture.jpg'].read_bytes()
            result = client.post('/api/analyze/body-grip', content=image, headers={
                'Content-Type': 'image/jpeg', 'X-Include-Hands': '1'})
            self.assertEqual(result.status_code, 200, result.text[:200])
            data = result.json()
            self.assertEqual(len(data['posture']['landmarks']), 33)
            self.assertEqual(data['posture']['status'], 'ready')
            self.assertIn('initial_grip', data)
            self.assertEqual(data['bow_level']['model_run'], RUN)

    def test_posture_can_show_two_errors_at_once(self):
        bundles = service.combined['bundles']
        with patch.object(bundles['head_down']['model'], 'predict', return_value=np.array([1])), \
             patch.object(bundles['shoulder_tilt']['model'], 'predict', return_value=np.array([1])):
            prediction = service.posture['model'].predict(np.zeros((1, 10)))
        np.testing.assert_array_equal(prediction, [[1, 1]])


if __name__ == '__main__':
    unittest.main()
