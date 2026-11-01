/**
 * 口型驱动
 *
 * 浏览器的 speechSynthesis 不暴露音频数据，无法做真实振幅分析。
 * 这里把要说的文本切成音节时间轴（中文按字、英文按词长、标点产生停顿），
 * 并用 TTS 的 boundary 事件随时校正位置，让口型与实际语音保持同步。
 * 若接入真实音频流（如服务端 TTS），改用 AnalyserLipSync 获取真实振幅。
 */

const PAUSE_LONG = /[。！？!?；;…]/;
const PAUSE_SHORT = /[，、,：:\s]/;
const CJK = /[\u3400-\u9fff]/;

export class TextLipSync {
  constructor(text, rate = 1) {
    this.items = [];
    let t = 0;
    let i = 0;
    while (i < text.length) {
      const ch = text[i];
      if (PAUSE_LONG.test(ch)) {
        this.items.push({ start: t, dur: 0.38 / rate, amp: 0, char: i });
        t += 0.38 / rate;
        i++;
      } else if (PAUSE_SHORT.test(ch)) {
        this.items.push({ start: t, dur: 0.16 / rate, amp: 0, char: i });
        t += 0.16 / rate;
        i++;
      } else if (CJK.test(ch)) {
        const dur = (0.19 + Math.random() * 0.06) / rate;
        this.items.push({ start: t, dur, amp: 0.55 + Math.random() * 0.45, char: i });
        t += dur;
        i++;
      } else {
        // 拉丁字母/数字：按词，约 3 个字母一个音节
        let j = i;
        while (j < text.length && /[A-Za-z0-9.%\-+]/.test(text[j])) j++;
        if (j === i) j = i + 1;
        const syl = Math.max(1, Math.round((j - i) / 3));
        for (let s = 0; s < syl; s++) {
          const dur = (0.13 + Math.random() * 0.05) / rate;
          this.items.push({ start: t, dur, amp: 0.45 + Math.random() * 0.4, char: i });
          t += dur;
        }
        i = j;
      }
    }
    this.duration = t;
    this.time = 0;
  }

  /** 收到 boundary 事件：把时间轴对齐到该字符 */
  seekChar(charIndex) {
    const it = this.items.find((x) => x.char >= charIndex);
    if (it && Math.abs(it.start - this.time) > 0.25) this.time = it.start;
  }

  /** 推进时间并返回 0..1 的张口程度 */
  step(dt) {
    this.time += dt;
    const t = this.time;
    // 二分查找当前音节
    let lo = 0;
    let hi = this.items.length - 1;
    while (lo < hi) {
      const mid = (lo + hi + 1) >> 1;
      if (this.items[mid].start <= t) lo = mid;
      else hi = mid - 1;
    }
    const it = this.items[lo];
    if (!it || t > this.duration) return 0;
    const p = (t - it.start) / it.dur;
    if (p < 0 || p > 1) return 0;
    return it.amp * Math.pow(Math.sin(Math.PI * p), 0.7);
  }

  /** 已说出的字符数（用于逐字显示字幕） */
  spokenChars() {
    let n = 0;
    for (const it of this.items) {
      if (it.start <= this.time) n = it.char + 1;
      else break;
    }
    return n;
  }
}

/** 真实音频振幅驱动（用于 <audio> 或 MediaStream） */
export class AnalyserLipSync {
  constructor(audioCtx, sourceNode) {
    this.analyser = audioCtx.createAnalyser();
    this.analyser.fftSize = 1024;
    sourceNode.connect(this.analyser);
    this.buf = new Float32Array(this.analyser.fftSize);
    this.level = 0;
  }
  step() {
    this.analyser.getFloatTimeDomainData(this.buf);
    let sum = 0;
    for (let i = 0; i < this.buf.length; i++) sum += this.buf[i] * this.buf[i];
    const rms = Math.sqrt(sum / this.buf.length);
    const target = Math.min(1, Math.max(0, (rms - 0.01) * 9));
    this.level += (target - this.level) * (target > this.level ? 0.6 : 0.25);
    return this.level;
  }
}
