import React from 'react';
import {bodyOverlayGeometry} from './bodyOverlay.js';

// The caller rejects old/live observations and camera orientation mismatches.
export default function BodyGripOverlay({landmarks,dimensions,measurement}) {
  const {width,height}=dimensions;
  const {points,edges,axis,distance}=bodyOverlayGeometry(landmarks,measurement);
  if(!Object.keys(points).length)return null;
  const wrist=points[16];
  const radius=Math.max(width,height)*.009;
  return <svg className="landmark-overlay" viewBox={`0 0 ${width} ${height}`} aria-label="ข้อมือขวาเทียบแกนกลางลำตัวในภาพที่ตรวจ">
    {edges.map(([a,b])=><line key={`${a}-${b}`} x1={points[a].x*width} y1={points[a].y*height} x2={points[b].x*width} y2={points[b].y*height} stroke="#ffdd44" strokeWidth={radius/2}/>)}
    {axis && <line x1={axis[0].x*width} y1={axis[0].y*height} x2={axis[1].x*width} y2={axis[1].y*height} stroke="#16b9ff" strokeWidth={radius/2} strokeDasharray={`${radius} ${radius}`}/>}
    {distance && <line x1={distance[0].x*width} y1={distance[0].y*height} x2={distance[1].x*width} y2={distance[1].y*height} stroke="#ffdd44" strokeWidth={radius/2}/>}
    {Object.entries(points).map(([id,p])=><circle key={id} cx={p.x*width} cy={p.y*height} r={radius} fill={id==='16' ? '#16b9ff' : '#ffdd44'} stroke="#fff" strokeWidth={radius/4}/>)}
    {wrist && <text x={wrist.x*width} y={wrist.y*height-radius*2} textAnchor="middle" fill="#fff" stroke="#18242c" strokeWidth={radius/8} paintOrder="stroke" fontSize={radius*2}>ข้อมือขวา</text>}
  </svg>;
}
