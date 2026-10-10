"""Load explicitly deployed, immutable combined-expert classifier artifacts."""
import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn

TASK_FEATURES = {
    'head_down': ['shoulder_tilt_deg', 'head_tilt_deg', 'torso_tilt_deg', 'head_height_ratio',
                  'head_side_offset_ratio', 'nose_below_ears_ratio', 'torso_length_ratio',
                  'hip_width_ratio', 'nose_depth_vs_shoulders_ratio', 'shoulder_depth_vs_hips_ratio'],
    'shoulder_tilt': ['shoulder_tilt_deg', 'head_tilt_deg', 'torso_tilt_deg', 'head_height_ratio',
                      'head_side_offset_ratio', 'nose_below_ears_ratio', 'torso_length_ratio',
                      'hip_width_ratio', 'nose_depth_vs_shoulders_ratio', 'shoulder_depth_vs_hips_ratio'],
    'initial_grip': ['bow_side_horizontal_ratio', 'wrist_height_body_ratio'],
    'bow_error': ['bow_side_horizontal_ratio', 'bow_side_perpendicular_ratio',
                  'wrist_height_screen_ratio', 'wrist_height_body_ratio'],
}


class IndependentPostureModels:
    """Keep the two selected classifiers independent and the existing API order."""
    def __init__(self, bundles):
        self.bundles = bundles

    def predict(self, X):
        frame = pd.DataFrame(X, columns=TASK_FEATURES['head_down'])
        return np.column_stack([self.bundles[task]['model'].predict(frame).astype(int)
                                for task in ['head_down', 'shoulder_tilt']])


def load_deployment(training_root, config_path):
    path = Path(config_path)
    if not path.exists():
        return None
    config = json.loads(path.read_text(encoding='utf-8'))
    if config.get('enabled') is not True:
        return None
    run = config['run']
    if Path(run).name != run or not run.startswith('combined_experts_'):
        raise ValueError('Invalid combined model run')
    bundles = {}
    for task, features in TASK_FEATURES.items():
        artifact = Path(training_root)/'models'/run/'final'/f'{task}.joblib'
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != config['model_sha256'][task]:
            raise ValueError(f'Deployed model hash mismatch: {task}')
        bundle = joblib.load(artifact)
        expected_classes = {'none', 'grip_too_high', 'grip_too_low'} if task == 'initial_grip' else {'0', '1'}
        if (bundle['schema'] != 'combined_experts_v1' or bundle['task'] != task
                or bundle['run'] != run or bundle['fit_splits'] != ['train', 'val']
                or bundle['feature_columns'] != features
                or bundle['sklearn_version'] != sklearn.__version__
                or set(map(str, bundle['model'].classes_)) != expected_classes):
            raise ValueError(f'Unsupported combined model: {task}')
        bundles[task] = bundle
    if bundles['initial_grip']['protocol'] != 'player_rightmost_comfortable_bow_position':
        raise ValueError('Unsupported initial grip protocol')
    if bundles['bow_error']['target_semantics'] != 'angle_wrong_or_bow_floating':
        raise ValueError('Unsupported bow error target')
    return {'config': config, 'bundles': bundles}
