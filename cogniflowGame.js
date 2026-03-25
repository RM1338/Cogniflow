/* ═══════════════════════════════════════════════════════
   COGNIFLOW — LIVING REEF (Advanced)
   EEG Biofeedback Canvas Engine
   
   EEG Integration:
     window.Cogniflow.setState('FOCUS' | 'RELAXED' | 'DROWSY' | 'STRESSED')
   ═══════════════════════════════════════════════════════ */

const canvas = document.getElementById('reefCanvas');
const ctx    = canvas.getContext('2d');

// ── Resize ─────────────────────────────────────────────
function resize() {
  const parent = canvas.parentElement;
  canvas.width  = parent.offsetWidth;
  canvas.height = parent.offsetHeight;
}
resize();

// ── State ──────────────────────────────────────────────
let currentState   = 'RELAXED';
let prevState      = 'RELAXED';
let bleachLevel    = 0;       // 0 → 1
let globalTime     = 0;
let healFlashTimer = 0;

const STATE_CFG = {
  FOCUS: {
    growthRate:   0.013,
    spawnChance:  0.055,
    swayAmp:      0.5,
    particleRate: 0.35,
    particleHue:  170,
    fishAlpha:    0.18,
    bgDeep:      [4, 18, 42],
    bgShallow:   [8, 30, 58],
  },
  RELAXED: {
    growthRate:   0.005,
    spawnChance:  0.018,
    swayAmp:      1.0,
    particleRate: 0.9,
    particleHue:  165,
    fishAlpha:    0.75,
    bgDeep:      [3, 14, 30],
    bgShallow:   [6, 24, 48],
  },
  DROWSY: {
    growthRate:   0.001,
    spawnChance:  0.004,
    swayAmp:      0.18,
    particleRate: 0.55,
    particleHue:  225,
    fishAlpha:    0.3,
    bgDeep:      [2, 7, 22],
    bgShallow:   [4, 12, 38],
  },
  STRESSED: {
    growthRate:   0.002,
    spawnChance:  0.008,
    swayAmp:      0.85,
    particleRate: 0.15,
    particleHue:  20,
    fishAlpha:    0.06,
    bgDeep:      [16, 5, 5],
    bgShallow:   [24, 8, 8],
  },
};

// ── Coral branches ─────────────────────────────────────
const MAX_DEPTH = 6;
const branches  = [];

function mkBranch(x1, y1, angle, len, depth, hue) {
  return {
    x1, y1,
    x2: x1 + Math.cos(angle) * len,
    y2: y1 + Math.sin(angle) * len,
    angle, len, depth, hue,
    bleach:   0,
    progress: 0,
    grown:    false,
    spawned:  false,
    thick:    Math.max(0.55, (MAX_DEPTH - depth + 1) * 0.72),
    phase:    Math.random() * Math.PI * 2,
    swaySpd:  0.28 + Math.random() * 0.38,
    ctrl1X:   0, ctrl1Y: 0,
  };
}

function buildCtrl(b) {
  const mid = 0.5;
  const cx  = b.x1 + (b.x2 - b.x1) * mid + Math.cos(b.angle + Math.PI / 2) * b.len * 0.08;
  const cy  = b.y1 + (b.y2 - b.y1) * mid;
  b.ctrl1X  = cx;
  b.ctrl1Y  = cy;
}

function initCoral() {
  const W = canvas.width, H = canvas.height;
  const N = 9;
  for (let i = 0; i < N; i++) {
    const x   = (W * 0.05) + (W * 0.9) * (i / (N - 1)) + (Math.random() - .5) * 28;
    const y   = H - 20 - Math.random() * 10;
    const hue = 8 + (i / N) * 55 + Math.random() * 14;   // 8–63: orange→yellow-pink
    const len = 36 + Math.random() * 22;
    const b   = mkBranch(x, y, -Math.PI / 2, len, 0, hue);
    buildCtrl(b);
    branches.push(b);
  }
}

