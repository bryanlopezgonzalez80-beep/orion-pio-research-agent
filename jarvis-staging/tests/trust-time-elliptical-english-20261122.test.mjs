// Run: node --test jarvis-staging/tests/trust-time-elliptical-english-20261122.test.mjs
// Offline regression: brief English calendar questions must not leak private tasks.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('elliptical English meeting queries respond in English without invented events',()=>{
  for(const phrase of ['Any meetings?', 'Any appointments?', 'My meetings', 'Show my meetings', 'Are there any meetings?', 'Is there a meeting?']){
    assert.equal(classifyCommand(phrase),'calendar',phrase);
    const result=trustedCommand(phrase,{tasks:[{title:'PRIVATE_MEETING_TITLE',status:'pending'}],loaded:true,verifiedAt:Date.now()});
    assert.equal(result?.language,'en',phrase);
    assert.match(result.text,/calendar is not connected/i,phrase);
    assert.doesNotMatch(result.text,/PRIVATE_MEETING_TITLE|\b\d+ minutes\b/i,phrase);
  }
});
