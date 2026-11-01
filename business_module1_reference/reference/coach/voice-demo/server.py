#!/usr/bin/env python3
"""Local trial server for the simulated hospital visit."""
from __future__ import annotations

import argparse
import realtime_voice
import json
import mimetypes
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from doctor_engine import DoctorState, SCENARIOS
from innovent_scenarios import PROFILE
from asr_provider import ASR_MODEL, transcribe
from remote_provider import RemoteDoctorProvider, RemoteAPIError, set_credits_runtime_key
from score_engine import SCORECARD, assess_with_api
from tts_provider import DEFAULT_VOICE, PREVIEW_TEXT, VOICES, SpeechError, edge_tts, synthesize, audio_type

SESSIONS: dict[str, dict] = {}
LOCK = threading.RLock()
STATIC = {"/realtime-voice.js":"realtime-voice.js","/event-stream.js": "event-stream.js","/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/app.js": "app.js", "/speech-loop.js": "speech-loop.js", "/radar.js": "radar.js", "/mic-loop.js": "mic-loop.js", "/pcm-worklet.js": "pcm-worklet.js"}


def provider_mode():
    return RemoteDoctorProvider().provider


def now():
    return datetime.now(timezone.utc).isoformat()


def finish_session(session, reason):
    """Caller holds LOCK. Deadline timer never waits for an external model."""
    if not session["ended"]:
        session["ended"] = True
        session["end_reason"] = reason
        session["ended_at"] = now()
        session["timer"].cancel()


def expire_session(session_id):
    with LOCK:
        session = SESSIONS.get(session_id)
        if session:
            finish_session(session, "timer")


def session_view(session):
    """Caller holds LOCK; always check the deadline, even if timer is delayed."""
    if not session["ended"] and time.monotonic() >= session["deadline_mono"]:
        finish_session(session, "timer")
    return {"finished": session["ended"], "end_reason": session.get("end_reason"),
            "duration_seconds": session["duration_seconds"],
            "remaining_seconds": max(0, session["deadline_mono"] - time.monotonic()),
            "deadline_at": session["deadline_at"], "server_now": time.time(),
            "transcript": [dict(m) for m in session["transcript"]]}


