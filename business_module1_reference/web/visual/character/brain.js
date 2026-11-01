/**
 * 小博士行为引擎
 *
 * 分层结构（每帧从上到下叠加）：
 *   1. 状态基础姿态 POSES[state]
 *   2. 视线（视线源：动作 > 指针 > 默认看向用户 + 漂移）
 *   3. 瞬时动作 actions（带包络淡入淡出，可叠加多个）
 *   4. 外部驱动：拖拽、麦克风输入电平、说话口型电平
 *   5. 弹簧系统：所有参数通过阻尼弹簧逼近目标 → 切换自然、有跟随与回弹
 *   6. 程序化细节层：呼吸、眨眼、眼球微跳、低频漂移、呆毛惯性
 *
 * 不同参数用不同弹簧：眼睛快且无回弹，头部稍慢带一点过冲，手臂有跟随，
 * 身体挤压回弹强。所以“眼睛先动、头随后、身体最后”的层次是自然产生的。
 */

const rand = (a, b) => a + Math.random() * (b - a);
const clamp = (x, a, b) => Math.min(Math.max(x, a), b);
const lerp = (a, b, t) => a + (b - a) * t;
const bump = (p) => Math.sin(Math.PI * clamp(p, 0, 1)); // 0→1→0
const easeOut = (p) => 1 - Math.pow(1 - clamp(p, 0, 1), 3);

export const STATES = ['awake', 'listening', 'thinking', 'speaking', 'done', 'error', 'rest', 'away'];

const DEFAULTS = {
  rootX: 0, rootY: 0, squash: 0, lean: 0.03, sway: 0, turn: 0,
  headYaw: 0, headPitch: 0.02, headRoll: 0,
  eyeX: 0, eyeY: 0, lidTop: 0.06, lidBot: 0, lidTilt: 0,
  browY: 0, browTilt: 0, browAsym: 0,
  mouthOpen: 0, mouthWide: 0, smile: 0.42, blush: 0.18,
  armLPitch: 0.05, armLAbd: 0.38, armLTwist: 0, armLElbow: -0.3,
  armRPitch: 0.05, armRAbd: 0.38, armRTwist: 0, armRElbow: -0.3,
  shoulderUp: 0, glassesY: 0, thinkDots: 0, book: 0, pupil: 1,
  // 猫的部分：耳朵、胡须、尾巴
  earBack: 0, earOut: 0, earAsym: 0, whisker: 0,
  tailUp: 0.55, tailWag: 0.35, tailSpeed: 0.55, tailCurl: 0,
};

const arms = (pitch, abd, elbow, twist = 0) => ({
  armLPitch: pitch, armLAbd: abd, armLElbow: elbow, armLTwist: twist,
  armRPitch: pitch, armRAbd: abd, armRElbow: elbow, armRTwist: twist,
});

const POSES = {
  awake: {},
  listening: {
    lean: 0.1, headPitch: 0.05, headRoll: 0.09, browY: 0.32, lidTop: 0, smile: 0.32, mouthWide: -0.2, pupil: 1.14,
    earBack: -0.35, earOut: -0.08, whisker: 0.35, tailUp: 0.85, tailWag: 0.12, tailSpeed: 0.35,
    ...arms(-0.7, -0.38, -1.15),
  },
  thinking: {
    lean: -0.01, headPitch: -0.1, headRoll: -0.12, lidTop: 0.3, lidTilt: 0.15, browAsym: 0.55,
    smile: 0.05, mouthWide: -0.45, thinkDots: 1, pupil: 0.9,
    earAsym: 0.35, earOut: 0.08, tailUp: 0.45, tailWag: 0.5, tailSpeed: 0.3, tailCurl: 0.3,
    armLPitch: -1.55, armLAbd: -0.95, armLElbow: -1.25, armLTwist: 0.35,
    armRPitch: -0.62, armRAbd: -0.45, armRElbow: -1.45,
  },
  speaking: {
    lean: 0.05, browY: 0.12, smile: 0.45, lidTop: 0.02, pupil: 1.05, earBack: -0.1, tailWag: 0.35, tailSpeed: 0.7,
    ...arms(-0.22, 0.36, -0.7),
  },
  done: { lean: 0.02, smile: 0.85, blush: 0.55, browY: 0.15, pupil: 1.12, earBack: -0.2, tailUp: 1, tailWag: 0.7, tailSpeed: 1.6 },
  error: {
    headRoll: 0.2, headPitch: 0.04, browTilt: -0.75, browY: 0.15, lidTop: 0.1, lidTilt: -0.25,
    smile: -0.35, mouthWide: -0.3, shoulderUp: 0.035, pupil: 0.92, earOut: 0.75, earBack: 0.25, tailUp: 0.12, tailWag: 0.08, tailSpeed: 0.3, whisker: -0.4, ...arms(-0.35, 0.72, -1.4),
  },
  rest: {
    lean: -0.03, squash: -0.035, headPitch: 0.27, headRoll: 0.08, lidTop: 1.1, browY: -0.15,
    smile: 0.12, mouthWide: -0.35, blush: 0.12, ...arms(0.02, 0.2, -0.1),
    earOut: 0.4, earBack: 0.3, whisker: -0.35, tailUp: 0, tailWag: 0.04, tailSpeed: 0.2, tailCurl: 1.4,
  },
  away: {
    turn: 0.42, headYaw: 0.12, headPitch: 0.24, lidTop: 0.5, lidTilt: -0.15, smile: 0.2, book: 1, earBack: 0.05, earAsym: 0.15, tailUp: 0.3, tailWag: 0.18, tailSpeed: 0.25, tailCurl: 0.6,
    ...arms(-1.0, -0.14, -1.25),
  },
};

