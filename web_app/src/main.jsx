import React, { useState, useEffect, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowUpRight, ArrowRight, Camera, CameraOff, Play, Check, ChevronRight, BookOpen,
  SlidersHorizontal, Sparkles, CircleHelp, ScanLine, X, History,
  AlertCircle, CheckCircle2, Leaf, Download } from 'lucide-react';
import '@fontsource/noto-sans-thai/400.css';
import '@fontsource/noto-sans-thai/500.css';
import '@fontsource/noto-sans-thai/600.css';
import '@fontsource/noto-serif-thai/500.css';
import '@fontsource/noto-serif-thai/600.css';
import '@fontsource/inter/500.css';
import './style.css';
import { displayDimensions, readHistory, saveHistory, summarizePosture, bowLabels, postureFeedback } from './practice.js';
import LessonVideo from './LessonVideo.jsx';
import {alignmentStatus,phaseReadiness,observeReadiness} from './guidedPractice.js';
import {PracticeGuide} from './PracticeGuide.jsx';
import PitchTuner from './PitchTuner.jsx';
import {newGripCheck,observeGrip,gripMessage,SETTLE_MS,TIMEOUT_MS} from './initialGrip.js';
import {bowModelFeedback} from './bowModel.js';
import CombinedModels from './CombinedModels.jsx';
import {thumbsUpOnScreenLeft} from './guidedPractice.js';
import BodyGripOverlay from './BodyGripOverlay.jsx';
import {freshBodyObservation,BODY_OVERLAY_MAX_AGE} from './bodyOverlay.js';

async function api(url, options) {
  const response = await fetch(url, options);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'เชื่อมต่อไม่สำเร็จ กรุณาลองใหม่');
  return data;
}
const emptyStats = { total: 0, usable: 0, headDown: 0, shoulderTilt: 0, neither: 0 };

function Logo() { return <a className="brand" href="#practice" aria-label="SawULearn หน้าเริ่มฝึก">
  <img src="/favicon.svg" alt=""/><span>SawU<span className="brand-light">Learn</span><small>เรียนรู้ซออู้ ทีละจังหวะ</small></span></a>; }

function App() {
  const [page, setPage] = useState(location.hash.slice(1) || 'practice');
  const [lessons, setLessons] = useState([]); const [modelInfo, setModelInfo] = useState(null);
  const [connection, setConnection] = useState('loading'); const [history, setHistory] = useState(readHistory);
  const [examples, setExamples] = useState([]); const [lesson, setLesson] = useState(null);
  useEffect(() => {
    const change = () => setPage(location.hash.slice(1) || 'practice');
    window.addEventListener('hashchange', change);
    Promise.all([api('/api/health'), api('/api/lessons'), api('/api/examples'), api('/api/models')]).then(([, lessonData, exampleData, modelData]) => {
      setLessons(lessonData); setExamples(exampleData); setModelInfo(modelData); setConnection('ready');
    }).catch(() => setConnection('error'));
    return () => window.removeEventListener('hashchange', change);
  }, []);
  const navigate = p => { location.hash = p; };
  const start = () => { navigate('practice'); setLesson(null); };
  return <><header className="site-header"><div className="nav-wrap"><Logo/><nav aria-label="เมนูหลัก">
    {[['practice', 'พื้นที่ฝึก'], ['lessons', 'บทเรียน'], ['history', 'บันทึกการฝึก'], ['models', 'ผลโมเดล']].map(([id, label]) =>
      <a key={id} href={`#${id}`} className={page === id ? 'active' : ''}>{label}</a>)}</nav>
    <div className="prototype"><span className={connection === 'ready' ? 'status-dot' : 'status-dot waiting'}/><span>{connection === 'ready' ? 'ต้นแบบพร้อมใช้งาน' : connection === 'error' ? 'ยังเชื่อมต่อไม่ได้' : 'กำลังเชื่อมต่อ'}</span></div>
  </div></header>
  <main>
    {page === 'practice' && <Practice key="practice" lessons={examples} connection={connection}
      onSave={session => { try { setHistory(saveHistory(session)); return true; } catch { return false; } }}
      onLesson={() => setLesson(lessons[0])} />}
    {page === 'lessons' && <Lessons lessons={lessons} start={start}/>}
    {page === 'history' && <HistoryPage sessions={history} start={start}/>}
    {page === 'models' && <Models info={modelInfo} connection={connection}/>}
    {!['practice', 'lessons', 'history', 'models'].includes(page) && <div className="empty-page"><h1>กลับมาเริ่มฝึกกัน</h1><a href="#practice" className="button primary">เปิดพื้นที่ฝึก</a></div>}
  </main>
  <footer><Logo/><p>จากภูมิปัญญาดนตรีไทย สู่การเรียนรู้ในจังหวะของคุณ</p><span>SAW U · LEARN WITH CARE</span></footer>
  {lesson && <LessonDialog lesson={lesson} close={() => setLesson(null)} start={start}/>}
  </>;
}