function spawnChildren(b) {
  if (b.spawned || b.depth >= MAX_DEPTH) return;
  b.spawned = true;
  const spread  = 0.32 + Math.random() * 0.22;
  const jitter  = () => (Math.random() - .5) * 0.14;
  const factor  = 0.64 + Math.random() * 0.06;
  const hueShft = (Math.random() - .5) * 18;
  const configs = [
    { angle: b.angle - spread + jitter(), len: b.len * factor },
    { angle: b.angle + spread + jitter(), len: b.len * (factor - 0.04) },
  ];
  configs.forEach(c => {
    const child = mkBranch(b.x2, b.y2, c.angle, c.len, b.depth + 1, b.hue + hueShft);
    buildCtrl(child);
    branches.push(child);
  });
}

// ── Particles (bioluminescence) ────────────────────────
const MAX_PARTICLES = 220;
const particles     = [];

function mkParticle(cfg) {
  const W = canvas.width, H = canvas.height;
  particles.push({
    x:      30 + Math.random() * (W - 60),
    y:      H - 35 - Math.random() * 40,
    vx:     (Math.random() - .5) * 0.28,
    vy:    -0.25 - Math.random() * 0.45,
    r:      0.9 + Math.random() * 1.6,
    alpha:  0.45 + Math.random() * 0.45,
    hue:    cfg.particleHue + (Math.random() - .5) * 30,
    life:   1.0,
    decay:  0.0028 + Math.random() * 0.0022,
    wander: (Math.random() - .5) * 0.007,
  });
}

// ── Fish ───────────────────────────────────────────────
const fish = [];

function initFish() {
  const W = canvas.width, H = canvas.height;
  for (let i = 0; i < 10; i++) {
    fish.push({
      x:      Math.random() * W,
      y:      H * 0.15 + Math.random() * H * 0.52,
      spd:    0.35 + Math.random() * 0.55,
      dir:    Math.random() > .5 ? 1 : -1,
      bob:    Math.random() * Math.PI * 2,
      size:   4.5 + Math.random() * 5.5,
      hue:    12 + Math.random() * 38,
      alpha:  0,
      stripe: Math.random() > .5,
    });
  }
}

// ── Anemones ───────────────────────────────────────────
const anemones = [];

function initAnemones() {
  const W = canvas.width, H = canvas.height;
  for (let i = 0; i < 15; i++) {
    anemones.push({
      x:    45 + Math.random() * (W - 90),
      y:    H - 25 + Math.random() * 18,
      arms: 5 + Math.floor(Math.random() * 4),
      h:    16 + Math.random() * 13,
      hue:  270 + Math.random() * 65,
      ph:   Math.random() * Math.PI * 2,
      spd:  0.4 + Math.random() * 0.3,
    });
  }
}

// ── Background draws ───────────────────────────────────
function drawBackground(cfg) {
  const W = canvas.width, H = canvas.height;
  const [dr, dg, db] = cfg.bgDeep;
  const [sr, sg, sb] = cfg.bgShallow;

  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0,   `rgb(${dr},${dg},${db})`);
  grad.addColorStop(0.55,`rgb(${Math.round((dr+sr)/2)},${Math.round((dg+sg)/2)},${Math.round((db+sb)/2)})`);
  grad.addColorStop(1,   `rgb(${sr},${sg},${sb})`);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, W, H);

  // Caustic shimmer — FOCUS / RELAXED only
  if (currentState === 'FOCUS' || currentState === 'RELAXED') {
    drawCaustics(W, H);
  }

  // Moonlit column — DROWSY
  if (currentState === 'DROWSY') {
    const moon = ctx.createRadialGradient(W * 0.5, -20, 0, W * 0.5, -20, H * 0.95);
    moon.addColorStop(0,   'rgba(110,85,230,.11)');
    moon.addColorStop(0.5, 'rgba(80,60,180,.05)');
    moon.addColorStop(1,   'transparent');
    ctx.fillStyle = moon;
    ctx.fillRect(0, 0, W, H);
  }

  // Thermal shimmer — STRESSED
  if (currentState === 'STRESSED') {
    drawThermalLines(W, H);
  }

  drawSand(W, H);
}