class Handler(BaseHTTPRequestHandler):
    def stream_voice(self):
        # Native audio GETs carry Sec-Fetch-Site, not necessarily Origin.
        host = f"127.0.0.1:{self.server.server_port}"
        if self.headers.get("Host") != host or not (self.same_origin() or self.headers.get("Sec-Fetch-Site") == "same-origin"):
            return self.json_response(403, {"error": "请从本机演示页面请求语音"})
        started = False
        try:
            data = {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}
            voice = data.get("voice", DEFAULT_VOICE)
            session = None
            if data.get("preview") == "true":
                speech_text = PREVIEW_TEXT
            else:
                with LOCK:
                    session = SESSIONS.get(data.get("session_id", ""))
                    if not session or session_view(session)["finished"]:
                        raise ValueError("会话已结束或失效")
                    if data.get("speech_id"):
                        speech_text = session.get("speech_segments", {}).get(data["speech_id"])
                        if not speech_text:
                            raise ValueError("无效的医生语音片段")
                    else:
                        index = int(data.get("message_index", -1))
                        transcript = session["transcript"]
                        if index < 0 or index >= len(transcript) or transcript[index]["role"] != "医生":
                            raise ValueError("只能朗读医生发言")
                        speech_text = transcript[index]["text"]
            def write_audio(chunk):
                nonlocal started
                if session:
                    with LOCK:
                        if session_view(session)["finished"]:
                            raise SpeechError("会话已结束")
                if not started:
                    self.protocol_version = "HTTP/1.1"
                    self.send_response(200)
                    self.send_header("Content-Type", audio_type(voice))
                    self.send_header("Transfer-Encoding", "chunked")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.close_connection = True
                    started = True
                self.wfile.write(f"{len(chunk):x}\r\n".encode() + chunk + b"\r\n")
                self.wfile.flush()
            synthesize(speech_text, voice, on_audio=write_audio)
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (ValueError, SpeechError, OSError) as exc:
            if not started:
                self.json_response(503 if isinstance(exc, SpeechError) else 400, {"error": str(exc)})
            # No terminating chunk on failure: browsers must not treat a cut-off
            # utterance as a successfully completed audio response.
            self.close_connection = True

    def begin_events(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

    def event(self, kind, data):
        self.wfile.write(("data: " + json.dumps({"type": kind, **data}, ensure_ascii=False) + "\n\n").encode())
        self.wfile.flush()

    def stream_turn(self, data):
        text = str(data.get("text", "")).strip()
        if not text or len(text) > 1200:
            raise ValueError("请提交 1–1200 字的发言")
        with LOCK:
            session = SESSIONS.get(str(data.get("session_id", "")))
            if not session:
                raise ValueError("会话已失效")
            snap = session_view(session)
            if snap["finished"]:
                return self.json_response(200, snap)
            if session["pending"]:
                return self.json_response(409, {"error": "医生正在回应，请稍候"})
            rep = {"role": "药代", "text": text, "at": now(), "input_method": str(data.get("input_method", "text"))[:20]}
            session["transcript"].append(rep)
            session["pending"] = True
            history = [dict(m) for m in session["transcript"]]
        started = time.monotonic()
        doctor = None
        def sentence_ready(sentence):
            nonlocal doctor
            with LOCK:
                if session_view(session)["finished"]:
                    raise RemoteAPIError("会话已结束")
                if doctor is None:
                    doctor = {"role": "医生", "text": "", "at": now(), "mode": provider_mode()}
                    session["transcript"].append(doctor)
                doctor["text"] += sentence
                token = uuid.uuid4().hex
                session.setdefault("speech_segments", {})[token] = sentence
                snapshot = session_view(session)
            self.event("sentence", {"text": sentence, "speech_id": token, "transcript": snapshot["transcript"],
                                    "elapsed_ms": round((time.monotonic()-started)*1000)})
        self.begin_events()
        try:
            self.event("accepted", {"rep": rep})
            session["doctor"].respond(text, history, int(snap["remaining_seconds"]), on_sentence=sentence_ready)
            with LOCK:
                if session["doctor"].finished:
                    finish_session(session, "doctor")
                snapshot = session_view(session)
            self.event("done", {**snapshot, "generation_ms": round((time.monotonic()-started)*1000)})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as exc:
            try:
                self.event("error", {"error": str(exc) if isinstance(exc, RemoteAPIError) else "医生生成中断，请重试"})
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            with LOCK:
                session["pending"] = False

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")

    def json_response(self, status, obj):
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def audio_response(self, payload, voice=DEFAULT_VOICE):
        self.send_response(200)
        self.send_header("Content-Type", audio_type(voice))
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def same_origin(self):
        expected = f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Origin") == f"http://{expected}" and self.headers.get("Host") == expected

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        limit = 6_100_000 if urlparse(self.path).path.startswith("/api/transcribe") else 100_000
        if length > limit or length < 0:
            raise ValueError("请求过大")
        return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/voice-stream":
            return self.stream_voice()
        if path == "/api/config":
            return self.json_response(200, {
                "scenarios": [{k: v[k] for k in ("id", "title", "tag", "public", "source_scenario_ids", "profile_id", "sources", "design_note") if k in v}
                              for v in SCENARIOS.values()],
                "profile": PROFILE,
                "voice_revision": 9, "realtime": realtime_voice.public_config(), "recognition": {"engine": "qwen_api" if provider_mode() == "credits" else "browser",
                                "model": ASR_MODEL},
                "scorecard": {"id": SCORECARD["id"], "status": SCORECARD["status"],
                              "dimensions": [{"id": d["id"], "name": d["name"], "domain": d["domain"]}
                                             for d in SCORECARD["dimensions"]]},
                "llm_available": RemoteDoctorProvider().readiness()["ready"],
                "provider_mode": provider_mode(),
                "api_status": RemoteDoctorProvider().readiness(),
                "voice": {"available": True, "engine": "Qwen3 TTS / Edge 备用",
                          "default": DEFAULT_VOICE, "choices": VOICES},
                "voice_note": "浏览器语音识别仅在支持 Web Speech API 的浏览器可用；也可键入文字试用。",
            })
        if path == "/api/health":
            return self.json_response(200, {"ok": True, "scorecard_id": SCORECARD["id"]})
        if path.startswith("/api/session/"):
            with LOCK:
                session = SESSIONS.get(path.rsplit("/", 1)[-1])
                if not session:
                    return self.json_response(404, {"error": "会话已失效"})
                snapshot = session_view(session)
            return self.json_response(200, snapshot)
        name = STATIC.get(path)
        if not name:
            self.send_error(404)
            return
        data = (HERE / name).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        try:
            data = self.read_json()
            path = urlparse(self.path).path
            if path == "/api/realtime/credentials":
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机页面配置百炼密钥"})
                return self.json_response(200, realtime_voice.configure(data))
            if path == "/api/realtime/disconnect":
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机页面操作"})
                realtime_voice.clear_config()
                return self.json_response(200, realtime_voice.public_config())
            if path in ("/api/turn/stream", "/api/transcribe/stream"):
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机演示页面请求"})
                if path == "/api/turn/stream":
                    return self.stream_turn(data)
                with LOCK:
                    session = SESSIONS.get(str(data.get("session_id", "")))
                    if not session:
                        raise ValueError("会话已失效")
                    if session_view(session)["finished"]:
                        return self.json_response(200, session_view(session))
                self.begin_events()
                try:
                    def draft(text):
                        with LOCK:
                            if session_view(session)["finished"]:
                                raise RemoteAPIError("会话已结束")
                        self.event("draft", {"text": text})
                    def asr_status(info):
                        with LOCK:
                            if session_view(session)["finished"]:
                                raise RemoteAPIError("会话已结束")
                        self.event("asr_status", info)
                    kwargs = {"on_status": asr_status} if data.get("engine") == "auto" else {}
                    text = transcribe(data.get("audio", ""), on_draft=draft, engine=str(data.get("engine", "qwen")), **kwargs)
                    with LOCK:
                        finished = session_view(session)["finished"]
                    self.event("done", {"text": text, "finished": finished})
                except (BrokenPipeError, ConnectionResetError):
                    pass
                except Exception as exc:
                    try:
                        self.event("error", {"error": str(exc) if isinstance(exc, (ValueError, RemoteAPIError)) else "转写中断"})
                    except (BrokenPipeError, ConnectionResetError):
                        pass
                return
            if path == "/api/transcribe":
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机演示页面请求转写"})
                with LOCK:
                    session = SESSIONS.get(str(data.get("session_id", "")))
                    if not session:
                        raise ValueError("会话已失效")
                    snapshot = session_view(session)
                    if snapshot["finished"]:
                        return self.json_response(200, snapshot)
                text = transcribe(data.get("audio", ""))
                with LOCK:
                    snapshot = session_view(session)
                    if snapshot["finished"]:
                        return self.json_response(200, snapshot)
                return self.json_response(200, {"text": text, "model": ASR_MODEL, "finished": False})
            if path == "/api/voice":
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机演示页面请求语音"})
                voice = str(data.get("voice", DEFAULT_VOICE))
                if data.get("preview") is True:
                    speech_text = PREVIEW_TEXT
                else:
                    with LOCK:
                        session = SESSIONS.get(str(data.get("session_id", "")))
                        if data.get("speech_id"):
                            if not session or session_view(session)["finished"]:
                                raise ValueError("会话已结束")
                            speech_text = session.get("speech_segments", {}).get(str(data["speech_id"]))
                            if not speech_text:
                                raise ValueError("无效的医生语音片段")
                        else:
                            speech_text = None
                        index = int(data.get("message_index", -1))
                        transcript = session["transcript"] if session else []
                        if speech_text is None:
                            if index < 0 or index >= len(transcript) or transcript[index]["role"] != "医生":
                                raise ValueError("只能朗读当前会话的医生发言")
                            speech_text = transcript[index]["text"]
                return self.audio_response(synthesize(speech_text, voice), voice)
            if path == "/api/credentials":
                if not self.same_origin():
                    return self.json_response(403, {"error": "请从本机演示页面提交密钥"})
                if provider_mode() != "credits":
                    raise ValueError("当前未选择 Credits 接口")
                key = str(data.get("api_key", "")).strip()
                if not key.startswith("sk-") or len(key) < 12 or len(key) > 256:
                    raise ValueError("请填入 Credits 控制台生成的完整 sk- 开头 API Key；活动 ID 或 UUID 不能用于调用")
                probe = RemoteDoctorProvider(key_override=key)
                try:
                    probe.chat("你是接口连通性检查。", "只回复：连接成功", max_tokens=160, temperature=0.45)
                except RemoteAPIError as exc:
                    if "HTTP 401" in str(exc):
                        raise RemoteAPIError("Credits 拒绝了这个 API Key，请在控制台重新复制完整密钥") from exc
                    if "HTTP 403" in str(exc):
                        raise RemoteAPIError("Credits 网关拒绝了请求，请稍后重试或联系平台支持") from exc
                    raise RemoteAPIError("Credits 模型验证失败：" + str(exc).replace(key, "[REDACTED]")[:180]) from exc
                set_credits_runtime_key(key)
                return self.json_response(200, {"ready": True, "model": probe.model})
            if path == "/api/session":
                duration = data.get("duration_seconds", 300)
                if isinstance(duration, bool) or not isinstance(duration, int) or not 30 <= duration <= 3600:
                    raise ValueError("拜访时长应为 30 秒至 60 分钟")
                readiness = RemoteDoctorProvider().readiness()
                if not readiness["ready"]:
                    raise RemoteAPIError("医生 API 未配置：" + "、".join(readiness["missing"]))
                sid = str(data.get("scenario_id", ""))
                if sid not in SCENARIOS:
                    raise ValueError("未知训练场景")
                # Give the doctor the actual chosen time, not a fixed 5/8-minute script.
                scenario = {**SCENARIOS[sid], "public": dict(SCENARIOS[sid]["public"])}
                scenario["public"]["setting"] = scenario["public"]["setting"].split("，约")[0] + f"；本次约定 {duration / 60:g} 分钟"
                session_id = uuid.uuid4().hex
                doctor_state = DoctorState(scenario)
                started = time.monotonic()
                opening, mode = doctor_state.opening()
                generation_ms = round((time.monotonic() - started) * 1000)
                transcript = [{"role": "医生", "text": opening, "at": now(), "mode": mode}]
                timer = threading.Timer(duration, expire_session, args=(session_id,))
                timer.daemon = True
                with LOCK:
                    SESSIONS[session_id] = {"scenario": scenario, "doctor": doctor_state,
                        "transcript": transcript, "duration_seconds": duration,
                        "deadline_mono": time.monotonic() + duration, "deadline_at": time.time() + duration,
                        "timer": timer, "ended": False, "pending": False, "score_lock": threading.Lock()}
                    timing = session_view(SESSIONS[session_id])
                timer.start()
                return self.json_response(200, {"session_id": session_id, "card": scenario["public"],
                                                "doctor": transcript[0], "mode": provider_mode(),
                                                "generation_ms": generation_ms, **timing})
            if path == "/api/turn":
                session_id = str(data.get("session_id", ""))
                text = str(data.get("text", "")).strip()
                if not text or len(text) > 1200:
                    raise ValueError("请提交 1–1200 字的发言")
                with LOCK:
                    session = SESSIONS.get(session_id)
                    if not session:
                        raise ValueError("会话已失效，请重新开始")
                    snapshot = session_view(session)
                    if snapshot["finished"]:
                        return self.json_response(200, snapshot)
                    if session["pending"]:
                        return self.json_response(409, {"error": "医生正在回应，请稍候"})
                    rep = {"role": "药代", "text": text, "at": now(),
                           "input_method": str(data.get("input_method", "text"))[:20]}
                    session["transcript"].append(rep)
                    session["pending"] = True
                    history = [dict(m) for m in session["transcript"]]
                    remaining = int(snapshot["remaining_seconds"])
                started = time.monotonic()
                try:
                    answer, mode, warning = session["doctor"].respond(text, history, remaining)
                except Exception:
                    with LOCK:
                        session["pending"] = False
                    raise
                generation_ms = round((time.monotonic() - started) * 1000)
                with LOCK:
                    session["pending"] = False
                    snapshot = session_view(session)
                    if snapshot["finished"]:
                        return self.json_response(200, snapshot)
                    doctor = {"role": "医生", "text": answer, "at": now(), "mode": mode}
                    session["transcript"].append(doctor)
                    if session["doctor"].finished:
                        finish_session(session, "doctor")
                    snapshot = session_view(session)
                return self.json_response(200, {"rep": rep, "doctor": doctor,
                                                "generation_ms": generation_ms,
                                                "warning": warning, **snapshot})
            if path == "/api/end":
                with LOCK:
                    session = SESSIONS.get(str(data.get("session_id", "")))
                    if not session:
                        raise ValueError("会话已失效，请重新开始")
                    session_view(session)
                    finish_session(session, "user")
                    snapshot = session_view(session)
                return self.json_response(200, snapshot)
            if path == "/api/score":
                session = SESSIONS.get(str(data.get("session_id", "")))
                if not session:
                    raise ValueError("会话已失效，请重新开始")
                with LOCK:
                    session_view(session)
                    finish_session(session, "user")
                    transcript = [dict(m) for m in session["transcript"]]
                corrections = data.get("corrections", {})
                if not isinstance(corrections, dict):
                    raise ValueError("转写修订格式错误")
                for key, revised in corrections.items():
                    idx = int(key)
                    if idx < 0 or idx >= len(transcript) or transcript[idx]["role"] != "药代":
                        raise ValueError("只能修订自己的发言")
                    if not isinstance(revised, str) or not revised.strip() or len(revised) > 1200:
                        raise ValueError("修订发言长度不正确")
                    transcript[idx]["text"] = revised.strip()
                    transcript[idx]["corrected"] = True
                # Serialize scoring of this session only; never block timer/turns.
                cache_key = json.dumps(transcript, ensure_ascii=False, sort_keys=True)
                with session["score_lock"]:
                    if session.get("score_key") == cache_key:
                        report = dict(session["score_report"])
                    else:
                        report = assess_with_api(transcript, session["scenario"]["id"], session["scenario"].get("facts"))
                        session["score_key"], session["score_report"] = cache_key, report
                report = dict(report)
                report["transcript"] = transcript
                report["session"] = {"duration_seconds": session["duration_seconds"], "end_reason": session["end_reason"]}
                report["scenario_sources"] = session["scenario"].get("sources", [])
                return self.json_response(200, report)
            self.send_error(404)
        except RemoteAPIError as exc:
            self.json_response(503, {"error": str(exc)})
        except SpeechError as exc:
            self.json_response(503, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError, KeyError) as exc:
            self.json_response(400, {"error": str(exc)})
        except Exception as exc:
            self.json_response(500, {"error": f"服务器错误：{type(exc).__name__}"})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    def active_session(sid):
        with LOCK:
            session = SESSIONS.get(sid)
            return bool(session and not session_view(session)["finished"])
    def speech_text(args):
        if args.get("preview") == "true": return PREVIEW_TEXT
        with LOCK:
            session = SESSIONS.get(args.get("session_id", ""))
            if not session or session_view(session)["finished"]: raise ValueError("会话已结束")
            if args.get("speech_id"):
                text = session.get("speech_segments", {}).get(args["speech_id"])
            else:
                index = int(args.get("message_index", -1)); messages = session["transcript"]
                text = messages[index]["text"] if 0 <= index < len(messages) and messages[index]["role"] == "医生" else None
            if not text or len(text)>220: raise ValueError("只能朗读当前会话的医生发言")
            return text
    realtime_voice.start_bridge(args.port+1, f"http://127.0.0.1:{args.port}", active_session, speech_text)
    readiness = RemoteDoctorProvider().readiness()
    print(f"MedRep voice demo: http://127.0.0.1:{args.port} (API: {provider_mode()}, ready: {readiness['ready']})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
