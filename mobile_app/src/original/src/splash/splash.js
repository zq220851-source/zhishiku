/**
 * 开屏动画（现代极简几何）
 *
 *   一个点 → 拉长、一分为二成为两只眼睛（眨一下）→ 镜圈与眉线画出眉线框眼镜
 *   → 白色的头从眼镜后展开、两只耳朵弹出、鼻子与 ω 嘴 → 藏青色圆盘在身后铺开，组成徽章
 *   → 两个镜片变成两扇“窗”，透过镜片看到真实的 3D 眼睛眨了一下
 *   → 两扇窗放大、合成一个圆，整只猫变成立体的 → 镜头后拉露出全身，圆盘压扁成脚下的影子
 *   → 挥手 → 回到停靠位，界面出现
 *
 * 平面图形的每一个形状都由 3D 模型投影得到（model.anchors.landmarks），
 * 所以“窗”打开时，窗里的立体五官与窗外的平面五官位置完全一致。
 * 平面部分与镜头、遮罩都只由时间 t 决定（可暂停、可拖动）；3D 角色本身是活的。
 */
import { reducedMotion } from '../app/prefs.js';

const SEEN_KEY = 'medrep.splash.v2';
const SVGNS = 'http://www.w3.org/2000/svg';
const NAVY = '#1e3457';

/** 时间轴（秒，1× 速度） */
const T = {
  dot0: 0.1, dot1: 0.42,
  split0: 0.52, split1: 0.92,
  blink0: 0.96, blink1: 1.14,
  ring0: 1.04, ringDur: 0.4,
  brow0: 1.3, brow1: 1.56,
  hood0: 1.5, hood1: 1.98,
  ear0: 1.66, earDur: 0.42,
  disc0: 1.6, disc1: 2.12,
  nose0: 1.86, mouth0: 1.92, mouth1: 2.14,
  word0: 2.1,
  win0: 2.62, win1: 2.86,
  blink3d: 2.92,
  merge0: 3.1, merge1: 3.62,
  pull0: 3.72, pull1: 4.5,
  wave: 4.36,
  exit: 5.2, end: 5.9,
};
export const SPLASH_STEPS = [
  [0, '一个点'],
  [T.split0, '一分为二：两只眼睛'],
  [T.ring0, '镜圈与眉线：眉线框眼镜'],
  [T.hood0, '头、耳朵、鼻子、嘴，圆盘铺开成徽章'],
  [T.win0, '镜片变成窗：透过镜片看到立体的眼睛'],
  [T.merge0, '两扇窗合成一个圆：整只猫变成立体'],
  [T.pull0, '镜头后拉：全身，圆盘压扁成影子'],
  [T.wave, '挥手'],
  [T.exit, '回到停靠位，界面出现'],
];

// 开屏期间画布放大 K 倍（中心不变），镜头后拉时身体不会被画布边缘截断。
// 取景同样乘以 K，所以角色在屏幕上的大小不变；退场时换回原尺寸与默认取景，像素完全一致。
const K = 1.7;
const CLOSE = { fh: 1.86 * K, fw: 1.86 * K, ty: 1.5 };
const FULL = { fh: 2.75 * K, fw: 2.25 * K, ty: 1.17 };

const clamp = (x, a = 0, b = 1) => Math.min(Math.max(x, a), b);
const lerp = (a, b, t) => a + (b - a) * t;
const seg = (t, a, b) => clamp((t - a) / (b - a));
const inOut = (p) => (p < 0.5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2);
const expoOut = (p) => (p >= 1 ? 1 : 1 - Math.pow(2, -10 * p));
const expoInOut = (p) => (p <= 0 ? 0 : p >= 1 ? 1 : p < 0.5 ? Math.pow(2, 20 * p - 10) / 2 : (2 - Math.pow(2, -20 * p + 10)) / 2);
const backOut = (p, c1 = 1.5) => (p >= 1 ? 1 : 1 + (c1 + 1) * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2));

