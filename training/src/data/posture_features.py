"""Original aspect-correct posture features used by the submitted models."""
import math

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
