import {test} from 'node:test';
import assert from 'node:assert/strict';
import {alignmentStatus,phaseReadiness,observeReadiness,thumbsUpOnScreenLeft} from '../src/guidedPractice.js';

const posture=()=>{const landmarks=Array.from({length:33},()=>({x:.5,y:.5,visibility:1,presence:1}));
  landmarks[0].y=.25;landmarks[11].x=.35;landmarks[12].x=.65;landmarks[23].y=landmarks[24].y=.75;
  return {status:'ready',predictions:{head_down:0,shoulder_tilt:0},landmarks};};
test('alignment requires both independent green flags and visible seated framing',()=>{
  const p=posture();assert.equal(alignmentStatus(p).ready,true);
  p.predictions.head_down=1;assert.equal(alignmentStatus(p).ready,false);
  p.predictions.shoulder_tilt=1;const flags=alignmentStatus(p);assert.equal(flags.head,false);assert.equal(flags.shoulders,false);
  p.predictions={head_down:0,shoulder_tilt:0};p.landmarks[23].presence=.1;assert.equal(alignmentStatus(p).ready,false);
  p.landmarks[23].presence=1;p.landmarks[0].x=.9;assert.equal(alignmentStatus(p).inFrame,false);
  assert.equal(alignmentStatus(null).ready,false);
});
test('body setup accepts off-centre framing but still requires visible body and two correct posture flags',()=>{
  const p=posture();p.landmarks.forEach(v=>v.x+=.24);
  assert.equal(alignmentStatus(p).inFrame,false);
  assert.equal(phaseReadiness('align',p,[],{relaxedAlignment:true}),true);
  p.predictions.head_down=1;
  assert.equal(phaseReadiness('align',p,[],{relaxedAlignment:true}),false);
  p.predictions.head_down=0;p.landmarks[24].presence=.1;
  assert.equal(phaseReadiness('align',p,[],{relaxedAlignment:true}),false);
});
test('return readiness resets after missing or stale body samples',()=>{
  let h=observeReadiness(null,true,100);h=observeReadiness(h,false,1200);h=observeReadiness(h,true,1800);
  assert.equal(h.complete,false);h=observeReadiness(h,true,8000);assert.equal(h.complete,false);
  h=observeReadiness(h,true,9600);assert.equal(h.complete,true);
});
test('thumb confirmation accepts screen-left extended thumb with curled fingers only',()=>{
  const p=Array.from({length:21},()=>({x:.25,y:.55}));p[0]={x:.25,y:.7};
  p[2]={x:.2,y:.59};p[3]={x:.18,y:.51};p[4]={x:.18,y:.4};
  for(const i of [8,12,16,20]){p[i-2]={x:.3,y:.48};p[i]={x:.29,y:.61};}
  assert.equal(thumbsUpOnScreenLeft([p]),true);
  assert.equal(phaseReadiness('ready',posture(),[p]),true);
  assert.equal(phaseReadiness('ready',posture(),[]),false);
  assert.equal(thumbsUpOnScreenLeft([p.map(v=>({...v,x:v.x+.5}))]),false);
  const palm=p.map(v=>({...v}));for(const i of [8,12,16,20])palm[i].y=.3;
  assert.equal(thumbsUpOnScreenLeft([palm]),false);
  const fist=p.map(v=>({...v}));fist[4].y=.6;assert.equal(thumbsUpOnScreenLeft([fist]),false);
  assert.equal(thumbsUpOnScreenLeft([]),false);
});
