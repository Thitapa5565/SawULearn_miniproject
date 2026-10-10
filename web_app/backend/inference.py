"""Current body-based practice service; loads only the four deployed classifiers."""
import math
import json
from pathlib import Path
import sys
import threading
import cv2
import numpy as np

TRAINING_ROOT = Path(__file__).resolve().parents[2] / 'training'
sys.path.insert(0, str(TRAINING_ROOT))
from src.data.posture_features import FEATURES, NAMES, geometry
from src.data.torso_hand_proxy import measure as measure_body_grip
from src.models.initial_grip import predict as predict_initial_grip, RIGHTMOST_GUARD
from .combined_models import IndependentPostureModels, load_deployment

LANDMARK_IDS = {'nose': 0, 'left_ear': 7, 'right_ear': 8, 'left_shoulder': 11,
                'right_shoulder': 12, 'left_hip': 23, 'right_hip': 24}

class ModelService:
    def __init__(self):
        self.detector = None
        self.hand_detector = None
        self.lock = threading.Lock()
        self.combined = load_deployment(TRAINING_ROOT, Path(__file__).parent/'combined_model.json')
        if self.combined is None:
            raise ValueError('The submitted deployment must enable the combined-expert models')
        self.active_run = self.combined['config']['run']
        bundles = self.combined['bundles']
        self.posture = {'targets': ['head_down', 'shoulder_tilt'],
                        'feature_columns': list(FEATURES),
                        'model': IndependentPostureModels(bundles),
                        'model_name': 'independent_random_forests', 'model_run': self.active_run}
        self.body_grip_run = self.active_run
        self.body_grip = {**bundles['initial_grip'], 'schema': 'initial_grip_rightmost_v1',
                          'variant': 'initial_grip', 'guard': RIGHTMOST_GUARD}
        self.bow_error = bundles['bow_error']

    def classify_bow_level(self, landmarks, width, height):
        return self.classify_combined_bow_error(landmarks, width, height)

    def classify_combined_bow_error(self, landmarks, width, height):
        import pandas as pd
        values, reason = measure_body_grip(landmarks, width, height)
        metadata = {'experimental': True, 'model_run': self.active_run,
                    'source':'body_hand_proxy', 'direct_bow_measurement':False,
                    'target_semantics':'angle_wrong_or_bow_floating'}
        if values is None:
            return {**metadata, 'status':'unavailable', 'prediction':None, 'reason':reason}
        columns = self.bow_error['feature_columns']
        X = np.array([[values[k] for k in columns]])
        lo, hi = np.array(self.bow_error['train_min']), np.array(self.bow_error['train_max'])
        margin = np.maximum((hi-lo)*.2, .02)
        if np.any(X[0]<lo-margin) or np.any(X[0]>hi+margin):
            return {**metadata, 'status':'unavailable', 'prediction':None,
                    'reason':'outside_training_range', 'features':values}
        predicted = int(self.bow_error['model'].predict(pd.DataFrame(X,columns=columns))[0])
        return {**metadata, 'status':'ready', 'prediction':'bow_angle_wrong' if predicted else 'none',
                'features':values, 'message':'ปรับองศาการสีให้ถูกต้อง' if predicted else 'ยังไม่พบมุมผิดหรือสีลอย'}

    def classify_body_grip(self, landmarks, width, height):
        values, reason = measure_body_grip(landmarks, width, height)
        metadata = {'experimental': True, 'model_run': self.body_grip_run,
                    'variant': self.body_grip['variant'], 'source': 'body_initial_experiment'}
        if values is None:
            return {**metadata, 'status': 'unavailable', 'prediction': None, 'reason': reason}
        return {**metadata, **predict_initial_grip(self.body_grip, values), 'features': values}

    def analyze_body_grip(self, encoded, include_hands=False, include_initial_grip=True, include_bow_level=True):
        data = self.analyze_guided(encoded, include_hands=include_hands)
        values, reason = measure_body_grip(data['posture']['landmarks'], data['width'], data['height'])
        data['body_measurement'] = {'status':'ready' if values is not None else 'unavailable',
                                    'features':values, 'reason':reason, 'source':'wrist_hip_geometry'}
        if include_initial_grip:
            data['initial_grip'] = self.classify_body_grip(data['posture']['landmarks'], data['width'], data['height'])
        if include_bow_level:
            data['bow_level'] = self.classify_bow_level(data['posture']['landmarks'], data['width'], data['height'])
        data['bow']['message'] = 'ประเมินแนวการสีจากลำตัวและข้อมือ'
        return data

    def classify_landmarks(self, landmarks, width, height):
        row = {'pose_detected': '1' if landmarks else '0', 'width': width, 'height': height}
        if landmarks:
            for name in NAMES:
                point = landmarks[LANDMARK_IDS[name]]
                for axis in ('x', 'y', 'z', 'visibility', 'presence'):
                    row[name + '_' + axis] = point[axis]
        values, status = geometry(row)
        if values is None:
            return {'status': 'unavailable', 'reason': status, 'predictions': None,
                    'message': 'ขยับกล้องให้เห็นศีรษะ ไหล่ และสะโพกชัดเจน แล้วลองอีกครั้ง'}
        if any(not 0 <= row[name + '_' + axis] <= 1 for name in NAMES for axis in ('x', 'y')):
            return {'status': 'unavailable', 'reason': 'body_outside_frame', 'predictions': None,
                    'message': 'ถอยกล้องอีกนิด ให้เห็นศีรษะ ไหล่ และสะโพกครบในภาพ'}
        X = [[values[k] for k in self.posture['feature_columns']]]
        predicted = self.posture['model'].predict(X)[0]
        return {'status': 'ready', 'model_run':self.active_run,
                'predictions': dict(zip(self.posture['targets'], map(int, predicted))),
                'features': values, 'message': 'วิเคราะห์ท่านั่งแล้ว'}

    @staticmethod
    def decode_image(encoded):
        if not encoded or len(encoded) > 4_000_000:
            raise ValueError('ภาพมีขนาดใหญ่เกินไปหรือไม่มีข้อมูลภาพ')
        # Check dimensions before OpenCV allocation (also reject compressed image bombs).
        from PIL import Image
        from io import BytesIO
        try:
            with Image.open(BytesIO(encoded)) as header:
                width, height = header.size
                if min(width, height) < 32 or max(width, height) > 2560 or width * height > 4_000_000:
                    raise ValueError('ใช้ภาพขนาด 32–2560 พิกเซล และไม่เกิน 4 ล้านพิกเซล')
                header.verify()
        except ValueError:
            raise
        except Exception as error:
            raise ValueError('ไม่สามารถอ่านภาพนี้ได้ ลองใช้ JPG หรือ PNG') from error
        bgr = cv2.imdecode(np.frombuffer(encoded, np.uint8), cv2.IMREAD_COLOR)
        if bgr is None:
            raise ValueError('ไม่สามารถอ่านข้อมูลภาพได้')
        return bgr

    def analyze_image(self, encoded):
        bgr = self.decode_image(encoded)
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions
        from mediapipe.tasks.python import vision
        # IMAGE mode isolates uploaded/live frames; no tracking state crosses sessions.
        with self.lock:
            if self.detector is None:
                self.detector = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=str(TRAINING_ROOT / 'models/pretrained/pose_landmarker_heavy.task')),
                    running_mode=vision.RunningMode.IMAGE, num_poses=1,
                    min_pose_detection_confidence=.5, min_pose_presence_confidence=.5))
            result = self.detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,
                                                   data=cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)))
        points = [{'x': p.x, 'y': p.y, 'z': p.z, 'visibility': p.visibility, 'presence': p.presence}
                  for p in result.pose_landmarks[0]] if result.pose_landmarks else []
        output = self.classify_landmarks(points, bgr.shape[1], bgr.shape[0])
        return {**output, 'landmarks': points, 'width': bgr.shape[1], 'height': bgr.shape[0]}

    def analyze_guided(self, encoded, include_hands=False):
        posture = self.analyze_image(encoded)
        hands = self.analyze_hands(encoded,pose=posture['landmarks'])['hands'] if include_hands else []
        return {'posture':posture,'hands':hands,'width':posture['width'],'height':posture['height'],
                'bow':{'status':'unavailable','prediction':None,'points':{},
                       'message':'เตรียมท่านั่งก่อนตรวจการจับเริ่มต้น'}}

    def analyze_hands(self, encoded, pose=None):
        bgr = self.decode_image(encoded)
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision
        height, width = bgr.shape[:2]
        if pose is None:
            pose = self.analyze_image(encoded)['landmarks']
        regions = [(0, 0, width, height)]
        # Wrists/forearms provide image crops, not replacements for finger marks.
        # Enlarge the crop before hand detection when the hands occupy few pixels.
        if pose:
            for wrist, elbow, index in [(15,13,19),(16,14,20)]:
                if min(pose[wrist]['visibility'], pose[wrist]['presence']) < .5:
                    continue
                w = np.array([pose[wrist]['x']*width,pose[wrist]['y']*height])
                e = np.array([pose[elbow]['x']*width,pose[elbow]['y']*height])
                finger = np.array([pose[index]['x']*width,pose[index]['y']*height])
                center = (w+finger)/2
                radius = max(40, .6*np.linalg.norm(w-e), 1.5*np.linalg.norm(w-finger))
                x0,y0 = np.maximum(0, center-radius).astype(int)
                x1,y1 = np.minimum([width,height], center+radius).astype(int)
                if min(x1-x0,y1-y0) >= 32:
                    regions.append((x0,y0,x1,y1))
        hands = []
        with self.lock:
            if self.hand_detector is None:
                self.hand_detector = vision.HandLandmarker.create_from_options(vision.HandLandmarkerOptions(
                    base_options=BaseOptions(model_asset_path=str(TRAINING_ROOT / 'models/pretrained/hand_landmarker.task')),
                    running_mode=vision.RunningMode.IMAGE, num_hands=2,
                    min_hand_detection_confidence=.5, min_hand_presence_confidence=.5))
            for x0,y0,x1,y1 in regions:
                if len(hands) >= 2:
                    break
                crop = bgr[y0:y1,x0:x1]
                factor = max(1, 256/min(crop.shape[:2]))
                crop = cv2.resize(crop, None, fx=factor, fy=factor)
                for turns in ([0] if x1-x0 == width else [0,1,3]):
                    rgb = np.ascontiguousarray(np.rot90(cv2.cvtColor(crop,cv2.COLOR_BGR2RGB),turns))
                    result = self.hand_detector.detect(mp.Image(image_format=mp.ImageFormat.SRGB,data=rgb))
                    for landmarks in result.hand_landmarks:
                        if not all(0 <= p.x <= 1 and 0 <= p.y <= 1 for p in landmarks):
                            continue
                        mapped = [((p.x,p.y),(1-p.y,p.x),(1-p.x,1-p.y),(p.y,1-p.x))[turns] for p in landmarks]
                        hand = [{'x':(x0+x*(x1-x0))/width,'y':(y0+y*(y1-y0))/height,
                                 'z':p.z*(x1-x0)/width} for p,(x,y) in zip(landmarks,mapped)]
                        if any(np.linalg.norm([(hand[0]['x']-old[0]['x'])*width,
                                              (hand[0]['y']-old[0]['y'])*height]) < .04*width for old in hands):
                            continue
                        hands.append(hand)
                        if len(hands) >= 2:
                            break
                    if len(hands) >= 2:
                        break
        return {'hands': hands, 'width': bgr.shape[1], 'height': bgr.shape[0],
                'status': 'ready' if hands else 'unavailable'}

    def close(self):
        if self.detector is not None:
            self.detector.close()
            self.detector = None
        if self.hand_detector is not None:
            self.hand_detector.close()
            self.hand_detector = None
