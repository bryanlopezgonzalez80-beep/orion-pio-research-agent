// Regression: untrusted task status must not become a verified pending commitment.
// Run from repository root: node --test jarvis-staging/tests/task-status-boundary-20261123.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand } from '../site/briefing.js';

const now = new Date('2026-11-23T17:00:00.000Z');
const verifiedAt = now.getTime() - 60_000;
const context = tasks => ({tasks, loaded:true, verifiedAt, now});

test('only pending tasks count: completed, cancelled, and unknown statuses are excluded', () => {
  const tasks = [
    {title:'Actual pending task', status:'pending', priority:'high'},
    {title:'SECRET COMPLETED', status:' Completed '},
    {title:'SECRET CANCELLED', status:'CANCELED'},
    {title:'SECRET UNKNOWN', status:'processing'},
    {title:'SECRET MISSING', status:'archived'}
  ];
  for (const english of [false, true]) {
    const output = dailyBriefing({...context(tasks), english});
    assert.match(output, english ? /1 pending/ : /1 pendientes/);
    assert.match(output, /Actual pending task/);
    for (const secret of ['SECRET COMPLETED','SECRET CANCELLED','SECRET UNKNOWN','SECRET MISSING']) {
      assert.doesNotMatch(output, new RegExp(secret));
    }
  }
});

test('expired verification never reveals a private task title or count', () => {
  const tasks=[{title:'PRIVATE ACCOUNT DETAILS',status:'pending'}];
  for(const english of [false,true]) {
    const output=dailyBriefing({tasks,loaded:true,verifiedAt:now.getTime()-15*60*1000,now,english});
    assert.doesNotMatch(output,/PRIVATE ACCOUNT DETAILS|1 pending|1 pendientes/);
    assert.match(output,english?/cannot verify/i:/no puedo verificar/i);
  }
});

test('calendar and departure questions cannot turn task titles into verified events', () => {
  const tasks=[{title:'Meeting at 9; traffic 12 minutes; leave at 8:45',status:'pending'}];
  for (const query of ['¿Tengo alguna reunión hoy?', 'Do I have any meetings?', '¿A qué hora debo salir?', 'When should I leave?']) {
    const result=trustedCommand(query,context(tasks));
    assert.ok(result,query);
    assert.doesNotMatch(result.text,/traffic 12 minutes|leave at 8:45/i);
    assert.match(result.text,/no (?:puedo|he consultado)|cannot|not connected|no está conectado/i);
  }
});
