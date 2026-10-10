import {test} from 'node:test';
import assert from 'node:assert/strict';
import {microphoneGraph,inputLevel,microphoneMessage} from '../src/microphone.js';
test('microphone analysis has a live output with zero playback gain',()=>{
  const edges=[],node=name=>({name,connect(other){edges.push([name,other.name]);}});
  const source=node('mic'),analyser=node('analyser'),silent={...node('silent'),gain:{value:1}},destination=node('speakers');
  microphoneGraph({createMediaStreamSource:()=>source,createAnalyser:()=>analyser,createGain:()=>silent,destination},{});
  assert.equal(silent.gain.value,0);assert.equal(analyser.fftSize,4096);
  assert.deepEqual(edges,[['mic','analyser'],['analyser','silent'],['silent','speakers']]);
});
test('zero input, quiet input and interrupted audio are distinguishable',()=>{
  const zero=inputLevel(new Float32Array(4096)),quiet=inputLevel(new Float32Array(4096).fill(.001));
  assert.equal(zero.percent,0);assert.ok(quiet.percent>zero.percent);
  assert.match(microphoneMessage({...zero,state:'running'}),/ไม่มีเสียงเข้า/);
  assert.match(microphoneMessage({...quiet,state:'running'}),/เสียงเข้าเบา/);
  assert.match(microphoneMessage({rms:.1,state:'interrupted'}),/เริ่มระบบเสียงต่อ/);
  assert.match(microphoneMessage({rms:.1,state:'running',muted:true}),/ไมค์ถูกพัก/);
});
