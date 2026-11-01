"""External chat-completions API only. No local model or scripted fallback."""
from __future__ import annotations

import json
import os
import ssl
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


class RemoteAPIError(RuntimeError):
    pass


_credits_runtime_key = ""


def set_credits_runtime_key(key: str) -> None:
    """Keep a verified browser-supplied key in this server process only."""
    global _credits_runtime_key
    _credits_runtime_key = key


class RemoteDoctorProvider:
    def __init__(self, key_override: str | None = None):
        self.provider = os.environ.get("MEDREP_API_PROVIDER", "credits").lower().strip()
        if self.provider == "credits":
            self.url = os.environ.get("MEDREP_CHAT_API_URL", "https://api.openai-next.com/v1/chat/completions")
            self.model = os.environ.get("MEDREP_CHAT_MODEL", "deepseek-v4.1-flash")
            self.key = key_override if key_override is not None else (_credits_runtime_key or os.environ.get("OPENAI_NEXT_API_KEY", ""))
            self.key_name = "OPENAI_NEXT_API_KEY"
        elif self.provider == "minimax":
            cfg = PROJECT_CONFIG["llm"]
            self.url = os.environ.get("MEDREP_CHAT_API_URL", cfg["base_url"])
            self.model = os.environ.get("MEDREP_CHAT_MODEL", cfg["model"])
            self.key = os.environ.get(cfg.get("api_key_env", "MINIMAX_API_KEY"), "")
            self.key_name = cfg.get("api_key_env", "MINIMAX_API_KEY")
        elif self.provider == "openai":
            self.url = os.environ.get("MEDREP_CHAT_API_URL", "https://api.openai.com/v1/chat/completions")
            self.model = os.environ.get("MEDREP_CHAT_MODEL", "")
            self.key = os.environ.get("OPENAI_API_KEY", "")
            self.key_name = "OPENAI_API_KEY"
        elif self.provider == "custom":
            self.url = os.environ.get("MEDREP_CHAT_API_URL", "")
            self.model = os.environ.get("MEDREP_CHAT_MODEL", "")
            self.key = os.environ.get("MEDREP_CHAT_API_KEY", "")
            self.key_name = "MEDREP_CHAT_API_KEY"
        else:
            raise RemoteAPIError("MEDREP_API_PROVIDER 仅支持 credits、minimax、openai 或 custom")

    def readiness(self):
        missing = []
        if not self.key:
            missing.append(self.key_name)
        if not self.model:
            missing.append("MEDREP_CHAT_MODEL")
        if not self.url:
            missing.append("MEDREP_CHAT_API_URL")
        return {"ready": not missing, "provider": self.provider, "model": self.model,
                "missing": missing}

    def chat(self, system: str, user: str, *, max_tokens=180, temperature=0.45, on_delta=None, fast=False) -> str:
        readiness = self.readiness()
        if not readiness["ready"]:
            raise RemoteAPIError("未配置外部模型 API：" + "、".join(readiness["missing"]))
        body = {
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        thinking = os.environ.get("MEDREP_CHAT_THINKING", "")
        if thinking in ("enabled", "disabled"):
            body["thinking"] = {"type": thinking}
        elif fast and self.provider == "credits" and self.model.startswith("deepseek"):
            body["thinking"] = {"type": "disabled"}
        if on_delta:
            body["stream"] = True
        req = urllib.request.Request(
            self.url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + self.key,
                     "User-Agent": "MedRepCoach/0.1"},
        )
        try:
            tls = ssl.create_default_context()
            # Some macOS Python installers have no bundled CA path, although the
            # system curl trust store is available at /etc/ssl/cert.pem.
            if not ssl.get_default_verify_paths().cafile and Path("/etc/ssl/cert.pem").is_file():
                tls.load_verify_locations(cafile="/etc/ssl/cert.pem")
            with urllib.request.urlopen(req, timeout=45, context=tls) as response:
                if on_delta:
                    content = ""
                    for line in response:
                        line = line.decode("utf-8").strip()
                        if not line.startswith("data:"):
                            continue
                        payload = line[5:].strip()
                        if payload == "[DONE]":
                            break
                        item = json.loads(payload)
                        if item.get("error"):
                            raise RemoteAPIError("医生流式生成失败")
                        for choice in item.get("choices", []):
                            delta = choice.get("delta", {}).get("content") or ""
                            if delta:
                                content += delta
                                on_delta(delta)
                    if not content.strip():
                        raise RemoteAPIError("医生未返回可用文本")
                    return content.strip()
                data = json.load(response)
        except urllib.error.HTTPError as exc:
            detail = exc.read(500).decode("utf-8", "ignore")
            raise RemoteAPIError(f"{self.provider} API 返回 HTTP {exc.code}：{detail[:180]}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RemoteAPIError(f"{self.provider} API 连接失败或超时") from exc
        except json.JSONDecodeError as exc:
            raise RemoteAPIError(f"{self.provider} API 返回的内容不是 JSON") from exc
        if data.get("base_resp", {}).get("status_code") not in (None, 0):
            raise RemoteAPIError(f"{self.provider} API 返回业务错误：{data['base_resp'].get('status_msg', 'unknown')}")
        if data.get("error"):
            raise RemoteAPIError(f"{self.provider} API 返回错误：{str(data['error'])[:180]}")
        try:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(x.get("text", "") for x in content if isinstance(x, dict))
            if not isinstance(content, str) or not content.strip():
                raise ValueError("empty content")
            return content.strip()
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise RemoteAPIError(f"{self.provider} API 未返回可用文本") from exc
