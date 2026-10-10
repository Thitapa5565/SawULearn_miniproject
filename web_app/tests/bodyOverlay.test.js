import test from 'node:test';
import assert from 'node:assert/strict';
import {bodyOverlayGeometry,freshBodyObservation,BODY_OVERLAY_MAX_AGE} from '../src/bodyOverlay.js';
const pose=()=>{
  const p=Array(33).fill(null);
  for(const [id,x,y] of [[11,.6,.3],[12,.4,.3],[23,.6,.7],[24,.4,.7],[16,.3,.6]])p[id]={x,y,visibility:1,presence:1};
  return p;
};
test('body overlay shows shoulders, hips, wrist and torso axis with a measured horizontal distance',()=>{
  const g=bodyOverlayGeometry(pose(),{status:'ready'});
  assert.equal(Object.keys(g.points).length,5);assert.equal(g.edges.length,4);
  assert.deepEqual(g.axis,[{x:.5,y:.3},{x:.5,y:.7}]);
  assert.deepEqual(g.distance[0],{x:.5,y:.6});
});
test('visible body marks remain when measurement is unavailable; missing points are never invented',()=>{
  const p=pose();p[24].visibility=.1;
  const g=bodyOverlayGeometry(p,{status:'unavailable'});
  assert.equal(Object.keys(g.points).length,4);assert.equal(g.axis,null);assert.equal(g.distance,null);
  assert.ok(g.points[16]);assert.equal(bodyOverlayGeometry([],{}).edges.length,0);
  p[16].x=NaN;assert.equal(bodyOverlayGeometry(p,{}).points[16],undefined);
});
test('old or rotated camera measurements cannot remain over live video; same-aspect resize is allowed',()=>{
  const observation={width:1280,height:720,time:1000,landmarks:pose()};
  assert.equal(freshBodyObservation(observation,{width:640,height:360},1200),observation);
  assert.equal(freshBodyObservation(observation,{width:720,height:1280},1200),null);
  assert.equal(freshBodyObservation(observation,{width:1280,height:720},1001+BODY_OVERLAY_MAX_AGE),null);
  assert.equal(freshBodyObservation(observation,{width:1280,height:720},900),null);
});
