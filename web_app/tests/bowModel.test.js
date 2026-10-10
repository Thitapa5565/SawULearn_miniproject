import test from 'node:test';
import assert from 'node:assert/strict';
import {bowModelFeedback} from '../src/bowModel.js';
import {freshBodyObservation,BODY_OVERLAY_MAX_AGE} from '../src/bodyOverlay.js';

test('angle and floating share the new warning without needing an initial grip baseline',()=>{
  const feedback=bowModelFeedback({status:'ready',prediction:'bow_angle_wrong',model_run:'combined'});
  assert.equal(feedback.state,'warning');
  assert.equal(feedback.label,'ปรับองศาการสีให้ถูกต้อง');
  assert.equal(feedback.model_run,'combined');
  assert.equal(bowModelFeedback({status:'ready',prediction:'none'}).state,'correct');
});
test('missing, out-of-range, invalid and stale predictions never show correct',()=>{
  for(const observation of [null,{status:'unavailable',prediction:'none'},
    {status:'ready',prediction:'unknown'},{status:'ready',prediction:null}])
    assert.equal(bowModelFeedback(observation).state,'waiting');
  const stale={time:0,width:1280,height:720,bowLevel:{status:'ready',prediction:'none'}};
  assert.equal(bowModelFeedback(freshBodyObservation(stale,{width:1280,height:720},BODY_OVERLAY_MAX_AGE+1)?.bowLevel).state,'waiting');
});
