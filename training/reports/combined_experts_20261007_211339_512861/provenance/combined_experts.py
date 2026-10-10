"""Reproducible combined-expert training and reporting; never activates web models.

The notebooks expose the training steps. This module keeps checks, metrics and
plotting consistent across the separate train, validation and test notebooks.
"""
from __future__ import annotations

import hashlib
import json
import platform
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import ParameterGrid, StratifiedGroupKFold
from sklearn.tree import DecisionTreeClassifier, export_text, plot_tree

ROOT = Path(__file__).resolve().parents[2]
BATCH = 'expert01_expert02_20261007'
DATA = ROOT / 'data/processed' / BATCH / 'training_ready'
POSTURE = ['shoulder_tilt_deg', 'head_tilt_deg', 'torso_tilt_deg', 'head_height_ratio',
           'head_side_offset_ratio', 'nose_below_ears_ratio', 'torso_length_ratio',
           'hip_width_ratio', 'nose_depth_vs_shoulders_ratio', 'shoulder_depth_vs_hips_ratio']
BODY = ['bow_side_horizontal_ratio', 'bow_side_perpendicular_ratio',
        'wrist_height_screen_ratio', 'wrist_height_body_ratio']
GRIP_TWO = ['bow_side_horizontal_ratio', 'wrist_height_body_ratio']
TASKS = {
    'head_down': dict(dataset='playing_posture_head_shoulder', target='target_head_down',
                      labels=['0', '1'], title='ก้มหน้า', features={'posture_10': POSTURE}),
    'shoulder_tilt': dict(dataset='playing_posture_head_shoulder', target='target_shoulder_tilt',
                          labels=['0', '1'], title='ไหล่เอียง', features={'posture_10': POSTURE}),
    'initial_grip': dict(dataset='initial_grip_rightmost', target='error_type',
                        labels=['none', 'grip_too_high', 'grip_too_low'], title='จับคันชักตอนเริ่ม',
                        features={'body_2': GRIP_TWO, 'body_4': BODY}),
    'bow_error': dict(dataset='bow_angle_float_body_proxy', target='target_bow_angle_wrong',
                     labels=['0', '1'], title='ควรปรับองศาการสี', features={'body_4': BODY}),
}
LABEL_TEXT = {'0': 'ไม่พบอาการ', '1': 'พบอาการ', 'none': 'จับพอดี',
              'grip_too_high': 'จับสูง', 'grip_too_low': 'จับต่ำ', '__unavailable__': 'จุดไม่ครบ'}
UNAVAILABLE = '__unavailable__'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def setup_plots():
    for path in [Path('C:/Windows/Fonts/tahoma.ttf'), Path('C:/Windows/Fonts/LeelawUI.ttf')]:
        if path.exists():
            font_manager.fontManager.addfont(str(path))
            plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(path)).get_name()
            break
    plt.rcParams.update({'axes.unicode_minus': False, 'figure.dpi': 110, 'font.size': 10})


def web_fingerprints():
    """Only deployed pointers and the model artifacts they actually reference."""
    backend = ROOT.parent / 'web_app/backend'
    paths = [ROOT/'models/final_latest.json', backend/'body_grip_model.json', backend/'bow_level_model.json']
    for path in list(paths):
        if not path.exists():
            continue
        config = read_json(path)
        if path.name == 'final_latest.json':
            paths += [ROOT/'models'/config['run']/'sawuai_models.joblib']
        elif path.name == 'body_grip_model.json':
            paths += [ROOT/'models'/config['run']/(config['variant']+'.joblib')]
        else:
            paths += [ROOT/'models'/config['run']/(task+'.joblib') for task in config['tasks']]
    return {p.relative_to(ROOT.parent).as_posix(): sha256(p) for p in paths if p.exists()}


