import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing } from '../site/briefing.js';

const task = Object.freeze({title:'Entrega nocturna',status:'pending',due_at:'2026-11-20T23:59:00-04:00'});
const context = (now) => ({tasks:Object.freeze([task]),loaded:true,verifiedAt:now.getTime(),now});

test('Puerto Rico midnight remains on Nov 20 before 04:00Z', () => {
  const text=dailyBriefing(context(new Date('2026-11-21T03:58:00Z')));
  assert.match(text,/1 con vencimiento más tarde hoy/);
  assert.match(text,/Entrega nocturna/);
});

test('Puerto Rico midnight rolls to Nov 21 at 04:00Z', () => {
  const text=dailyBriefing(context(new Date('2026-11-21T04:00:00Z')));
  assert.match(text,/1 atrasadas/);
  assert.match(text,/0 con vencimiento más tarde hoy/);
});

test('year boundary follows Puerto Rico rather than UTC', () => {
  const now=new Date('2027-01-01T02:00:00Z');
  const text=dailyBriefing({tasks:[{title:'Cierre de año',status:'pending',due_at:'2026-12-31T23:00:00-04:00'}],loaded:true,verifiedAt:now.getTime(),now});
  assert.match(text,/1 con vencimiento más tarde hoy/);
});