export function Practice({ lessons, connection, onSave, onLesson }) {
  const video = useRef(null), stream = useRef(null), requestVersion = useRef(0), busy = useRef(false), mounted = useRef(true);
  const startTime = useRef(null), captureTimer = useRef(null);
  const captureCanvas=useRef(null), previewUrl=useRef(null);
  const [distanceView,setDistanceView]=useState(true), [theater,setTheater]=useState(false);
  const [phase,setPhase]=useState('idle'),[gestureCount,setGestureCount]=useState(0);
  const phaseRef=useRef('idle'),guideHold=useRef({since:0,count:0});phaseRef.current=phase;
  const gripCheck=useRef(null),[initialGrip,setInitialGrip]=useState(null),[gripClock,setGripClock]=useState(0);
  const reviewFrame=useRef(null);
  const [bodyObservation,setBodyObservation]=useState(null);
  const [practiceOptions,setPracticeOptions]=useState(false);
  const [hands, setHands] = useState([]);
  const [image, setImage] = useState(null);
  const [processedImage, setProcessedImage] = useState(null);
  const [live,setLive]=useState(false);
  const [dimensions,setDimensions]=useState({width:1280,height:720});
  const [videoDimensions,setVideoDimensions]=useState({width:1280,height:720});
  const [error, setError] = useState(''); const [processing, setProcessing] = useState(false);
  const [posture, setPosture] = useState(null);
  const [showPoints,setShowPoints]=useState(true);
  const [stats, setStats] = useState(emptyStats); const [saved, setSaved] = useState(false); const [sessionResult, setSessionResult] = useState(null);
  const [elapsed, setElapsed] = useState(0);
  // The reviewed PP_correct clips also supply correct bow-hold examples.
  const defaultImage = lessons.find(l => l.id === 'posture')?.image;
  const focused=live && ['align','ready','grip','practice'].includes(phase);
  useEffect(()=>{if(!focused)return;const previous=document.body.style.overflow;
    document.body.style.overflow='hidden';return()=>{document.body.style.overflow=previous;};},[focused]);
  const clearPreview = () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current=null; setProcessedImage(null); };
  const publishPreview = (blob,data) => { const next=URL.createObjectURL(blob);
    reviewFrame.current=data ? {blob,data} : null;
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
    previewUrl.current=next; setProcessedImage(next); };
  const stop = () => {
    reviewFrame.current=null;
    gripCheck.current=null;setInitialGrip(null);
    setPracticeOptions(false);
    setBodyObservation(null);setShowPoints(true);
    setPhase('idle');setGestureCount(0);
    if (live && video.current?.readyState >= 2 && video.current.videoWidth) {
      const element = video.current, canvas = document.createElement('canvas');
      const scale = Math.min(1, 1280 / element.videoWidth, 1280 / element.videoHeight);
      canvas.width = Math.round(element.videoWidth * scale); canvas.height = Math.round(element.videoHeight * scale);
      canvas.getContext('2d').drawImage(element, 0, 0, canvas.width, canvas.height);
      setImage(canvas.toDataURL('image/jpeg', .9)); setDimensions({ width: canvas.width, height: canvas.height });
      setPosture(null);
    }
    clearPreview();setHands([]);
    requestVersion.current++; stream.current?.getTracks().forEach(t => t.stop()); stream.current = null;
    clearTimeout(captureTimer.current); captureTimer.current = null; if (video.current) video.current.pause(); setLive(false); };
  const reset = () => { stop(); setImage(null);
    setPosture(null);
    setStats(emptyStats); setSaved(false); setSessionResult(null); setError(''); setElapsed(0); startTime.current = null;
 };
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; requestVersion.current++;
    stream.current?.getTracks().forEach(t => t.stop()); clearTimeout(captureTimer.current);
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
 }; }, []);
  useEffect(()=>{const hide=()=>{if(document.hidden && stream.current){requestVersion.current++;guideHold.current={since:0,count:0};
    setBodyObservation(null);
    if(phaseRef.current==='grip'){gripCheck.current=null;setInitialGrip(null);}
    setPosture(null);setHands([]);}};
    document.addEventListener('visibilitychange',hide);return()=>document.removeEventListener('visibilitychange',hide);},[]);
  useEffect(()=>{if(!bodyObservation || !live)return;
    const timer=setTimeout(()=>setBodyObservation(current=>current===bodyObservation ? null : current),
      Math.max(0,BODY_OVERLAY_MAX_AGE-(performance.now()-bodyObservation.time)));
    return()=>clearTimeout(timer);
  },[bodyObservation,live]);
  useEffect(() => { const timer = setInterval(() => { if (startTime.current && live) setElapsed(Math.floor((Date.now() - startTime.current) / 1000)); }, 1000);
    return () => clearInterval(timer); }, [live]);
  const applyFrame = data => {
    setPosture(data.posture); setHands(data.hands || []);
    setDimensions({width:data.width,height:data.height}); setSaved(false);
    if(!live || phaseRef.current==='practice') {
      const next = summarizePosture([data.posture]);
      setStats(previous => Object.fromEntries(Object.keys(next).map(k => [k,previous[k]+next[k]])));
    }
  };
  const analyzeFrame=async(blob,preview=false)=>{
    if(busy.current || !mounted.current)return;
    busy.current=true;const version=requestVersion.current;setProcessing(true);setError('');
    const sampledAt=performance.now();
    try {
      const data=await api('/api/analyze/body-grip',{method:'POST',headers:{'Content-Type':'image/jpeg',
        'X-Include-Hands':['ready','grip'].includes(phaseRef.current) ? '1' : '0',
        'X-Include-Initial-Grip':phaseRef.current==='grip' ? '1' : '0',
        'X-Include-Bow-Level':phaseRef.current==='practice' ? '1' : '0'},body:blob});
      if(!mounted.current || version!==requestVersion.current)return;
      applyFrame(data);
      setBodyObservation({landmarks:data.posture?.landmarks,measurement:data.body_measurement || data.initial_grip,
        bowLevel:data.bow_level,width:data.width,height:data.height,time:sampledAt});
      if(live && phaseRef.current==='grip'){
        const check=observeGrip(gripCheck.current || newGripCheck(sampledAt),data.initial_grip,sampledAt,
          {thumbRaised:thumbsUpOnScreenLeft(data.hands || [])});
        gripCheck.current=check;setInitialGrip(check);
        if(check.stage==='locked')completePractice();
      }
      if(preview)publishPreview(blob,data);
    } catch(e){if(mounted.current && version===requestVersion.current){
      setError(e.message);setPosture(null);setHands([]);setBodyObservation(null);
    }} finally {busy.current=false;if(mounted.current)setProcessing(false);}
  };
  const capture=async()=>{
    const element=video.current,version=requestVersion.current;
    if(!element || element.readyState<2 || !element.videoWidth)return;
    const scale=Math.min(1,960/element.videoWidth,960/element.videoHeight);
    const canvas=captureCanvas.current ||= document.createElement('canvas');
    canvas.width=Math.round(element.videoWidth*scale);canvas.height=Math.round(element.videoHeight*scale);
    canvas.getContext('2d').drawImage(element,0,0,canvas.width,canvas.height);
    const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/jpeg',.82));
    if(blob && mounted.current && version===requestVersion.current)await analyzeFrame(blob,true);
  };
  const startCamera = async () => {
    reset();setPhase('align');
    const version = requestVersion.current;
    try {
      if (!window.isSecureContext) throw new Error('ที่อยู่นี้เป็น HTTP จึงเปิดกล้องไม่ได้ บน iPad ให้เปิดหน้า HTTPS หลังติดตั้งและเชื่อถือใบรับรองแล้ว');
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('เบราว์เซอร์นี้ไม่รองรับการเปิดกล้อง กรุณาใช้ Safari รุ่นปัจจุบันบน iPad');
      const camera = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30, max: 30 }, facingMode: 'user' }, audio: false });
      if (!mounted.current || version !== requestVersion.current) { camera.getTracks().forEach(t => t.stop()); return; }
      stream.current = camera; setLive(true);
    } catch (e) { setPhase('intro'); setError(e.name === 'NotAllowedError' ? 'ยังไม่ได้อนุญาตกล้อง กดอนุญาตในเบราว์เซอร์ได้' : e.name === 'NotFoundError' ? 'ไม่พบกล้อง กรุณาเชื่อมต่อกล้องก่อนเริ่มฝึก' : e.message); }
  };
  useEffect(() => { if (live && video.current && stream.current) { video.current.srcObject = stream.current;
    video.current.play().then(()=>window.dispatchEvent(new Event('practice-camera-ready'))).catch(() => setError('เริ่มกล้องไม่สำเร็จ กรุณาลองเปิดใหม่')); }
  }, [live]);
  useEffect(()=>{
    if(!live)return;
    let active=true;
    const tick=async()=>{const started=performance.now();
      if(!busy.current && !document.hidden)await capture();
      if(active)captureTimer.current=setTimeout(tick,Math.max(40,350-(performance.now()-started)));
    };
    captureTimer.current=setTimeout(tick,40);
    return()=>{active=false;clearTimeout(captureTimer.current);captureTimer.current=null;};
  },[live,phase]);
  const completePractice=()=>{
    requestVersion.current++;phaseRef.current='practice';setPhase('practice');
    startTime.current=Date.now();setElapsed(0);setStats(emptyStats);setError('');
  };
  const beginGripCheck=()=>{
    requestVersion.current++;phaseRef.current='grip';setPhase('grip');
    const check=newGripCheck(performance.now());gripCheck.current=check;setInitialGrip(check);setGripClock(check.started);
    startTime.current=null;setError('');
  };
  const skipGrip=()=>{const check={...(gripCheck.current || newGripCheck(performance.now())),stage:'locked',prediction:'uncertain',reason:'skipped',experimental:true};
    gripCheck.current=check;setInitialGrip(check);completePractice();};
  const enterPractice=()=>{
    if(phaseRef.current!=='ready' || !live)return;
    beginGripCheck();
  };
  useEffect(()=>{if(phase!=='grip')return;const timer=setInterval(()=>{
    const now=performance.now();setGripClock(now);
    if(!document.hidden && gripCheck.current && now-gripCheck.current.started>TIMEOUT_MS) {
      const check={...gripCheck.current,stage:'locked',prediction:'uncertain',reason:'timeout',experimental:true};
      gripCheck.current=check;setInitialGrip(check);completePractice();
    }
  },250);return()=>clearInterval(timer);},[phase]);
  useEffect(()=>{guideHold.current={since:null,count:0};setGestureCount(0);},[phase]);
  useEffect(()=>{
    if(!live || document.hidden || !['align','ready'].includes(phase))return;
    const ready=phaseReadiness(phase,posture,hands,{relaxedAlignment:true});
    const hold=observeReadiness(guideHold.current,ready,performance.now());guideHold.current=hold;
    if(phase==='ready')setGestureCount(Math.min(2,hold.count));
    if(hold.complete){
      if(phase==='align')setPhase('ready');
      else if(phase==='ready')enterPractice();
    }
  },[posture,hands,phase,live]);
  const finish = () => { if (!stats.usable && !activeBow?.prediction) { setError('ยังไม่มีผลที่วิเคราะห์ได้ ลองจัดกล้องหรือวิเคราะห์ภาพก่อนบันทึก'); return; }
    const session = { id: crypto.randomUUID(), date: new Date().toISOString(), mode:'combined', source:'camera', seconds: elapsed,
      stats, bow: activeBow?.prediction || undefined,
      bowMode:'body',initialGrip,bowFrames:initialGrip?.samples?.length || 0,
      bowFloat:levelFeedback,bowError:levelFeedback,modelRun:posture?.model_run,
      bowNote:'โมเดลรอบสองคน: จับสูงต่ำตรวจตอนเริ่มในท่าคันชักขวาสุด; มุมผิดหรือสีลอยประเมินจากลำตัวและข้อมือระหว่างสี' };
    stop();
    if (onSave(session)) { setSaved(true); setSessionResult(session); } else setError('บันทึกไม่ได้ พื้นที่เก็บข้อมูลของเบราว์เซอร์อาจเต็ม'); };
  const predictions = posture?.status === 'ready' ? posture.predictions : null;
  const symptoms=postureFeedback(posture);
  const alignment=alignmentStatus(posture,{relaxed:true});
  const startIntro=()=>{reset();setPhase('intro');};
  const viewImage = image || defaultImage;
  const activeBow={prediction:initialGrip?.stage==='locked' && initialGrip.prediction!=='uncertain' ? initialGrip.prediction : null};
  const layoutDimensions=displayDimensions(dimensions,videoDimensions,live);
  const liveBody=live ? freshBodyObservation(bodyObservation,layoutDimensions,performance.now()) : null;
  const levelFeedback=bowModelFeedback(liveBody?.bowLevel);
  const updateVideoSize=element=>{if(element?.videoWidth>0 && element.videoHeight>0 &&
      (element.videoWidth!==videoDimensions.width || element.videoHeight!==videoDimensions.height)){
    setVideoDimensions({width:element.videoWidth,height:element.videoHeight});
    requestVersion.current++;setBodyObservation(null);
    if(phaseRef.current==='grip'){const check=newGripCheck(performance.now());gripCheck.current=check;setInitialGrip(check);setGripClock(check.started);}
  }};
  return <div className={`practice-page phase-${phase} body-practice ${focused ? 'session-focus' : ''} ${distanceView ? 'distance-view' : ''} ${theater ? 'theater-view' : ''}`}>
    {focused && <div className="practice-focus-header"><strong>SawULearn <small>{({align:'จัดท่านั่ง',ready:'ยืนยันพร้อม',grip:'ตรวจการจับ',practice:'กำลังฝึก'})[phase]}</small></strong><div>
      <button className="button secondary" onClick={()=>setPracticeOptions(true)}><SlidersHorizontal size={18}/>ตั้งค่า</button>
      <button className="button primary" onClick={()=>phase==='practice' && (stats.usable || activeBow?.prediction) ? finish() : stop()}>{phase==='practice' ? 'จบฝึก' : 'ยกเลิก'}</button>
    </div></div>}
    <div className="practice-display-controls">
    <button className="button secondary" aria-pressed={distanceView} onClick={()=>setDistanceView(!distanceView)}>{distanceView ? 'ตัวอักษรใหญ่ · นั่งไกล' : 'เปิดโหมดนั่งไกล'}</button>
    <button className="button secondary" aria-pressed={theater} onClick={()=>setTheater(!theater)}>{theater ? 'ออกจากเต็มพื้นที่' : 'ขยายเต็มพื้นที่'}</button>
    <span>ก้มหน้าและไหล่เอียงอาจเกิดพร้อมกัน</span></div><div className="intro"><div><div className="eyebrow"><span/> YOUR QUIET PRACTICE SPACE</div>
    <h1>ค่อย ๆ ฝึก ให้ท่าทางลงตัว</h1><p>ตรวจท่านั่ง เทียบเสียง และช่วยปรับแนวการสีจากลำตัวและมือ</p></div>
    <button className="button lesson-link" onClick={onLesson} disabled={!lessons.length}><BookOpen size={18}/> ดูบทเรียนซออู้ <ArrowUpRight size={17}/></button></div>
    {phase==='idle' && <button className="button primary start-practice" disabled={connection!=='ready'} onClick={startIntro}><Play size={22}/>เริ่มฝึก</button>}
    <PracticeGuide phase={phase} example={defaultImage} status={alignment} gestureCount={gestureCount}
      onCancel={reset} onStartPractice={enterPractice} canStartPractice={live} grip={initialGrip}
      settleSeconds={initialGrip ? Math.max(0,Math.ceil((initialGrip.started+SETTLE_MS-gripClock)/1000)) : 0}
      onSkipGrip={skipGrip} onNext={startCamera}/>
    {phase==='intro' && error && <p className="alert" role="alert">{error}</p>}
    {predictions?.head_down===1 && predictions?.shoulder_tilt===1 && <p className="combined-warning" role="status">พบก้มหน้าและไหล่เอียงพร้อมกัน · เงยหน้าและปรับไหล่ให้สมดุล</p>}
    <div className="live-feedback" aria-label="ผลตรวจพร้อมกัน" aria-live="polite" aria-atomic="true">
      {['head_down','shoulder_tilt'].map((key,i)=>{const item=symptoms?.find(s=>s.key===key);return <div key={key} className={`live-status ${!item ? 'waiting' : item.active ? 'warning' : 'correct'}`}>
        <span>{i===0 ? 'ศีรษะ / คอ' : 'ไหล่'}</span><strong>{!item ? 'รอภาพชัด' : item.active ? item.label : i===0 ? 'ไม่ก้มหน้า' : 'ไหล่ไม่เอียง'}</strong>
        <small>{!item ? 'ให้เห็นศีรษะ ไหล่ และสะโพก' : item.active ? i===0 ? 'เงยหน้าขึ้นเล็กน้อย' : 'ปรับไหล่ให้สมดุล' : 'ไม่พบอาการในภาพที่ตรวจ'}</small></div>;})}
      {phase==='practice' && <div className={`live-status ${levelFeedback.state}`}><span>แนวการสี · มุมผิดหรือสีลอย</span><strong>{levelFeedback.label}</strong><small>{levelFeedback.detail}</small></div>}
    </div>
    <div className="workspace"><section className={`camera-panel ${live ? 'live-panel' : ''}`}><div className="panel-heading"><div className="panel-title"><ScanLine size={20}/><h2>พื้นที่ฝึกของคุณ</h2></div>
      <span className="combined-badge">ท่านั่ง + คันชัก</span></div>
      {['intro','align','ready','grip','practice'].includes(phase) && <PitchTuner active={true} initialGrip={live && ['grip','practice'].includes(phase) ? initialGrip : null}/>}

      <div className="viewfinder-scroll"><div className="viewfinder" style={{aspectRatio:`${layoutDimensions.width}/${layoutDimensions.height}`,'--image-ratio':layoutDimensions.width/layoutDimensions.height}} aria-label="ภาพสำหรับตรวจท่าทาง">
        {live ? <video ref={video} muted playsInline onResize={e=>updateVideoSize(e.currentTarget)}
          onLoadedMetadata={e=>{updateVideoSize(e.currentTarget);setDimensions({width:e.currentTarget.videoWidth,height:e.currentTarget.videoHeight});}}/>
          : viewImage ? <img src={viewImage} alt="ตัวอย่างท่านั่งซออู้" onLoad={e=>setDimensions({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})}/>
          : <div className="camera-empty"><Camera size={36}/><p>เตรียมกล้อง แล้วเริ่มฝึกไปด้วยกัน</p></div>}
        <div className="view-top"><span className="view-badge"><span className={`status-dot ${live ? 'live' : 'waiting'}`}/>{live ? 'กล้องของคุณ' : 'ตัวอย่างท่านั่ง'}</span>
          <span className="view-badge mono">{processing ? 'กำลังวิเคราะห์…' : `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`}</span></div>
        {showPoints && <BodyGripOverlay landmarks={liveBody?.landmarks} measurement={liveBody?.measurement} dimensions={layoutDimensions}/>}
        {phase==='grip' && <div className="capture-countdown" role="status"><span>ดึงคันชักไปทางขวาของคุณ</span><strong>{initialGrip && gripClock<initialGrip.started+SETTLE_MS ? Math.max(1,Math.ceil((initialGrip.started+SETTLE_MS-gripClock)/1000)) : 'ถือนิ่ง'}</strong><span>{gripMessage(initialGrip)}</span></div>}
        {!image && !live && <div className="view-welcome"><span className="welcome-icon"><Camera size={24}/></span><h3>พร้อมเมื่อคุณพร้อม</h3><p>เปิดกล้องเพื่อดูท่าของตัวเอง<br/>จัดกล้องให้เห็นมือและสะโพกชัด</p></div>}
        {live && phase==='grip' && <div className="view-bottom"><CircleHelp size={18}/>{gripMessage(initialGrip)}</div>}
        <span className="frame-corner tl"/><span className="frame-corner br"/>
      </div></div>
      <div className="camera-toolbar"><div className="capture-buttons">
        {live ? <button className="button primary" onClick={stop}><CameraOff size={18}/>ปิดกล้อง</button> : phase!=='intro' && <button className="button primary" onClick={startIntro} disabled={connection !== 'ready'}><Camera size={18}/>เริ่มฝึกด้วยกล้อง</button>}
        {live && phase==='practice' && <button className="button secondary initial-grip-recheck" onClick={beginGripCheck}>ตรวจการจับเริ่มต้นใหม่</button>}
        {phase==='practice' && <button className="button primary" onClick={finish} disabled={!stats.usable && !activeBow?.prediction}><Check size={17}/>จบฝึกและบันทึก</button>}
      </div><button className={`icon-button ${showPoints ? 'selected' : ''}`} onClick={() => setShowPoints(!showPoints)} aria-label="แสดงหรือซ่อนจุดลำตัว" aria-pressed={showPoints}><ScanLine size={19}/></button></div>
      <div className="camera-note"><Leaf size={14}/><span>คำแนะนำอัปเดตจากภาพล่าสุดที่ตรวจ · วัดจากลำตัวในเครื่อง</span></div>
      {error && <p className="alert" role="alert"><AlertCircle size={17}/>{error}</p>}
      {live && processedImage && <details className="analysis-preview"><summary>ดูภาพล่าสุดที่ระบบตรวจ · จุดลำตัวตรงกับภาพนี้</summary>
        <div className="analysis-preview-image" style={{aspectRatio:`${dimensions.width}/${dimensions.height}`}}>
          <img src={processedImage} decoding="async" alt="ภาพล่าสุดพร้อมจุดลำตัว"/>
          {showPoints && <BodyGripOverlay landmarks={posture?.landmarks} dimensions={dimensions} measurement={reviewFrame.current?.data?.body_measurement || reviewFrame.current?.data?.initial_grip}/>}</div>
        <p>ภาพวิดีโอด้านบนเล่นต่อเนื่องและอาจเคลื่อนไปจากภาพที่ตรวจแล้ว</p></details>}
    </section>
    <aside className="feedback-column"><div className="feedback-panel"><div className="panel-heading"><h2>คำแนะนำระหว่างฝึก</h2><Sparkles size={19}/></div>
      <p className="small-lead">สังเกต ปรับทีละนิด แล้วลองอีกครั้ง</p>
      <h3 className="feedback-section-title">ท่านั่ง</h3>
        <FeedbackCard number="01" title="แนวศีรษะ" state={predictions ? predictions.head_down ? 'warning' : 'correct' : 'waiting'}
          text={predictions ? predictions.head_down ? 'พบการก้มหน้า ลองเงยศีรษะเล็กน้อยและมองไปข้างหน้า' : 'ไม่พบการก้มหน้าในภาพที่ตรวจ' : 'เมื่อเริ่มฝึก เราจะช่วยดูแนวศีรษะให้คุณ'}/>
        <FeedbackCard number="02" title="สมดุลของไหล่" state={predictions ? predictions.shoulder_tilt ? 'warning' : 'correct' : 'waiting'}
          text={predictions ? predictions.shoulder_tilt ? 'พบไหล่เอียง ลองผ่อนคลายและจัดไหล่ทั้งสองข้างให้สมดุล' : 'ไม่พบไหล่เอียงในภาพที่ตรวจ' : 'จัดไหล่ให้เห็นชัดทั้งสองข้างก่อนเริ่ม'}/>
        <div className="feedback-context"><CircleHelp size={17}/><p>{posture?.status === 'unavailable' ? posture.message : 'ตรวจเฉพาะก้มหน้าและไหล่เอียง เมื่อจุดไม่ครบจะรอให้จัดกล้องใหม่'}</p></div>
      {phase==='practice' && <><h3 className="feedback-section-title">แนวการสี</h3><FeedbackCard number="03" title={levelFeedback.label} state={levelFeedback.state} text={levelFeedback.detail}/></>}
      <div className="practice-summary"><span className="eyebrow muted">THIS PRACTICE</span><div><span>ภาพที่ตรวจท่านั่งได้</span><b className="mono">{stats.usable}<small> ภาพ</small></b></div>
      <div><span>ภาพตรวจจับสูง–ต่ำตอนเริ่ม</span><b className="mono">{initialGrip?.samples?.length || 0}<small> ภาพ</small></b></div>
      <div className="thin-progress"><span style={{ width: `${stats.total ? stats.usable / stats.total * 100 : 0}%` }}/></div>
      <p>{stats.usable ? `ท่านั่งไม่พบสองอาการใน ${stats.neither} จาก ${stats.usable} ภาพ` : 'ฝึกในจังหวะที่สบาย ไม่ต้องรีบ'}</p></div>
      <button className="button finish-button" onClick={finish} disabled={saved || (!stats.usable && !activeBow?.prediction)}>{saved ? <CheckCircle2 size={18}/> : <Check size={18}/>} {saved ? 'บันทึกการฝึกแล้ว' : 'จบและบันทึกการฝึก'}</button>
    </div><div className="quiet-note"><span>“</span><p>ท่าที่ผ่อนคลาย<br/>คือจุดเริ่มต้นของเสียงที่ไพเราะ</p><small>ค่อย ๆ เรียนรู้ไปด้วยกัน</small></div></aside></div>
    <section className="before-practice"><div className="before-title"><span className="eyebrow muted">A LITTLE PREPARATION</span><h2>ก่อนเริ่ม อีกนิดเดียว</h2></div>
      {[['01', 'จัดกล้องให้เห็นครบ', 'ศีรษะ ไหล่ และสะโพกอยู่ในภาพ'], ['02', 'ให้แสงอยู่ด้านหน้า', 'มองเห็นท่าทางและมือได้ชัดขึ้น'], ['03', 'เริ่มจากท่าที่สบาย', 'ผ่อนคลายไหล่ แล้วลองสีช้า ๆ']].map(([n, title, text]) => <div className="preparation-step" key={n}><span>{n}</span><div><h3>{title}</h3><p>{text}</p></div></div>)}
    </section>
    {practiceOptions && focused && <Dialog title="ตั้งค่าการฝึก" close={()=>setPracticeOptions(false)} className="practice-options-dialog">
      <p>กล้องและผลตรวจยังทำงานระหว่างเปิดหน้านี้</p>
      <label className="practice-option"><input type="checkbox" checked={showPoints} onChange={e=>setShowPoints(e.target.checked)}/>แสดงจุดและแกนกลางลำตัว</label>
      <p className="muted-copy">โมเดลจากผู้เล่นสองคนช่วยเตือนมุมผิดหรือสีลอยจากตำแหน่งลำตัวและข้อมือ เป็นการประมาณและอาจตรวจไม่พบความผิดบางครั้ง</p>
      {processedImage && <details className="analysis-preview"><summary>ดูภาพล่าสุดที่ระบบตรวจ</summary><div className="analysis-preview-image" style={{aspectRatio:`${dimensions.width}/${dimensions.height}`}}><img src={processedImage} alt="ภาพล่าสุดพร้อมจุดลำตัวจากภาพเดียวกัน"/><BodyGripOverlay landmarks={posture?.landmarks} dimensions={dimensions} measurement={reviewFrame.current?.data?.body_measurement || reviewFrame.current?.data?.initial_grip}/></div></details>}
      <button className="button primary" onClick={()=>setPracticeOptions(false)}>กลับไปฝึก</button>
    </Dialog>}
    {sessionResult && <SessionDialog session={sessionResult} close={() => setSessionResult(null)}/>}
  </div>;
}

