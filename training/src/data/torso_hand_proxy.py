"""Signed bow-wrist position relative to the torso, not XYZ depth or bow geometry."""
import math
import numpy as np

LANDMARKS = {'left_shoulder': 11, 'right_shoulder': 12, 'right_wrist': 16,
             'left_hip': 23, 'right_hip': 24}
FEATURES = ['bow_side_horizontal_ratio', 'bow_side_perpendicular_ratio',
            'wrist_height_screen_ratio', 'wrist_height_body_ratio']


def measure(landmarks, width, height, minimum_visibility=.5):
    if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0
               for v in (width, height)):
        return None, 'invalid_dimensions'
    points = {}
    for name, index in LANDMARKS.items():
        try:
            p = landmarks[index]
            xy = np.array([float(p['x']), float(p['y'])])
            quality = [float(p['visibility']), float(p['presence'])]
            if (not np.isfinite(xy).all() or np.any(xy < 0) or np.any(xy > 1)
                    or not all(math.isfinite(q) for q in quality)
                    or min(quality) < minimum_visibility):
                return None, f'{name}_not_visible'
            points[name] = xy * [width, height]
        except (KeyError, IndexError, TypeError, ValueError):
            return None, f'{name}_not_visible'
    shoulders = (points['left_shoulder'] + points['right_shoulder']) / 2
    hips = (points['left_hip'] + points['right_hip']) / 2
    wrist = points['right_wrist']
    torso = shoulders - hips
    torso_length = float(np.linalg.norm(torso))
    shoulder_width = float(np.linalg.norm(points['left_shoulder'] - points['right_shoulder']))
    if min(torso_length, shoulder_width) < max(10, .03 * math.hypot(width, height)):
        return None, 'body_axis_too_short'
    # Front seated view: the pelvis must be below the shoulder midpoint.
    # Confidence alone does not catch hips hallucinated on the chest/neck.
    if hips[1] - shoulders[1] < max(10, .2 * shoulder_width):
        return None, 'hips_not_below_shoulders'
    if abs(torso[1]) < .2 * torso_length:
        return None, 'body_axis_nearly_horizontal'
    up = torso / torso_length
    side = np.array([up[1], -up[0]])
    if np.dot(side, points['right_shoulder'] - points['left_shoulder']) < 0:
        side = -side
    # The torso LINE is evaluated at wrist height, not at one fixed midpoint.
    axis_x = hips[0] + (wrist[1] - hips[1]) * torso[0] / torso[1]
    screen_direction = np.sign(points['right_shoulder'][0] - points['left_shoulder'][0])
    if abs(points['right_shoulder'][0] - points['left_shoulder'][0]) < .2 * shoulder_width:
        return None, 'shoulders_nearly_vertical'
    values = dict(zip(FEATURES, [float((wrist[0] - axis_x) * screen_direction / shoulder_width),
                               float(np.dot(wrist - hips, side) / shoulder_width),
                               float((hips[1] - wrist[1]) / torso_length),
                               float(np.dot(wrist - hips, up) / torso_length)]))
    return values, 'measured'


def from_csv(row):
    landmarks = [{} for _ in range(33)]
    for name, index in LANDMARKS.items():
        landmarks[index] = {key: row.get(f'{name}_{key}')
                            for key in ('x', 'y', 'visibility', 'presence')}
    return measure(landmarks, float(row['width']), float(row['height']))