def verify_prepared_data():
    """Verify integrity and split identity; no test feature/target rows are read here."""
    summary = read_json(DATA.parent/'summary.json')
    if not summary['data_ready']:
        raise ValueError('Combined data is not ready')
    manifests = {}
    for name in sorted({t['dataset'] for t in TASKS.values()}):
        folder = DATA/name
        manifest = read_json(folder/'manifest.json')
        if not manifest['data_ready'] or not manifest['human_review_complete']:
            raise ValueError(f'Incomplete human review: {name}')
        if manifest['dataset_sha256'] != summary['dataset_sha256']:
            raise ValueError('Dataset identities differ')
        for split in ['train', 'val', 'test']:
            if sha256(folder/f'{split}.csv') != manifest['split_sha256'][split]:
                raise ValueError(f'Prepared CSV changed: {name}/{split}')
        # Identity columns only: test values remain hidden until selection lock.
        ids = {s: pd.read_csv(folder/f'{s}.csv', usecols=['clip_id', 'frame_path', 'video_sha256'])
               for s in ['train', 'val', 'test']}
        for i, a in enumerate(ids):
            if ids[a]['frame_path'].duplicated().any():
                raise ValueError('Duplicate frame within one task')
            for b in list(ids)[i+1:]:
                for key in ['clip_id', 'frame_path', 'video_sha256']:
                    if set(ids[a][key]) & set(ids[b][key]):
                        raise ValueError(f'Split leakage: {name}/{key}')
        manifests[name] = manifest
    # Across tasks a physical clip must also retain the same split.
    identities = pd.concat([pd.read_csv(DATA/name/f'{s}.csv', usecols=['clip_id']).assign(split=s)
                           for name in manifests for s in ['train', 'val', 'test']])
    if (identities.groupby('clip_id')['split'].nunique() > 1).any():
        raise ValueError('Cross-task split leakage')
    return summary, manifests


def load_split(task, split):
    spec = TASKS[task]
    folder = DATA/spec['dataset']
    manifest = read_json(folder/'manifest.json')
    if sha256(folder/f'{split}.csv') != manifest['split_sha256'][split]:
        raise ValueError('Data changed since review')
    df = pd.read_csv(folder/f'{split}.csv')
    if not np.isfinite(df[manifest['feature_columns']].to_numpy(dtype=float)).all():
        raise ValueError('Non-finite feature')
    if not set(df[spec['target']].astype(str)) <= set(spec['labels']):
        raise ValueError('Unexpected target')
    if set(df['split']) != {split}:
        raise ValueError('Wrong split')
    return df


def clip_weights(df):
    return (1 / df.groupby('clip_id')['clip_id'].transform('size')).to_numpy()


def fitting_weights(df, target, mode):
    weights = clip_weights(df)
    if mode == 'clip_class_balanced':
        y = df[target].astype(str).to_numpy()
        totals = {label: weights[y == label].sum() for label in np.unique(y)}
        weights = weights * np.array([1/totals[label] for label in y])
    elif mode != 'clip_equal':
        raise ValueError('Unknown weight mode')
    return weights / weights.mean()


def metric_values(df, target, predictions, labels):
    y = df[target].astype(str).to_numpy()
    pred = np.asarray(predictions).astype(str)
    weight = clip_weights(df)
    return {
        'frames': int(len(df)), 'clips': int(df['clip_id'].nunique()),
        'frame_accuracy': float(accuracy_score(y, pred)),
        'frame_macro_f1': float(f1_score(y, pred, labels=labels, average='macro', zero_division=0)),
        'clip_balanced_accuracy': float(accuracy_score(y, pred, sample_weight=weight)),
        'clip_balanced_macro_f1': float(f1_score(y, pred, labels=labels, average='macro',
                                               sample_weight=weight, zero_division=0)),
        'coverage': float(np.mean(pred != UNAVAILABLE)),
        'clip_balanced_coverage': float(np.average(pred != UNAVAILABLE, weights=weight)),
    }


def build_folds(df, task, n_splits=3, seed=42):
    spec = TASKS[task]
    splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    folds = list(splitter.split(df, df[spec['target']], groups=df['clip_id']))
    for fit, held in folds:
        if set(df.iloc[fit]['clip_id']) & set(df.iloc[held]['clip_id']):
            raise ValueError('CV group leakage')
        for indices in [fit, held]:
            if set(df.iloc[indices][spec['target']].astype(str)) != set(spec['labels']):
                raise ValueError(f'CV fold misses a class: {task}; reduce CV_FOLDS')
    return folds


