// Combined angle/floating target; unavailable input never becomes a correct result.
export function bowModelFeedback(observation) {
  if(observation?.status!=='ready' || !['none','bow_angle_wrong'].includes(observation.prediction))
    return {state:'waiting',label:'รอภาพมือและลำตัวชัด',
      detail:observation?.reason==='outside_training_range' ? 'ท่านี้อยู่นอกช่วงข้อมูลที่เรียนรู้ ลองจัดท่าและกล้องใหม่' : 'ให้เห็นไหล่ สะโพก และข้อมือขวา',
      prediction:null,model_run:observation?.model_run || null};
  const warning=observation.prediction==='bow_angle_wrong';
  return {state:warning ? 'warning' : 'correct',
    label:warning ? 'ปรับองศาการสีให้ถูกต้อง' : 'ยังไม่พบมุมผิดหรือสีลอย',
    detail:warning ? 'ลองปรับแนวคันชักและระดับมือให้เหมาะสม' : 'ประเมินจากตำแหน่งลำตัวและข้อมือในภาพ',
    prediction:observation.prediction,model_run:observation.model_run};
}
