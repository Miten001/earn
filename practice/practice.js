'use strict';

const durations = [6, 10, 14];
const symbols = ['b', 'c', 'e', 'h', 'k', 'm', 'p', 'r', 's', 't', 'v', 'y'];
const colors = ['#242039', '#5531bf', '#207541'];
const template = document.querySelector('#challenge-template');
const list = document.querySelector('#challenges');
const progress = document.querySelector('#progress');
let rows = [];
let ticker;

function pickSymbols() {
  const pool = [...symbols];
  return Array.from({ length: 3 }, () => pool.splice(Math.floor(Math.random() * pool.length), 1)[0]);
}

function drawSymbol(symbol, rowIndex, tileIndex) {
  const tilt = Math.floor(Math.random() * 39) - 19;
  const x = 11 + Math.floor(Math.random() * 21);
  const y = 15 + Math.floor(Math.random() * 31);
  return `<svg viewBox="0 0 100 72" aria-hidden="true" focusable="false">
    <text x="50" y="54" text-anchor="middle" font-family="Georgia, serif" font-size="60" font-style="italic" fill="${colors[(rowIndex + tileIndex) % colors.length]}" transform="rotate(${tilt} 50 36)">${symbol}</text>
    <circle cx="${x}" cy="${y}" r="2.5" fill="#7852de" opacity=".7" />
    <path d="M8 ${y}L91 ${72 - y} M25 63l24 -17" stroke="#8668ad" stroke-opacity=".65" fill="none" stroke-dasharray="3 2" />
  </svg>`;
}

function refreshProgress() {
  const finished = rows.filter(row => row.done).length;
  progress.textContent = `${finished} / ${rows.length} completed`;
  if (finished === rows.length) clearInterval(ticker);
}

function finish(row, automatic) {
  row.done = true;
  row.element.classList.add('done');
  row.status.textContent = automatic ? 'Auto-selected' : 'Matched';
  for (const tile of row.tiles) {
    tile.setAttribute('aria-disabled', 'true');
    tile.tabIndex = -1;
    tile.classList.remove('is-wrong');
  }
  row.answer.classList.add('is-answer');
  row.answer.setAttribute('aria-pressed', 'true');
  refreshProgress();
}

function updateTime(row, now) {
  const remaining = Math.max(0, row.deadline - now);
  const seconds = Math.ceil(remaining / 1000);
  row.count.textContent = `00:${String(seconds).padStart(2, '0')}`;
  row.count.setAttribute('aria-label', `${seconds} seconds left`);
  row.bar.style.transform = `scaleX(${Math.min(1, remaining / row.duration)})`;
  return remaining;
}

function tick() {
  const now = performance.now();
  for (const row of rows) {
    if (!row.done && updateTime(row, now) === 0) row.answer.click();
  }
}

function buildRow(seconds, index, start) {
  const element = template.content.firstElementChild.cloneNode(true);
  const heading = element.querySelector('h3');
  heading.id = `challenge-${index + 1}`;
  heading.textContent = `Challenge ${String(index + 1).padStart(2, '0')}`;
  element.setAttribute('aria-labelledby', heading.id);
  const options = pickSymbols();
  const targetIndex = Math.floor(Math.random() * options.length);
  const target = options[targetIndex];
  element.querySelector('.target b').textContent = target;

  const duration = seconds * 1000;
  const row = {
    element, duration, deadline: start + duration, done: false,
    status: element.querySelector('.status'), count: element.querySelector('.count'),
    bar: element.querySelector('.track span'), tiles: [], answer: null,
  };
  row.status.setAttribute('aria-live', 'polite');
  const choices = element.querySelector('.choices');
  options.forEach((symbol, tileIndex) => {
    const tile = document.createElement('button');
    tile.type = 'button';
    tile.className = 'tile';
    tile.setAttribute('aria-label', `Choose symbol ${symbol}`);
    tile.setAttribute('aria-pressed', 'false');
    tile.innerHTML = drawSymbol(symbol, index, tileIndex);
    tile.addEventListener('click', () => {
      if (row.done) return;
      const expired = updateTime(row, performance.now()) === 0;
      if (tile === row.answer) {
        finish(row, expired);
      } else if (expired) {
        row.answer.click();
      } else {
        row.tiles.forEach(option => option.classList.toggle('is-wrong', option === tile));
        row.status.textContent = 'Try again';
      }
    });
    if (tileIndex === targetIndex) row.answer = tile;
    row.tiles.push(tile);
    choices.append(tile);
  });
  return row;
}

function startRound() {
  clearInterval(ticker);
  const start = performance.now();
  rows = durations.map((seconds, index) => buildRow(seconds, index, start));
  list.replaceChildren(...rows.map(row => row.element));
  refreshProgress();
  tick();
  ticker = setInterval(tick, 50);
}

document.querySelector('#reset').addEventListener('click', startRound);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) tick();
});
startRound();