const ERROR_VARIANTS = {
  unheard: { headRoll: 0.28, lean: 0.12, browTilt: -0.5, browAsym: 0.3, earOut: 0.1, earBack: -0.3, earAsym: 0.4, tailUp: 0.5, ...arms(-0.5, 0.2, -1.0) },
  offline: {},
  blocked: { headRoll: 0.06, browTilt: -0.4, smile: -0.1, ...arms(-1.0, 0.45, -1.15) },
  unsupported: { headRoll: 0.15, browTilt: -0.5 },
};

// 弹簧参数 [刚度, 阻尼比]
const SPRING = {
  rootX: [70, 0.85], rootY: [230, 0.42], squash: [380, 0.28], lean: [70, 0.75], sway: [60, 0.55], turn: [45, 0.85],
  headYaw: [85, 0.72], headPitch: [85, 0.72], headRoll: [80, 0.7],
  eyeX: [700, 1], eyeY: [700, 1], lidTop: [900, 1], lidBot: [500, 1], lidTilt: [300, 1],
  browY: [260, 0.8], browTilt: [240, 0.85], browAsym: [200, 0.85],
  mouthOpen: [600, 0.95], mouthWide: [300, 0.9], smile: [160, 1], blush: [40, 1],
  shoulderUp: [200, 0.7], glassesY: [420, 0.45], thinkDots: [60, 1], book: [70, 1], pupil: [90, 1],
  earBack: [320, 0.32], earOut: [220, 0.45], earAsym: [300, 0.35], whisker: [260, 0.5],
  tailUp: [30, 0.9], tailWag: [12, 1], tailSpeed: [8, 1], tailCurl: [25, 1],
};
const ARM_SPRING = [115, 0.62];