def candidate_grid(tree_grid, forest_grid):
    candidates = []
    for family, grid in [('decision_tree', tree_grid), ('random_forest', forest_grid)]:
        for params in ParameterGrid(grid):
            for mode in ['clip_equal', 'clip_class_balanced']:
                candidates.append(dict(family=family, params=params, weight_mode=mode))
    return candidates


def make_estimator(candidate, seed=42, n_jobs=2):
    if candidate['family'] == 'decision_tree':
        return DecisionTreeClassifier(**candidate['params'], random_state=seed)
    return RandomForestClassifier(**candidate['params'], random_state=seed, n_jobs=n_jobs)


def fit_candidate(task, df, candidate, seed=42, n_jobs=2):
    model = make_estimator(candidate, seed, n_jobs)
    spec = TASKS[task]
    model.fit(df[candidate['features']], df[spec['target']],
              sample_weight=fitting_weights(df, spec['target'], candidate['weight_mode']))
    return model


def search_task(task, df, candidates, folds, seed=42, n_jobs=2):
    spec = TASKS[task]
    trials = []
    expanded = [(name, cols, c) for name, cols in spec['features'].items() for c in candidates]
    for number, (feature_set, features, base) in enumerate(expanded, 1):
        candidate = {**base, 'feature_set': feature_set, 'features': features}
        oof = np.empty(len(df), dtype=object)
        fold_scores = []
        for fit, held in folds:
            model = fit_candidate(task, df.iloc[fit], candidate, seed, n_jobs)
            predicted = model.predict(df.iloc[held][features])
            oof[held] = predicted
            fold_scores.append(metric_values(df.iloc[held], spec['target'], predicted,
                                             spec['labels'])['clip_balanced_macro_f1'])
        trials.append({**candidate, 'candidate_id': f'{task}_{number:03}',
                       'cv': metric_values(df, spec['target'], oof, spec['labels']),
                       'fold_f1': fold_scores, 'fold_f1_std': float(np.std(fold_scores))})
        if number == 1 or number % 12 == 0 or number == len(expanded):
            print(f'{task}: {number}/{len(expanded)} configurations completed', flush=True)
    return trials


def trial_table(trials):
    return pd.DataFrame([dict(candidate_id=t['candidate_id'], family=t['family'],
                             feature_set=t['feature_set'], weight_mode=t['weight_mode'],
                             parameters=json.dumps(t['params']),
                             cv_f1=t['cv']['clip_balanced_macro_f1'],
                             cv_accuracy=t['cv']['clip_balanced_accuracy'],
                             fold_std=t['fold_f1_std']) for t in trials]).sort_values(
                                 ['cv_f1', 'fold_std'], ascending=[False, True])


def trial_key(t):
    depth = t['params'].get('max_depth')
    return (t['cv']['clip_balanced_macro_f1'], -t['fold_f1_std'],
            -(depth if depth is not None else 999), t['params'].get('min_samples_leaf', 1),
            -len(t['features']))


def validate_shortlist(task, train, val, trials, seed=42, n_jobs=2):
    """Only the best TRAIN-CV candidate per family reaches fixed validation."""
    spec = TASKS[task]
    results, models = [], {}
    for family in ['decision_tree', 'random_forest']:
        candidate = max((t for t in trials if t['family'] == family), key=trial_key)
        model = fit_candidate(task, train, candidate, seed, n_jobs)
        train_score = metric_values(train, spec['target'], model.predict(train[candidate['features']]), spec['labels'])
        val_score = metric_values(val, spec['target'], model.predict(val[candidate['features']]), spec['labels'])
        results.append({**candidate, 'train': train_score, 'val': val_score})
        models[candidate['candidate_id']] = model
    dummy = DummyClassifier(strategy='most_frequent').fit(
        train[spec['features'][next(iter(spec['features']))]], train[spec['target']],
        sample_weight=clip_weights(train))
    dummy_features = spec['features'][next(iter(spec['features']))]
    baseline = metric_values(val, spec['target'], dummy.predict(val[dummy_features]), spec['labels'])
    selected = max(results, key=lambda t: (t['val']['clip_balanced_macro_f1'],
                                          t['cv']['clip_balanced_macro_f1'],
                                          t['family'] == 'decision_tree'))
    return results, models, selected, dummy, baseline


