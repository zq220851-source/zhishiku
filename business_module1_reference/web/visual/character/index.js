/**
 * 小博士角色 · 对外入口
 *
 * 正式产品只需要从这里引入，不必直接接触 Stage / Brain / model 等内部模块。
 * 本模块只负责角色本身（渲染、动画、指针交互、口型），不包含任何业务逻辑、AI 或语音识别。
 *
 *   import { createXiaoboshi } from './character/index.js';
 *   const xb = createXiaoboshi(document.getElementById('pet'), { onTap: () => openPanel() });
 *   xb.setState('thinking');
 *   xb.speak('这道题建议先说明研究人群。');   // 无声口型 + 逐字回调
 *   xb.destroy();
 */
import { Stage } from './stage.js';
import { attachPointerInteractions } from './interactions.js';
import { TextLipSync, AnalyserLipSync } from './lipsync.js';
import { STATES } from './brain.js';
import { GLASSES } from './glasses.js';
import { OUTFITS } from './outfits.js';

export { STATES, GLASSES, OUTFITS, TextLipSync, AnalyserLipSync };
export const ERROR_VARIANTS = ['unheard', 'offline', 'blocked', 'unsupported'];

/**
 * 当前环境能否渲染角色（WebGL）。返回 false 时不要调用 createXiaoboshi，
 * 改为隐藏角色、保留文字入口；所有业务流程都不依赖角色本身。
 */
export function isSupported() {
  try {
    const c = document.createElement('canvas');
    const gl = c.getContext('webgl2') || c.getContext('webgl');
    if (!gl) return false;
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return true;
  } catch {
    return false;
  }
}
export const DEFAULT_LOOK = { glasses: 'browline', outfit: 'labcoat' };

/**
 * @param {HTMLElement} host  角色所在的容器。尺寸由业务方的 CSS 决定，角色会自适应（建议宽高比约 0.87）。
 * @param {object} [options]
 * @param {{glasses?: string, outfit?: string}} [options.look]  造型，默认眉线框 + 白大褂
 * @param {boolean} [options.reducedMotion]  减少动画；不传则跟随系统 prefers-reduced-motion
 * @param {boolean} [options.draggable=false]  是否允许拖动（拖动时只播放角色反应；容器位置由 onDrag* 回调自行处理）
 * @param {boolean} [options.autoRest=true]  长时间无互动后自动进入休息
 * @param {number}  [options.restAfter=90]  自动休息的空闲秒数
 * @param {-1|0|1}  [options.facing=0]  页面内容在角色的哪一侧（-1 左，1 右），角色会略微朝向内容
 * @param {(part: 'head'|'body'|'arm'|'hand'|'keyboard') => void} [options.onTap]
 * @param {() => void} [options.onDragStart]
 * @param {(x: number, y: number, down: {x:number,y:number,rect:DOMRect}) => void} [options.onDragMove]
 * @param {(x: number, y: number, vx: number, vy: number) => void} [options.onDragEnd]
 * @param {string} [options.label='小博士，学术训练助理']  无障碍名称
 */