/** 动作库：返回 { dur, look?, fn(T, p, w, ctx), start?(brain) } */
const ACTIONS = {
  earTwitch: () => {
    const dir = Math.random() < 0.5 ? -1 : 1;
    return {
      dur: 0.32, attack: 0.03, release: 0.12,
      start: (b) => b.kick('earAsym', 9 * dir),
      fn: () => {},
    };
  },
  sniff: () => ({
    dur: 1.1, look: { x: 0, y: -0.15 },
    fn: (T, p, w, ctx) => {
      T.whisker += Math.sin(ctx.time * 26) * 0.5 * w; T.headPitch -= 0.05 * w; T.lidTop += 0.15 * w;
      T.earBack -= 0.2 * w;
    },
  }),
  tailFlick: () => ({
    dur: 1.2, fn: (T, p, w) => { T.tailWag += 0.6 * w; T.tailSpeed += 1.0 * w; T.tailUp += 0.2 * w; },
  }),
  knead: () => ({
    dur: 2.2, eyeMode: 'happy',
    fn: (T, p, w, ctx) => {
      const k = Math.sin(ctx.time * 7);
      T.armLPitch = lerp(T.armLPitch, -0.75 + k * 0.18, w); T.armLElbow = lerp(T.armLElbow, -1.1, w); T.armLAbd = lerp(T.armLAbd, -0.1, w);
      T.armRPitch = lerp(T.armRPitch, -0.75 - k * 0.18, w); T.armRElbow = lerp(T.armRElbow, -1.1, w); T.armRAbd = lerp(T.armRAbd, -0.1, w);
      T.lidTop = lerp(T.lidTop, 1.1, w); T.smile += 0.4 * w; T.blush += 0.3 * w; T.earOut += 0.15 * w;
    },
  }),
  glance: () => {
    const look = { x: rand(-0.95, 0.95), y: rand(-0.35, 0.5) };
    const roll = rand(-0.08, 0.08);
    return { dur: rand(1.2, 2.4), look, fn: (T, p, w) => { T.headRoll += roll * w; } };
  },
  curiousTilt: () => {
    const dir = Math.random() < 0.5 ? -1 : 1;
    return {
      dur: rand(1.6, 2.4),
      fn: (T, p, w) => { T.headRoll += 0.17 * dir * w; T.browAsym += 0.3 * w; T.browY += 0.1 * w; },
    };
  },
  lookAtViewer: () => ({
    dur: 1.6, look: { x: 0, y: 0 },
    fn: (T, p, w) => { T.smile += 0.15 * w; T.browY += 0.15 * w; },
  }),
  shiftWeight: () => {
    const dir = Math.random() < 0.5 ? -1 : 1;
    return {
      dur: rand(2, 3),
      fn: (T, p, w) => {
        T.sway += 0.05 * dir * w; T.rootX += 0.03 * dir * w; T.headRoll -= 0.04 * dir * w;
        T.armLAbd += 0.06 * w; T.armRAbd -= 0.04 * w;
      },
    };
  },
  tuftShake: () => ({
    dur: 0.75, attack: 0.05, release: 0.15,
    fn: (T, p, w) => { T.headYaw += Math.sin(p * Math.PI * 6) * 0.13 * w; T.lidTop += 0.4 * w; },
  }),
  glassesNudge: () => ({
    dur: 0.7,
    fn: (T, p, w) => { T.glassesY += 0.028 * bump(p * 1.6); T.lidBot += 0.35 * w; T.smile += 0.1 * w; },
  }),
  deepBreath: () => ({
    dur: 2.6,
    fn: (T, p, w) => {
      const b = bump(p);
      T.squash += 0.035 * b; T.lean -= 0.05 * b; T.shoulderUp += 0.04 * b; T.lidTop += 0.45 * b;
      T.headPitch -= 0.06 * b;
    },
  }),
  readPage: (brain) => ({
    dur: rand(2.2, 3.2),
    look: { x: brain.facing * 0.9, y: -0.35 },
    fn: (T, p, w) => { T.lidTop += 0.22 * w; T.headPitch += 0.04 * Math.sin(p * Math.PI * 3) * w; },
  }),
  hum: () => ({
    dur: 2.4, eyeMode: 'happy',
    fn: (T, p, w) => {
      T.sway += Math.sin(p * Math.PI * 4) * 0.06 * w; T.headRoll += Math.sin(p * Math.PI * 4 + 0.6) * 0.08 * w;
      T.lidTop = lerp(T.lidTop, 1.1, w); T.smile += 0.4 * w; T.blush += 0.25 * w;
      T.tailWag += 0.3 * w; T.tailSpeed += 0.4 * w;
    },
  }),
  stretch: () => ({
    dur: 2.6, attack: 0.25, release: 0.3,
    fn: (T, p, w) => {
      T.armLAbd = lerp(T.armLAbd, 2.55, w); T.armRAbd = lerp(T.armRAbd, 2.55, w);
      T.armLElbow = lerp(T.armLElbow, -0.25, w); T.armRElbow = lerp(T.armRElbow, -0.25, w);
      T.lean -= 0.08 * w; T.squash += 0.06 * w; T.lidTop = lerp(T.lidTop, 1.1, w);
      T.mouthOpen = lerp(T.mouthOpen, 0.55, w * bump(p)); T.mouthWide -= 0.4 * w; T.headPitch -= 0.12 * w;
    },
  }),
  yawn: () => ({
    dur: 2.2, attack: 0.3, release: 0.35,
    fn: (T, p, w) => {
      T.mouthOpen = lerp(T.mouthOpen, 0.85, w); T.mouthWide -= 0.5 * w; T.lidTop = lerp(T.lidTop, 0.9, w);
      T.headPitch -= 0.14 * w; T.browY += 0.2 * w;
      T.armLPitch = lerp(T.armLPitch, -1.05, w); T.armLElbow = lerp(T.armLElbow, -1.9, w); T.armLAbd = lerp(T.armLAbd, -0.05, w);
    },
  }),
  nodOff: () => ({
    dur: 2.6, attack: 0.5, release: 0.08,
    fn: (T, p, w) => { T.headPitch += 0.16 * w; T.lean += 0.04 * w; },
  }),
  wave: () => ({
    dur: 1.7, look: { x: 0, y: 0 },
    fn: (T, p, w, ctx) => {
      T.armRAbd = lerp(T.armRAbd, 2.25, w); T.armRPitch = lerp(T.armRPitch, -0.25, w);
      T.armRElbow = lerp(T.armRElbow, -0.55 + Math.sin(ctx.time * 13) * 0.38, w);
      T.smile += 0.35 * w; T.browY += 0.25 * w; T.headRoll -= 0.08 * w;
    },
  }),
  hop: () => ({
    dur: 0.5, start: (b) => { b.kick('squash', -1.2); b.later(0.08, () => b.kick('rootY', 2.4)); },
    fn: () => {},
  }),
  cheer: () => ({
    dur: 1.4, eyeMode: 'happy', look: { x: 0, y: 0.15 },
    start: (b) => { b.kick('squash', -1.4); b.later(0.1, () => b.kick('rootY', 2.8)); },
    fn: (T, p, w) => {
      T.armLAbd = lerp(T.armLAbd, 2.05, w); T.armRAbd = lerp(T.armRAbd, 2.05, w);
      T.armLElbow = lerp(T.armLElbow, -0.55, w); T.armRElbow = lerp(T.armRElbow, -0.55, w);
      T.lidTop = lerp(T.lidTop, 1.1, w); T.smile = lerp(T.smile, 1, w); T.blush += 0.6 * w; T.mouthOpen = lerp(T.mouthOpen, 0.35, w);
      T.earBack -= 0.3 * w; T.tailUp += 0.4 * w;
      T.headPitch -= 0.1 * w;
    },
  }),
  nod: () => ({
    dur: 0.55, attack: 0.05, release: 0.1,
    fn: (T, p) => { T.headPitch += 0.17 * bump(p); },
  }),
  smallNod: () => ({
    dur: 0.42, attack: 0.05, release: 0.1,
    fn: (T, p) => { T.headPitch += 0.08 * bump(p); },
  }),
  headShake: () => ({
    dur: 1.0, attack: 0.1, release: 0.2,
    fn: (T, p, w) => { T.headYaw += Math.sin(p * Math.PI * 4) * 0.2 * w; },
  }),
  pokeHead: () => ({
    dur: 1.0, attack: 0.02, release: 0.35,
    start: (b) => { b.kick('squash', -2.4); b.kick('headPitch', -2.2); b.kick('glassesY', 0.5); },
    fn: (T, p, w) => {
      const s = p < 0.45 ? 1 : 0;
      T.lidTop = lerp(T.lidTop, 0.78, w * s); T.lidBot = lerp(T.lidBot, 0.5, w * s); T.browTilt += 0.4 * w * s;
      T.mouthOpen = lerp(T.mouthOpen, 0.18, w * s); T.mouthWide -= 0.5 * w * s;
      T.earBack += 0.9 * w * s; T.earOut += 0.3 * w * s; T.whisker -= 0.4 * w * s;
      T.smile += 0.3 * w * (1 - s); T.blush += 0.4 * w;
    },
  }),
  pokeBody: () => ({
    dur: 1.25, eyeMode: 'happy', attack: 0.04, release: 0.3,
    start: (b) => b.kick('squash', -2.0),
    fn: (T, p, w) => {
      T.squash += Math.sin(p * Math.PI * 7) * 0.04 * w; T.sway += Math.sin(p * Math.PI * 5) * 0.04 * w;
      T.lidTop = lerp(T.lidTop, 1.1, w); T.smile = lerp(T.smile, 1, w); T.blush += 0.7 * w;
      T.mouthOpen = lerp(T.mouthOpen, 0.3 + 0.15 * Math.sin(p * 30), w);
      T.armLPitch = lerp(T.armLPitch, -0.45, w); T.armLAbd = lerp(T.armLAbd, -0.12, w); T.armLElbow = lerp(T.armLElbow, -1.3, w);
      T.armRPitch = lerp(T.armRPitch, -0.45, w); T.armRAbd = lerp(T.armRAbd, -0.12, w); T.armRElbow = lerp(T.armRElbow, -1.3, w);
    },
  }),
  pokeArm: () => ({
    dur: 0.7, attack: 0.03, release: 0.3, look: { x: 0, y: -0.5 },
    start: (b) => b.kick('squash', -1.0),
    fn: (T, p, w) => { T.browY += 0.5 * w; T.lidTop = lerp(T.lidTop, 0, w); T.mouthOpen = lerp(T.mouthOpen, 0.2, w); T.mouthWide -= 0.5 * w; },
  }),
  grumpy: (brain) => ({
    dur: 2.1, look: { x: -brain.facing * 0.9, y: 0.25 },
    fn: (T, p, w) => {
      T.turn -= 0.45 * brain.facing * w; T.browTilt = lerp(T.browTilt, 0.85, w); T.lidTop = lerp(T.lidTop, 0.35, w);
      T.smile = lerp(T.smile, -0.3, w); T.mouthWide -= 0.6 * w; T.blush += 0.7 * w;
      T.armLPitch = lerp(T.armLPitch, -0.85, w); T.armLAbd = lerp(T.armLAbd, -0.42, w); T.armLElbow = lerp(T.armLElbow, -1.7, w);
      T.armRPitch = lerp(T.armRPitch, -0.85, w); T.armRAbd = lerp(T.armRAbd, -0.42, w); T.armRElbow = lerp(T.armRElbow, -1.7, w);
      T.headPitch -= 0.06 * w;
      T.earBack += 0.85 * w; T.earOut += 0.35 * w; T.tailWag += 0.6 * w; T.tailSpeed += 1.6 * w; T.whisker -= 0.5 * w;
    },
  }),
  surprised: () => ({
    dur: 0.7, attack: 0.02, release: 0.4,
    start: (b) => { b.kick('rootY', 1.2); b.kick('squash', 1.6); },
    fn: (T, p, w) => {
      T.browY += 0.8 * w; T.lidTop = lerp(T.lidTop, -0.05, w); T.mouthOpen = lerp(T.mouthOpen, 0.32, w); T.mouthWide -= 0.6 * w;
      T.pupil = lerp(T.pupil, 0.78, w); // 受惊瞳孔收缩
      T.earBack -= 0.55 * w; T.whisker += 0.6 * w; T.tailUp += 0.6 * w;
      T.armLAbd += 0.4 * w; T.armRAbd += 0.4 * w;
    },
  }),
  wakeUp: () => ({
    dur: 1.6, attack: 0.02, release: 0.4,
    fn: (T, p, w) => {
      // 眼睑先抖两下再睁开
      const flutter = p < 0.55 ? 0.55 + 0.45 * Math.abs(Math.cos(p * Math.PI * 4.5)) : 0;
      T.lidTop = lerp(T.lidTop, flutter, w);
      T.headPitch += (p < 0.5 ? 0.12 : -0.06) * w;
      T.armLAbd += 0.6 * bump(p) * w; T.armRAbd += 0.6 * bump(p) * w;
      T.squash += 0.05 * bump(p);
    },
  }),
  listenNod: () => ({
    dur: 0.5, attack: 0.05, release: 0.1,
    fn: (T, p) => { T.headPitch += 0.09 * bump(p); T.browY += 0.1 * bump(p); },
  }),
  expectTilt: () => {
    const dir = Math.random() < 0.5 ? -1 : 1;
    return { dur: 1.6, fn: (T, p, w) => { T.headRoll += 0.16 * dir * w; T.browY += 0.25 * w; T.browAsym += 0.25 * w; } };
  },
  thinkBeat: () => {
    const side = Math.random() < 0.5 ? -1 : 1;
    return {
      dur: rand(1.0, 1.8), look: { x: 0.6 * side, y: 0.65 },
      fn: (T, p, w) => { T.headRoll += -0.06 * side * w; T.browAsym += 0.1 * w; },
    };
  },
  hmm: () => ({
    dur: 0.9, look: { x: 0.5, y: 0.7 },
    fn: (T, p) => { T.headPitch += 0.08 * bump(p); },
  }),
  gesture: () => {
    const which = Math.random();
    const L = which < 0.4 || which > 0.8;
    const R = which >= 0.4;
    const pitch = rand(-0.95, -0.5);
    const abd = rand(0.15, 0.55);
    return {
      dur: rand(0.9, 1.5), attack: 0.25, release: 0.35,
      fn: (T, p, w) => {
        if (L) { T.armLPitch = lerp(T.armLPitch, pitch, w); T.armLAbd = lerp(T.armLAbd, abd, w); T.armLElbow = lerp(T.armLElbow, -1.25, w); }
        if (R) { T.armRPitch = lerp(T.armRPitch, pitch, w); T.armRAbd = lerp(T.armRAbd, abd, w); T.armRElbow = lerp(T.armRElbow, -1.25, w); }
        T.browY += 0.18 * w; T.lean += 0.03 * w;
      },
    };
  },
  speakGlance: () => ({
    dur: rand(0.7, 1.2), look: { x: rand(-0.6, 0.6), y: rand(0.15, 0.45) },
    fn: () => {},
  }),
  land: () => ({
    dur: 0.6, attack: 0.02, release: 0.4,
    start: (b) => b.later(0.12, () => b.kick('squash', -2.6)),
    fn: (T, p, w) => { T.smile += 0.3 * w; T.lidTop = lerp(T.lidTop, 0.4, w * bump(p)); },
  }),
  pageTurn: () => ({
    dur: 1.1,
    fn: (T, p, w) => { T.armRPitch -= 0.25 * bump(p); T.armRAbd -= 0.2 * bump(p); T.headYaw -= 0.08 * bump(p); },
  }),
};

