/* Continuous, hands-free input. Playback suspends recognition to avoid echo.
 * A final transcript is submitted only after a quiet gap; interim text stays draft.
 */
class SpeechLoop {
  constructor({Recognition, onDraft, onUtterance, onState, onError, gapMs = 5000}) {
    Object.assign(this, {Recognition, onDraft, onUtterance, onState, onError, gapMs});
    this.enabled = false; this.suspended = true; this.rec = null;
    this.finalText = ''; this.interimText = ''; this.timer = null; this.restart = null;
  }
  enable() { this.enabled = true; this.resume(); }
  disable() { this.enabled = false; this.suspend(); this.onState('paused'); }
  suspend() {
    this.suspended = true; clearTimeout(this.timer); clearTimeout(this.restart);
    const old = this.rec; this.rec = null;
    if (old) { try { old.abort(); } catch (_) {} }
  }
  resume() {
    this.suspended = false;
    if (this.enabled && !this.rec) this.listen();
  }
  listen() {
    if (!this.enabled || this.suspended || this.rec) return;
    this.finalText = ''; this.interimText = '';
    const rec = new this.Recognition(); this.rec = rec;
    rec.lang = 'zh-CN'; rec.continuous = true; rec.interimResults = true; rec.maxAlternatives = 1;
    rec.onstart = () => { if (this.rec === rec) this.onState('listening'); };
    rec.onresult = ev => {
      if (this.rec !== rec || !this.enabled || this.suspended) return;
      clearTimeout(this.timer); this.interimText = '';
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        if (ev.results[i].isFinal) this.finalText += ev.results[i][0].transcript;
        else this.interimText += ev.results[i][0].transcript;
      }
      this.onDraft(this.finalText + this.interimText);
      if (this.finalText.trim() && !this.interimText.trim()) this.queueFlush();
    };
    rec.onerror = ev => {
      if (this.rec !== rec) return;
      if (ev.error === 'no-speech' || ev.error === 'aborted') return;
      this.disable();
      this.onError(ev.error === 'not-allowed' || ev.error === 'service-not-allowed'
        ? '麦克风或语音识别未获授权，请允许麦克风后重新开启连续对话。'
        : `语音识别暂不可用（${ev.error}），请重试连续对话或使用文字。`);
    };
    rec.onend = () => {
      if (this.rec !== rec) return;
      this.rec = null;
      if (!this.enabled || this.suspended) return;
      if (this.interimText.trim()) {
        this.disable(); this.onError('语音识别提前结束，草稿已保留；可修订后发送，再开启连续对话。');
      } else if (this.finalText.trim()) this.queueFlush();
      else this.restart = setTimeout(() => this.listen(), 300);
    };
    try { rec.start(); } catch (e) { this.rec = null; this.disable(); this.onError(e.message); }
  }
  queueFlush() {
    clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      if (!this.enabled || this.suspended) return;
      const text = this.finalText.trim();
      if (!text) return;
      this.suspend(); this.finalText = ''; this.interimText = '';
      this.onUtterance(text);
    }, this.gapMs);
  }
}
if (typeof module !== 'undefined') module.exports = {SpeechLoop};
