// Reproduce: node --test jarvis-staging/tests/trust-time-curly-apostrophe-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, englishIntent, trustedCommand, recentVerification} from '../site/briefing.js';

test('iPhone curly apostrophe preserves English travel intent and private task isolation', () => {
  for (const utterance of ['I’m running late', 'JARVIS, I’m running late', 'Am I running late?']) {
    assert.equal(classifyCommand(utterance), 'travel', utterance);
    assert.equal(englishIntent(utterance), true, utterance);
    const response = trustedCommand(utterance, {
      loaded: true, verifiedAt: Date.now(),
      tasks: [{title: 'PRIVATE_IPHONE_SENTINEL', status: 'pending'}],
    });
    assert.equal(response.language, 'en', utterance);
    assert.match(response.text, /cannot calculate a reliable departure time/i);
    assert.doesNotMatch(response.text, /PRIVATE_IPHONE_SENTINEL/);
  }
});

test('15-minute freshness expires exactly at boundary and rejects future verification', () => {
  const now = Date.UTC(2026, 10, 22, 19, 0, 0);
  assert.equal(recentVerification(now - 899999, now), true);
  assert.equal(recentVerification(now - 900000, now), false);
  assert.equal(recentVerification(now + 1, now), false);
});