// 自主动作池（权重）：只在对应状态下自发出现
const IDLE_POOL = {
  awake: [
    ['glance', 3], ['curiousTilt', 2], ['lookAtViewer', 1.5], ['shiftWeight', 2], ['tuftShake', 0.8],
    ['glassesNudge', 1.4], ['deepBreath', 1], ['readPage', 2], ['hum', 0.5], ['stretch', 0.35],
    ['earTwitch', 2.2], ['sniff', 1], ['tailFlick', 1.2], ['knead', 0.4],
  ],
  rest: [['nodOff', 1], ['earTwitch', 0.8]],
  thinking: [['thinkBeat', 1]],
  speaking: [['gesture', 3], ['speakGlance', 1.2], ['smallNod', 1.5]],
  away: [['pageTurn', 1], ['glassesNudge', 0.6], ['earTwitch', 0.8]],
};
const IDLE_INTERVAL = {
  awake: [3.8, 8], rest: [9, 16], thinking: [1.2, 2.2], speaking: [0.9, 2.0], away: [5, 10],
};

const noise = (t, seed) =>
  Math.sin(t * 0.37 + seed) * 0.5 + Math.sin(t * 0.83 + seed * 2.3 + 1.3) * 0.3 + Math.sin(t * 1.71 + seed * 3.7 + 2.1) * 0.2;

