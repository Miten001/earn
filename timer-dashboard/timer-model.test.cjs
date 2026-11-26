'use strict';

const assert = require('node:assert/strict');
const { test } = require('node:test');
const { start, advance, toggle, restart, format } = require('./timer-model.js');

test('timers expire independently and only once even if an update is late', () => {
  const first = start('Chrome', 6, 1000);
  const second = start('Edge', 10, 1000);
  assert.equal(advance(first, 6999), false);
  assert.equal(format(first.remaining), '00:01');
  assert.equal(advance(first, 7000), true);
  assert.equal(advance(second, 7000), false);
  assert.equal(advance(first, 12000), false);
  assert.equal(advance(second, 12000), true);
  assert.equal(second.remaining, 0);
});

test('pause, resume and restart keep the correct remaining time', () => {
  const timer = start('Window 1', 10, 0);
  advance(timer, 4000);
  toggle(timer, 4000);
  advance(timer, 10000);
  assert.equal(timer.remaining, 6000);
  toggle(timer, 10000);
  assert.equal(advance(timer, 15999), false);
  assert.equal(advance(timer, 16000), true);
  restart(timer, 16000);
  assert.equal(timer.remaining, 10000);
  assert.equal(advance(timer, 26000), true);
  toggle(timer, 26000);
  assert.equal(timer.state, 'running');
});

test('invalid durations are rejected and long durations format correctly', () => {
  for (const duration of [0, -1, 0.5, NaN, 60000]) assert.throws(() => start('Window', duration, 0), RangeError);
  assert.equal(format(0), '00:00');
  assert.equal(format(59999000), '999:59');
});
