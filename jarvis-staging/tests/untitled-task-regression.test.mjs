import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-22T16:00:00Z');
const base={loaded:true,verifiedAt:now.getTime()-1000,now};

test('literal Sin título is a valid saved task, not an empty placeholder',()=>{
  const result=dailyBriefing({...base,tasks:[{title:'Sin título',status:'pending'}]});
  assert.match(result,/1 pendientes/);
  assert.match(result,/1\. Sin título/);
});
test('invisible-only titles are not counted as saved commitments',()=>{
  const result=dailyBriefing({...base,tasks:[{title:'\\u200b\\ufeff',status:'pending'}]});
  assert.match(result,/0 pendientes/);
});