function el(name, attrs = {}, parent) {
  const e = document.createElementNS(SVGNS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  parent?.appendChild(e);
  return e;
}
/** 经过各点的平滑闭合曲线（用于软尖） */
const smoothD = (p) => {
  const m = (a, b) => ({ x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 });
  let d = `M${p[0].x} ${p[0].y}`;
  for (let i = 1; i < p.length - 1; i++) {
    const e = m(p[i], p[i + 1]);
    d += `Q${p[i].x} ${p[i].y} ${i === p.length - 2 ? p[i + 1].x : e.x} ${i === p.length - 2 ? p[i + 1].y : e.y}`;
  }
  return d + 'Z';
};
const polyD = (pts, close = true) =>
  pts.map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join('') + (close ? 'Z' : '');
/** 以 (ox, oy) 为原点缩放 */
const scaleAt = (ox, oy, sx, sy = sx) => `translate(${ox} ${oy}) scale(${Math.max(sx, 0.0001)} ${Math.max(sy, 0.0001)}) translate(${-ox} ${-oy})`;

/** 是否需要播放开屏：首次访问播放；?splash 强制播放；?splash=dev 打开调试面板；减少动画时不播放 */
export function splashMode() {
  const q = new URLSearchParams(location.search);
  if (q.has('splash')) return q.get('splash') === 'dev' ? 'dev' : 'force';
  if (reducedMotion()) return null;
  try {
    return localStorage.getItem(SEEN_KEY) ? null : 'first';
  } catch {
    return null;
  }
}

export function runSplash(app, mode) {
  const pet = app.pet;
  const { stage, brain, host } = pet;
  const dev = mode === 'dev';
  const q = new URLSearchParams(location.search);

  // ---------- DOM ----------
  const root = document.createElement('div');
  root.className = 'splash';
  root.setAttribute('aria-hidden', 'true');
  const svg = el('svg', { class: 'splash-svg' }, root);
  const disc = el('ellipse', { fill: NAVY }, svg);
  const flat = el('g', {}, svg);
  const earsG = el('g', {}, flat);
  const tuftEl = el('path', { fill: '#ffffff', stroke: '#ffffff', 'stroke-linejoin': 'round' }, flat);
  const hood = el('ellipse', { fill: '#ffffff' }, flat);
  const face = el('path', { fill: '#f3ece2' }, flat);
  const eyesG = el('g', {}, flat);
  const pill = el('g', { fill: '#16264d' }, flat);
  const lensG = el('g', { fill: 'none', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, flat);
  const nose = el('path', { fill: '#e58e98' }, flat);
  const mouth = el('path', { fill: 'none', stroke: '#3b3640', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }, flat);
  const word = document.createElement('div');
  word.className = 'splash-word';
  word.innerHTML = 'MedRep <b>Coach</b>';
  root.appendChild(word);
  const skip = document.createElement('div');
  skip.className = 'splash-skip';
  skip.textContent = '点击任意处跳过';
  if (!dev) root.appendChild(skip);
  document.body.appendChild(root);
  document.body.classList.add('splashing');

  // ---------- 镜头 ----------
  const FOV_K = (2 * Math.atan(K * Math.tan((22 * Math.PI) / 360)) * 180) / Math.PI;
  const setFraming = (f) => {
    stage.camera.fov = FOV_K;
    stage.opts.frameHeight = f.fh;
    stage.opts.frameWidth = f.fw;
    stage.target.y = f.ty;
    stage._frame();
  };
  const framingAt = (p) => ({ fh: lerp(CLOSE.fh, FULL.fh, p), fw: lerp(CLOSE.fw, FULL.fw, p), ty: lerp(CLOSE.ty, FULL.ty, p) });

  // ---------- 几何（由 3D 投影） ----------
  let G = null;
  let nodes = null;
  function measure() {
    pet.enterSplash(K);
    host.classList.add('splash-top');
    brain.lookLocked = true;
    brain.reducedMotion = true; // 冻结细节运动，保证投影出的形状与 3D 姿态一致
    brain.nextIdle = Infinity;
    brain.autoRest = false;
    if (brain.state !== 'awake') brain.setState('awake', { quick: true });
    brain.actions = [];
    for (let i = 0; i < 90; i++) brain.update(1 / 60);
    stage.parallax.x = stage.parallax.y = stage.parallax.tx = stage.parallax.ty = 0;
    // 全身取景下的地面位置（影子的终点）
    setFraming(FULL);
    stage.render(0);
    const full = project(stage);
    // 特写取景下的五官
    setFraming(CLOSE);
    stage.render(0);
    G = buildGeometry(stage, full);
    svg.setAttribute('viewBox', `0 0 ${innerWidth} ${innerHeight}`);
    word.style.top = `${G.C.y + G.Rd + Math.max(22, G.R * 0.22)}px`;
    buildNodes();
  }

  function buildNodes() {
    earsG.replaceChildren();
    eyesG.replaceChildren();
    pill.replaceChildren();
    lensG.replaceChildren();
    const ears = G.ears.map((e) => {
      const g = el('g', {}, earsG);
      el('path', { d: polyD(e.outer), fill: '#fff', stroke: '#fff', 'stroke-width': G.R * 0.12, 'stroke-linejoin': 'round' }, g);
      el('path', { d: polyD(e.inner), fill: '#f2c3c6', stroke: '#f2c3c6', 'stroke-width': G.R * 0.05, 'stroke-linejoin': 'round' }, g);
      return { g, e };
    });
    hood.setAttribute('cx', G.C.x);
    hood.setAttribute('cy', G.C.y);
    hood.setAttribute('rx', G.rx);
    hood.setAttribute('ry', G.ry);
    face.setAttribute('d', polyD(G.face));
    tuftEl.setAttribute('d', smoothD(G.tuft));
    tuftEl.setAttribute('stroke-width', G.R * 0.06);
    const eyes = G.eyes.map((e) => {
      const g = el('g', {}, eyesG);
      el('ellipse', { cx: e.x, cy: e.y, rx: e.rx, ry: e.ry, fill: '#16264d' }, g);
      const iris = el('ellipse', { cx: e.x, cy: e.y + e.ry * 0.3, rx: e.rx * 0.64, ry: e.ry * 0.52, fill: '#2a4f9e' }, g);
      const hl = el('circle', { cx: e.x - e.rx * 0.3, cy: e.y - e.ry * 0.38, r: e.rx * 0.3, fill: '#fff' }, g);
      return { g, e, iris, hl };
    });
    const pa = el('ellipse', {}, pill);
    const pb = el('ellipse', {}, pill);
    const pr = el('rect', {}, pill);
    const rings = G.lenses.map((l) =>
      el('path', { d: polyD(l.pts), pathLength: 1, stroke: '#2b2f38', 'stroke-width': G.thin, 'stroke-dasharray': '1 1' }, lensG),
    );
    const brows = G.lenses.map((l) =>
      el('path', { d: polyD(l.upper, false), pathLength: 1, stroke: '#20232b', 'stroke-width': G.thick, 'stroke-dasharray': '1 1' }, lensG),
    );
    const bridge = el('path', { d: G.bridgeD, pathLength: 1, stroke: '#20232b', 'stroke-width': G.thick * 0.8, 'stroke-dasharray': '1 1' }, lensG);
    nose.setAttribute('d', G.noseD);
    mouth.setAttribute('d', G.mouthD);
    mouth.setAttribute('pathLength', 1);
    mouth.setAttribute('stroke-dasharray', '1 1');
    mouth.setAttribute('stroke-width', G.thin * 1.05);
    nodes = { ears, eyes, pa, pb, pr, rings, brows, bridge };
  }

  // ---------- 渲染：完全由 t 决定 ----------
  function render(t) {
    const g = G;
    const n = nodes;
    const [eL, eR] = g.eyes;
    const mid = { x: (eL.x + eR.x) / 2, y: (eL.y + eR.y) / 2 };

    // 1. 点 → 拉长 → 一分为二
    const dp = backOut(seg(t, T.dot0, T.dot1), 1.7);
    const sp = inOut(seg(t, T.split0, T.split1));
    const split = t >= T.split0;
    const r0 = eL.ry * 0.78;
    const ax = lerp(mid.x, eL.x, sp);
    const bx = lerp(mid.x, eR.x, sp);
    const erx = lerp(r0, eL.rx, sp);
    const ery = lerp(r0, eL.ry, sp);
    // 颈部先变粗（拉长成胶囊），再变细断开
    const neck = split ? ery * 2 * (1 - clamp((sp - 0.35) / 0.4)) * (1 - 0.25 * Math.sin(Math.PI * clamp(sp / 0.35))) : 0;
    const showPill = t < T.split1 + 0.02;
    pill.style.display = showPill ? '' : 'none';
    eyesG.style.display = showPill ? 'none' : '';
    if (showPill) {
      for (const [e, x] of [[n.pa, ax], [n.pb, bx]]) {
        e.setAttribute('cx', x);
        e.setAttribute('cy', mid.y);
        e.setAttribute('rx', (split ? erx : r0) * dp);
        e.setAttribute('ry', (split ? ery : r0) * dp);
      }
      n.pr.setAttribute('x', ax);
      n.pr.setAttribute('y', mid.y - neck / 2);
      n.pr.setAttribute('width', Math.max(0, bx - ax));
      n.pr.setAttribute('height', Math.max(0, neck));
    }
    // 眨眼 + 虹膜与高光出现
    const bk = seg(t, T.blink0, T.blink1);
    const bs = 1 - 0.88 * Math.sin(Math.PI * bk);
    const det = expoOut(seg(t, T.split1, T.split1 + 0.3));
    for (const { g: eg, e, iris, hl } of n.eyes) {
      eg.setAttribute('transform', scaleAt(e.x, e.y, 1, bs));
      iris.style.opacity = det;
      hl.style.opacity = det;
    }

    // 2. 镜圈（左右错开）→ 眉线 → 鼻梁
    n.rings.forEach((r, i) => {
      const p = inOut(seg(t, T.ring0 + i * 0.07, T.ring0 + i * 0.07 + T.ringDur));
      r.setAttribute('stroke-dashoffset', 1 - p);
      r.style.opacity = p > 0 ? 1 : 0;
    });
    n.brows.forEach((b, i) => {
      const p = expoOut(seg(t, T.brow0 + i * 0.05, T.brow1 + i * 0.05));
      b.setAttribute('stroke-dashoffset', 1 - p);
      b.style.opacity = p > 0 ? 1 : 0;
    });
    const brp = expoOut(seg(t, T.brow0 + 0.03, T.brow1));
    n.bridge.setAttribute('stroke-dashoffset', 1 - brp);
    n.bridge.style.opacity = brp > 0 ? 1 : 0;

    // 3. 头从眼镜后展开 → 脸盘 → 耳朵 → 鼻子、嘴
    const hp = expoOut(seg(t, T.hood0, T.hood1));
    hood.setAttribute('transform', scaleAt(mid.x, mid.y, hp));
    const fp = expoOut(seg(t, T.hood0 + 0.06, T.hood1 + 0.06));
    face.setAttribute('transform', scaleAt(mid.x, mid.y, fp));
    n.ears.forEach(({ g: eg, e }, i) => {
      const p = backOut(seg(t, T.ear0 + i * 0.07, T.ear0 + i * 0.07 + T.earDur), 2.1);
      eg.setAttribute('transform', scaleAt(e.baseMid.x, e.baseMid.y, p));
    });
    const tp = backOut(seg(t, T.ear0 + 0.04, T.ear0 + 0.04 + T.earDur), 2.1);
    const tb = { x: (g.tuft[0].x + g.tuft[4].x) / 2, y: (g.tuft[0].y + g.tuft[4].y) / 2 };
    tuftEl.setAttribute('transform', scaleAt(tb.x, tb.y, tp));
    const np = backOut(seg(t, T.nose0, T.nose0 + 0.22), 2.2);
    nose.setAttribute('transform', scaleAt(g.noseC.x, g.noseC.y, np));
    const mp = inOut(seg(t, T.mouth0, T.mouth1));
    mouth.setAttribute('stroke-dashoffset', 1 - mp);
    mouth.style.opacity = mp > 0 ? 1 : 0;

    // 4. 藏青圆盘铺开；后拉时压扁成影子
    const dk = expoOut(seg(t, T.disc0, T.disc1));
    const pull = inOut(seg(t, T.pull0, T.pull1));
    disc.setAttribute('cx', lerp(g.C.x, g.shadow.x, pull));
    disc.setAttribute('cy', lerp(g.C.y, g.shadow.y, pull));
    disc.setAttribute('rx', lerp(g.Rd * dk, g.shadow.rx, pull));
    disc.setAttribute('ry', lerp(g.Rd * dk, g.shadow.rx * 0.2, pull));
    disc.style.opacity = String((1 - pull * pull) * (dk > 0 ? 1 : 0));

    // 5. 窗：先在两个镜片里打开，再放大合成一个圆，后拉时覆盖全部
    // 退场后角色交还给停靠位，这里不再控制画布、遮罩和镜头
    const handedOff = fired.has('exit');
    const wp = expoOut(seg(t, T.win0, T.win1));
    const mg = expoInOut(seg(t, T.merge0, T.merge1));
    const cover = inOut(seg(t, T.pull0, T.pull0 + 0.4));
    if (handedOff) {
      /* 交给 pet.js */
    } else if (t < T.win0) {
      host.style.opacity = '0';
      host.style.clipPath = '';
    } else {
      host.style.opacity = '1';
      if (cover >= 1) host.style.clipPath = 'none';
      else {
        const hr = host.getBoundingClientRect();
        const circles = g.lenses.map((l) => {
          const cx = lerp(l.c.x, g.C.x, mg) - hr.left;
          const cy = lerp(l.c.y, g.C.y, mg) - hr.top;
          const r = lerp(lerp(0, l.r, wp), g.Rd, mg) + cover * Math.hypot(hr.width, hr.height);
          return `M${(cx - r).toFixed(1)} ${cy.toFixed(1)}a${r.toFixed(1)} ${r.toFixed(1)} 0 1 0 ${(2 * r).toFixed(1)} 0a${r.toFixed(1)} ${r.toFixed(1)} 0 1 0 ${(-2 * r).toFixed(1)} 0Z`;
        });
        host.style.clipPath = `path('${circles.join('')}')`;
      }
    }
    // 窗外的平面图形在合并过程中淡出（窗内已经被 3D 覆盖）
    flat.style.opacity = String(1 - inOut(seg(t, T.merge0 + 0.1, T.merge1 - 0.05)));

    // 6. 镜头后拉
    if (t >= T.win0 && !handedOff) {
      setFraming(framingAt(pull));
      if (stage.timeScale === 0) stage.render(0);
    }

    // 字标：后拉时先隐去，落到脚下后再出现
    const wordVis = Math.max(1 - seg(t, T.pull0, T.pull0 + 0.2), seg(t, T.pull1 - 0.15, T.pull1 + 0.15));
    word.style.opacity = String(seg(t, T.word0, T.word0 + 0.4) * wordVis * (1 - seg(t, T.exit - 0.3, T.exit)));
    word.style.transform = `translateY(${lerp(0, g.wordShift, pull)}px)`;
    skip.style.opacity = String(seg(t, 0.6, 1.1) * (1 - seg(t, T.exit - 0.3, T.exit)) * 0.85);
    root.style.backgroundColor = `rgba(244,246,249,${1 - inOut(seg(t, T.exit + 0.05, T.exit + 0.55))})`;
  }

  // ---------- 3D 与应用事件（播放越过时触发一次） ----------
  const fired = new Set();
  function events(t) {
    const once = (k, at, fn) => {
      if (t >= at && !fired.has(k)) {
        fired.add(k);
        fn();
      }
    };
    once('blink', T.blink3d, () => (brain.blink.next = brain.time));
    once('alive', T.pull0, () => {
      brain.reducedMotion = reducedMotion();
      brain.play('lookAtViewer', { essential: true });
    });
    once('wave', T.wave, () => brain.play('wave', { essential: true }));
    once('exit', T.exit, () => leave(false));
    once('end', T.end, () => finish());
  }

  function leave(instant) {
    // 换回原尺寸画布 + 默认取景（与放大画布 + FULL 取景的像素完全一致），再飞回停靠位
    delete stage.opts.frameHeight;
    delete stage.opts.frameWidth;
    stage.camera.fov = 22;
    stage.target.y = FULL.ty;
    pet.enterSplash(1);
    stage.render(0);
    host.style.clipPath = '';
    host.style.opacity = '1';
    brain.lookLocked = false;
    brain.reducedMotion = reducedMotion();
    brain.nextIdle = brain.time + 4;
    brain.autoRest = true;
    pet.exitSplash({ instant });
    if (!instant) setTimeout(() => brain.play('smallNod', { essential: true }), 450);
    const items = [...document.querySelectorAll('.topbar, .tabbar, .view .page > *')];
    items.forEach((n, i) => {
      n.style.animationDelay = `${(instant ? 0 : 120) + i * 55}ms`;
      n.classList.add('app-enter');
    });
    setTimeout(() => items.forEach((n) => {
      n.classList.remove('app-enter');
      n.style.animationDelay = '';
    }), 1600);
  }

  let done = false;
  function finish() {
    if (done) return;
    done = true;
    try {
      localStorage.setItem(SEEN_KEY, '1');
    } catch {
      /* ignore */
    }
    host.classList.remove('splash-top');
    host.style.opacity = '';
    host.style.clipPath = '';
    stage.timeScale = 1;
    document.body.classList.remove('splashing');
    removeEventListener('pointerdown', onSkip, true);
    removeEventListener('keydown', onSkip, true);
    removeEventListener('resize', onResize);
    if (dev) root.style.display = 'none';
    else root.remove();
    setTimeout(() => pet.greet(), 700);
  }

  // ---------- 播放 ----------
  let t = q.has('at') ? +q.get('at') : 0;
  let speed = q.has('at') ? 0 : 1;
  let last = performance.now();
  function frame(now) {
    if (done && !dev) return;
    // rAF 的时间戳可能早于初始化时记录的 performance.now()，所以下限取 0，避免时间倒退
    const dt = clamp((now - last) / 1000, 0, 0.12);
    last = now;
    if (!done) {
      t += dt * speed;
      stage.timeScale = speed;
      if (t < T.exit) render(t);
      else render(Math.min(t, T.end));
      events(t);
      devUI?.update(t);
    }
    requestAnimationFrame(frame);
  }

  function onSkip(e) {
    if (dev || done) return;
    if (e.type === 'keydown' && ['Shift', 'Control', 'Alt', 'Meta'].includes(e.key)) return;
    if (t < T.exit) {
      fired.add('exit');
      leave(t < T.win0);
    }
    t = Math.max(t, T.exit);
    root.style.transition = 'opacity 0.35s ease';
    root.style.opacity = '0';
    setTimeout(finish, 360);
  }
  addEventListener('pointerdown', onSkip, true);
  addEventListener('keydown', onSkip, true);

  let resizeTimer = 0;
  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (done || t >= T.win0) return;
      measure();
      render(t);
    }, 120);
  }
  addEventListener('resize', onResize);

  measure();
  render(t);
  if (q.has('at')) events(t);
  requestAnimationFrame(frame);

  // ---------- 调试面板（?splash=dev） ----------
  const devUI = dev ? createDevPanel() : null;
  function createDevPanel() {
    const p = document.createElement('div');
    p.className = 'splash-dev';
    p.innerHTML = `
      <button data-k="replay">重播</button>
      <button data-k="pause">暂停</button>
      <span class="sep"></span>
      <button data-s="0.25">0.25×</button><button data-s="0.5">0.5×</button><button data-s="1" aria-pressed="true">1×</button>
      <span class="sep"></span>
      <button data-k="prev">上一步</button><button data-k="next">下一步</button>
      <input type="range" min="0" max="${T.exit}" step="0.01" value="0" aria-label="时间轴" />
      <output></output>`;
    document.body.appendChild(p);
    const out = p.querySelector('output');
    const range = p.querySelector('input');
    const pauseBtn = p.querySelector('[data-k="pause"]');
    let lastSpeed = 1;
    const setSpeed = (s) => {
      speed = s;
      if (s > 0) lastSpeed = s;
      pauseBtn.textContent = s === 0 ? '继续' : '暂停';
      p.querySelectorAll('[data-s]').forEach((b) => b.setAttribute('aria-pressed', String(+b.dataset.s === lastSpeed)));
    };
    const replay = (at = 0, s = lastSpeed) => {
      if (done) {
        done = false;
        root.style.display = '';
        root.style.opacity = '';
        root.style.transition = '';
        document.body.classList.add('splashing');
      }
      fired.clear();
      measure();
      t = at;
      events(at);
      setSpeed(s);
      last = performance.now();
    };
    const times = SPLASH_STEPS.map((x) => x[0]);
    const seekStep = (dir) => {
      const cur = times.reduce((acc, x, i) => (t + 0.001 >= x ? i : acc), 0);
      const target = times[clamp(cur + dir, 0, times.length - 1)];
      if (target < t) replay(target, 0);
      else {
        t = target;
        setSpeed(0);
      }
    };
    p.addEventListener('click', (e) => {
      const b = e.target.closest('button');
      if (!b) return;
      if (b.dataset.s) {
        lastSpeed = +b.dataset.s;
        setSpeed(speed === 0 ? 0 : lastSpeed);
      } else if (b.dataset.k === 'replay') replay(0, lastSpeed);
      else if (b.dataset.k === 'pause') setSpeed(speed === 0 ? lastSpeed : 0);
      else if (b.dataset.k === 'prev') seekStep(-1);
      else if (b.dataset.k === 'next') seekStep(1);
    });
    range.addEventListener('input', () => {
      const v = +range.value;
      if (v < t && t >= T.win0) replay(v, 0);
      else {
        t = v;
        setSpeed(0);
      }
    });
    if (speed === 0) setSpeed(0);
    return {
      update(tt) {
        const step = [...SPLASH_STEPS].reverse().find((x) => tt >= x[0]);
        out.textContent = `${tt.toFixed(2)}s · ${step ? step[1] : ''}`;
        if (document.activeElement !== range) range.value = String(Math.min(tt, T.exit));
      },
    };
  }
}

