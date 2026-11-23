import test from 'node:test';
import assert from 'node:assert/strict';
import { trustedCommand } from '../site/briefing.js';

const now = new Date('2026-11-23T15:00:00Z');
const context = { now, loaded: true, verifiedAt: now.getTime() - 1000,
  tasks: [{ title: 'PRIVATE_ROUTE_MARKER leave at 8:10, traffic 25 min',
    due_at: '2026-11-23T17:00:00-04:00', status: 'pending', priority: 'high' }] };

for (const [query, expectedLanguage] of [
  ['JARVIS, ¿a qué hora debo salir?', 'es'],
  ['JARVIS, when should I leave?', 'en'],
  ['Voy a llegar tarde', 'es'],
  ['Will I be late?', 'en'],
]) {
  test(`unverified departure question does not infer routes: ${query}`, () => {
    const result = trustedCommand(query, context);
    assert.ok(result, 'must produce a trust-first response');
    assert.equal(result.language, expectedLanguage);
    assert.doesNotMatch(result.text, /PRIVATE_ROUTE_MARKER|8:10|25 min/i);
    assert.match(result.text, expectedLanguage === 'es' ? /No puedo calcular/ : /cannot calculate/i);
  });
}
