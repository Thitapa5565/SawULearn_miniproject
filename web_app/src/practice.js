export const HISTORY_KEY = 'sawulearn.practice.v1';
export function displayDimensions(analysis,videoSize,showVideo) {
  const valid=s=>s && ['width','height'].every(k=>Number.isFinite(s[k]) && s[k]>0);
  const size=showVideo && valid(videoSize) ? videoSize : valid(analysis) ? analysis : {width:1280,height:720};
  return {width:size.width,height:size.height};
}
export const pointDefinitions = [
  ['A', 'ปลายด้ามฝั่งจับ', '#277aa2'], ['B', 'ปลายคันชักอีกด้าน', '#865bb4'],
  ['C', 'นิ้วหัวแม่โป้ง', '#c97e31'], ['D', 'บนสายใกล้ลูกบิด', '#42816a'], ['E', 'บนสายตรงหย่อง', '#b34f62'],
];
export function postureFeedback(posture) {
  if(posture?.status !== 'ready' || !posture.predictions) return null;
  return [
    {key:'head_down',label:'ก้มหน้า',active:posture.predictions.head_down === 1},
    {key:'shoulder_tilt',label:'ไหล่เอียง',active:posture.predictions.shoulder_tilt === 1},
  ];
}
export function normalizePoint(clientX, clientY, rect) {
  return [Math.min(1, Math.max(0, (clientX - rect.left) / rect.width)),
    Math.min(1, Math.max(0, (clientY - rect.top) / rect.height))];
}
export function summarizePosture(samples) {
  const usable = samples.filter(s => s.status === 'ready' && s.predictions);
  return { total: samples.length, usable: usable.length,
    headDown: usable.filter(s => s.predictions.head_down === 1).length,
    shoulderTilt: usable.filter(s => s.predictions.shoulder_tilt === 1).length,
    neither: usable.filter(s => !s.predictions.head_down && !s.predictions.shoulder_tilt).length };
}
export function readHistory(storage = localStorage) {
  try { const value = JSON.parse(storage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(value) ? value.filter(s => s && typeof s.id === 'string' && typeof s.date === 'string').slice(0, 100) : [];
  } catch { return []; }
}
export function saveHistory(session, storage = localStorage) {
  const history = [session, ...readHistory(storage)].slice(0, 100);
  storage.setItem(HISTORY_KEY, JSON.stringify(history));
  return history;
}
export const bowLabels = { none: 'ไม่พบข้อผิดพลาดที่ตรวจได้', grip_too_high: 'ตำแหน่งจับสูงเกินไป',
  grip_too_low: 'ตำแหน่งจับต่ำเกินไป', bow_angle_wrong: 'มุมหรือระยะคันชักยังไม่เหมาะสม' };
