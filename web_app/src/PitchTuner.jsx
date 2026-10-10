import React,{useState,useRef,useEffect} from 'react';
import {NOTE_TABLE,detectPitch,pitchFeedback,PITCH_TOLERANCE_HZ,PITCH_METER_RANGE_HZ} from './pitch.js';
import {microphoneGraph,inputLevel,microphoneMessage} from './microphone.js';
import {gripResultLabel} from './initialGrip.js';

export default function PitchTuner({active,initialGrip=null}) {
  const [noteId,setNoteId]=useState('do'),[listening,setListening]=useState(false),[starting,setStarting]=useState(false);
  const [pitch,setPitch]=useState(null),[error,setError]=useState('');
  const [signal,setSignal]=useState(null);
  const audio=useRef(null),generation=useRef(0),alive=useRef(true);
  const note=NOTE_TABLE.find(n=>n.id===noteId),feedback=pitchFeedback(pitch,note);
  const meterDelta=feedback ? Math.max(-PITCH_METER_RANGE_HZ,Math.min(PITCH_METER_RANGE_HZ,feedback.deltaHz)) : 0;
  const greenBand=PITCH_TOLERANCE_HZ/PITCH_METER_RANGE_HZ*45;
  const stop=()=>{generation.current++;const old=audio.current;audio.current=null;
    if(old){clearTimeout(old.timer);old.source.disconnect();old.analyser.disconnect();old.silent.disconnect();old.stream.getTracks().forEach(t=>t.stop());void old.context.close().catch(()=>{});}
    if(alive.current){setListening(false);setStarting(false);setPitch(null);setSignal(null);}};
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;stop();};},[]);
  useEffect(()=>{if(!active)stop();},[active]);
  useEffect(()=>{const hidden=()=>{if(document.hidden)stop();};document.addEventListener('visibilitychange',hidden);
    return()=>document.removeEventListener('visibilitychange',hidden);},[]);
  const resume=()=>{const current=audio.current;if(current)void current.context.resume().catch(()=>setError('เริ่มระบบเสียงต่อไม่ได้ ลองปิดและเปิดไมค์ใหม่'));};
  useEffect(()=>{window.addEventListener('practice-camera-ready',resume);return()=>window.removeEventListener('practice-camera-ready',resume);},[]);
  const start=async()=>{stop();setError('');setStarting(true);const version=generation.current;
    let context,stream;
    try {
      if(!window.isSecureContext||!navigator.mediaDevices?.getUserMedia)throw new Error('เปิดเว็บผ่าน HTTPS เพื่อใช้ไมโครโฟน');
      const Context=window.AudioContext||window.webkitAudioContext;
      if(!Context)throw new Error('เบราว์เซอร์นี้ยังเปิดระบบเสียงไม่ได้');
      context=new Context();await context.resume(); // User click is required on iPad.
      stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:false,noiseSuppression:false,autoGainControl:false},video:false});
      if(!alive.current||version!==generation.current){stream.getTracks().forEach(t=>t.stop());await context.close();return;}
      const graph=microphoneGraph(context,stream),{analyser}=graph;
      // Camera/microphone acquisition may interrupt the iPad audio session.
      void context.resume().catch(()=>{});
      const state={context,stream,...graph,timer:null,resumedAt:0},buffer=new Float32Array(analyser.fftSize),recent=[];
      audio.current=state;setListening(true);setStarting(false);
      const sample=()=>{if(audio.current!==state)return;
        const track=stream.getAudioTracks()[0];
        if(track?.readyState==='ended'){stop();setError('ไมค์หยุดแล้ว กดเปิดไมค์อีกครั้ง');return;}
        if(context.state!=='running' && Date.now()-state.resumedAt>2000){state.resumedAt=Date.now();void context.resume().catch(()=>{});}
        buffer.fill(0);
        if(context.state==='running')analyser.getFloatTimeDomainData(buffer);
        const level=inputLevel(buffer);setSignal({...level,state:context.state,muted:track?.muted||false});
        const value=context.state==='running' && !track?.muted ? detectPitch(buffer,context.sampleRate) : null;
        if(value){recent.push(value.hz);if(recent.length>3)recent.shift();setPitch([...recent].sort((a,b)=>a-b)[Math.floor(recent.length/2)]);}
        else {recent.length=0;setPitch(null);}
        state.timer=setTimeout(sample,100);
      };sample();
    } catch(e){stream?.getTracks().forEach(t=>t.stop());void context?.close().catch(()=>{});
      if(alive.current&&version===generation.current){setStarting(false);setError(e.name==='NotAllowedError' ? 'ยังไม่ได้อนุญาตไมโครโฟน กดเปิดไมค์อีกครั้งและอนุญาตในเบราว์เซอร์' : e.message);}}
  };
  return <section className={`pitch-tuner ${feedback?.state||'waiting'}`} aria-label="เลือกโน้ตและเทียบเสียง">
    <div className="tuner-heading"><div><span className="eyebrow muted">ฝึกสีให้ตรงเสียง</span><h2>เลือกโน้ต แล้วดูหลอดคีย์</h2></div><button className="button primary" disabled={!active||starting} onClick={listening ? stop : start}>{starting ? 'กำลังเปิดไมค์…' : listening ? 'ปิดไมค์' : 'เปิดไมค์เทียบเสียง'}</button></div>
    <div className="note-selector"><label htmlFor="practice-note">โน้ตที่ฝึก</label><select id="practice-note" aria-label="โน้ตที่ฝึก" value={noteId} onChange={e=>{setNoteId(e.target.value);setPitch(null);}}>{NOTE_TABLE.map(n=><option key={n.id} value={n.id}>{n.name} · {n.hz.toFixed(2)} Hz</option>)}</select><strong>{note.finger==='สายเปล่า' ? `สายเปล่า · ${note.string}` : `${note.finger} · ${note.string}`}</strong></div>
    <div className="tuner-reading" role="status"><strong>{feedback?.label||(listening ? 'สีโน้ตต่อเนื่องหนึ่งเสียง' : 'รอเปิดไมค์')}</strong><span>{pitch ? `${pitch.toFixed(2)} Hz` : '— Hz'} <small>/ เป้าหมาย {note.hz.toFixed(2)} Hz</small></span></div>
    <div className="pitch-tube" role="meter" aria-label="ความต่างจากเสียงเป้าหมาย หน่วยเฮิรตซ์" aria-valuemin={-PITCH_METER_RANGE_HZ} aria-valuemax={PITCH_METER_RANGE_HZ} aria-valuenow={meterDelta} aria-valuetext={feedback ? `${feedback.label} ${feedback.deltaHz.toFixed(2)} Hz` : 'ยังไม่มีเสียงที่ตรวจได้'} style={{'--pitch-low-bound':`${50-greenBand}%`,'--pitch-high-bound':`${50+greenBand}%`}}>
      <div className="pitch-center"/><div className="pitch-ticks"/>{feedback&&<div className="pitch-needle" style={{left:`${50+meterDelta/PITCH_METER_RANGE_HZ*45}%`}}/>}</div>
    <div className="pitch-scale"><span>ต่ำไป</span><b>ตรงคีย์ ±{PITCH_TOLERANCE_HZ} Hz</b><span>สูงไป</span></div>
    {initialGrip?.stage==='locked'&&<div className={`tuner-grip-result ${initialGrip.prediction==='none' ? 'correct' : ['grip_too_high','grip_too_low'].includes(initialGrip.prediction) ? 'warning' : 'waiting'}`} role="status"><span>จับสูง / ต่ำ · ตอนเริ่มฝึก</span><strong>{gripResultLabel(initialGrip)}</strong><small>{initialGrip.prediction==='uncertain' ? 'ยังแยกท่าจับผิดกับท่าพอดีไม่ชัด · ตรวจใหม่ได้' : 'เก็บผลจากตอนเริ่ม ไม่ตรวจซ้ำระหว่างสี'}</small></div>}
    {listening&&signal&&<div className="microphone-signal"><div className="microphone-level" role="meter" aria-label="ระดับเสียงเข้าไมค์" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(signal.percent)}><span style={{width:`${signal.percent}%`}}/></div><small role="status">{microphoneMessage(signal)}{signal.rms>=.002&&!pitch&&signal.state==='running' ? ' · รับเสียงแต่ยังแยกโน้ตไม่ได้ สีทีละเสียงให้ต่อเนื่อง' : ''}</small>{signal.state!=='running'&&<button className="button secondary" onClick={resume}>เริ่มระบบเสียงต่อ</button>}</div>}
    <p className="pitch-advice">{feedback?.advice||(!active ? 'เตรียมกล้องให้พร้อม แล้วเปิดไมค์เพื่อเริ่มเทียบเสียง' : 'สีทีละเสียงในห้องเงียบ ระบบจะรอเมื่อเสียงเบาหรือฟังไม่ชัด')}{feedback&&<small> · {feedback.deltaHz>0?'+':''}{feedback.deltaHz.toFixed(2)} Hz</small>}</p>
    {error&&<p className="alert" role="alert">{error}</p>}
    <details className="note-table"><summary>ดูตารางความถี่และตำแหน่งนิ้ว</summary><div className="table-wrap"><table><thead><tr><th>โน้ต</th><th>Hz</th><th>สาย</th><th>นิ้ว</th></tr></thead><tbody>{NOTE_TABLE.map(n=><tr key={n.id}><td>{n.name}</td><td>{n.hz.toFixed(2)}</td><td>{n.string}</td><td>{n.finger}</td></tr>)}</tbody></table></div><p>ใช้ความถี่อ้างอิงจากตารางที่คุณกำหนด</p></details>
    <small className="tuner-privacy">ฟังและคำนวณในเครื่อง · ไม่อัดเสียงหรือส่งเสียงขึ้นเซิร์ฟเวอร์</small>
  </section>;
}
