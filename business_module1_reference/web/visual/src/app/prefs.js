/** 用户偏好：声音、动画、角色显示、安静模式。持久化到 localStorage。 */
const KEY = 'medrep.prefs.v1';
const DEFAULTS = {
  sound: true, // 仅在用户主动进入语音模式后才会朗读；其他场景从不发声
  motion: 'system', // system | reduce | full
  petVisible: true,
  quiet: false, // 安静：小博士休息，不主动做任何事
  petSide: 'right',
  petY: null,
  look: { glasses: 'browline', outfit: 'labcoat' }, // 眼镜与服装款式（在状态实验室里切换）
  lookVersion: 2, // 默认造型变更时递增，旧存储里的造型会被替换一次
  petSideM: 'right', // 移动端单独记忆位置
  petYM: null, // null = 坐在底部导航栏右侧的预留位
};

let state = { ...DEFAULTS };
try {
  const stored = JSON.parse(localStorage.getItem(KEY) || '{}');
  state = { ...DEFAULTS, ...stored };
  if (stored.lookVersion !== DEFAULTS.lookVersion) {
    state.look = { ...DEFAULTS.look };
    state.lookVersion = DEFAULTS.lookVersion;
  }
} catch {
  /* 忽略损坏的存储 */
}
const subs = new Set();

export const prefs = {
  get: (k) => state[k],
  all: () => ({ ...state }),
  set(patch) {
    state = { ...state, ...patch };
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      /* 隐私模式等情况下无法写入 */
    }
    subs.forEach((fn) => fn(state, patch));
  },
  subscribe(fn) {
    subs.add(fn);
    return () => subs.delete(fn);
  },
};

// 其他标签页（例如状态实验室）修改了偏好：同步过来
addEventListener('storage', (e) => {
  if (e.key !== KEY || !e.newValue) return;
  try {
    const next = { ...DEFAULTS, ...JSON.parse(e.newValue) };
    const patch = {};
    for (const k of Object.keys(next)) if (JSON.stringify(next[k]) !== JSON.stringify(state[k])) patch[k] = next[k];
    state = next;
    if (Object.keys(patch).length) subs.forEach((fn) => fn(state, patch));
  } catch {
    /* ignore */
  }
});

const mq = matchMedia('(prefers-reduced-motion: reduce)');
export function reducedMotion() {
  const m = state.motion;
  return m === 'reduce' || (m === 'system' && mq.matches);
}
mq.addEventListener?.('change', () => subs.forEach((fn) => fn(state, { motion: state.motion })));
