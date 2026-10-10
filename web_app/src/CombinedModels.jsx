import React from 'react';

const TASKS=[['head_down','ก้มหน้า'],['shoulder_tilt','ไหล่เอียง'],
  ['initial_grip','จับสูง–ต่ำตอนเริ่ม'],['bow_error','ปรับองศาการสี']];
const modelName=name=>name==='random_forest' ? 'Random Forest' : 'Decision Tree';
const number=value=>Number.isFinite(value) ? value.toFixed(3) : '—';

export default function CombinedModels({info}) {
  return <div className="content-page">
    <div className="intro"><div><div className="eyebrow">MODEL · EXPERT01 + EXPERT02</div>
      <h1>ผลโมเดลที่ใช้อยู่</h1><p>ฝึกจากข้อมูลผู้เล่นสองคน แยกก้มหน้าและไหล่เอียงเป็นสองคำตอบ</p></div></div>
    <div className="model-cards">{TASKS.map(([task,title])=>{
      const result=info.test[task],m=result.all_reviewed;
      return <article key={task}><span className="eyebrow muted">{modelName(result.family)} · TEST</span>
        <h2>{title}</h2><strong>{number(m.clip_balanced_macro_f1)}</strong>
        <p>Macro F1 · รวมภาพที่จุดไม่ครบ · ให้น้ำหนักคลิปเท่ากัน</p>
        <span>{m.frames} เฟรม / {m.clips} คลิป<br/>จุดครบ {(m.clip_balanced_coverage*100).toFixed(1)}% เมื่อคลิปมีน้ำหนักเท่ากัน</span>
      </article>;
    })}</div>
    <h2 className="section-title">Validation และ Test</h2>
    <p className="muted-copy">Validation ใช้รุ่นฝึกด้วย train ส่วน test ใช้รุ่นสุดท้ายที่ฝึกด้วย train + validation หลังเลือกค่าแล้ว</p>
    <div className="table-wrap"><table><thead><tr><th>งาน</th><th>โมเดล</th><th>Feature</th><th>VAL F1 เมื่อจุดครบ</th><th>TEST F1 เมื่อจุดครบ</th><th>TEST F1 รวมจุดไม่ครบ</th></tr></thead>
      <tbody>{TASKS.map(([task,title])=>{const v=info.validation[task],t=info.test[task];return <tr key={task}>
        <td>{title}</td><td>{modelName(t.family)}</td><td>{t.feature_columns.length}</td>
        <td>{number(v.conditional.clip_balanced_macro_f1)}</td><td>{number(t.conditional.clip_balanced_macro_f1)}</td>
        <td>{number(t.all_reviewed.clip_balanced_macro_f1)}</td></tr>;})}</tbody></table></div>
    <h2 className="section-title">ผล test รายคำตอบ</h2>
    <div className="table-wrap"><table><thead><tr><th>คำตอบ</th><th>Precision</th><th>Recall</th><th>F1</th><th>เฟรมจริง</th></tr></thead>
      <tbody>{TASKS.flatMap(([task,title])=>{
        const labels=task==='initial_grip' ? [['none','จับพอดี'],['grip_too_high','จับสูง'],['grip_too_low','จับต่ำ']] : [['1',title]];
        return labels.map(([label,text])=>{const m=info.test[task].classification_reports.unweighted[label];return <tr key={task+label}>
          <td>{text}</td><td>{number(m.precision)}</td><td>{number(m.recall)}</td><td>{number(m['f1-score'])}</td><td>{m.support}</td></tr>;});
      })}</tbody></table></div>
    <div className="content-note"><p>ข้อมูลมีผู้เล่นสองคน โดยทั้งสองคนมีคลิปในชุดฝึกและทดสอบ จึงยังไม่ใช่ผลทดสอบผู้เล่นใหม่ทั้งคน
      ท่านั่งทายถูกทั้งสองคำตอบต่อเฟรม {(info.posture_joint.exact_match*100).toFixed(1)}%
      {info.posture_joint.jointly_positive_frames===0 && ' · ชุด test ไม่มีเฟรมที่ผิดทั้งก้มหน้าและไหล่เอียงพร้อมกัน จึงยังวัดความไวของกรณีร่วมไม่ได้'}</p></div>
    <div className="content-note"><p>คำเตือนมุมผิดหรือสีลอยเป็นรุ่นทดลองจากตำแหน่งลำตัวและมือ ไม่ได้วัดซอหรือหย่องโดยตรง
      ชุด test ตรวจพบภาพผิด {(info.test.bow_error.classification_reports.unweighted['1'].recall*100).toFixed(1)}% เมื่อรวมภาพที่จุดไม่ครบ
      การใช้งานจริงมีการรอเมื่อจุดไม่ครบ/อยู่นอกช่วงข้อมูล และตรวจการจับจากหลายเฟรมพร้อมเกณฑ์ความไม่แน่ใจ จึงอาจสรุปผลได้น้อยกว่าคะแนนตัวจำแนกในตาราง</p></div>
    <details><summary>พารามิเตอร์และ Feature ที่ใช้</summary>{TASKS.map(([task,title])=>{
      const s=info.selection[task].selected;return <div key={task}><h3>{title}</h3><p>{JSON.stringify(s.params)}</p><p>{s.features.join(', ')}</p></div>;
    })}<p>Run: {info.run}</p></details>
  </div>;
}
