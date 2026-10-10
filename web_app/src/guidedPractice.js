export const CAPTURE_SECONDS=30;
export const GUIDE_STEPS=['เริ่มฝึก','จัดท่านั่ง','ยืนยันพร้อม','จับภาพ 30 วินาที','มาร์ก A–E','กลับที่นั่ง','ยกนิ้วโป้ง · พร้อมฝึก'];

export function alignmentStatus(posture,{relaxed=false}={}) {
  const p=posture?.landmarks;
  const visible=i=>p?.[i] && Math.min(p[i].visibility ?? 0,p[i].presence ?? 0)>=.5;
  const available=posture?.status==='ready' && posture.predictions && [0,11,12,23,24].every(visible);
  if(!available)return {inFrame:false,head:false,shoulders:false,ready:false};
  const shoulderX=(p[11].x+p[12].x)/2,hipY=(p[23].y+p[24].y)/2;
  const width=Math.abs(p[11].x-p[12].x);
  const inFrame=relaxed ? returnStatus(posture).inFrame : p[0].x>=.28 && p[0].x<=.72 && p[0].y>=.08 && p[0].y<=.5 &&
    shoulderX>=.28 && shoulderX<=.72 && hipY>=.48 && hipY<=.94 && width>=.12 && width<=.62;
  const head=posture.predictions.head_down===0,shoulders=posture.predictions.shoulder_tilt===0;
  return {inFrame,head,shoulders,ready:inFrame && head && shoulders};
}

// Returning to the seat is a framing check, independent of posture correctness
// and instrument patch matching. Do not block posture/audio on a missing bow.
export function returnStatus(posture) {
  const p=posture?.landmarks;
  const visible=[0,11,12,23,24].every(i=>p?.[i] &&
    Math.min(p[i].visibility ?? 0,p[i].presence ?? 0)>=.5 &&
    ['x','y'].every(k=>Number.isFinite(p[i][k]) && p[i][k]>=0 && p[i][k]<=1));
  if(!visible)return {inFrame:false,head:false,shoulders:false,ready:false};
  const center=(p[11].x+p[12].x)/2,hipY=(p[23].y+p[24].y)/2,width=Math.abs(p[11].x-p[12].x);
  const inFrame=p[0].x>=.15 && p[0].x<=.85 && p[0].y>=.02 && p[0].y<=.65 &&
    center>=.15 && center<=.85 && hipY>=.40 && hipY<=.99 && width>=.10 && width<=.75;
  return {inFrame,head:inFrame,shoulders:inFrame,ready:inFrame};
}

export function observeReadiness(previous,ready,time,duration=1500) {
  if(!ready)return {since:null,last:time,count:0,complete:false};
  const continuous=previous?.count>0 && time-previous.last<=5000;
  const since=continuous ? previous.since : time,count=continuous ? previous.count+1 : 1;
  return {since,last:time,count,complete:count>=2 && time-since>=duration};
}

export function phaseReadiness(phase,posture,hands,{relaxedAlignment=false}={}) {
  if(phase==='align')return alignmentStatus(posture,{relaxed:relaxedAlignment}).ready;
  if(phase==='return')return returnStatus(posture).ready;
  if(phase==='consent' || phase==='ready')return thumbsUpOnScreenLeft(hands);
  return false;
}

export function bowTrackingMessage(bow) {
  if(bow?.status==='ready')return 'จับคู่จุดคันชักครบแล้ว';
  const d=bow?.tracking;
  const messages={body_not_visible:'ยังเห็นศีรษะ ไหล่ หรือสะโพกไม่ครบ',
    frame_size_changed:'แนวหรือขนาดภาพกล้องเปลี่ยน กรุณาวางกลับแนวเดิมหรือมาร์กใหม่',
    outside_frame:'จุดอยู่ใกล้ขอบภาพ ให้เห็นปลายคันชักและสายซอครบ',
    weak_texture:'บริเวณจุดยังไม่ชัด ลองเพิ่มแสงและถือนิ่ง',
    patch_changed:'ตำแหน่งในภาพปัจจุบันต่างจากภาพที่มาร์ก ลองถือซอใกล้ท่าเดิม',
    ambiguous_patch:'ยังแยกจุดจากบริเวณรอบข้างไม่ได้ ลองถือซอและคันชักนิ่ง',
    inconsistent_match:'จุดที่พบยังไม่สอดคล้องกับภาพที่มาร์ก กำลังลองหาใหม่',
    geometry_changed:'แนวคันชักหรือสายต่างจากภาพที่มาร์ก ลองถือใกล้ท่าเดิม',
    torso_not_visible:'ยังเห็นแนวไหล่และลำตัวไม่ครบ',
    torso_transform_unreliable:'ยังเทียบตำแหน่งกับภาพเดิมไม่ได้ ลองวางกล้องใกล้มุมเดิม',
    camera_changed_too_much:'มุมกล้องเปลี่ยนมาก ลองวางกลับมุมเดิมหรือมาร์กใหม่',
    instrument_outside_frame:'ซอหรือคันชักอยู่นอกภาพ ให้เห็นปลายครบ',
    invalid_geometry:'ยังหาแนวคันชักหรือสายไม่ครบ'};
  return `${d?.point ? `จุด ${d.point}: ` : ''}${messages[d?.reason] || bow?.message || 'กำลังหาจุดจากภาพที่บันทึกไว้'}`;
}

export function thumbsUpOnScreenLeft(hands) {
  const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y);
  return (hands || []).some(p=>{
    if(p.length!==21 || p.some(v=>!Number.isFinite(v.x)||!Number.isFinite(v.y)))return false;
    const scale=distance(p[0],p[9]);if(scale<.025 || p[0].x>=.5)return false;
    // A vertical, extended thumb and at least three curled fingers. Screen-left,
    // regardless of anatomical handedness; video is not mirrored.
    const extended=p[4].y<p[3].y-.10*scale && p[4].y<p[2].y-.35*scale &&
      distance(p[4],p[0])>distance(p[2],p[0])*1.25;
    const curled=[8,12,16,20].filter(i=>distance(p[i],p[0])<distance(p[i-2],p[0])*1.25).length;
    return extended && curled>=3;
  });
}

export function guideTransition(phase,event) {
  const transitions={idle:{start:'intro'},intro:{next:'align'},align:{aligned:'consent'},
    consent:{thumbs:'capture'},capture:{captured:'mark'},mark:{saved:'return',retake:'capture'},
    return:{aligned:'ready',confirm_return:'ready',retake:'capture'},
    ready:{thumbs:'practice',confirm_ready:'practice',retake:'capture'},practice:{retake:'capture'}};
  return event==='cancel' ? 'idle' : transitions[phase]?.[event] || phase;
}
