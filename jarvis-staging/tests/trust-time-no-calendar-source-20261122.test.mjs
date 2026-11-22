// Run: node --test jarvis-staging/tests/trust-time-no-calendar-source-20261122.test.mjs
// Offline integration checks against the actual briefing module. No API or private data.
import test from 'node:test';
import assert from 'node:assert/strict';
import { trustedCommand, dailyBriefing } from '../site/briefing.js';

const now = new Date('2026-11-22T04:10:00Z');
const context = {
  now,
  loaded: true,
  verifiedAt: now.getTime() - 60_000,
  tasks: [{ title: 'PRIVATE-PLACEHOLDER', status: 'pending', priority: 'high',
    due_at: '2026-11-22T09:00:00-04:00' }],
};

test('calendar queries disclose missing source in both languages without exposing tasks', () => {
  for (const [query, language, expected] of [
    ['¿Tengo alguna cita?', 'es', /calendario.*no est[aá] conectado/i],
    ['Do I have any appointments?', 'en', /calendar is not connected/i],
  ]) {
    const result = trustedCommand(query, context);
    assert.equal(result?.language, language);
    assert.match(result.text, expected);
    assert.doesNotMatch(result.text, /PRIVATE-PLACEHOLDER/);
    assert.doesNotMatch(result.text, /\b\d{1,2}:\d{2}\b/);
  }
});

test('travel requests refuse departure advice without authorized sources', () => {
  for (const [query, language] of [
    ['¿A qué hora debo salir?', 'es'],
    ['When should I leave?', 'en'],
  ]) {
    const result = trustedCommand(query, context);
    assert.equal(result?.language, language);
    assert.doesNotMatch(result.text, /PRIVATE-PLACEHOLDER|\b\d+\s*(?:minutos?|minutes?)\b/i);
    assert.match(result.text, language === 'es' ? /punto de partida autorizado/i : /authorized starting point/i);
    assert.match(result.text, language === 'es' ? /tr[aá]fico/i : /traffic/i);
  }
});

test('fresh task briefing discloses task provenance, not verified calendar events', () => {
  for (const english of [false, true]) {
    const result = dailyBriefing({ ...context, english });
    assert.match(result, english ? /JARVIS tasks verified/i : /tareas de JARVIS verificadas/i);
    assert.match(result, english ? /not appointments/i : /no citas/i);
    assert.match(result, /PRIVATE-PLACEHOLDER/);
  }
});

test('failed refresh does not imply an empty calendar or leak stale tasks', () => {
  for (const english of [false, true]) {
    const result = dailyBriefing({ ...context, loaded: false, english });
    assert.doesNotMatch(result, /PRIVATE-PLACEHOLDER/);
    assert.match(result, english ? /cannot verify/i : /No puedo verificar/i);
    assert.doesNotMatch(result, english ? /No pending tasks were recorded/i : /No hay tareas pendientes registradas/i);
  }
});
