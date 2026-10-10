// Collect only a fresh, stationary initial pose. Never reinterpret missing data as correct.
export const SETTLE_MS=10000, WINDOW_MS=2000, TIMEOUT_MS=SETTLE_MS+20000;
export const gripLabels={none:'ตำแหน่งจับพอดี',grip_too_high:'จับสูงไป',grip_too_low:'จับต่ำไป',uncertain:'ยังสรุปการจับไม่ได้'};
export function gripResultLabel(check) {
  return check?.prediction==='uncertain' && check.candidate_prediction==='grip_too_high' ? 'อาจจับสูงไป' : gripLabels[check?.prediction] || gripLabels.uncertain;
}
export function newGripCheck(now) {return {started:now,samples:[],stage:'settling',prediction:null};}
export function observeGrip(previous,observation,time,{thumbRaised=false}={}) {
  if(previous.stage==='locked')return previous;
  if(time<previous.started+SETTLE_MS)return {...previous,stage:'settling',samples:[]};
  if(time-previous.started>TIMEOUT_MS)return {...previous,stage:'locked',prediction:'uncertain',reason:'timeout'};
  const x=observation?.features?.bow_side_horizontal_ratio,height=observation?.features?.wrist_height_body_ratio;
  if(thumbRaised || observation?.status!=='ready' || !Object.hasOwn(gripLabels,observation.prediction) ||
      !Number.isFinite(x) || !Number.isFinite(height) || height>=.85)
    return {...previous,stage:'waiting',samples:[],reason:thumbRaised || height>=.85 ? 'lower_hand' : observation?.reason || 'missing_pose'};
  let samples=previous.samples;
  if(samples.length && (time-samples.at(-1).time>2500 || time<=samples.at(-1).time ||
      Math.abs(x-samples[0].features.bow_side_horizontal_ratio)>.15))samples=[];
  samples=[...samples,{time,prediction:observation.prediction,features:observation.features,
    candidate_prediction:observation.candidate_prediction,model_support:observation.model_support,reason:observation.reason}];
  if(samples.length<3 || time-samples[0].time<WINDOW_MS)return {...previous,stage:'sampling',samples,reason:null};
  const votes={none:0,grip_too_high:0,grip_too_low:0,uncertain:0};
  samples.forEach(s=>votes[s.prediction]++);
  const best=Object.keys(votes).sort((a,b)=>votes[b]-votes[a])[0];
  const prediction=votes[best]>samples.length/2 ? best : 'uncertain';
  const candidates={grip_too_high:0,grip_too_low:0};
  samples.filter(s=>s.prediction==='uncertain').forEach(s=>{if(Object.hasOwn(candidates,s.candidate_prediction))candidates[s.candidate_prediction]++;});
  const candidate=Object.keys(candidates).find(k=>candidates[k]>samples.length/2) || null;
  return {...previous,stage:'locked',samples,votes,prediction,candidate_prediction:prediction==='uncertain' ? candidate : null,
    model_run:observation.model_run,variant:observation.variant,experimental:true,
    reason:prediction==='uncertain' ? candidate ? 'model_disagreement' : 'mixed_votes' : null};
}
export function gripMessage(check) {
  if(!check)return 'เตรียมท่าเริ่มฝึก';
  if(check.stage==='locked')return check.reason==='model_disagreement' ?
    `${gripResultLabel(check)} · ยังแยกท่าจับผิดกับท่าพอดีไม่ชัด` : `${gripResultLabel(check)} · ผลตอนเริ่มฝึก`;
  if(check.stage==='settling')return 'ลดนิ้วโป้งลง ดึงคันชักไปทางขวาของคุณจนสุดช่วงสีที่สบาย แล้วถือนิ่ง';
  if(check.stage==='sampling')return 'ค้างคันชักไว้ทางขวา · กำลังตรวจท่านิ่ง 2 วินาที';
  return check.reason==='lower_hand' ? 'วางมือกลับมาจับคันชักก่อนตรวจ' : 'ให้เห็นไหล่ สะโพก และข้อมือขวาชัด แล้วถือนิ่ง';
}