function drawCaustics(W, H) {
  ctx.save();
  for (let i = 0; i < 7; i++) {
    const t  = globalTime * 0.016 + i * 1.9;
    const cx = (Math.sin(t * 0.7 + i) * 0.5 + 0.5) * W;
    const cy = (Math.sin(t * 0.5 + i * 1.3) * 0.3 + 0.1) * H;
    const r  = 28 + Math.sin(t * 1.2) * 10;
    const g  = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    g.addColorStop(0, 'rgba(80,220,190,.032)');
    g.addColorStop(1, 'transparent');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();
}

function drawThermalLines(W, H) {
  ctx.save();
  ctx.globalAlpha = 0.06;
  ctx.strokeStyle = `rgba(255,120,60,1)`;
  ctx.lineWidth = 0.6;
  for (let i = 0; i < 5; i++) {
    const yBase = H * (0.2 + i * 0.14) + Math.sin(globalTime * 0.03 + i * 2) * 12;
    ctx.beginPath();
    ctx.moveTo(0, yBase);
    for (let x = 0; x <= W; x += 6) {
      ctx.lineTo(x, yBase + Math.sin(x * 0.025 + globalTime * 0.04 + i) * (8 + i * 3));
    }
    ctx.stroke();
  }
  ctx.restore();
}

function drawSand(W, H) {
  const g = ctx.createLinearGradient(0, H - 38, 0, H);
  g.addColorStop(0, 'transparent');
  g.addColorStop(0.25, 'rgba(165,128,72,.17)');
  g.addColorStop(1,    'rgba(145,110,55,.38)');
  ctx.fillStyle = g;
  ctx.fillRect(0, H - 38, W, 38);

  ctx.save();
  ctx.globalAlpha = 0.1;
  ctx.strokeStyle = 'rgba(200,162,85,1)';
  ctx.lineWidth = 0.5;
  for (let i = 0; i < 7; i++) {
    ctx.beginPath();
    ctx.moveTo(0, H - 6 - i * 5);
    for (let x = 0; x <= W; x += 5) {
      ctx.lineTo(x, H - 6 - i * 5 + Math.sin(x * 0.028 + i * 1.4) * 1.8);
    }
    ctx.stroke();
  }
  ctx.restore();
}

// ── Render anemones ────────────────────────────────────
function drawAnemones(cfg) {
  const sway = cfg.swayAmp;
  anemones.forEach(a => {
    const sw = Math.sin(globalTime * 0.023 * a.spd + a.ph) * sway;
    const sat = currentState === 'STRESSED'
      ? Math.max(10, 55 - bleachLevel * 45)
      : (currentState === 'DROWSY' ? 28 : 58);

    for (let t = 0; t < a.arms; t++) {
      const baseAngle = (t / a.arms) * Math.PI * 0.72 - Math.PI * 0.36;
      const angle     = baseAngle + sw * 0.12;
      const tipX = a.x + Math.sin(angle + sw * 0.22) * a.h;
      const tipY = a.y - Math.cos(angle) * a.h;
      const hue  = a.hue + t * 9;
      const lit  = currentState === 'STRESSED' ? 55 + bleachLevel * 30 : 54;

      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.quadraticCurveTo(
        a.x + Math.sin(angle) * a.h * 0.48 + sw * 2.8,
        a.y - a.h * 0.52,
        tipX, tipY
      );
      ctx.strokeStyle = `hsla(${hue},${sat}%,${lit}%,0.52)`;
      ctx.lineWidth = 1.15;
      ctx.stroke();

      ctx.beginPath();
      ctx.arc(tipX, tipY, 1.9, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${hue},${sat + 12}%,${lit + 14}%,0.6)`;
      ctx.fill();
    }
  });
}

// ── Render coral ───────────────────────────────────────
function drawBranches(cfg) {
  const sway = cfg.swayAmp;

  branches.forEach(b => {
    if (b.progress <= 0) return;
    const p  = Math.min(b.progress, 1);
    const sw = Math.sin(globalTime * 0.022 * b.swaySpd + b.phase) * sway;
    const swayX = sw * (b.depth * 1.15);

    // Drawn tip (with sway baked in)
    const tx = b.x1 + (b.x2 - b.x1) * p + swayX;
    const ty = b.y1 + (b.y2 - b.y1) * p;
    const cx = b.ctrl1X + swayX * 0.5;
    const cy = b.ctrl1Y;

    // Bleach interpolation
    const localBleach = Math.min(1, b.bleach);
    const satPct = Math.max(0, 72 - localBleach * 72);
    const litPct = 48 + localBleach * 40;
    const alpha  = 0.48 + (1 - localBleach) * 0.45;

    const drowsyMod = currentState === 'DROWSY' ? 0.38 : 1.0;

    ctx.beginPath();
    ctx.moveTo(b.x1, b.y1);
    ctx.quadraticCurveTo(cx, cy, tx, ty);
    ctx.strokeStyle = `hsla(${b.hue},${satPct * drowsyMod}%,${litPct}%,${alpha})`;
    ctx.lineWidth   = Math.max(0.35, b.thick * (1 - b.depth * 0.055));
    ctx.lineCap     = 'round';
    ctx.stroke();

    // Tip glow (only on grown tips in non-stressed states)
    if (b.grown && b.depth >= 3 && currentState !== 'STRESSED') {
      const gHue = currentState === 'DROWSY' ? 210 : b.hue + 15;
      ctx.beginPath();
      ctx.arc(tx, ty, 1.4, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${gHue},85%,80%,${0.22 * (1 - localBleach)})`;
      ctx.fill();
    }
  });
}

// ── Render particles ───────────────────────────────────
function drawParticles() {
  particles.forEach(p => {
    if (p.life <= 0) return;
    const a = p.alpha * p.life;

    // Core dot
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${p.hue},82%,75%,${a})`;
    ctx.fill();

    // Soft glow halo
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.r * 3.2, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${p.hue},82%,75%,${a * 0.1})`;
    ctx.fill();
  });
}

