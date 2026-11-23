import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

// No network, credentials, or live user data: deterministic Puerto Rico clock.
const now=new Date('2026-11-23T14:00:00.000Z');
const verifiedAt=now.getTime()-60_000;
const task=(title,status)=>({title,status,due_at:'2026-11-23T15:00:00Z',priority:'high'});

test('completed and cancelled tasks are not represented as outstanding in Spanish',()=>{
  const text=dailyBriefing({tasks:[
    task('PRIVATE_DONE_MARKER','done'),
    task('PRIVATE_CANCELLED_MARKER','cancelled'),
    task('PRIVATE_COMPLETED_MARKER','completed'),
    task('PRIVATE_CANCELED_MARKER','canceled'),
    task('Active safe task','pending')
  ],loaded:true,verifiedAt,now});
  assert.match(text,/1 pendientes/);
  assert.match(text,/1 con vencimiento/);
  assert.match(text,/Active safe task/);
  assert.doesNotMatch(text,/PRIVATE_(?:DONE|CANCELLED|COMPLETED|CANCELED)_MARKER/);
  assert.match(text,/calendario.*no est[aá]n conectados/i);
});

test('completed-only tasks do not become invented meetings in English',()=>{
  const text=dailyBriefing({tasks:[task('PRIVATE_FINISHED','done')],loaded:true,verifiedAt,now,english:true});
  assert.match(text,/0 pending/);
  assert.match(text,/No pending tasks were recorded/);
  assert.doesNotMatch(text,/PRIVATE_FINISHED/);
  assert.match(text,/cannot confirm meetings or departure times/);
});

test('stale verification never exposes inactive task titles',()=>{
  const text=dailyBriefing({tasks:[task('PRIVATE_STALE','cancelled')],loaded:true,verifiedAt:now.getTime()-16*60_000,now});
  assert.match(text,/No puedo verificar tus tareas/);
  assert.doesNotMatch(text,/PRIVATE_STALE/);
});