function FeedbackCard({ number, title, text, state }) { return <div className={`feedback-card ${state}`}><div className="feedback-card-title"><span className="card-number">{number}</span><h3>{title}</h3>{state === 'correct' ? <CheckCircle2 size={20}/> : state === 'warning' ? <AlertCircle size={20}/> : <span className="waiting-ring"/>}</div><p>{text}</p><span className="feedback-label">{state === 'correct' ? 'ไม่พบอาการที่ตรวจ' : state === 'warning' ? 'ลองปรับอีกนิด' : 'รอเริ่มฝึก'}</span></div>; }

function Dialog({ title, close, children, className = '' }) {
  const dialog = useRef(null);
  useEffect(() => { dialog.current?.showModal(); return () => dialog.current?.close(); }, []);
  return <dialog ref={dialog} className={className} onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === dialog.current) close(); }}><div className="dialog-header"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="ปิด"><X size={22}/></button></div>{children}</dialog>;
}
function LessonDialog({ lesson, close, start }) { return <Dialog title={lesson.title} close={close} className="lesson-dialog"><LessonVideo lesson={lesson}/><p>{lesson.subtitle}</p><button className="button primary" onClick={start}>ฝึกท่านั่งและคันชัก <ArrowRight size={18}/></button></Dialog>; }
function SessionDialog({ session, close }) { const stats = session.stats; return <Dialog title="เก็บอีกหนึ่งจังหวะของการเรียนรู้" close={close}><span className="session-check"><CheckCircle2 size={32}/></span><p>บันทึกการฝึกในเบราว์เซอร์นี้แล้ว</p>{stats && <div className="session-grid"><div><b>{stats.usable}</b><span>ภาพที่ตรวจท่านั่งได้</span></div><div><b>{stats.headDown}</b><span>ภาพที่พบก้มหน้า</span></div><div><b>{stats.shoulderTilt}</b><span>ภาพที่พบไหล่เอียง</span></div></div>}
    <p>คันชัก: {session.bow ? bowLabels[session.bow] : 'ยังสรุปจับสูง–ต่ำไม่ได้'}{session.bow && <small> · {session.bowMode==='roboflow' ? 'ผล A/B/C ล่าสุด' : 'ผลตอนเริ่มฝึก'}</small>}</p>
    <p className="muted-copy">จำนวนภาพที่พบอาการไม่ใช่คะแนนความแม่นยำของผู้เล่น</p><button className="button primary" onClick={close}>กลับไปฝึกต่อ <ArrowRight size={17}/></button></Dialog>; }