// ── Render fish ────────────────────────────────────────
function drawFish(cfg) {
  fish.forEach(f => {
    const target = cfg.fishAlpha;
    f.alpha += (target - f.alpha) * 0.008;
    if (f.alpha < 0.015) return;

    f.x   += f.spd * f.dir;
    f.bob += 0.038;
    const by = f.y + Math.sin(f.bob) * 3.2;
    const W  = canvas.width;
    if (f.x > W + 40) f.x = -40;
    if (f.x < -40)    f.x = W + 40;

    ctx.save();
    ctx.translate(f.x, by);
    ctx.scale(f.dir, 1);
    ctx.globalAlpha = f.alpha * 0.72;

    // Body
    ctx.beginPath();
    ctx.ellipse(0, 0, f.size, f.size * 0.44, 0, 0, Math.PI * 2);
    ctx.fillStyle = `hsla(${f.hue},68%,62%,1)`;
    ctx.fill();

    // Stripe
    if (f.stripe) {
      ctx.beginPath();
      ctx.ellipse(f.size * 0.1, 0, f.size * 0.22, f.size * 0.4, 0, 0, Math.PI * 2);
      ctx.fillStyle = `hsla(${f.hue + 160},55%,88%,.55)`;
      ctx.fill();
    }

    // Tail
    ctx.beginPath();
    ctx.moveTo(-f.size * 0.9, 0);
    ctx.lineTo(-f.size * 1.75, -f.size * 0.42);
    ctx.lineTo(-f.size * 1.75,  f.size * 0.42);
    ctx.closePath();
    ctx.fillStyle = `hsla(${f.hue},62%,54%,1)`;
    ctx.fill();

    // Eye
    ctx.beginPath();
    ctx.arc(f.size * 0.6, -f.size * 0.08, f.size * 0.1, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(10,10,20,.85)';
    ctx.fill();

    ctx.restore();
  });
}

// ── Depth vignette ─────────────────────────────────────
function drawVignette() {
  const W = canvas.width, H = canvas.height;
  const v = ctx.createRadialGradient(W/2, H/2, H * 0.25, W/2, H/2, H * 0.82);
  v.addColorStop(0, 'transparent');
  v.addColorStop(1, 'rgba(1,5,14,.55)');
  ctx.fillStyle = v;
  ctx.fillRect(0, 0, W, H);
}

// ── Update logic ───────────────────────────────────────
function update() {
  const cfg = STATE_CFG[currentState];
  globalTime++;

  // Bleach
  if (currentState === 'STRESSED') {
    bleachLevel = Math.min(1, bleachLevel + 0.00065);
    branches.forEach(b => { b.bleach = Math.min(1, b.bleach + 0.0012 * (0.6 + Math.random() * 0.8)); });
  } else {
    const wasHigh = bleachLevel > 0.05;
    bleachLevel = Math.max(0, bleachLevel - 0.00095);
    branches.forEach(b => { b.bleach = Math.max(0, b.bleach - 0.0018); });
    if (wasHigh && bleachLevel <= 0.04) triggerHealFlash();
  }

  // Grow branches
  branches.forEach(b => {
    if (!b.grown) {
      b.progress = Math.min(1, b.progress + cfg.growthRate);
      if (b.progress >= 1) b.grown = true;
    }
  });

  // Spawn new children from grown tips
  if (Math.random() < cfg.spawnChance) {
    const tips = branches.filter(b => b.grown && !b.spawned && b.depth < MAX_DEPTH);
    if (tips.length) spawnChildren(tips[Math.floor(Math.random() * tips.length)]);
  }

  // Particles
  if (particles.length < MAX_PARTICLES && Math.random() < cfg.particleRate * 0.042) {
    mkParticle(cfg);
  }
  particles.forEach(p => {
    p.x    += p.vx + p.wander;
    p.y    += p.vy;
    p.life -= p.decay;
  });
  for (let i = particles.length - 1; i >= 0; i--) {
    if (particles[i].life <= 0) particles.splice(i, 1);
  }

  // Heal flash timer
  if (healFlashTimer > 0) healFlashTimer--;

  // Update HUD
  updateHUD();
}

function triggerHealFlash() {
  const el = document.getElementById('healFlash');
  if (el) {
    el.style.opacity = '1';
    setTimeout(() => { el.style.opacity = '0'; }, 600);
  }
}

function updateHUD() {
  const grownN  = branches.filter(b => b.grown).length;
  const pct     = branches.length ? Math.round(grownN / branches.length * 100) : 0;
  
  const mGrowth = document.getElementById('mGrowth');
  if(mGrowth) mGrowth.textContent = pct + '%';

  const mBranches = document.getElementById('mBranches');
  if(mBranches) mBranches.textContent  = branches.length;

  const mParticles = document.getElementById('mParticles');
  if(mParticles) mParticles.textContent = particles.length;

  const bleachBar = document.getElementById('bleachBar');
  if(bleachBar) bleachBar.style.transform = `scaleX(${bleachLevel.toFixed(3)})`;
}

// ── Render ─────────────────────────────────────────────
function render() {
  const cfg = STATE_CFG[currentState];
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  drawBackground(cfg);
  drawAnemones(cfg);
  drawBranches(cfg);
  drawParticles();
  drawFish(cfg);
  drawVignette();

  // DROWSY dark overlay
  if (currentState === 'DROWSY') {
    ctx.fillStyle = 'rgba(6,3,24,.3)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
  }
}

// ── Main loop ──────────────────────────────────────────
function loop() {
  update();
  render();
  requestAnimationFrame(loop);
}

// ── setState ───────────────────────────────────────────
function setState(s) {
  if (!STATE_CFG[s]) return;
  prevState    = currentState;
  currentState = s;
}

// ── Resize (debounced) ─────────────────────────────────
let resizeTimer;
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(() => {
    resize();
    branches.length = 0;
    particles.length = 0;
    anemones.length = 0;
    fish.length = 0;
    bleachLevel = 0;
    initCoral();
    initFish();
    initAnemones();
  }, 320);
});

// ══════════════════════════════════════════════════════
//  PUBLIC API
// ══════════════════════════════════════════════════════
window.Cogniflow = {
  setState,
  getState:       () => currentState,
  getBleachLevel: () => parseFloat(bleachLevel.toFixed(3)),
  getBranchCount: () => branches.length,
  getGrownPct:    () => branches.length ? Math.round(branches.filter(b=>b.grown).length / branches.length * 100) : 0,
};

// ── Init ───────────────────────────────────────────────
initCoral();
initFish();
initAnemones();
loop();