export class Brain {
  constructor(model) {
    this.model = model;
    this.time = 0;
    this.state = 'awake';
    this.variant = null;
    this.reducedMotion = false;
    this.facing = -1; // 页面内容所在方向（-1 左，1 右），用于“看向页面”
    this.cur = { ...DEFAULTS };
    this.vel = Object.fromEntries(Object.keys(DEFAULTS).map((k) => [k, 0]));
    this.actions = [];
    this.recent = [];
    this.timers = [];
    this.listeners = new Map();
    this.nextIdle = rand(2, 4);
    this.idleTime = 0; // 距离上次用户互动的时间
    this.restAfter = 90;
    this.autoRest = true;
    this.blink = { next: rand(1.5, 4), t: -1 };
    this.saccade = { next: 0.6, x: 0, y: 0 };
    this.breath = 0;
    this.pointer = { x: 0, y: 0, active: false, last: -99 };
    this.hovering = false;
    this.drag = { on: false, vx: 0, vy: 0 };
    this.voiceLevel = 0; // 说话口型电平 0..1
    this.inputLevel = 0; // 麦克风电平 0..1
    this.inputLevelSmooth = 0;
    this.silence = 0;
    this.lastNod = 0;
    this.prevVoice = 0;
    this.pokes = [];
    this.tuft = { x: 0, z: 0, vx: 0, vz: 0, px: 0, pz: 0, pvx: 0, pvz: 0, pRootV: 0 };
  }

  on(evt, cb) {
    if (!this.listeners.has(evt)) this.listeners.set(evt, new Set());
    this.listeners.get(evt).add(cb);
    return () => this.listeners.get(evt).delete(cb);
  }
  emit(evt, data) {
    this.listeners.get(evt)?.forEach((cb) => cb(data));
  }

  kick(key, v) {
    this.vel[key] += v * (this.reducedMotion ? 0.15 : 1);
  }
  later(delay, fn) {
    this.timers.push({ at: this.time + delay, fn });
  }

  play(name, opts = {}) {
    const factory = ACTIONS[name];
    if (!factory) return;
    if (this.reducedMotion && !opts.essential) {
      // 减少动画：只保留表情类动作，去掉大幅度身体动作
      if (['stretch', 'hum', 'tuftShake', 'shiftWeight', 'hop', 'gesture', 'pageTurn', 'nodOff', 'knead', 'tailFlick'].includes(name)) return;
    }
    const a = factory(this);
    a.name = name;
    a.t = 0;
    a.attack ??= 0.2;
    a.release ??= 0.3;
    if (opts.replace) this.actions = this.actions.filter((x) => !opts.replace.includes(x.name));
    this.actions.push(a);
    a.start?.(this);
    this.recent.unshift(name);
    this.recent.length = Math.min(this.recent.length, 3);
  }