def new_run(seed, cv_folds, tree_grid, forest_grid, before, summary, manifests):
    run = 'combined_experts_' + datetime.now(ZoneInfo('Asia/Bangkok')).strftime('%Y%m%d_%H%M%S_%f')
    report, models = ROOT/'reports'/run, ROOT/'models'/run
    report.mkdir(parents=True, exist_ok=False)
    models.mkdir(parents=True, exist_ok=False)
    (models/'validation').mkdir()
    (models/'final').mkdir()
    record = dict(run=run, batch=BATCH, started_at=datetime.now(ZoneInfo('Asia/Bangkok')).isoformat(),
                  seed=seed, cv_folds=cv_folds, tree_grid=tree_grid, forest_grid=forest_grid,
                  dataset_sha256=summary['dataset_sha256'], manifests=manifests,
                  selection_policy='TRAIN grouped CV shortlist per family; fixed VAL macro F1 chooses family; TEST after lock only',
                  metrics_policy='Primary: frame macro F1 with equal total weight per clip; fixed class list',
                  sklearn_version=sklearn.__version__, python_version=platform.python_version(),
                  web_before=before, deployed=False, tasks={})
    save_json(report/'training_record.json', record)
    return run, report, models, record


def save_bundle(task, model, candidate, fit_df, fit_splits, path, run):
    spec = TASKS[task]
    bundle = dict(schema='combined_experts_v1', run=run, task=task, model=model,
                  target=spec['target'], feature_columns=candidate['features'],
                  feature_set=candidate['feature_set'], family=candidate['family'],
                  params=candidate['params'], weight_mode=candidate['weight_mode'],
                  fit_splits=fit_splits, fit_frames=len(fit_df), fit_clips=fit_df['clip_id'].nunique(),
                  sklearn_version=sklearn.__version__, dataset_sha256=read_json(DATA.parent/'summary.json')['dataset_sha256'],
                  train_min=fit_df[candidate['features']].min().tolist(),
                  train_max=fit_df[candidate['features']].max().tolist(),
                  experimental=task in ['initial_grip', 'bow_error'],
                  protocol='player_rightmost_comfortable_bow_position' if task == 'initial_grip' else None,
                  target_semantics='angle_wrong_or_bow_floating' if task == 'bow_error' else None,
                  uncertainty_guard_applied=False)
    joblib.dump(bundle, path)
    return bundle


