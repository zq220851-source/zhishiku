"""Exact-text Mandarin speech for synthetic doctor utterances.

Uses Credits Qwen3 TTS for the selected Maia/Andre voices and Edge for backups.
The remote doctor generates the words; this module only reads those words aloud.
"""
from __future__ import annotations

import asyncio
import io
import json
import ssl
import urllib.request
import wave
from remote_provider import RemoteDoctorProvider

try:
    import edge_tts
except ImportError:
    edge_tts = None


VOICES = (
    {"id": "Maia", "label": "四月 Maia · 女医生 / 已选"},
    {"id": "Andre", "label": "安德雷 Andre · 男医生 / 已选"},
    {"id": "zh-CN-XiaoxiaoNeural", "label": "备用 · 晓晓 · 女声 / 温和普通话"},
    {"id": "zh-CN-XiaoyiNeural", "label": "备用 · 晓伊 · 女声 / 明快普通话"},
    {"id": "zh-CN-YunxiNeural", "label": "备用 · 云希 · 男声 / 亲和普通话"},
    {"id": "zh-CN-YunjianNeural", "label": "备用 · 云健 · 男声 / 稳重普通话"},
)
VOICE_IDS = {item["id"] for item in VOICES}
DEFAULT_VOICE = VOICES[0]["id"]
PREVIEW_TEXT = "您好，我是今天的模拟医生。我们先聊您关心的问题。"


class SpeechError(RuntimeError):
    pass


async def _synthesize(text: str, voice: str, on_audio=None) -> bytes:
    chunks = bytearray()
    async for part in edge_tts.Communicate(text, voice, rate="-5%").stream():
        if part["type"] == "audio":
            chunks.extend(part["data"])
            if len(chunks) > 2_000_000:
                raise SpeechError("语音内容过长")
            if on_audio:
                on_audio(part["data"])
    if len(chunks) < 1024:
        raise SpeechError("语音服务未返回可播放的音频")
    return bytes(chunks)


def synthesize(text: str, voice: str, on_audio=None) -> bytes:
    if voice not in VOICE_IDS:
        raise ValueError("未知音色")
    if not text or len(text) > 220:
        raise ValueError("朗读文字长度不正确")
    if voice in {"Maia", "Andre"}:
        return synthesize_qwen(text, voice, on_audio)
    if edge_tts is None:
        raise SpeechError("缺少备用语音依赖 edge-tts")
    try:
        return asyncio.run(asyncio.wait_for(_synthesize(text, voice, on_audio), timeout=30))
    except (TimeoutError, OSError) as exc:
        raise SpeechError("普通话语音服务连接失败或超时") from exc
    except SpeechError:
        raise
    except Exception as exc:
        raise SpeechError("普通话语音服务暂不可用") from exc


def audio_type(voice):
    return "audio/wav" if voice in {"Maia", "Andre"} else "audio/mpeg"


def synthesize_qwen(text, voice, on_audio=None):
    provider = RemoteDoctorProvider()
    if provider.provider != "credits" or not provider.key:
        raise SpeechError("所选医生音色需要连接 Credits；也可选择备用音色")
    payload = {"model": "qwen3-tts-flash", "input": text, "voice": voice, "response_format": "wav"}
    req = urllib.request.Request("https://api.openai-next.com/v1/audio/speech",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Authorization": "Bearer " + provider.key, "Content-Type": "application/json", "User-Agent": "MedRepCoach/0.1"})
    try:
        tls = ssl.create_default_context()
        if not ssl.get_default_verify_paths().cafile:
            tls.load_verify_locations(cafile="/etc/ssl/cert.pem")
        with urllib.request.urlopen(req, timeout=30, context=tls) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise SpeechError("语音内容过长")
        # Credits currently returns WAV with a streaming placeholder length.
        # Finalize the header before browser playback; do not label it as MP3.
        with wave.open(io.BytesIO(raw)) as source:
            params = source.getparams()
            pcm = source.readframes(source.getnframes())
        if not pcm or len(pcm) % (params.nchannels * params.sampwidth):
            raise SpeechError("语音音频不完整")
        output = io.BytesIO()
        with wave.open(output, "wb") as target:
            target.setnchannels(params.nchannels)
            target.setsampwidth(params.sampwidth)
            target.setframerate(params.framerate)
            target.writeframes(pcm)
        audio = output.getvalue()
    except SpeechError:
        raise
    except Exception as exc:
        raise SpeechError("Credits 医生音色生成失败，请重试或选择备用音色") from exc
    if on_audio:
        on_audio(audio)
    return audio
