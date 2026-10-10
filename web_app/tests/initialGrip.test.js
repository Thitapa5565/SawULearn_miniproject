import test from 'node:test';
import assert from 'node:assert/strict';
import {newGripCheck,observeGrip,gripResultLabel,SETTLE_MS,TIMEOUT_MS} from '../src/initialGrip.js';
const sample=(prediction='none',x=.5,height=.4)=>({status:'ready',prediction,features:{bow_side_horizontal_ratio:x,wrist_height_body_ratio:height},model_run:'trial',variant:'first_2s_unfiltered'});
test('settling and thumbs-up observations cannot become a correct initial grip',()=>{
  assert.equal(SETTLE_MS,10000);
  let check=observeGrip(newGripCheck(0),sample(),SETTLE_MS-1);
  assert.equal(check.samples.length,0);
  check=observeGrip(check,sample(),SETTLE_MS,{thumbRaised:true});
  assert.equal(check.prediction,null);assert.equal(check.samples.length,0);
  check=observeGrip(check,sample('none',.5,1),SETTLE_MS+500);
  assert.equal(check.samples.length,0);
});
test('fresh 2-second stationary observations lock votes; later bowing cannot overwrite result',()=>{
  let check=newGripCheck(0);
  for(const offset of [0,1000,2000])check=observeGrip(check,sample('grip_too_high'),SETTLE_MS+offset);
  assert.equal(check.stage,'locked');assert.equal(check.prediction,'grip_too_high');
  assert.equal(check.model_run,'trial');
  assert.equal(observeGrip(check,sample('none',2),SETTLE_MS+3000),check);
  assert.equal(newGripCheck(10000).prediction,null);
});
test('gaps, missing pose and movement restart the sample window instead of faking success',()=>{
  let check=observeGrip(newGripCheck(0),sample(),SETTLE_MS);
  check=observeGrip(check,sample(),SETTLE_MS+3000);assert.equal(check.samples.length,1);
  check=observeGrip(check,{status:'unavailable'},SETTLE_MS+3500);assert.equal(check.samples.length,0);
  check=observeGrip(check,sample(),SETTLE_MS+4000);
  check=observeGrip(check,sample('none',1),SETTLE_MS+5000);assert.equal(check.samples.length,1);assert.equal(check.prediction,null);
});
test('no majority and timeout remain uncertain, including missing observations',()=>{
  let check=newGripCheck(0);
  for(const [i,label] of ['none','grip_too_high','grip_too_low'].entries())check=observeGrip(check,sample(label),SETTLE_MS+i*1000);
  assert.equal(check.prediction,'uncertain');
  check=observeGrip(newGripCheck(0),{status:'unavailable'},TIMEOUT_MS+1);
  assert.equal(check.prediction,'uncertain');assert.equal(check.reason,'timeout');
});