function Lessons({ lessons, start }) { const lesson = lessons[0]; return <div className="content-page"><PageTitle eyebrow="LEARN FROM THE DETAILS" title="เริ่มจากท่าทางที่เข้าใจ" text="ดูบทเรียนหนึ่งคลิป แล้วฝึกท่านั่งและการจับคันชักไปพร้อมกัน"/>
  {lesson && <article className="main-lesson"><div className="main-lesson-copy"><span className="eyebrow muted">บทเรียนซออู้ · DLTV</span><h2>{lesson.title}</h2><p>{lesson.subtitle}</p></div>
    <LessonVideo lesson={lesson}/><div className="lesson-next"><p>สังเกตท่านั่ง ตำแหน่งมือ และแนวคันชัก แล้วลองฝึกในจังหวะของคุณ</p>
      <button className="button primary" onClick={start}>ฝึกท่านั่งและคันชัก <ArrowRight size={18}/></button></div></article>}
  {!lessons.length && <p className="alert">กำลังโหลดบทเรียน หากไม่แสดงให้ตรวจว่าเซิร์ฟเวอร์เปิดอยู่</p>}
  <div className="content-note"><Leaf size={20}/><p>คำแนะนำบนเว็บเป็นคำแนะนำเบื้องต้น ควรใช้ประกอบการเรียนกับครูซออู้</p></div></div>; }
