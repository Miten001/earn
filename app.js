(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const canvas = $("designCanvas");
  const card = $("canvasCard");
  const ctx = canvas.getContext("2d", { alpha: false });
  let activeCtx = ctx;
  const cursor = $("autoCursor");

  const palettes = [
    {
      name: "Ultraviolet bloom",
      description: "Cool glow on midnight ink",
      colors: ["#67e6f1", "#9b7cf6", "#e17ee7", "#d9f584"],
      background: "#080d20",
      glow: "#352060"
    },
    {
      name: "Solar afterglow",
      description: "Warm sparks through deep plum",
      colors: ["#ffcd6b", "#ff7c91", "#c47dff", "#6ce7d2"],
      background: "#170b24",
      glow: "#702950"
    },
    {
      name: "Pacific signal",
      description: "Electric cyan and mineral blue",
      colors: ["#63f0e1", "#52c6ff", "#7e8cff", "#fcf17b"],
      background: "#061a2a",
      glow: "#084a62"
    },
    {
      name: "Botanical voltage",
      description: "Acid green meets soft violet",
      colors: ["#d7fa80", "#79f0b8", "#bb88fc", "#f29bd9"],
      background: "#0c1d1c",
      glow: "#315537"
    }
  ];

  const styleMeta = {
    kaleido: { name: "Prismatic kaleidoscope", short: "KALEIDO" },
    orbit: { name: "Tidal orbit study", short: "ORBITALS" },
    lattice: { name: "Aurora flow field", short: "FLOW FIELD" },
    bloom: { name: "Electric botanical", short: "BLOOM" },
    spiro: { name: "Cycloid spirograph", short: "SPIROGRAPH" },
    constellation: { name: "Starfield constellation", short: "STARFIELD" }
  };

  const state = {
    style: "auto",
    density: 68,
    speed: 54,
    paletteIndex: 0,
    autoCycle: true,
    showCursor: true,
    playing: true,
    phase: "drawing",
    loop: 0,
    completed: 0,
    design: null,
    queuedNew: false,
    phaseStarted: performance.now(),
    lastCursor: { x: 0.5, y: 0.5 },
    size: { width: 1, height: 1, dpr: 1 }
  };

  function randomSeed() {
    const values = new Uint32Array(1);
    if (window.crypto && window.crypto.getRandomValues) window.crypto.getRandomValues(values);
    else values[0] = Math.floor(Math.random() * 0xffffffff);
    return values[0] || 123456789;
  }

  function makeRandom(seed) {
    let value = seed >>> 0;
    return () => {
      value += 0x6D2B79F5;
      let t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const pick = (items, random) => items[Math.floor(random() * items.length)];

  function rgba(hex, alpha) {
    const value = hex.replace("#", "");
    const r = parseInt(value.slice(0, 2), 16);
    const g = parseInt(value.slice(2, 4), 16);
    const b = parseInt(value.slice(4, 6), 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  }

  function addLine(ops, x1, y1, x2, y2, color, width = 1, alpha = .72, control = null) {
    ops.push({
      kind: "line", x1: clamp(x1), y1: clamp(y1), x2: clamp(x2), y2: clamp(y2),
      color, width, alpha, control
    });
  }

  function addDot(ops, x, y, color, radius = 1.2, alpha = .9) {
    ops.push({ kind: "dot", x: clamp(x), y: clamp(y), color, radius, alpha });
  }

  function createKaleido(random, density) {
    const ops = [];
    const rays = Math.round(7 + density / 10);
    const rings = Math.round(11 + density * .24);
    const centerX = .5 + (random() - .5) * .045;
    const centerY = .5 + (random() - .5) * .045;
    const baseRotation = random() * Math.PI;
    const distortion = .05 + random() * .10;

    for (let ring = 0; ring < rings; ring++) {
      const t1 = ring / rings;
      const t2 = (ring + 1) / rings;
      const r1 = .025 + Math.pow(t1, .78) * .43;
      const r2 = .025 + Math.pow(t2, .78) * .43;
      const wave = Math.sin(t1 * Math.PI * (2 + Math.floor(random() * 3))) * distortion;

      for (let ray = 0; ray < rays; ray++) {
        const a1 = baseRotation + (ray / rays) * Math.PI * 2;
        const a2 = baseRotation + ((ray + .55 + wave) / rays) * Math.PI * 2;
        const color = (ray + ring) % 4;
        const x1 = centerX + Math.cos(a1) * r1;
        const y1 = centerY + Math.sin(a1) * r1;
        const x2 = centerX + Math.cos(a2) * r2;
        const y2 = centerY + Math.sin(a2) * r2;
        const bendX = centerX + Math.cos((a1 + a2) / 2) * (r1 + r2) * .54;
        const bendY = centerY + Math.sin((a1 + a2) / 2) * (r1 + r2) * .54;
        addLine(ops, x1, y1, x2, y2, color, .45 + (ring % 5) * .11, .35 + t1 * .52, { x: bendX, y: bendY });

        if (ring % 3 === 0) {
          const mirrorA = baseRotation - ((ray + .55 + wave) / rays) * Math.PI * 2;
          addLine(ops, x1, y1, centerX + Math.cos(mirrorA) * r2, centerY + Math.sin(mirrorA) * r2, (color + 1) % 4, .36, .42);
        }
      }
      if (ring % 4 === 0) addDot(ops, centerX, centerY, ring % 4, 1.4 + ring * .025, .65);
    }
    return ops;
  }

  function createOrbit(random, density) {
    const ops = [];
    const count = Math.round(5 + density / 13);
    const steps = Math.round(24 + density * .22);
    const centerX = .5 + (random() - .5) * .10;
    const centerY = .5 + (random() - .5) * .08;
    const tilt = (-.55 + random() * 1.1);

    for (let orbit = 0; orbit < count; orbit++) {
      const radiusX = .12 + orbit * (.025 + random() * .008);
      const radiusY = radiusX * (.27 + random() * .48);
      const rotation = tilt + orbit * (Math.PI / count) * .42;
      let previous = null;
      const start = random() * Math.PI * 2;
      const sweep = Math.PI * (1.38 + random() * .72);

      for (let step = 0; step <= steps; step++) {
        const a = start + (step / steps) * sweep;
        const wobble = Math.sin(a * (2 + orbit % 3) + orbit) * .013;
        const px = Math.cos(a) * (radiusX + wobble);
        const py = Math.sin(a) * (radiusY + wobble);
        const x = centerX + px * Math.cos(rotation) - py * Math.sin(rotation);
        const y = centerY + px * Math.sin(rotation) + py * Math.cos(rotation);
        if (previous) addLine(ops, previous.x, previous.y, x, y, orbit % 4, .55 + (orbit % 3) * .18, .38 + orbit / count * .46);
        previous = { x, y };
      }
      const satA = start + sweep * (.3 + random() * .45);
      const satX = centerX + Math.cos(satA) * radiusX * Math.cos(rotation) - Math.sin(satA) * radiusY * Math.sin(rotation);
      const satY = centerY + Math.cos(satA) * radiusX * Math.sin(rotation) + Math.sin(satA) * radiusY * Math.cos(rotation);
      addDot(ops, satX, satY, (orbit + 2) % 4, 1.5 + random() * 1.7, .9);
    }

    for (let i = 0; i < 24 + density / 2; i++) {
      const a = random() * Math.PI * 2;
      const d = .03 + random() * .41;
      addDot(ops, centerX + Math.cos(a) * d, centerY + Math.sin(a) * d * .72, Math.floor(random() * 4), .45 + random() * 1.1, .32 + random() * .4);
    }
    return ops;
  }

  function createLattice(random, density) {
    const ops = [];
    const paths = Math.round(9 + density / 8);
    const steps = Math.round(20 + density * .22);
    const direction = random() > .5 ? 1 : -1;
    const phase = random() * Math.PI * 2;
    const frequency = 1.4 + random() * 2.3;

    for (let path = 0; path < paths; path++) {
      const base = .08 + (path / Math.max(paths - 1, 1)) * .84;
      let previous = null;
      for (let step = 0; step <= steps; step++) {
        const t = step / steps;
        const wave = Math.sin(t * Math.PI * frequency + path * .52 + phase) * (.045 + .022 * Math.sin(path));
        const drift = Math.cos(t * Math.PI * 2 + path * .37) * .024;
        const x = direction > 0 ? t : 1 - t;
        const y = base + wave + drift * (t - .5);
        if (previous) {
          const cx = (previous.x + x) / 2 + Math.sin(path + step) * .005;
          const cy = (previous.y + y) / 2 + Math.cos(path - step) * .008;
          addLine(ops, previous.x, previous.y, x, y, (path + Math.floor(step / 7)) % 4, .4 + (path % 4) * .11, .35 + t * .38, { x: cx, y: cy });
        }
        previous = { x, y };
      }
    }

    for (let path = 0; path < Math.max(5, Math.round(paths * .55)); path++) {
      const base = .15 + (path / Math.max(4, paths * .55 - 1)) * .7;
      let previous = null;
      for (let step = 0; step <= Math.round(steps * .65); step++) {
        const t = step / Math.round(steps * .65);
        const x = base + Math.sin(t * Math.PI * (frequency + .3) + path) * .055;
        const y = t;
        if (previous) addLine(ops, previous.x, previous.y, x, y, (path + 1) % 4, .32, .2 + t * .25);
        previous = { x, y };
      }
    }
    return ops;
  }

  function createBloom(random, density) {
    const ops = [];
    const petals = Math.round(8 + density / 11);
    const steps = Math.round(14 + density * .16);
    const centerX = .5 + (random() - .5) * .05;
    const centerY = .5 + (random() - .5) * .05;
    const spin = random() * Math.PI * 2;

    for (let petal = 0; petal < petals; petal++) {
      const a = spin + petal / petals * Math.PI * 2;
      const length = .20 + random() * .25;
      const width = .06 + random() * .10;
      let previous = { x: centerX, y: centerY };
      for (let step = 1; step <= steps; step++) {
        const t = step / steps;
        const swell = Math.sin(t * Math.PI) * width;
        const radius = t * length;
        const x = centerX + Math.cos(a) * radius + Math.cos(a + Math.PI / 2) * swell;
        const y = centerY + Math.sin(a) * radius + Math.sin(a + Math.PI / 2) * swell;
        addLine(ops, previous.x, previous.y, x, y, (petal + Math.floor(step / 4)) % 4, .42 + t * .48, .35 + t * .48, { x: previous.x + Math.cos(a + Math.PI / 2) * swell * .6, y: previous.y + Math.sin(a + Math.PI / 2) * swell * .6 });
        previous = { x, y };
      }
      if (petal % 2 === 0) addDot(ops, previous.x, previous.y, petal % 4, 1.1 + random() * 1.6, .86);
    }
    for (let i = 0; i < 30 + density / 2; i++) {
      const a = random() * Math.PI * 2;
      const d = random() * .43;
      addDot(ops, centerX + Math.cos(a) * d, centerY + Math.sin(a) * d, Math.floor(random() * 4), .3 + random() * 1, .2 + random() * .5);
    }
    return ops;
  }

  function createSpiro(random, density) {
    const ops = [];
    const arms = Math.round(3 + density / 30);
    const steps = Math.round(120 + density * 1.8);
    const centerX = .5 + (random() - .5) * .03;
    const centerY = .5 + (random() - .5) * .03;

    for (let arm = 0; arm < arms; arm++) {
      const R = .16 + random() * .10;
      const r = R * (.28 + random() * .38);
      const d = r * (.55 + random() * .75);
      const spins = 4 + Math.floor(random() * 9);
      const k = (R - r) / r;
      const scale = .42 / ((R - r) + d);
      const rotation = random() * Math.PI * 2;
      let previous = null;

      for (let step = 0; step <= steps; step++) {
        const t = (step / steps) * Math.PI * 2 * spins;
        const x = (R - r) * Math.cos(t) + d * Math.cos(k * t);
        const y = (R - r) * Math.sin(t) - d * Math.sin(k * t);
        const px = centerX + (x * Math.cos(rotation) - y * Math.sin(rotation)) * scale;
        const py = centerY + (x * Math.sin(rotation) + y * Math.cos(rotation)) * scale;
        if (previous) {
          addLine(ops, previous.x, previous.y, px, py, (arm + Math.floor(step / 40)) % 4, .5, .3 + (step / steps) * .45);
        }
        previous = { x: px, y: py };
      }
    }

    for (let i = 0; i < 22; i++) {
      const a = random() * Math.PI * 2;
      const d = random() * .10;
      addDot(ops, centerX + Math.cos(a) * d, centerY + Math.sin(a) * d, Math.floor(random() * 4), .5 + random() * 1.3, .55 + random() * .35);
    }
    return ops;
  }

  function createConstellation(random, density) {
    const ops = [];
    const count = Math.round(26 + density / 2.6);
    const points = [];
    for (let i = 0; i < count; i++) {
      const a = random() * Math.PI * 2;
      const d = Math.pow(random(), .62) * .45;
      points.push({
        x: .5 + Math.cos(a) * d,
        y: .5 + Math.sin(a) * d * .85,
        r: .35 + Math.pow(random(), 2.2) * 2.2
      });
    }

    const threshold = .17 + density * .0007;
    for (let i = 0; i < points.length; i++) {
      const near = [];
      for (let j = 0; j < points.length; j++) {
        if (i === j) continue;
        const dist = Math.hypot(points[i].x - points[j].x, points[i].y - points[j].y);
        if (dist < threshold) near.push({ j, dist });
      }
      near.sort((a, b) => a.dist - b.dist);
      const links = Math.min(2 + Math.floor(random() * 2), near.length);
      for (let k = 0; k < links; k++) {
        const { j, dist } = near[k];
        if (j > i) addLine(ops, points[i].x, points[i].y, points[j].x, points[j].y, (i + j) % 4, .32, (.62 - dist / threshold) * .55 + .12);
      }
    }

    for (const p of points) addDot(ops, p.x, p.y, Math.floor(random() * 4), p.r, .45 + random() * .5);
    return ops;
  }

  function makeOperations(type, seed) {
    const random = makeRandom(seed);
    if (type === "kaleido") return createKaleido(random, state.density);
    if (type === "orbit") return createOrbit(random, state.density);
    if (type === "lattice") return createLattice(random, state.density);
    if (type === "spiro") return createSpiro(random, state.density);
    if (type === "constellation") return createConstellation(random, state.density);
    return createBloom(random, state.density);
  }

  function paintBase() {
    const { width, height } = state.size;
    const palette = palettes[state.paletteIndex];
    activeCtx.globalCompositeOperation = "source-over";
    activeCtx.globalAlpha = 1;
    activeCtx.fillStyle = palette.background;
    activeCtx.fillRect(0, 0, width, height);

    const primaryGlow = activeCtx.createRadialGradient(width * .50, height * .49, 0, width * .5, height * .49, Math.max(width, height) * .63);
    primaryGlow.addColorStop(0, rgba(palette.glow, .40));
    primaryGlow.addColorStop(.45, rgba(palette.glow, .12));
    primaryGlow.addColorStop(1, rgba(palette.background, 0));
    activeCtx.fillStyle = primaryGlow;
    activeCtx.fillRect(0, 0, width, height);

    const edgeGlow = activeCtx.createRadialGradient(width * .09, height * .85, 0, width * .09, height * .85, width * .55);
    edgeGlow.addColorStop(0, rgba(palette.colors[1], .075));
    edgeGlow.addColorStop(1, rgba(palette.colors[1], 0));
    activeCtx.fillStyle = edgeGlow;
    activeCtx.fillRect(0, 0, width, height);
  }

  function drawOperation(op, index) {
    const { width, height } = state.size;
    const colors = palettes[state.paletteIndex].colors;
    const color = colors[op.color % colors.length];
    activeCtx.globalCompositeOperation = "lighter";
    activeCtx.globalAlpha = op.alpha;
    activeCtx.strokeStyle = color;
    activeCtx.fillStyle = color;
    activeCtx.lineCap = "round";
    activeCtx.lineJoin = "round";
    activeCtx.shadowColor = color;
    activeCtx.shadowBlur = index % 11 === 0 ? 8 : 2;

    if (op.kind === "line") {
      activeCtx.lineWidth = op.width;
      activeCtx.beginPath();
      activeCtx.moveTo(op.x1 * width, op.y1 * height);
      if (op.control) activeCtx.quadraticCurveTo(op.control.x * width, op.control.y * height, op.x2 * width, op.y2 * height);
      else activeCtx.lineTo(op.x2 * width, op.y2 * height);
      activeCtx.stroke();
      state.lastCursor = { x: op.x2, y: op.y2 };
    } else {
      activeCtx.beginPath();
      activeCtx.arc(op.x * width, op.y * height, op.radius, 0, Math.PI * 2);
      activeCtx.fill();
      state.lastCursor = { x: op.x, y: op.y };
    }
    activeCtx.shadowBlur = 0;
  }

  function updateCursor(click = false) {
    if (!state.showCursor || state.phase === "clearing" || !state.playing) {
      cursor.classList.remove("visible");
      return;
    }
    const colors = palettes[state.paletteIndex].colors;
    cursor.style.left = `${state.lastCursor.x * 100}%`;
    cursor.style.top = `${state.lastCursor.y * 100}%`;
    cursor.style.setProperty("--cursor-color", colors[(state.design?.operations.length || 0) % colors.length]);
    cursor.classList.add("visible");
    if (click) {
      cursor.classList.remove("is-clicking");
      // Restart the click flare animation without affecting pointer movement.
      void cursor.offsetWidth;
      cursor.classList.add("is-clicking");
    }
  }

  function setRangeFill(input) {
    const percent = ((Number(input.value) - Number(input.min)) / (Number(input.max) - Number(input.min))) * 100;
    input.style.setProperty("--range-fill", `${percent}%`);
  }

  function setPhase(phase) {
    state.phase = phase;
    state.phaseStarted = performance.now();
    const stateBox = $("canvasState");
    stateBox.classList.toggle("is-clearing", phase === "clearing");
    stateBox.classList.toggle("is-paused", !state.playing);

    const labels = {
      drawing: "DRAWING",
      holding: "DESIGN COMPLETE",
      finished: "AWAITING NEXT",
      clearing: "CLEARING",
      paused: "PAUSED"
    };
    $("stateText").textContent = labels[phase] || "DRAWING";
  }

  function updateStaticUI() {
    const palette = palettes[state.paletteIndex];
    $("paletteName").textContent = palette.name;
    $("paletteDescription").textContent = palette.description;
    $("paletteSwatches").querySelectorAll("i").forEach((swatch, index) => {
      swatch.style.background = palette.colors[index];
    });
    $("densityValue").textContent = state.density;
    $("speedValue").textContent = state.speed < 34 ? "Leisurely" : state.speed > 72 ? "Rapid" : "Balanced";
    setRangeFill($("densityRange"));
    setRangeFill($("speedRange"));
    $("completedCount").textContent = state.completed;
  }

  function updateProgress() {
    const design = state.design;
    if (!design) return;
    const total = design.operations.length;
    const done = Math.min(design.index, total);
    const percent = total ? Math.round(done / total * 100) : 0;
    $("strokeValue").textContent = `${done.toLocaleString()} / ${total.toLocaleString()}`;
    $("progressPercent").textContent = `${percent}%`;
    $("progressBar").style.width = `${percent}%`;

    if (state.phase === "drawing") $("progressText").textContent = `Tracing ${design.type === "lattice" ? "a living field" : "a new composition"}`;
    else if (state.phase === "holding") $("progressText").textContent = "Letting the composition breathe";
    else if (state.phase === "clearing") $("progressText").textContent = "Dissolving the current canvas";
    else if (state.phase === "finished") $("progressText").textContent = "Ready when you are";
  }

  function createDesign(incrementLoop = true, forcedSeed) {
    const allStyles = ["kaleido", "orbit", "lattice", "bloom", "spiro", "constellation"];
    const seed = forcedSeed != null ? (forcedSeed >>> 0) || randomSeed() : randomSeed();
    const random = makeRandom(seed);
    const type = state.style === "auto" ? pick(allStyles, random) : state.style;
    if (incrementLoop) state.loop += 1;
    state.design = { seed, type, index: 0, operations: makeOperations(type, seed) };
    state.queuedNew = false;
    state.lastCursor = { x: .5, y: .5 };
    paintBase();
    setPhase("drawing");

    const meta = styleMeta[type];
    $("seedValue").textContent = seed.toString(16).toUpperCase().padStart(8, "0").slice(-6);
    $("modeValue").textContent = meta.short;
    $("loopValue").textContent = String(state.loop).padStart(2, "0");
    $("designName").textContent = meta.name;
    updateProgress();
    updateCursor();
  }

  function queueFreshDesign() {
    state.queuedNew = true;
    if (!state.playing) togglePlaying(true);
    if (state.phase !== "clearing") setPhase("clearing");
  }

  function clearFrame() {
    const palette = palettes[state.paletteIndex];
    const { width, height } = state.size;
    activeCtx.globalCompositeOperation = "source-over";
    activeCtx.globalAlpha = 1;
    activeCtx.fillStyle = rgba(palette.background, .12);
    activeCtx.fillRect(0, 0, width, height);
  }

  function togglePlaying(force) {
    state.playing = typeof force === "boolean" ? force : !state.playing;
    const playButton = $("playToggle");
    playButton.classList.toggle("is-paused", !state.playing);
    $("playLabel").textContent = state.playing ? "Pause studio" : "Resume studio";
    if (!state.playing) {
      $("canvasState").classList.add("is-paused");
      $("stateText").textContent = "PAUSED";
      cursor.classList.remove("visible");
    } else {
      $("canvasState").classList.remove("is-paused");
      setPhase(state.phase);
      updateCursor();
    }
  }

  function animate(now) {
    if (state.playing && state.design) {
      const design = state.design;
      if (state.phase === "drawing") {
        const strokesPerFrame = Math.max(2, Math.round(1 + state.speed / 9));
        const end = Math.min(design.index + strokesPerFrame, design.operations.length);
        for (; design.index < end; design.index++) drawOperation(design.operations[design.index], design.index);
        updateCursor(design.index % 20 === 0);
        updateProgress();

        if (design.index >= design.operations.length) {
          state.completed += 1;
          $("completedCount").textContent = state.completed;
          setPhase("holding");
          updateProgress();
        }
      } else if (state.phase === "holding") {
        if (now - state.phaseStarted > 1500) {
          if (state.autoCycle || state.queuedNew) setPhase("clearing");
          else setPhase("finished");
          updateProgress();
        }
      } else if (state.phase === "clearing") {
        clearFrame();
        cursor.classList.remove("visible");
        updateProgress();
        if (now - state.phaseStarted > 720) createDesign(true);
      } else if (state.phase === "finished" && state.autoCycle) {
        setPhase("clearing");
      }
    }
    requestAnimationFrame(animate);
  }

  function resizeCanvas() {
    const rect = canvas.getBoundingClientRect();
    if (rect.width < 2 || rect.height < 2) return;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    state.size = { width: rect.width, height: rect.height, dpr };
    canvas.width = Math.round(rect.width * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = true;
    paintBase();
    if (state.design) {
      // A resize starts a clean version of the same live idea rather than stretching pixels.
      const existing = state.design;
      state.design = { ...existing, index: 0, operations: makeOperations(existing.type, existing.seed) };
      setPhase("drawing");
      updateProgress();
    }
  }

  function updateClock() {
    $("localTime").textContent = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date());
  }

  $("densityRange").addEventListener("input", (event) => {
    state.density = Number(event.target.value);
    updateStaticUI();
  });

  $("speedRange").addEventListener("input", (event) => {
    state.speed = Number(event.target.value);
    updateStaticUI();
  });

  $("styleGrid").addEventListener("click", (event) => {
    const button = event.target.closest(".style-card");
    if (!button) return;
    state.style = button.dataset.style;
    document.querySelectorAll(".style-card").forEach((cardButton) => cardButton.classList.toggle("active", cardButton === button));
    queueFreshDesign();
  });

  function nextPalette() {
    state.paletteIndex = (state.paletteIndex + 1) % palettes.length;
    updateStaticUI();
    queueFreshDesign();
  }
  $("newPalette").addEventListener("click", nextPalette);
  $("cyclePalette").addEventListener("click", nextPalette);

  $("autoCycle").addEventListener("change", (event) => {
    state.autoCycle = event.target.checked;
    if (state.autoCycle && state.phase === "finished") queueFreshDesign();
  });
  $("cursorToggle").addEventListener("change", (event) => {
    state.showCursor = event.target.checked;
    updateCursor();
  });
  $("playToggle").addEventListener("click", () => togglePlaying());
  $("clearButton").addEventListener("click", queueFreshDesign);
  $("createButton").addEventListener("click", queueFreshDesign);

  $("fullscreenButton").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await card.requestFullscreen();
    } catch (_) { /* Fullscreen can be unavailable in embedded previews. */ }
  });
  document.addEventListener("fullscreenchange", () => requestAnimationFrame(resizeCanvas));

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(resizeCanvas, 100);
  });

  function flashButton(button, label) {
    if (button.dataset.label == null) button.dataset.label = button.textContent;
    clearTimeout(button._flashTimer);
    button.textContent = label;
    button.classList.add("is-flash");
    button._flashTimer = setTimeout(() => {
      button.textContent = button.dataset.label;
      button.classList.remove("is-flash");
    }, 1400);
  }

  function exportPNG() {
    const design = state.design;
    const { width, height } = state.size;
    const scale = 2;
    const out = document.createElement("canvas");
    out.width = Math.max(1, Math.round(width * scale));
    out.height = Math.max(1, Math.round(height * scale));
    const octx = out.getContext("2d");
    octx.scale(scale, scale);
    octx.imageSmoothingEnabled = true;

    const previousCtx = activeCtx;
    const previousCursor = state.lastCursor;
    activeCtx = octx;
    try {
      paintBase();
      if (design) {
        for (let i = 0; i < design.operations.length; i++) drawOperation(design.operations[i], i);
      }
    } finally {
      activeCtx = previousCtx;
      state.lastCursor = previousCursor;
    }

    const slug = design ? `${design.seed.toString(16)}-${design.type}` : Date.now().toString(16);
    const link = document.createElement("a");
    link.download = `loopsketch-${slug}.png`;
    link.href = out.toDataURL("image/png");
    link.click();
  }

  function copySeed() {
    const design = state.design;
    if (!design) return;
    const value = `LoopSketch seed ${design.seed.toString(16).toUpperCase().padStart(8, "0")} (${design.type})`;
    const done = () => flashButton($("copySeedButton"), "Copied ✓");
    const fail = () => flashButton($("copySeedButton"), "Press Ctrl+C");
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(value).then(done, fail);
    } else {
      const area = document.createElement("textarea");
      area.value = value;
      area.style.position = "fixed";
      area.style.opacity = "0";
      document.body.appendChild(area);
      area.select();
      try {
        document.execCommand("copy");
        done();
      } catch (_) {
        fail();
      }
      document.body.removeChild(area);
    }
  }

  function applySeed() {
    const raw = $("seedInput").value.trim();
    if (!raw) {
      flashButton($("applySeedButton"), "Empty");
      return;
    }
    const cleaned = raw.replace(/^#|0x/gi, "").replace(/[\s-]/g, "");
    const parsed = parseInt(cleaned, 16);
    if (Number.isNaN(parsed)) {
      flashButton($("applySeedButton"), "Invalid");
      return;
    }
    $("seedInput").value = "";
    if (!state.playing) togglePlaying(true);
    createDesign(true, parsed);
    flashButton($("applySeedButton"), "Loaded");
  }

  $("exportButton").addEventListener("click", () => {
    exportPNG();
    flashButton($("exportButton"), "Saved ✓");
  });
  $("copySeedButton").addEventListener("click", copySeed);
  $("applySeedButton").addEventListener("click", applySeed);
  $("seedInput").addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      applySeed();
    }
  });

  document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) return;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    switch (event.key.toLowerCase()) {
      case " ":
        event.preventDefault();
        togglePlaying();
        break;
      case "n":
        queueFreshDesign();
        break;
      case "p":
        nextPalette();
        break;
      case "e":
        exportPNG();
        flashButton($("exportButton"), "Saved ✓");
        break;
      case "c":
        copySeed();
        break;
      case "f":
        $("fullscreenButton").click();
        break;
    }
  });

  updateStaticUI();
  updateClock();
  setInterval(updateClock, 20_000);
  resizeCanvas();
  createDesign(true);
  requestAnimationFrame(animate);
})();
