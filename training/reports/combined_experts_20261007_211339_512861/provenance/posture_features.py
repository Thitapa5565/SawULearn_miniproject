"""Aspect-correct body geometry with fixed clip splits and explicit exclusions."""
import math
from collections import Counter

from .pose_pipeline import load_context, read_csv, sha256, write_csv, write_json

NAMES = ('nose', 'left_ear', 'right_ear', 'left_shoulder', 'right_shoulder', 'left_hip', 'right_hip')
FEATURES = ('shoulder_tilt_deg', 'head_tilt_deg', 'torso_tilt_deg', 'head_height_ratio',
            'head_side_offset_ratio', 'nose_below_ears_ratio', 'torso_length_ratio',
            'hip_width_ratio', 'nose_depth_vs_shoulders_ratio', 'shoulder_depth_vs_hips_ratio')
META = ('clip_id', 'frame_path', 'source_frame_index', 'timestamp_s', 'split', 'video_sha256',
        'expert', 'session_id', 'take_id', 'category', 'label', 'error_type')


def geometry(row, threshold=.5):
    if row['pose_detected'] != '1':
        return None, 'pose_missing'
    width, height = int(row['width']), int(row['height'])
    points = {}
    for name in NAMES:
        try:
            values = {a: float(row[name+'_'+a]) for a in ('x', 'y', 'z', 'visibility', 'presence')}
        except (KeyError, ValueError):
            return None, 'invalid_body_point'
        if not all(math.isfinite(v) for v in values.values()):
            return None, 'invalid_body_point'
        if values['visibility'] < threshold or values['presence'] < threshold:
            return None, 'body_point_low_visibility'
        points[name] = (values['x']*width, values['y']*height, values['z']*width)
    def midpoint(a, b):
        return tuple((x+y)/2 for x, y in zip(points[a], points[b]))
    def subtract(a, b):
        return tuple(x-y for x, y in zip(a, b))
    def length(v):
        return math.hypot(v[0], v[1])
    def tilt(a, b):
        dx, dy, _ = subtract(a, b)
        if dx < 0:
            dx, dy = -dx, -dy
        return math.degrees(math.atan2(dy, dx))
    shoulders = midpoint('left_shoulder', 'right_shoulder')
    hips = midpoint('left_hip', 'right_hip')
    ears = midpoint('left_ear', 'right_ear')
    shoulder_axis = subtract(points['left_shoulder'], points['right_shoulder'])
    if shoulder_axis[0] < 0:
        shoulder_axis = tuple(-v for v in shoulder_axis)
    scale = length(shoulder_axis)
    torso = subtract(shoulders, hips)
    torso_length = length(torso)
    if scale < 10 or torso_length < 10:
        return None, 'degenerate_body_geometry'
    head = subtract(points['nose'], shoulders)
    values = (tilt(points['left_shoulder'], points['right_shoulder']),
              tilt(points['left_ear'], points['right_ear']), math.degrees(math.atan2(torso[0], -torso[1])),
              (head[0]*torso[0]+head[1]*torso[1])/torso_length/scale,
              (head[0]*shoulder_axis[0]+head[1]*shoulder_axis[1])/(scale*scale),
              (points['nose'][1]-ears[1])/scale, torso_length/scale,
              length(subtract(points['left_hip'], points['right_hip']))/scale,
              (points['nose'][2]-shoulders[2])/scale, (shoulders[2]-hips[2])/scale)
    if not all(math.isfinite(v) for v in values):
        return None, 'invalid_body_geometry'
    return dict(zip(FEATURES, values)), 'ready'


def prepare(context):
    paths = context['paths']
    source = paths['processed'] / 'pose_landmarks/landmarks.csv'
    rows = read_csv(source)
    frames = read_csv(paths['extracted'] / 'frame_index.csv')
    if len(rows) != len(frames) or any(any(r[k] != f[k] for k in f) for r, f in zip(rows, frames)):
        raise ValueError('Pose table does not match authoritative frame index')
    tasks = {c['clip_id']: c['tasks'] for c in context['clips']}
    accepted, audit = [], []
    for row in rows:
        physical = tasks[row['clip_id']][0]
        if any(row[k] != physical[k] for k in ('split', 'video_sha256', 'expert')):
            raise ValueError('Pose data changed source split or video identity')
        selected = [t for t in tasks[row['clip_id']] if t['category']=='playing_posture'
                    and float(t['start_s']) <= float(row['timestamp_s']) < float(t['end_s'])]
        if not selected:
            continue
        if len(selected) != 1:
            raise ValueError('Ambiguous posture label')
        task = selected[0]
        metadata = {k: (row[k] if k in row else task[k]) for k in META}
        for k in ('category', 'label', 'error_type', 'session_id', 'take_id'):
            metadata[k] = task[k]
        values, status = geometry(row)
        audit.append({**metadata, 'geometry_status': status})
        if values is not None:
            accepted.append({**metadata, **values})
    counts = Counter(r['clip_id'] for r in accepted)
    for row in accepted:
        row['clip_weight'] = 1/counts[row['clip_id']]
    dest = paths['processed'] / 'training_ready/playing_posture'
    fields = [*META, 'clip_weight', *FEATURES]
    write_csv(dest/'all_features.csv', accepted, fields)
    write_csv(dest/'audit.csv', audit, [*META, 'geometry_status'])
    coverage = {}
    for split in ('train', 'val', 'test'):
        subset = [r for r in accepted if r['split']==split]
        write_csv(dest/f'{split}.csv', subset, fields)
        coverage[split] = {label: {'frames': sum(r['error_type']==label for r in subset),
                                  'clips': len({r['clip_id'] for r in subset if r['error_type']==label})}
                           for label in ('none', 'back_hunched', 'shoulder_tilt', 'head_down')}
    expected_clips = {c['clip_id'] for c in context['clips'] if any(t['category']=='playing_posture' for t in c['tasks'])}
    summary = {'category': 'playing_posture', 'feature_rows': len(accepted), 'audited_frames': len(audit),
               'excluded_by_reason': dict(Counter(r['geometry_status'] for r in audit if r['geometry_status']!='ready')),
               'coverage': coverage, 'source_landmarks_sha256': sha256(source),
               'source_labels_sha256': context['labels_sha256'], 'feature_columns': list(FEATURES),
               'target_column': 'error_type', 'sample_weight_column': 'clip_weight',
               'split_files': {split:f'{split}.csv' for split in ('train','val','test')},
               'split_sha256': {split:sha256(dest/f'{split}.csv') for split in ('train','val','test')},
               'data_ready': expected_clips==set(counts) and all(v['frames']>0 for split in coverage.values() for v in split.values()),
               'note': 'Data-format and clip coverage readiness only. Fixed splits retained; no model trained. Geometry uses pixel aspect ratio; z is relative MediaPipe depth, not physical distance.'}
    write_json(dest/'manifest.json', summary)
    return summary


def main():
    summary = prepare(load_context())
    print(f"Posture: {summary['feature_rows']} feature rows; data_ready={summary['data_ready']}")


if __name__ == '__main__':
    main()
