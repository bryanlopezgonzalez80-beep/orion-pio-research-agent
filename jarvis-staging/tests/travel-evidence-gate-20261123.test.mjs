import test from 'node:test';
import assert from 'node:assert/strict';
import { trustedCommand, classifyCommand } from '../site/briefing.js';

// Deliberately include misleading task titles: they are not traffic or calendar evidence.
for (const [spoken, expectedLanguage] of [
  ['JARVIS, ¿a qué hora debo salir?', 'es'],
  ['When should I leave?', 'en'],
  ['Voy a llegar tarde', 'es'],
  ['Will I be late?', 'en'],
]) {
  test(`departure request does not invent ETA: ${spoken}`, () => {
    assert.equal(classifyCommand(spoken), 'travel');
    const result = trustedCommand(spoken, {
      tasks: [{title: 'Traffic: 12 minutes, meeting at 9', status: 'pending'}],
      loaded: true,
      verifiedAt: Date.now(),
    });
    assert.equal(result?.language, expectedLanguage);
    assert.equal(typeof result?.text, 'string');
    assert.match(result.text, expectedLanguage === 'es'
      ? /no puedo|no tengo|no dispongo/i
      : /cannot|do not have|don't have/i);
    assert.doesNotMatch(result.text, /12 minutes|9:00|9 a\.m\./i);
  });
}