/** 当前镜头下，把世界坐标投影到页面像素 */
function project(stage) {
  const cam = stage.camera;
  cam.updateMatrixWorld();
  const rect = stage.canvas.getBoundingClientRect();
  const P = (v) => {
    const p = v.clone().project(cam);
    return { x: rect.left + ((p.x + 1) / 2) * rect.width, y: rect.top + ((1 - p.y) / 2) * rect.height };
  };
  const L = stage.model.anchors.landmarks();
  const g = P(L.ground);
  const side = L.ground.clone();
  side.x += 0.62;
  return { P, L, ground: g, shadowRx: Math.abs(P(side).x - g.x) };
}

/** 特写镜头下的平面图形几何 */
function buildGeometry(stage, full) {
  const { P, L } = project(stage);
  const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
  const C = P(L.head);
  const rx = dist(P(L.hoodX), C);
  const ry = dist(P(L.hoodY), C);
  const R = (rx + ry) / 2;

  const ears = L.ears.map((e) => {
    const tip = P(e.tip);
    const [b0, b1] = e.base.map(P);
    const baseMid = { x: (b0.x + b1.x) / 2, y: (b0.y + b1.y) / 2 };
    // 耳根略微压进头部轮廓，避免露出接缝；尖端用真实位置
    const inward = (b) => ({ x: lerp(b.x, C.x, 0.08), y: lerp(b.y, C.y, 0.08) });
    const outer = [inward(b0), tip, inward(b1)];
    const cen = { x: (outer[0].x + outer[1].x + outer[2].x) / 3, y: (outer[0].y + outer[1].y + outer[2].y) / 3 };
    const inner = outer.map((p) => ({ x: lerp(cen.x, p.x, 0.52), y: lerp(cen.y, p.y, 0.52) + R * 0.02 }));
    return { outer, inner, baseMid };
  });

  const lenses = [...L.lenses]
    .sort((a, b) => P(a.center).x - P(b.center).x)
    .map((l) => {
      const pts = l.pts.map(P);
      const c = { x: pts.reduce((s, p) => s + p.x, 0) / pts.length, y: pts.reduce((s, p) => s + p.y, 0) / pts.length };
      const r = pts.reduce((s, p) => s + dist(p, c), 0) / pts.length;
      const n = pts.length;
      const upper = [];
      for (let i = n / 2; i >= 0; i--) upper.push(pts[i]);
      return { pts, c, r, upper };
    });
  const [lL, lR] = lenses;
  const n = lL.pts.length;
  const a = lL.pts[Math.round(n * 0.1)];
  const b = lR.pts[Math.round(n * 0.4)];
  const bridgeD = `M${a.x} ${a.y}Q${(a.x + b.x) / 2} ${Math.min(a.y, b.y) - R * 0.05} ${b.x} ${b.y}`;

  const eyes = L.eyes
    .map((e) => {
      const c = P(e.c);
      return { x: c.x, y: c.y, rx: dist(P(e.x), c), ry: dist(P(e.y), c) };
    })
    .sort((p, q) => p.x - q.x);

  const noseC = P(L.nose);
  const nw = dist(P(L.noseW), noseC);
  const noseD = `M${noseC.x - nw} ${noseC.y - nw * 0.42}Q${noseC.x} ${noseC.y - nw * 0.62} ${noseC.x + nw} ${noseC.y - nw * 0.42}Q${noseC.x + nw * 0.25} ${noseC.y + nw * 0.55} ${noseC.x} ${noseC.y + nw * 0.6}Q${noseC.x - nw * 0.25} ${noseC.y + nw * 0.55} ${noseC.x - nw} ${noseC.y - nw * 0.42}Z`;
  const M = P(L.mouth);
  const mr = dist(P(L.mouthW), M) / 2;
  const mouthD = `M${M.x - 2 * mr} ${M.y}A${mr} ${mr * 0.9} 0 0 0 ${M.x} ${M.y}A${mr} ${mr * 0.9} 0 0 0 ${M.x + 2 * mr} ${M.y}`;

  const Rd = Math.max(rx, ry) * 1.3;
  const tuft = L.tuft.map(P);
  return {
    C, rx, ry, R, Rd, tuft,
    thin: Math.max(1.6, R * 0.022),
    thick: Math.max(3, R * 0.06),
    ears, lenses, bridgeD, eyes, noseC, noseD, mouthD,
    face: L.facePlate.map(P),
    shadow: { x: full.ground.x, y: full.ground.y, rx: full.shadowRx },
    wordShift: full.ground.y + 28 - (C.y + Rd + Math.max(22, R * 0.22)),
  };
}