  /** 用户产生任何互动时调用：重置无聊计时，必要时从休息中唤醒 */
  touch() {
    this.idleTime = 0;
    if (this.state === 'rest' && !this.lockedRest) this.setState('awake');
  }

  setState(state, opts = {}) {
    if (!STATES.includes(state)) return;
    const prev = this.state;
    if (prev === state && opts.variant === this.variant) return;
    this.state = state;
    this.variant = opts.variant ?? null;
    this.lockedRest = state === 'rest' && !!opts.locked;
    this.nextIdle = rand(...(IDLE_INTERVAL[state] || [3, 6]));
    clearTimeout(this._autoReturn);
    // 转场动作：让切换有“意图”，而不是姿态直接插值
    const wake = prev === 'rest' || prev === 'away';
    if (wake && state !== 'rest') this.play(state === 'listening' ? 'surprised' : 'wakeUp', { essential: true });
    switch (state) {
      case 'awake':
        if (prev === 'speaking') this.play('nod');
        if (wake) this.later(1.3, () => this.state === 'awake' && this.play('wave'));
        break;
      case 'listening':
        if (!wake) this.play('surprised');
        this.silence = 0;
        break;
      case 'thinking':
        this.play('hmm');
        break;
      case 'speaking':
        this.play('lookAtViewer');
        break;
      case 'done':
        this.play('cheer', { essential: true });
        this._autoReturn = setTimeout(() => this.state === 'done' && this.setState('awake'), opts.hold ?? 2400);
        break;
      case 'error':
        this.play(this.variant === 'unheard' ? 'expectTilt' : 'headShake', { essential: true });
        if (opts.autoReturn) this._autoReturn = setTimeout(() => this.state === 'error' && this.setState('awake'), opts.autoReturn);
        break;
      case 'rest':
        if (prev === 'awake' && !opts.quick) this.play('yawn');
        break;
    }
    this.emit('state', { state, prev, variant: this.variant });
  }

  // ---------- 输入 ----------
  setPointer(nx, ny) {
    // nx, ny：以角色为中心、已归一化的指针方向（-1..1，y 向上为正）
    this.pointer.x = clamp(nx, -1, 1);
    this.pointer.y = clamp(ny, -1, 1);
    this.pointer.active = true;
    this.pointer.last = this.time;
  }
  setHover(on) {
    if (on && !this.hovering) {
      this.touch();
      if (this.state === 'awake' && !this.reducedMotion) this.kick('browY', 3);
    }
    this.hovering = on;
  }
  poke(part = 'body') {
    this.touch();
    const now = this.time;
    this.pokes = this.pokes.filter((t) => now - t < 3);
    this.pokes.push(now);
    if (this.state !== 'awake' && this.state !== 'done') return; // 其他状态下只唤醒或忽略，不打断语音流程
    if (this.pokes.length >= 5) {
      this.pokes = [];
      this.play('grumpy', { replace: ['pokeHead', 'pokeBody', 'pokeArm'] });
      this.later(2.0, () => { this.play('lookAtViewer'); this.play('smallNod'); });
      this.emit('reaction', 'grumpy');
      return;
    }
    const name = part === 'head' ? 'pokeHead' : part === 'arm' || part === 'hand' ? 'pokeArm' : 'pokeBody';
    this.play(name, { replace: ['pokeHead', 'pokeBody', 'pokeArm'], essential: true });
    this.emit('reaction', name);
  }
  dragStart() {
    this.touch();
    this.drag.on = true;
    this.play('surprised', { essential: true });
  }
  dragMove(vx, vy) {
    this.drag.vx = vx;
    this.drag.vy = vy;
  }
  dragEnd() {
    this.drag.on = false;
    this.drag.vx = this.drag.vy = 0;
    this.play('land', { essential: true });
  }
  setVoiceLevel(v) {
    this.voiceLevel = clamp(v, 0, 1);
  }
  setInputLevel(v) {
    this.inputLevel = clamp(v, 0, 1);
  }

