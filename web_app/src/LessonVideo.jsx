import React, { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Play } from 'lucide-react';

export default function LessonVideo({ lesson }) {
  const video = useRef(null);
  const [started, setStarted] = useState(false), [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!started) return;
    const element = video.current;
    let hls, disposed = false;
    if (element.canPlayType('application/vnd.apple.mpegurl')) {
      element.src = lesson.video;
      element.play().catch(() => {});
    } else {
      import('hls.js').then(({default:Hls}) => {
        if (disposed) return;
        if (!Hls.isSupported()) {setFailed(true); return;}
        hls = new Hls({ maxBufferLength: 20, backBufferLength: 20 });
        hls.attachMedia(element);
        hls.loadSource(lesson.video);
        hls.on(Hls.Events.MANIFEST_PARSED, () => element.play().catch(() => {}));
        hls.on(Hls.Events.ERROR, (_, data) => { if (data.fatal && !disposed) { setFailed(true); hls.destroy(); } });
      }).catch(() => {if (!disposed) setFailed(true);});
    }
    return () => { disposed = true; hls?.destroy(); element.pause(); element.removeAttribute('src'); element.load(); };
  }, [started, lesson.video]);
  return <div className="lesson-player">
    <div className="lesson-screen">
      {started ? <video ref={video} controls playsInline preload="none" aria-label={lesson.title}
        onError={() => setFailed(true)}/> : <button className="lesson-start" onClick={() => setStarted(true)}>
          <span className="lesson-play-icon"><Play size={28}/></span>
          <span className="eyebrow">DLTV · เรียนดนตรีไทย</span><strong>เรียนรู้ซออู้ไปด้วยกัน</strong>
          <span>เล่นคลิปบทเรียน</span>
        </button>}
    </div>
    {failed && <p className="alert" role="alert">เล่นคลิปในหน้านี้ไม่สำเร็จ เปิดบทเรียนบน DLTV ได้จากลิงก์ด้านล่าง</p>}
    <div className="lesson-source"><span>ที่มา: {lesson.source}</span>
      <a href={lesson.source_url} target="_blank" rel="noopener noreferrer">เปิดบทเรียนบน DLTV <ArrowUpRight size={15}/></a></div>
  </div>;
}
