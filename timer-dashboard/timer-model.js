'use strict';

const WindowTimers = (() => {
  function start(label, seconds, now) {
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 59999) {
      throw new RangeError('Enter a duration from 1 second to 999:59.');
    }
    const duration = seconds * 1000;
    return { label, duration, remaining: duration, deadline: now + duration, state: 'running' };
  }

  // Returns true once per run: exactly when the timer moves to done.
  function advance(timer, now) {
    if (timer.state !== 'running') return false;
    timer.remaining = Math.min(timer.duration, Math.max(0, timer.deadline - now));
    if (timer.remaining > 0) return false;
    timer.state = 'done';
    return true;
  }

  function toggle(timer, now) {
    if (timer.state === 'running') {
      timer.state = 'paused';
    } else if (timer.state === 'paused') {
      timer.deadline = now + timer.remaining;
      timer.state = 'running';
    } else {
      restart(timer, now);
    }
  }

  function restart(timer, now) {
    timer.remaining = timer.duration;
    timer.deadline = now + timer.duration;
    timer.state = 'running';
  }

  function format(ms) {
    const total = Math.ceil(ms / 1000);
    return `${String(Math.floor(total / 60)).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`;
  }

  return { start, advance, toggle, restart, format };
})();

if (typeof module !== 'undefined') module.exports = WindowTimers;