function PageTitle({ eyebrow, title, text }) { return <div className="page-title"><span className="eyebrow"><span/>{eyebrow}</span><h1>{title}</h1><p>{text}</p></div>; }
function HistoryPage({ sessions, start }) {
  const exportData = () => { const url = URL.createObjectURL(new Blob([JSON.stringify(sessions, null, 2)], { type:'application/json' }));
    const a = document.createElement('a'); a.href=url; a.download='sawulearn-practice.json'; a.click(); URL.revokeObjectURL(url); };
  return <div className="content-page"><PageTitle eyebrow="ONE PRACTICE AT A TIME" title="ทุกครั้งที่ฝึก มีความหมาย" text="กลับมาดูสิ่งที่สังเกตได้ แล้วค่อย ๆ เรียนรู้จากการฝึกแต่ละครั้ง"/>
  {sessions.length ? <><div className="history-heading"><span>บันทึก {sessions.length} ครั้ง · เก็บในเบราว์เซอร์นี้</span><button className="button secondary" onClick={exportData}><Download size={16}/>ดาวน์โหลดบันทึก</button></div><div className="history-list">{sessions.map(s => <article key={s.id}><div className="history-icon"><History size={22}/></div><div><h2>{s.mode === 'combined' ? 'ฝึกท่านั่งและคันชัก' : s.mode === 'posture' ? 'ฝึกท่านั่ง' : 'ฝึกจับคันชัก'}</h2><p>{new Date(s.date).toLocaleString('th-TH', { dateStyle:'medium',timeStyle:'short' })} · {s.source === 'example' ? 'ภาพ / คลิปตัวอย่าง' : s.source === 'camera' ? 'กล้อง' : 'ภาพ / คลิปที่อัปโหลด'}</p></div><div className="history-result">{s.stats && <><strong>ท่านั่ง: ตรวจได้ {s.stats.usable} ภาพ</strong><span>ก้มหน้า {s.stats.headDown} · ไหล่เอียง {s.stats.shoulderTilt}</span></>}
      {s.bow ? <strong>คันชัก: {bowLabels[s.bow]}{s.mode === 'combined' ? ' (ตอนเริ่มฝึก)' : ''}</strong> : s.mode === 'combined' && <span>คันชัก: ยังไม่มีผลในภาพสุดท้าย</span>}</div></article>)}</div></>
  : <div className="empty-state"><History size={36}/><h2>พื้นที่สำหรับจังหวะแรกของคุณ</h2><p>เมื่อจบและบันทึกการฝึก ผลจะมาอยู่ตรงนี้</p><button className="button primary" onClick={start}>เริ่มฝึกครั้งแรก <ArrowRight size={17}/></button></div>}
  <div className="content-note"><CircleHelp size={19}/><p>บันทึกเฉพาะผลสรุป ไม่มีภาพหรือวิดีโอ และไม่ซิงก์ข้ามเครื่อง</p></div></div>;
}

