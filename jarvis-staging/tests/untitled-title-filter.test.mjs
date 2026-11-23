import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-23T02:45:00Z');
const verifiedAt=now.getTime()-1000;
const task=title=>({title,status:'pending',priority:'normal',due_at:null});

test('a legitimate Sin título task remains pending',()=>{
  const reply=dailyBriefing({tasks:[task('Sin título')],loaded:true,verifiedAt,now});
  assert.match(reply,/1 pendientes/);
  assert.match(reply,/Prioridades sugeridas: 1\. Sin título/);
});

test('invisible-only and whitespace-only titles do not become commitments',()=>{
  const reply=dailyBriefing({tasks:[task('  '),task('\u200b\u2060'),task('Sin título')],loaded:true,verifiedAt,now,english:true});
  assert.match(reply,/1 pending/);
  assert.match(reply,/Suggested priorities: 1\. Sin título/);
});

test('unverified tasks never become confirmed counts',()=>{
  const reply=dailyBriefing({tasks:[task('Sin título')],loaded:true,verifiedAt:now.getTime()-16*60*1000,now});
  assert.match(reply,/No puedo verificar/);
  assert.doesNotMatch(reply,/1 pendientes/);
});