def evaluate_bundle(task, bundle, split, report_dir, tag='selected'):
    """Conditional usable-frame metrics and all-reviewed metrics with unavailable failures."""
    spec = TASKS[task]
    df = load_split(task, split)
    pred = bundle['model'].predict(df[bundle['feature_columns']]).astype(str)
    probability = bundle['model'].predict_proba(df[bundle['feature_columns']]).max(axis=1)
    usable = df[['frame_path', 'clip_id', 'expert', 'timestamp_s', spec['target']]].copy()
    usable['prediction'] = pred
    usable['model_support'] = probability
    audit = pd.read_csv(DATA/spec['dataset']/f'{split}_audit.csv')
    if audit['frame_path'].duplicated().any() or not set(df['frame_path']) <= set(audit['frame_path']):
        raise ValueError('Audit frame identity mismatch')
    all_rows = audit.merge(usable[['frame_path', 'prediction', 'model_support']], on='frame_path', how='left', validate='one_to_one')
    all_rows['prediction'] = all_rows['prediction'].fillna(UNAVAILABLE)
    all_rows['truth'] = all_rows[spec['target']].astype(str)
    all_rows['is_available'] = all_rows['prediction'] != UNAVAILABLE
    all_rows['is_correct'] = all_rows['truth'] == all_rows['prediction']
    conditional = metric_values(df, spec['target'], pred, spec['labels'])
    all_metrics = metric_values(all_rows, spec['target'], all_rows['prediction'], spec['labels'])
    per_expert = {expert: metric_values(g, spec['target'], g['prediction'], spec['labels'])
                  for expert, g in all_rows.groupby('expert')}
    weight = clip_weights(all_rows)
    reports = {
        'unweighted': classification_report(all_rows['truth'], all_rows['prediction'], labels=spec['labels'],
                                           output_dict=True, zero_division=0),
        'clip_balanced': classification_report(all_rows['truth'], all_rows['prediction'], labels=spec['labels'],
                                               sample_weight=weight, output_dict=True, zero_division=0),
    }
    per_clip = []
    for clip, group in all_rows.groupby('clip_id'):
        per_clip.append(dict(clip_id=clip, expert=group['expert'].iloc[0], frames=len(group),
                             available=int(group['is_available'].sum()), accuracy=float(group['is_correct'].mean()),
                             positive_frames=int((group['truth'] == '1').sum()) if spec['labels']==['0','1'] else None))
    result = dict(task=task, split=split, tag=tag, conditional=conditional, all_reviewed=all_metrics,
                  per_expert=per_expert, classification_reports=reports, feature_columns=bundle['feature_columns'],
                  family=bundle['family'], fit_splits=bundle['fit_splits'])
    out = Path(report_dir)/split/tag
    out.mkdir(parents=True, exist_ok=True)
    all_rows.to_csv(out/f'{task}_predictions.csv', index=False, encoding='utf-8-sig')
    all_rows.loc[~all_rows['is_correct']].to_csv(out/f'{task}_errors.csv', index=False, encoding='utf-8-sig')
    pd.DataFrame(per_clip).to_csv(out/f'{task}_per_clip.csv', index=False, encoding='utf-8-sig')
    save_json(out/f'{task}_metrics.json', result)
    return result, all_rows


def result_table(results):
    return pd.DataFrame([dict(task=TASKS[k]['title'], family=r['family'], features=len(r['feature_columns']),
                             usable_frames=r['conditional']['frames'], reviewed_frames=r['all_reviewed']['frames'],
                             clips=r['all_reviewed']['clips'], usable_accuracy=r['conditional']['frame_accuracy'],
                             usable_macro_f1=r['conditional']['frame_macro_f1'],
                             balanced_f1_usable=r['conditional']['clip_balanced_macro_f1'],
                             balanced_accuracy_all=r['all_reviewed']['clip_balanced_accuracy'],
                             balanced_f1_all=r['all_reviewed']['clip_balanced_macro_f1'],
                             balanced_coverage=r['all_reviewed']['clip_balanced_coverage']) for k,r in results.items()])


def plot_confusions(task, rows):
    spec = TASKS[task]
    labels = [*spec['labels'], UNAVAILABLE]
    matrix = confusion_matrix(rows['truth'], rows['prediction'], labels=labels)[:-1, :]
    normalized = np.divide(matrix, matrix.sum(axis=1, keepdims=True),
                           out=np.zeros_like(matrix, dtype=float), where=matrix.sum(axis=1, keepdims=True)!=0)
    fig, axes = plt.subplots(1,2,figsize=(12,4))
    for ax, data, title in zip(axes, [matrix, normalized], ['จำนวนเฟรม', 'สัดส่วนภายในคำตอบจริง']):
        ax.imshow(data, cmap='Blues', vmin=0)
        ax.set_xticks(range(len(labels)), [LABEL_TEXT[x] for x in labels], rotation=15)
        ax.set_yticks(range(len(labels)-1), [LABEL_TEXT[x] for x in labels[:-1]])
        ax.set(xlabel='ผลทำนาย', ylabel='คำตอบจริง', title=f"{spec['title']} · {title}")
        for (i,j), value in np.ndenumerate(data):
            ax.text(j,i,f'{value:.1%}' if data is normalized else str(int(value)), ha='center',va='center',
                    color='white' if value>data.max()/2 else 'black')
    fig.tight_layout()
    return fig


