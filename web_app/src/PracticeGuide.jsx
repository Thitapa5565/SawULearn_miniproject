import React from 'react';
import {SETTLE_MS} from './initialGrip.js';

export function PracticeGuide({phase,example,onNext,onCancel,status,gestureCount,onStartPractice,canStartPractice,grip,settleSeconds,onSkipGrip}) {
  if(['idle','practice'].includes(phase))return null;
  const index={intro:1,align:1,ready:2,grip:3}[phase] || 1;
  return <section className="practice-guide" aria-label="เตรียมฝึก">
    <div className="guide-progress"><strong>ขั้นตอน {index} / 3 · เตรียมฝึก</strong><button className="button secondary" onClick={onCancel}>ยกเลิกขั้นตอน</button></div>
    {phase==='intro' && <div className="guide-example"><img src={example} alt="ตัวอย่างท่านั่งซออู้ที่เหมาะสมจาก expert01"/><div><h2>เลือกโน้ตและเปิดไมค์ก่อนถอยไปนั่ง</h2><p>ตั้งค่าเสียงด้านล่าง แล้วกดเปิดกล้อง วางกล้องให้เห็นศีรษะ ไหล่ สะโพก และมือขวา หน้าฝึกจะขยายให้เอง</p><button className="button primary" onClick={onNext}>เปิดกล้อง · เข้าหน้าฝึก</button></div></div>}
    {phase==='align' && <><h2>{status.inFrame ? 'เงยหน้าและจัดไหล่ รอทั้งสองช่องสีเขียว' : 'ให้เห็นศีรษะ ไหล่ สะโพก และมือขวาครบ'}</h2><p>นั่งในตำแหน่งที่สบาย ไม่ต้องตรงกลางเป๊ะ แล้วคงท่าประมาณ 2 วินาที</p><div className="alignment-checks"><span className={status.head && status.inFrame ? 'good' : ''}>ศีรษะ / คอ {status.head && status.inFrame ? '✓' : 'รอ'}</span><span className={status.shoulders && status.inFrame ? 'good' : ''}>ไหล่ {status.shoulders && status.inFrame ? '✓' : 'รอ'}</span></div></>}
    {phase==='ready' && <><h2>👍 ยกนิ้วโป้งฝั่งซ้ายของจอเมื่อพร้อม</h2><p>ค้างประมาณ 2 วินาที แล้วลดมือจับคันชัก ดึงไปทางขวาของคุณจนสุดช่วงสีที่สบาย ระบบนับถอยหลัง {SETTLE_MS/1000} วินาทีให้ตั้งท่า แล้วตรวจท่านิ่ง 2 วินาทีก่อนเริ่มฝึก</p><p role="status">{gestureCount ? `พบการยืนยัน ${gestureCount}/2 ครั้ง` : 'รอนิ้วโป้งยืนยันพร้อม'}</p><button className="button secondary" disabled={!canStartPractice} onClick={onStartPractice}>ยืนยันด้วยปุ่มแทนท่ามือ</button></>}
    {phase==='grip' && <><h2>{settleSeconds>0 ? `ดึงคันชักไปทางขวา · เตรียมท่า ${settleSeconds}` : 'ค้างคันชักไว้ทางขวา · ถือนิ่ง'}</h2><p>ทางขวาของผู้เล่น ดึงจนสุดช่วงสีที่สบาย คงมือและลำตัวให้นิ่งประมาณ 2 วินาที ยังไม่ต้องสีซอหรือยกนิ้วโป้งระหว่างตรวจ</p><p role="status">{grip?.stage==='sampling' ? `กำลังเก็บท่านิ่ง · ${grip.samples.length} ภาพ` : settleSeconds>0 ? 'กำลังให้เวลาตั้งท่าเริ่มต้น' : 'รอภาพไหล่ สะโพก และข้อมือขวาที่ชัดเจน'}</p><button className="button secondary" onClick={onSkipGrip}>ฝึกท่านั่งและเสียงก่อน · ข้ามผลการจับ</button></>}
  </section>;
}