export function createXiaoboshi(host, options = {}) {
  const o = {
    look: DEFAULT_LOOK, draggable: false, autoRest: true, restAfter: 90, facing: 0,
    label: '小博士，学术训练助理', ...options,
  };
  const stage = new Stage(host, { look: { ...DEFAULT_LOOK, ...o.look } });
  const { brain } = stage;
  brain.facing = o.facing;
  brain.autoRest = o.autoRest;
  brain.restAfter = o.restAfter;

  const mq = matchMedia('(prefers-reduced-motion: reduce)');
  let rmOverride = o.reducedMotion;
  const applyRM = () => (brain.reducedMotion = rmOverride ?? mq.matches);
  applyRM();
  mq.addEventListener?.('change', applyRM);

  host.setAttribute('aria-label', o.label);
  const detach = attachPointerInteractions(stage, host, {
    draggable: o.draggable,
    onTap: o.onTap,
    onDragStart: o.onDragStart,
    onDragMove: o.onDragMove,
    onDragEnd: o.onDragEnd,
  });

  let speechRaf = 0;
  let speechDone = null;
  const stopSpeech = (complete = false) => {
    cancelAnimationFrame(speechRaf);
    brain.setVoiceLevel(0);
    const done = speechDone;
    speechDone = null;
    done?.(complete);
  };

  const api = {
    /** 底层对象，仅供高级定制；正常接入不需要 */
    stage,
    brain,

    /**
     * 切换状态。
     * @param {'awake'|'listening'|'thinking'|'speaking'|'done'|'error'|'rest'|'away'} state
     * @param {object} [opts]
     * @param {'unheard'|'offline'|'blocked'|'unsupported'} [opts.variant]  仅 error 使用
     * @param {boolean} [opts.locked]  rest 时锁定（安静模式），用户互动也不会自动醒来
     * @param {number} [opts.autoReturn]  error 在多少毫秒后自动回到 awake
     * @param {number} [opts.hold]  done 保持多少毫秒后回到 awake（默认 2400）
     * @param {boolean} [opts.quick]  进入 rest 时不打哈欠
     */
    setState(state, opts) {
      if (state !== 'speaking') stopSpeech(false);
      brain.setState(state, opts);
    },
    get state() {
      return brain.state;
    },

    /** 用户有任何互动时调用（重置空闲计时；非锁定的休息状态会醒来） */
    touch: () => brain.touch(),

    /** 播放一个动作，例如 'wave'、'nod'、'cheer'、'glassesNudge'、'earTwitch'。见 HANDOFF.md 动作表 */
    play: (name) => brain.play(name, { essential: true }),

    /**
     * 说话口型（真实音频）：每帧传入 0..1 的音量。
     * 有真实 TTS 音频流时用 AnalyserLipSync 计算后传入。
     */
    setVoiceLevel: (v) => brain.setVoiceLevel(v),

    /** 倾听反应：每帧传入真实麦克风电平 0..1（角色会随你说话点头、竖耳朵） */
    setInputLevel: (v) => brain.setInputLevel(v),

    /**
     * 没有音频数据时的口型：按文本音节时间轴驱动，自动进入 speaking，结束后回到 awake。
     * @param {string} text
     * @param {object} [opts]
     * @param {number} [opts.rate=1]  语速倍率（文字阅读模式建议 2.5–3.2）
     * @param {(shown: string) => void} [opts.onProgress]  逐字回调，可用于字幕
     *   返回值的 seekChar(charIndex) 可与 TTS 的 boundary 事件对齐
     * @returns {{ stop(): void, seekChar(i: number): void, done: Promise<boolean> }}  done 为 true 表示完整说完，false 表示被打断
     */
    speak(text, { rate = 1, onProgress } = {}) {
      stopSpeech(false);
      const sync = new TextLipSync(text, rate);
      brain.setState('speaking');
      let last = performance.now();
      const done = new Promise((resolve) => (speechDone = resolve));
      const tick = (now) => {
        const dt = (now - last) / 1000;
        last = now;
        brain.setVoiceLevel(sync.step(dt));
        onProgress?.(text.slice(0, sync.spokenChars()));
        if (sync.time < sync.duration) speechRaf = requestAnimationFrame(tick);
        else {
          onProgress?.(text);
          stopSpeech(true);
          if (brain.state === 'speaking') brain.setState('awake');
        }
      };
      speechRaf = requestAnimationFrame(tick);
      return {
        stop: () => {
          stopSpeech(false);
          if (brain.state === 'speaking') brain.setState('awake');
        },
        seekChar: (i) => sync.seekChar(i),
        done,
      };
    },

    /** 更换眼镜 / 服装，见 GLASSES、OUTFITS */
    setLook: (look) => stage.setLook({ ...DEFAULT_LOOK, ...look }),

    /** 减少动画；传 null 恢复跟随系统设置 */
    setReducedMotion(v) {
      rmOverride = v ?? undefined;
      applyRM();
    },

    /** 页面内容在角色哪一侧：-1 左，1 右，0 正对用户 */
    setFacing: (f) => (brain.facing = f),

    /** 暂停 / 恢复渲染（隐藏角色时调用以节省电量；标签页不可见时会自动暂停） */
    pause() {
      stage.running = false;
    },
    resume() {
      if (stage.running) return;
      stage.running = true;
      stage.timer.reset?.();
      requestAnimationFrame(stage._loop);
    },

    /**
     * 订阅事件：
     *  'state'    { state, prev, variant }  状态变化
     *  'reaction' 'pokeHead' | 'pokeBody' | 'pokeArm' | 'grumpy'  被点击后的反应
     *  'autorest' 空闲后自动入睡
     * @returns {() => void} 取消订阅
     */
    on: (evt, cb) => brain.on(evt, cb),

    /** 角色头部在页面中的位置（用于对齐气泡） */
    headPosition: () => stage.headScreenPos(),

    destroy() {
      stopSpeech(false);
      clearTimeout(brain._autoReturn);
      mq.removeEventListener?.('change', applyRM);
      detach();
      stage.destroy();
    },
  };
  return api;
}
