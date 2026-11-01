'use client';
import { useEffect, useRef, useState } from 'react';
type Recognition = { lang: string; continuous: boolean; interimResults: boolean; start(): void; stop(): void; abort(): void; onresult: ((e: { resultIndex: number; results: { length: number; [i: number]: { isFinal: boolean; [j: number]: { transcript: string } } } }) => void) | null; onerror: ((e: { error: string }) => void) | null; onend: (() => void) | null };
export function SpeechInput({ disabled, onText, testOnly=true }: { disabled: boolean; onText: (text: string) => void; testOnly?:boolean }) {
  const [supported, setSupported] = useState(false), [active, setActive] = useState(false), [status, setStatus] = useState('');
  const recognition = useRef<Recognition | null>(null); const receive = useRef(onText); receive.current = onText;
  useEffect(() => { const w = window as unknown as { SpeechRecognition?: new() => Recognition; webkitSpeechRecognition?: new() => Recognition }; setSupported(Boolean(w.SpeechRecognition || w.webkitSpeechRecognition)); return () => recognition.current?.abort(); }, []);
  function start() {
    const w = window as unknown as { SpeechRecognition?: new() => Recognition; webkitSpeechRecognition?: new() => Recognition }; const Factory = w.SpeechRecognition || w.webkitSpeechRecognition; if (!Factory) return;
    const r = new Factory(); recognition.current = r; r.lang = 'zh-CN'; r.continuous = true; r.interimResults = false;
    r.onresult = event => { for (let i = event.resultIndex; i < event.results.length; i++) if (event.results[i].isFinal) receive.current(event.results[i][0].transcript); };
    r.onerror = () => { setActive(false); setStatus('语音输入未完成，请检查浏览器麦克风权限，或继续输入文字。已转写的文字仍保留。'); };
    r.onend = () => { setActive(false); setStatus('已停止。请核对转写文字，再确认保存。'); };
    try { r.start(); setActive(true); setStatus('正在听，请连续说完这次拜访。'); } catch { setStatus('当前浏览器未能启动语音输入，可继续用文字。'); }
  }
  return <div><button className="secondary" disabled={disabled || !supported} onClick={() => active ? recognition.current?.stop() : start()}>{active ? '结束口述' : testOnly ? '开始语音输入（虚构测试）' : '开始语音输入'}</button><small>{supported ? (testOnly ? '由浏览器提供转写，可能使用其语音服务；只说虚构测试内容。转写后由你核对，不会自动提交。' : '由浏览器语音服务转写，先核对文字再保存；请勿口述患者身份信息。') : '当前浏览器没有可用的语音转写接口，请整段输入文字。'}</small>{status && <p role="status">{status}</p>}</div>;
}