def plot_importance(bundle, title):
    table = pd.DataFrame({'feature':bundle['feature_columns'], 'importance':bundle['model'].feature_importances_})
    table = table.sort_values('importance')
    fig, ax = plt.subplots(figsize=(9,max(3,len(table)*.35)))
    ax.barh(table['feature'],table['importance'],color='#21677c')
    ax.set(title=title, xlabel='Impurity-based feature importance')
    fig.tight_layout()
    return fig, table.sort_values('importance',ascending=False)


def plot_model_tree(bundle, title, max_depth=3):
    model = bundle['model']
    tree = model if isinstance(model,DecisionTreeClassifier) else model.estimators_[0]
    fig, ax = plt.subplots(figsize=(20,9))
    plot_tree(tree, feature_names=bundle['feature_columns'],
              class_names=[LABEL_TEXT.get(str(x),str(x)) for x in tree.classes_]
              if tree is model else [LABEL_TEXT.get(str(x),str(x)) for x in model.classes_],
              filled=True,rounded=True,max_depth=max_depth,fontsize=8,ax=ax)
    ax.set_title(title + (' · ต้นแรกของ Forest เป็นตัวอย่าง' if tree is not model else ''))
    fig.tight_layout()
    return fig


def save_tree_rules(bundle, path):
    model = bundle['model']
    if isinstance(model,DecisionTreeClassifier):
        Path(path).write_text(export_text(model, feature_names=bundle['feature_columns'], max_depth=30),encoding='utf-8')


def posture_joint(split, rows_by_task, report_dir):
    a = rows_by_task['head_down'][['frame_path','clip_id','expert','truth','prediction']]
    b = rows_by_task['shoulder_tilt'][['frame_path','truth','prediction']]
    joined = a.merge(b,on='frame_path',suffixes=('_head','_shoulder'),validate='one_to_one')
    joined['exact_match'] = (joined['truth_head']==joined['prediction_head']) & (joined['truth_shoulder']==joined['prediction_shoulder'])
    both = (joined['truth_head']=='1') & (joined['truth_shoulder']=='1')
    detected_both = (joined['prediction_head']=='1') & (joined['prediction_shoulder']=='1')
    result = dict(frames=len(joined), exact_match=float(joined['exact_match'].mean()),
                  clip_balanced_exact_match=float(np.average(joined['exact_match'],weights=clip_weights(joined))),
                  jointly_positive_frames=int(both.sum()), jointly_positive_clips=int(joined.loc[both,'clip_id'].nunique()),
                  both_symptoms_detected=int((both & detected_both).sum()),
                  joint_recall=float(detected_both[both].mean()) if both.any() else None)
    save_json(Path(report_dir)/split/'posture_joint_metrics.json',result)
    joined.to_csv(Path(report_dir)/split/'posture_joint_predictions.csv',index=False,encoding='utf-8-sig')
    return result


def bootstrap_clip_f1(rows, task, repeats=500, seed=42):
    """Resample physical clips, not correlated frames; descriptive small-sample interval."""
    spec = TASKS[task]
    groups = [g for _,g in rows.groupby('clip_id')]
    rng = np.random.default_rng(seed)
    values = []
    for _ in range(repeats):
        pieces = [groups[index].assign(clip_id=f'bootstrap_{i}')
                  for i,index in enumerate(rng.integers(0,len(groups),len(groups)))]
        sample = pd.concat(pieces,ignore_index=True)
        values.append(f1_score(sample['truth'],sample['prediction'],labels=spec['labels'],average='macro',
                               sample_weight=clip_weights(sample),zero_division=0))
    lo,hi = np.quantile(values,[.025,.975])
    return dict(low=float(lo),high=float(hi),repeats=repeats,
                note='Descriptive 95% clip bootstrap; some resamples omit a class; only two players, not population generalization.')
