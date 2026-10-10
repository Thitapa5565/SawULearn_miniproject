import {test} from 'node:test';
import assert from 'node:assert/strict';
import {NOTE_TABLE,detectPitch,pitchFeedback} from '../src/pitch.js';

const tone=(hz,rate,amplitude=.2,harmonic=.08)=>Float32Array.from({length:4096},(_,i)=>amplitude*Math.sin(2*Math.PI*hz*i/rate+.7)+harmonic*Math.sin(4*Math.PI*hz*i/rate));
test('all nine user references and finger/string mappings are exact',()=>{
  assert.deepEqual(NOTE_TABLE.map(n=>n.hz),[228.31,256.26,287.67,304.77,342.20,384.27,431.42,457.15,512.52]);
  assert.equal(NOTE_TABLE[1].finger,'นิ้วชี้');assert.equal(NOTE_TABLE[1].string,'สายทุ้ม');assert.equal(NOTE_TABLE[8].finger,'นิ้วก้อย');
});
test('microphone DSP identifies reference tones with harmonics at common sample rates',()=>{
  for(const rate of [44100,48000])for(const note of NOTE_TABLE){
    const result=detectPitch(tone(note.hz,rate),rate);assert.ok(result,`${note.name} detected`);
    assert.ok(Math.abs(1200*Math.log2(result.hz/note.hz))<3,`${note.name} accurate`);
  }
});
test('silence, weak sound and random noise do not retain a pitch',()=>{
  assert.equal(detectPitch(new Float32Array(4096),48000),null);
  assert.equal(detectPitch(tone(342.2,48000,.0001,0),48000),null);
  let seed=42;const noise=Float32Array.from({length:4096},()=>{seed=(1664525*seed+1013904223)>>>0;return (seed/2**32-.5)*.4;});
  assert.equal(detectPitch(noise,48000),null);
});
test('a strong second harmonic does not replace the audible fundamental',()=>{
  const result=detectPitch(tone(342.2,48000,.05,.25),48000);
  assert.ok(result);assert.ok(Math.abs(1200*Math.log2(result.hz/342.2))<3);
});
test('quiet sustained instrument tone still measures while very weak input remains unavailable',()=>{
  const result=detectPitch(tone(228.31,48000,.004,.001),48000);
  assert.ok(result);assert.ok(Math.abs(1200*Math.log2(result.hz/228.31))<3);
  assert.equal(detectPitch(tone(228.31,48000,.0001,0),48000),null);
});
test('pitch feedback keeps wrong octaves and advises direction relative to the bridge',()=>{
  const n=NOTE_TABLE[1];assert.equal(pitchFeedback(n.hz,n).state,'tuned');
  assert.equal(pitchFeedback(n.hz*.97,n).state,'low');assert.match(pitchFeedback(n.hz*.97,n).advice,/เข้าหาหย่อง/);
  assert.equal(pitchFeedback(n.hz*1.03,n).state,'high');assert.match(pitchFeedback(n.hz*1.03,n).advice,/ออกจากหย่อง/);
  assert.equal(pitchFeedback(n.hz*2,n).cents,1200);assert.equal(pitchFeedback(null,n),null);
  assert.match(pitchFeedback(NOTE_TABLE[0].hz*.97,NOTE_TABLE[0]).advice,/ลูกบิด/);
});
test('every reference accepts deviations up to five Hz, including both boundaries',()=>{
  for(const note of NOTE_TABLE){
    for(const delta of [-5,-4.99,0,4.99,5])assert.equal(pitchFeedback(note.hz+delta,note).state,'tuned',`${note.name} ${delta} Hz`);
    assert.equal(pitchFeedback(note.hz-5.01,note).state,'low');
    assert.equal(pitchFeedback(note.hz+5.01,note).state,'high');
    assert.ok(Math.abs(pitchFeedback(note.hz+4,note).deltaHz-4)<1e-9);
    assert.notEqual(pitchFeedback(note.hz*2,note).state,'tuned');
  }
});
