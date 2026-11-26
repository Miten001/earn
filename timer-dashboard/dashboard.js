'use strict';

const byId = id => document.getElementById(id);
const form = byId('timer-form');
const labelInput = byId('timer-name');
const minutes = byId('minutes');
const seconds = byId('seconds');
const list = byId('timer-list');
const template = byId('timer-template');
const empty = byId('empty');
const running = byId('running');
const announcement = byId('announcement');
const notifications = byId('notifications');
const float = byId('float');
const note = byId('option-note');
const timers = new Set();
const states = { running: 'Running', paused: 'Paused', done: 'Time’s up' };
let next = 1;
let ticker;
let panel;
let notify = false;

function showDone(finished) {
  const message = `Time’s up: ${finished.map(timer => timer.label).join(', ')}.`;
  announcement.textContent = message;
  if (notify && window.Notification?.permission === 'granted') {
    try {
      new Notification('Window Timers', { body: message });
    } catch {
      note.textContent = 'System notification unavailable. Check the alert on this dashboard.';
    }
  }
}

function patch(row, timer) {
  const text = WindowTimers.format(timer.remaining);
  if (row.clock.textContent !== text) row.clock.textContent = text;
  if (row.element.dataset.state !== timer.state) {
    row.element.dataset.state = timer.state;
    row.state.textContent = states[timer.state];
    if (row.toggle) {
      row.toggle.textContent = { running: 'Pause', paused: 'Resume', done: 'Start again' }[timer.state];
    }
  }
  row.bar.style.transform = `scaleX(${timer.remaining / timer.duration})`;
}

function render() {
  let active = 0;
  for (const timer of timers) {
    if (timer.state === 'running') active++;
    patch(timer.row, timer);
    if (timer.floatingRow) patch(timer.floatingRow, timer);
  }
  empty.hidden = timers.size !== 0;
  running.textContent = `${active} RUNNING`;
  if (panel) panel.summary.textContent = timers.size ? `${active} running · ${timers.size} total` : 'Add timers from the main dashboard.';
  if (active && ticker === undefined) ticker = window.setInterval(update, 125);
  if (!active && ticker !== undefined) {
    window.clearInterval(ticker);
    ticker = undefined;
  }
}

function checkExpiry(now) {
  const finished = [...timers].filter(timer => WindowTimers.advance(timer, now));
  if (finished.length) showDone(finished);
}

function update() {
  checkExpiry(Date.now());
  render();
}

function buildRow(timer, owner) {
  const element = owner.importNode(template.content.firstElementChild, true);
  element.querySelector('h3').textContent = timer.label;
  const clock = element.querySelector('.clock');
  clock.setAttribute('aria-label', `Time remaining for ${timer.label}`);
  return { element, clock, state: element.querySelector('.state'), bar: element.querySelector('.track span') };
}

function addFloatingRow(timer) {
  if (!panel) return;
  const row = buildRow(timer, panel.window.document);
  row.element.querySelector('.timer-actions').remove();
  timer.floatingRow = row;
  panel.list.append(row.element);
}

function addTimer(label, duration, now) {
  const timer = WindowTimers.start(label, duration, now);
  const row = buildRow(timer, document);
  timer.row = row;
  row.toggle = row.element.querySelector('.toggle');
  const reset = row.element.querySelector('.reset');
  const remove = row.element.querySelector('.remove');

  row.toggle.addEventListener('click', () => {
    const time = Date.now();
    const previous = timer.state;
    checkExpiry(time);
    // If it just expired, preserve that result instead of treating a click on Pause as Start again.
    if (previous !== 'running' || timer.state === 'running') WindowTimers.toggle(timer, time);
    render();
  });
  reset.addEventListener('click', () => {
    const time = Date.now();
    checkExpiry(time);
    WindowTimers.restart(timer, time);
    render();
  });
  remove.addEventListener('click', () => {
    timers.delete(timer);
    row.element.remove();
    timer.floatingRow?.element.remove();
    if (!timers.size) announcement.textContent = '';
    labelInput.focus();
    update();
  });
  timers.add(timer);
  list.append(row.element);
  addFloatingRow(timer);
}

form.addEventListener('submit', event => {
  event.preventDefault();
  const duration = minutes.valueAsNumber * 60 + seconds.valueAsNumber;
  if (!duration) {
    seconds.setCustomValidity('Set at least one second.');
    seconds.reportValidity();
    return;
  }
  addTimer(labelInput.value.trim() || `Window ${next}`, duration, Date.now());
  next++;
  labelInput.value = '';
  update();
  labelInput.focus();
});
form.addEventListener('input', () => seconds.setCustomValidity(''));
form.querySelectorAll('[data-seconds]').forEach(button => button.addEventListener('click', () => {
  const duration = Number(button.dataset.seconds);
  minutes.value = Math.floor(duration / 60);
  seconds.value = duration % 60;
  seconds.setCustomValidity('');
}));

notifications.addEventListener('click', async () => {
  if (notify) {
    notify = false;
    notifications.textContent = 'Enable notifications';
    notifications.setAttribute('aria-pressed', 'false');
    note.textContent = 'Timers always show an alert here at zero.';
    return;
  }
  if (!window.Notification?.requestPermission) {
    note.textContent = 'System notifications aren’t available here. Alerts will still appear on the dashboard.';
    return;
  }
  notifications.disabled = true;
  try {
    notify = await Notification.requestPermission() === 'granted';
  } catch {
    notify = false;
  } finally {
    notifications.disabled = false;
  }
  notifications.textContent = notify ? 'Mute notifications' : 'Enable notifications';
  notifications.setAttribute('aria-pressed', String(notify));
  note.textContent = notify ? 'System notifications enabled for this session.' : 'Notifications not allowed. Alerts will still appear on the dashboard.';
});

if (window.documentPictureInPicture?.requestWindow) {
  float.hidden = false;
  float.addEventListener('click', async () => {
    float.disabled = true;
    try {
      const floatingWindow = await window.documentPictureInPicture.requestWindow({ width: 335, height: 390 });
      const doc = floatingWindow.document;
      doc.title = 'Window Timers';
      doc.documentElement.lang = 'en';
      doc.body.className = 'floating';
      const style = doc.createElement('link');
      style.rel = 'stylesheet';
      style.href = document.querySelector('link[rel="stylesheet"]').href;
      doc.head.append(style);
      const heading = doc.createElement('h1');
      heading.textContent = 'Window Timers';
      const summary = doc.createElement('p');
      summary.className = 'float-summary';
      const floatList = doc.createElement('div');
      floatList.className = 'timer-list';
      doc.body.append(heading, summary, floatList);
      panel = { window: floatingWindow, summary, list: floatList };
      floatingWindow.addEventListener('pagehide', () => {
        panel = undefined;
        for (const timer of timers) timer.floatingRow = undefined;
        float.disabled = false;
      }, { once: true });
      timers.forEach(addFloatingRow);
      update();
    } catch {
      float.disabled = false;
      note.textContent = 'Floating panel unavailable here. Try opening the dashboard in its own tab.';
    }
  });
}

// Browser scheduling can pause in the background; recompute against the deadline on return.
document.addEventListener('visibilitychange', update);
window.addEventListener('focus', update);