  // ---------- 每帧 ----------
  update(dt) {
    dt = Math.min(dt, 1 / 20);
    this.time += dt;
    const t = this.time;
    const rm = this.reducedMotion;
    this.idleTime += dt;

    for (let i = this.timers.length - 1; i >= 0; i--) {
      if (this.timers[i].at <= t) {
        const { fn } = this.timers[i];
        this.timers.splice(i, 1);
        fn();
      }
    }

    // 1. 基础姿态
    const T = { ...DEFAULTS, ...POSES[this.state] };
    if (this.state === 'error' && this.variant) Object.assign(T, ERROR_VARIANTS[this.variant]);
    T.turn += this.facing * 0.22;
    if (this.hovering && this.state === 'awake') {
      T.browY += 0.22; T.lean += 0.05; T.smile += 0.12; T.lidTop = 0; T.pupil = 1.15; T.earBack -= 0.3; T.tailWag += 0.2;
    }

    // 2. 视线
    let look = { x: noise(t * 0.6, 1) * 0.12, y: noise(t * 0.5, 7) * 0.08 };
    const pointerFresh = t - this.pointer.last < 5 && this.pointer.active && !this.lookLocked;
    if (pointerFresh && ['awake', 'done', 'listening'].includes(this.state)) {
      const k = this.state === 'listening' ? 0.35 : 1;
      look = { x: lerp(look.x, this.pointer.x, k), y: lerp(look.y, this.pointer.y, k) };
    }
    if (this.state === 'thinking') look = { x: 0.45, y: 0.6 };
    if (this.state === 'away') look = { x: -0.2, y: -0.6 };

    // 3. 动作
    let eyeMode = 'normal';
    for (let i = this.actions.length - 1; i >= 0; i--) {
      const a = this.actions[i];
      a.t += dt;
      const p = a.t / a.dur;
      if (p >= 1) {
        this.actions.splice(i, 1);
        continue;
      }
      const at = a.attack / a.dur;
      const rl = a.release / a.dur;
      const w = p < at ? easeOut(p / at) : p > 1 - rl ? easeOut((1 - p) / rl) : 1;
      if (a.look) look = { x: lerp(look.x, a.look.x, w), y: lerp(look.y, a.look.y, w) };
      if (a.eyeMode && w > 0.5) eyeMode = a.eyeMode;
      a.fn(T, p, w, { time: t });
    }

    // 4. 外部驱动
    if (this.drag.on) {
      const { vx, vy } = this.drag;
      T.rootY = 0.16;
      T.sway = clamp(-vx * 0.0011, -0.65, 0.65);
      T.lean = clamp(vy * 0.0006, -0.35, 0.35) + 0.05;
      T.armLAbd = 1.05 + clamp(vx * 0.0006, -0.4, 0.4); T.armRAbd = 1.05 - clamp(vx * 0.0006, -0.4, 0.4);
      T.armLElbow = T.armRElbow = -0.35;
      T.armLPitch = T.armRPitch = -0.15;
      T.lidTop = 0; T.browY = 0.65; T.mouthOpen = 0.28; T.mouthWide = -0.55; T.smile = 0.1;
      T.earBack = 0.45; T.earOut = 0.25; T.tailUp = 0; T.tailCurl = 0; T.tailWag = 0.15; T.whisker = 0.4;
      look = { x: 0, y: -0.7 };
    }

    if (this.state === 'listening') {
      this.inputLevelSmooth = lerp(this.inputLevelSmooth, this.inputLevel, 1 - Math.exp(-dt * 12));
      const L = this.inputLevelSmooth;
      T.lean += L * 0.05; T.browY += L * 0.2; T.earBack -= L * 0.25; T.whisker += L * 0.3;
      if (this.inputLevel > 0.22) {
        if (this.silence > 0.5 && t - this.lastNod > 1.4) {
          this.play('listenNod');
          this.lastNod = t;
        }
        this.silence = 0;
      } else {
        this.silence += dt;
        if (this.silence > 2.6 && this.silence - dt <= 2.6) this.play('expectTilt');
      }
      if (!rm) this.tuft.vz += (this.inputLevel - 0.1) * dt * 30 * Math.sin(t * 40);
    }

    let speechMouth = 0;
    if (this.state === 'speaking') {
      speechMouth = this.voiceLevel * (rm ? 0.75 : 1);
      // 音节起点：轻微点头/挑眉，让说话带节奏
      if (this.voiceLevel - this.prevVoice > 0.35 && !rm) {
        this.kick('headPitch', 0.5);
        if (Math.random() < 0.25) this.kick('browY', 2.2);
      }
      T.mouthWide += Math.sin(t * 5.3) * 0.25;
    }
    this.prevVoice = this.voiceLevel;

    // 大幅度转移视线时顺带眨眼（真人转头时常伴随眨眼，能掩盖眼球“滑动”感）
    const shift = Math.hypot(look.x - (this.lastLook?.x ?? look.x), look.y - (this.lastLook?.y ?? look.y));
    this.lookTravel = (this.lookTravel || 0) * Math.exp(-dt * 6) + shift;
    if (this.lookTravel > 0.55 && this.blink.t < 0 && t - (this.lastGazeBlink || 0) > 1.2) {
      this.blink.next = t;
      this.lastGazeBlink = t;
      this.lookTravel = 0;
    }
    this.lastLook = { x: look.x, y: look.y };

    look.x = clamp(look.x + this.saccade.x, -1, 1);
    look.y = clamp(look.y + this.saccade.y, -1, 1);
    T.eyeX = look.x;
    T.eyeY = look.y;
    T.headYaw += look.x * 0.42;
    T.headPitch -= look.y * 0.22;
    // 身体跟着头转一点点，转得更大时肩膀也参与
    T.turn += look.x * 0.12;
    T.sway -= look.x * 0.015;

    if (this.state === 'thinking' && !rm) {
      // 托腮的手指轻敲：每隔几秒敲两三下
      const cyc = t % 3.4;
      if (cyc < 0.6) T.armLElbow += Math.sin(cyc * Math.PI * 2 / 0.3) * 0.06;
    }
    if (this.state === 'awake') {
      // 表情不是恒定的：嘴角与眉毛有很慢的微小起伏
      T.smile += noise(t * 0.35, 11) * 0.08;
      T.browY += noise(t * 0.3, 13) * 0.06;
    }

    // 5. 弹簧
    for (const k in DEFAULTS) {
      const [stiff, zeta0] = SPRING[k] || ARM_SPRING;
      const zeta = rm ? Math.max(zeta0, 1) : zeta0;
      const c = 2 * Math.sqrt(stiff) * zeta;
      const steps = 2; // 子步进，避免高刚度弹簧在低帧率下发散
      const h = dt / steps;
      for (let s = 0; s < steps; s++) {
        const a = stiff * (T[k] - this.cur[k]) - c * this.vel[k];
        this.vel[k] += a * h;
        this.cur[k] += this.vel[k] * h;
      }
    }

    // 6. 程序化细节
    const O = { ...this.cur };
    const breathRate = this.state === 'rest' ? 0.16 : this.state === 'listening' ? 0.3 : 0.24;
    this.breath += dt * Math.PI * 2 * breathRate;
    const bA = rm ? 0.35 : 1;
    O.squash += Math.sin(this.breath) * 0.013 * bA;
    O.shoulderUp += Math.sin(this.breath) * 0.008 * bA;
    O.headPitch += Math.sin(this.breath - 0.7) * 0.012 * bA;
    if (!rm) {
      O.headRoll += noise(t, 3) * 0.025;
      O.headYaw += noise(t * 0.8, 5) * 0.03;
      O.sway += noise(t * 0.7, 9) * 0.012;
    }

    // 眨眼
    const canBlink = this.state !== 'rest' && O.lidTop < 0.85;
    if (canBlink) {
      if (this.blink.t < 0 && t >= this.blink.next) this.blink.t = 0;
      if (this.blink.t >= 0) {
        this.blink.t += dt;
        const p = this.blink.t / 0.17;
        const close = p < 0.38 ? p / 0.38 : 1 - (p - 0.38) / 0.62;
        O.lidTop = Math.max(O.lidTop, clamp(close, 0, 1) * 1.05);
        if (p >= 1) {
          this.blink.t = -1;
          const dbl = Math.random() < 0.16;
          this.blink.next = t + (dbl ? 0.12 : rand(1.8, 5.5) * (this.state === 'thinking' ? 1.5 : 1));
        }
      }
    }

    // 眼球微跳：视线并非完全静止
    if (t >= this.saccade.next) {
      const amp = this.state === 'listening' ? 0.05 : 0.11;
      this.saccade.x = rand(-amp, amp);
      this.saccade.y = rand(-amp, amp) * 0.7;
      this.saccade.next = t + rand(0.45, 2.0);
    }

    this.tailPhase = (this.tailPhase || 0) + dt * Math.PI * 2 * Math.max(this.cur.tailSpeed, 0.05) * (rm ? 0.4 : 1);
    O.tailPhase = this.tailPhase;
    if (rm) O.tailWag *= 0.4;
    O.mouthOpen = Math.max(O.mouthOpen, speechMouth);
    O.eyeMode = eyeMode;

    // 呆毛：头部角加速度驱动的欠阻尼弹簧
    const tf = this.tuft;
    const ax = O.headPitch + O.lean;
    const az = O.headRoll + O.sway;
    const avx = (ax - tf.px) / dt;
    const avz = (az - tf.pz) / dt;
    const rootV = this.vel.rootY;
    const g = rm ? 0.2 : 1;
    tf.vx -= (avx - tf.pvx) * 0.9 * g;
    tf.vz -= (avz - tf.pvz) * 0.9 * g;
    tf.vz += (rootV - tf.pRootV) * 0.35 * g;
    tf.px = ax; tf.pz = az; tf.pvx = avx; tf.pvz = avz; tf.pRootV = rootV;
    const tuftRestZ = this.state === 'rest' ? -0.55 : this.state === 'error' ? -0.25 : 0;
    const tuftRestX = this.state === 'rest' ? 0.25 : 0;
    const kT = 170;
    const cT = 2 * Math.sqrt(kT) * (rm ? 1 : 0.16);
    tf.vx += (kT * (tuftRestX - tf.x) - cT * tf.vx) * dt;
    tf.vz += (kT * (tuftRestZ - tf.z) - cT * tf.vz) * dt;
    tf.x = clamp(tf.x + tf.vx * dt, -0.9, 0.9);
    tf.z = clamp(tf.z + tf.vz * dt, -0.9, 0.9);
    O.tuftX = tf.x;
    O.tuftZ = tf.z;

    // 7. 自主行为调度（注意力预算：用户越久不互动，动作越少越轻）
    this.scheduleIdle(dt);

    if (this.autoRest && this.state === 'awake' && this.idleTime > this.restAfter) {
      this.setState('rest');
      this.emit('autorest');
    }

    this.model.apply(O, t);
    this.out = O;
  }

  scheduleIdle() {
    if (this.drag.on) return;
    const pool = IDLE_POOL[this.state];
    if (!pool) return;
    if (this.time < this.nextIdle) return;
    const busy = this.actions.some((a) => !['smallNod', 'listenNod'].includes(a.name));
    const [a, b] = IDLE_INTERVAL[this.state];
    const boredom = this.state === 'awake' ? clamp(this.idleTime / 50, 0, 1.5) : 0;
    this.nextIdle = this.time + rand(a, b) * (1 + boredom);
    if (busy && this.state === 'awake') return;
    let choices = pool.filter(([n]) => !this.recent.slice(0, 2).includes(n));
    if (this.idleTime < 25) choices = choices.filter(([n]) => n !== 'stretch');
    if (this.reducedMotion) {
      // 减少动画：只保留偶尔的视线移动
      if (this.state !== 'awake' || Math.random() > 0.35) return;
      choices = [['glance', 1]];
    }
    const total = choices.reduce((s, [, w]) => s + w, 0);
    let r = Math.random() * total;
    for (const [name, w] of choices) {
      r -= w;
      if (r <= 0) {
        this.play(name);
        break;
      }
    }
  }
}
