import { test } from 'node:test';
import assert from 'node:assert/strict';
import { normalizePoint, displayDimensions, summarizePosture, readHistory, saveHistory } from '../src/practice.js';

test('live view uses camera dimensions after orientation changes, not delayed analysis dimensions',()=>{
  assert.deepEqual(displayDimensions({width:1280,height:720},{width:720,height:1280},true),{width:720,height:1280});
  assert.deepEqual(displayDimensions({width:1280,height:720},{width:720,height:1280},false),{width:1280,height:720});
  assert.deepEqual(displayDimensions({width:960,height:540},{width:0,height:0},true),{width:960,height:540});
});
test('annotation coordinates use the displayed image bounds and remain normalized', () => {
  assert.deepEqual(normalizePoint(150, 100, { left:50, top:50, width:200, height:100 }), [.5,.5]);
  assert.deepEqual(normalizePoint(-5, 900, { left:0, top:0, width:200, height:100 }), [0,1]);
});
test('missing pose is not a correct or incorrect posture; mixed symptoms count separately', () => {
  assert.deepEqual(summarizePosture([{status:'unavailable'}, {status:'ready',predictions:{head_down:1,shoulder_tilt:1}},
    {status:'ready',predictions:{head_down:0,shoulder_tilt:0}}]), { total:3,usable:2,headDown:1,shoulderTilt:1,neither:1 });
});
test('practice summaries round-trip and malformed browser data starts empty', () => {
  let value = 'invalid'; const storage={getItem:()=>value,setItem:(_,next)=>{value=next;}};
  assert.deepEqual(readHistory(storage), []);
  const record={id:'one',date:'2026-10-05',mode:'bow',bow:'grip_too_high'};
  saveHistory(record,storage); assert.deepEqual(readHistory(storage),[record]);
});
test('one practice record keeps both sections and preserves older records', () => {
  let value = JSON.stringify([{id:'old',date:'2026-10-05',mode:'bow',bow:'grip_too_high'}]);
  const storage={getItem:()=>value,setItem:(_,next)=>{value=next;}};
  const record={id:'combined',date:'2026-10-05',mode:'combined',stats:{usable:2,headDown:1,shoulderTilt:0},
    bow:'none',bowFrames:1};
  saveHistory(record,storage);
  assert.equal(readHistory(storage)[0].stats.usable,2);
  assert.equal(readHistory(storage)[0].bow,'none');
  assert.equal(readHistory(storage)[1].bow,'grip_too_high');
});