function Models({info,connection}) {
  if(!info)return <div className="content-page"><h1>{connection==='error' ? 'ยังโหลดผลโมเดลไม่ได้' : 'กำลังโหลดผลโมเดล…'}</h1></div>;
  if(info.deployment==='combined_experts_v1')return <CombinedModels info={info}/>;
  const p=info.summary.tasks.playing_posture_head_shoulder;
  const grip=info.initial_grip_trial?.summary, rightmost=grip?.protocol==='player_rightmost_comfortable_bow_position';
  const gripSplit=rightmost ? 'val' : 'test', g=grip?.splits?.[gripSplit]?.new;
  const comparisons=Object.entries(info.comparisons).filter(([category])=>category!=='bow_hold').flatMap(([category,models])=>Object.entries(models).map(([name,v])=>({category,name,train:v.train.clip_balanced_frame_macro_f1,val:v.val.clip_balanced_frame_macro_f1})));
  const modelName=name=>name==='independent_trees' ? 'Decision Tree แยกสองอาการ' : name==='decision_tree' ? 'Decision Tree' : 'Random Forest';
  return <div className="content-page"><PageTitle eyebrow="UNDERSTAND THE FEEDBACK" title="เห็นทั้งผล และขอบเขตของโมเดล" text="ผลของโมเดลท่านั่งและการจับจากลำตัวที่เว็บใช้อยู่"/>
    <div className="model-cards"><article><span className="eyebrow muted">POSTURE · TEST</span><h2>ก้มหน้า / ไหล่เอียง</h2><strong>{(p.test.frame_exact_match*100).toFixed(1)}<small>%</small></strong><p>ทายถูกครบสองคำตอบต่อเฟรม</p><span>ฝึก {p.fit_frames} เฟรม / {p.fit_clips} คลิป<br/>ทดสอบ {p.test.frames} เฟรม / {p.test.clips} คลิป</span></article>
      <article><span className="eyebrow muted">INITIAL GRIP · {gripSplit.toUpperCase()}</span><h2>{rightmost ? 'คันชักขวาสุด · ทดลอง' : 'การจับจากลำตัว · ทดลอง'}</h2><strong>{g ? g.clip_balanced_macro_f1_including_uncertain.toFixed(3) : '—'}</strong><p>Macro F1 · รวมผลไม่แน่ใจในตัวหาร</p>{g&&<span>{rightmost ? 'Validation' : 'ทดสอบ'} {g.frames} เฟรม / {g.clips} คลิป<br/>ผลที่สรุปได้ {(g.clip_balanced_coverage*100).toFixed(1)}% · ให้น้ำหนักคลิปเท่ากัน</span>}</article></div>
    {info.summary.posture_update&&<p className="content-note">ท่านั่งแยกสองอาการ จึงแสดงก้มหน้าและไหล่เอียงพร้อมกันได้ ข้อมูล train มีสองอาการพร้อมกันเพียง 1 เฟรม และ validation ไม่มีกรณีนี้ จึงยังประเมินความแม่นยำของกรณีร่วมไม่ได้</p>}
    <h2 className="section-title">เปรียบเทียบโมเดลท่านั่ง</h2><p className="muted-copy">คะแนนก่อนรวม train + validation · F1 รายเฟรมให้น้ำหนักคลิปเท่ากัน</p>
    <div className="table-wrap"><table><thead><tr><th>โมเดล</th><th>Train macro F1</th><th>Validation macro F1</th></tr></thead><tbody>{comparisons.map(r=><tr key={r.category+r.name}><td>{modelName(r.name)}</td><td>{r.train.toFixed(3)}</td><td>{r.val.toFixed(3)}</td></tr>)}</tbody></table></div>
    <h2 className="section-title">ผล test รายอาการของท่านั่ง</h2><div className="table-wrap"><table><thead><tr><th>อาการ</th><th>Precision</th><th>Recall</th><th>F1</th><th>เฟรมที่มีอาการ</th></tr></thead><tbody>{[['head_down','ก้มหน้า'],['shoulder_tilt','ไหล่เอียง']].map(([key,label])=>{const m=p.test.per_symptom[key];return <tr key={key}><td>{label}</td><td>{m.precision.toFixed(3)}</td><td>{m.recall.toFixed(3)}</td><td>{m['f1-score'].toFixed(3)}</td><td>{m.support}</td></tr>;})}</tbody></table></div>
    {grip&&<><h2 className="section-title">การจับเริ่มต้นจากลำตัว</h2><p className="muted-copy">{rightmost ? `เรียนจากเฟรมขวาสุดที่ตรวจเลือกไว้ · ${grip.selected} · TRAIN CV แยกคลิป F1 ${grip.cv.clip_balanced_macro_f1_including_uncertain.toFixed(3)} · รอ 10 วินาทีแล้วตรวจท่านิ่ง 2 วินาที · ยังไม่มี test สำหรับวิธีนี้` : 'ใช้ระยะมือและความสูงมือช่วยตรวจซ้ำ ผลสองรุ่นที่ขัดกันจะไม่ยืนยันว่าจับพอดี · เลือกรุ่นตรวจซ้ำจาก TRAIN CV แยกคลิป'}</p><div className="table-wrap"><table><thead><tr><th>ชุดข้อมูล</th><th>Macro F1 รวมผลไม่แน่ใจ</th><th>ผลที่สรุปได้</th><th>เฟรม / คลิป</th></tr></thead><tbody>{Object.entries(grip.splits).map(([split,value])=>{const m=value.new;return <tr key={split}><td>{split}</td><td>{m.clip_balanced_macro_f1_including_uncertain.toFixed(3)}</td><td>{(m.clip_balanced_coverage*100).toFixed(1)}%</td><td>{m.frames} / {m.clips}</td></tr>;})}</tbody></table></div>
      {rightmost&&<><h2 className="section-title">Validation รายท่า · คันชักขวาสุด</h2><div className="table-wrap"><table><thead><tr><th>ท่าจับจริง</th><th>Recall</th><th>เฟรมที่เลือก / สรุปได้</th></tr></thead><tbody>{[['none','พอดี'],['grip_too_high','สูงไป'],['grip_too_low','ต่ำไป']].map(([key,label])=>{const m=g.classification_report[key], c=g.per_label_coverage[key];return <tr key={key}><td>{label}</td><td>{(m.recall*100).toFixed(1)}%</td><td>{c.frames} / {c.accepted_frames}</td></tr>;})}</tbody></table></div><p className="muted-copy">ท่าสูงและต่ำมีอย่างละ 1 คลิปใน validation · ท่าต่ำยังถูกทายเป็นพอดี 2 จาก 5 เฟรม · เฟรมที่ตรวจไม่ได้คงอยู่ในคะแนน</p></>}
    </>}
    {info.bow_level_trial?.summary&&<><h2 className="section-title">ผลทดลองเดิม · ไม่ใช้แจ้งเตือนในหน้าฝึก</h2><div className="table-wrap"><table><thead><tr><th>สิ่งที่ประมาณ</th><th>ตัวชี้วัด</th><th>Validation</th><th>Test</th></tr></thead><tbody>{Object.entries(info.bow_level_trial.summary.tasks).map(([task,v])=><tr key={task}><td>{{level_error:'แนว / ระดับผิด',angle_deviation:'ความเอียงจาก 90°',bridge_distance:'ระยะหย่อง / ความยาวแนวสาย'}[task]}</td><td>{v.metric==='mae' ? task==='angle_deviation' ? 'MAE (องศา)' : 'MAE (สัดส่วน)' : 'Macro F1'}</td><td>{v.val.score.toFixed(3)}</td><td>{v.test.score.toFixed(3)}</td></tr>)}</tbody></table></div></>}
    <div className="content-note"><CircleHelp size={22}/><p>ข้อมูลมี expert01 ฉากและมุมกล้องเดียว ยังไม่ทดสอบกับผู้เล่นใหม่ และ test นี้เคยใช้ทดลองมาก่อน การจับสูงและพอดีมีค่าทับกัน จึงมีผลไม่แน่ใจได้บ่อย ค่ามุมและระยะเป็นการประมาณจากร่างกาย ไม่ใช่การวัดซอโดยตรง</p></div>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
