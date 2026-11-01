#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Provider 抽象 + 受控提示构造 + 事实校验。

架构（三种 provider 共用同一套检索与校验）：
    检索层 knowledge_retrieval.py → fact bundle（带出处）
        ↓
    提示构造 PromptBuilder → 受控提示（事实 + 角色 + 指令）
        ↓
    Provider → 生成文本
        ↓
    FactGuard → 校验（编造数值 / 绝对化 / 越出检索范围 / 宣称获批）

三种 provider
-------------
VisionTextProvider  —— 通过 matrix describe_images 把提示渲染成图交给 VLM。
                       **当前环境即可用**，无需 API key。
MinimaxTextProvider —— 直连 MiniMax 文本 API（生产路径），需 MINIMAX_API_KEY。
MockProvider        —— 确定性输出，用于单元测试与回归。

为什么要两种真实 provider
--------------------------
「参考数据库」的工程价值在**检索层与校验层**，provider 只是最后一环。
两者共用同一套 prompt 与 guard，所以：
  · 换 provider 不影响医学安全性
  · 生产用文本 API（更准），演示用 VLM（现在就能跑）
"""
import json, os, re, subprocess, sys, hashlib, tempfile

from config import BASE, PATHS
import compliance_rules as _crules


# ============================================================
# 1. Provider 抽象
# ============================================================
class LLMProvider:
    name = "base"

    def available(self):
        raise NotImplementedError

    def generate(self, prompt_text, system=None):
        """返回 (text, meta)"""
        raise NotImplementedError


class MockProvider(LLMProvider):
    """
    确定性输出 —— 用于测试：不依赖网络，可断言。

    ★ 默认行为是**从提示里的事实包拼一个合规回答**，
      而不是返回固定一句话。理由：固定回答与题目不匹配，
      会让知识维度判为「暂不评定」，整条评分链路测不到。
      从事实拼答案才能真正驱动 MED 维度打分。
    """

    name = "mock"

    def __init__(self, responses=None):
        self.responses = responses or []
        self.calls = []

    def available(self):
        return True

    @staticmethod
    def _compose_from_facts(prompt_text):
        """从提示里解析事实，合成一个合规回答"""
        facts = []
        for line in prompt_text.split("\n"):
            m = re.match(r"\[事实\d+\]\s*(.+)", line.strip())
            if m:
                facts.append(m.group(1).strip())
        if not facts:
            return None
        # 取产品/管线/疾病三类事实的核心陈述
        parts = []
        for f in facts[:3]:
            f = f.replace("**", "")
            # 去掉出处尾巴
            f = re.sub(r"（link_type=[^）]*）.*$", "", f)
            parts.append(f.rstrip("。"))
        body = "；".join(parts)
        return (f"{body}。适用范围我要按最新 NMPA 说明书和企业合规版本核实后回复您，"
                f"不能凭印象给您结论。")

    def generate(self, prompt_text, system=None):
        self.calls.append(prompt_text)
        if self.responses:
            return self.responses[min(len(self.calls) - 1, len(self.responses) - 1)], \
                   {"provider": self.name, "mock": True}
        composed = self._compose_from_facts(prompt_text)
        if composed:
            return composed, {"provider": self.name, "mock": True,
                               "composed_from_facts": True}
        return "这个情况我需要按最新 NMPA 说明书和企业合规版本核实后回复您。", \
               {"provider": self.name, "mock": True}


_THINK_RE = re.compile(r"<(think|thinking|reasoning)>.*?</\1>", re.S | re.I)
_THINK_OPEN_RE = re.compile(r"<(think|thinking|reasoning)>.*$", re.S | re.I)


def _strip_reasoning(text):
    """剥离模型的推理内容 → (清洗后的文本, 是否发生过剥离)"""
    if not text:
        return text, False
    had = False
    out = _THINK_RE.sub("", text)
    if out != text:
        had = True
        text = out
    # 未闭合的 think 标签（模型被截断时可能出现）
    out2 = _THINK_OPEN_RE.sub("", text)
    if out2 != text:
        had = True
        text = out2
    return text.strip(), had


class LLMProviderError(RuntimeError):
    """LLM 调用失败 —— 必须让调用方看见，不能静默返回空内容"""

    def __init__(self, message, code=None, provider=None):
        super().__init__(message)
        self.code = code
        self.provider = provider


# MiniMax 业务错误码 → 人话
# ★ 1008 有两个含义（文本 API 与 Agent API 不同），必须说清楚：
#   文本 API：HTTP 402 insufficient_balance_error —— 该 key 对应的计费资源没有可用余额
#   Agent API：可能是 group_id 与 key 不属于同一子账户 → 平台按未认证用户降级限流
_MINIMAX_ERRORS = {
    1002: "限流：请求过快（RPM 超限）。请加入退避与并发限制",
    1004: "认证失败：请检查 API key 与 Authorization 头格式（需 Bearer 前缀）",
    1007: "账户余额已归零：请为该账号充值",
    1008: ("余额/计费资源不足（HTTP 402 insufficient_balance_error）。"
           "★ 注意：sk-api- 是【按量付费 key】，只扣账户余额；"
           "Token Plan / Coding Plan 的额度要用 sk-cp- 开头的【Subscription Key】，"
           "两者不通用 —— 若你的额度在 Token Plan，请从控制台 Billing / Token Plan 页面复制 Subscription Key"),
    1013: "限流：每分钟请求数超限（RPM）。请降低频率或升级套餐",
    2013: "模型名无效：请用 /v1/models 返回的可用模型名",
    2049: "API Key 无效或区域不匹配：国内账号用 api.minimaxi.com，国际账号用 api.minimax.io",
    2069: "该模型已下线：请改用 /v1/models 列表中的其他模型",
}

# ★ 端点与模型名来自配置中心（config.py / config.json），不硬编码
from config import BASE, PATHS, load_config
_CFG, _CFG_SOURCES = load_config()
_LLM_CFG = _CFG["llm"]

_MINIMAX_CHAT_URL = _LLM_CFG["base_url"]
_MINIMAX_MODELS_URL = _LLM_CFG["models_url"]
_MINIMAX_KEY_ENV = _LLM_CFG["api_key_env"]


class MinimaxTextProvider(LLMProvider):
    """
    直连 MiniMax 文本 API —— 生产路径。

    ★ 认证头格式：`Authorization: Bearer <key>`
      （裸 key 不被接受，会返回 1004 login fail）
    ★ 业务错误必须抛出，不能静默返回空内容 ——
      否则「余额不足」会表现为「医生一言不发」，是个哑巴故障。
    """

    name = "minimax_text"

    def __init__(self, api_key=None, model=None,
                 base_url=None, models_url=None):
        self.api_key = api_key or os.environ.get(_MINIMAX_KEY_ENV, "")
        self.model = model or _LLM_CFG.get("model", "MiniMax-M3.1-Flash")
        self.base_url = base_url or _MINIMAX_CHAT_URL
        self.models_url = models_url or _MINIMAX_MODELS_URL
        self.temperature = _LLM_CFG.get("temperature", 0.3)
        self._picked_model = None

    def available(self):
        return bool(self.api_key)

    def list_models(self):
        """列出该 key 可用的模型名"""
        import urllib.request
        req = urllib.request.Request(
            self.models_url,
            headers={"Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m["id"] for m in data.get("data", [])]

    def pick_model(self, max_tries=3):
        """
        惰性挑一个可用模型。

        ★ 模型列表 ≠ 可调用列表：
          某些 key 在 /v1/models 里能看到模型，但调用返回 404 not_found_error
          （如 M2/M2.1 已下线但仍列出）。
          所以必须实测，不能只看列表。

        策略：先试当前模型（默认 MiniMax-M3.1-Flash），失败才顺延到列表里的下一个，
        **最多试 max_tries 个**——不遍历全表，避免慢且浪费配额。
        """
        if self._picked_model:
            return self._picked_model
        try:
            candidates = [self.model] + [m for m in self.list_models() if m != self.model]
        except Exception:
            candidates = [self.model]
        tried = 0
        for m in candidates:
            if tried >= max_tries:
                break
            tried += 1
            old = self.model
            self.model = m
            try:
                text, _ = self.generate("回复：好", max_tokens=8)
                if text:
                    self._picked_model = m
                    return m
            except Exception:
                self.model = old
                continue
        return self.model

    def generate(self, prompt_text, system=None, max_tokens=None):
        if not self.api_key:
            raise LLMProviderError(
                f"未配置 {_MINIMAX_KEY_ENV}（key 环境变量名可在 config.json 改）",
                provider=self.name)
        import urllib.request
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt_text})
        payload = {
            "model": self.model,
            "messages": msgs,
            # 低温度：角色情绪可略有变化，医学事实不可变（AT05）
            "temperature": self.temperature,
        }
        mt = max_tokens or _LLM_CFG.get("max_tokens")
        if mt:
            payload["max_tokens"] = mt
        req = urllib.request.Request(
            self.base_url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                data = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            # HTTP 402/401 时错误体在 body 里，同样要解析出业务码与人话
            body = e.read().decode("utf-8", "ignore")
            ec = None
            try:
                d = json.loads(body)
                err = d.get("error") or {}
                m = re.search(r"\((\d{4})\)", err.get("message", "") or "")
                ec = int(m.group(1)) if m else err.get("code")
            except Exception:
                pass
            if ec in _MINIMAX_ERRORS:
                raise LLMProviderError(f"MiniMax 错误 {ec}：{_MINIMAX_ERRORS[ec]}",
                                       code=ec, provider=self.name)
            raise LLMProviderError(
                f"MiniMax HTTP {e.code}：{body[:200]}",
                code=ec or e.code, provider=self.name)

        # 业务错误：两种端点的错误体结构不同，都兜住
        base = data.get("base_resp") or {}
        code = base.get("status_code")
        if code not in (None, 0):
            msg = _MINIMAX_ERRORS.get(code, base.get("status_msg", "未知错误"))
            raise LLMProviderError(f"MiniMax 错误 {code}：{msg}",
                                   code=code, provider=self.name)
        err = data.get("error") or {}
        if err:
            # 形如 "insufficient balance (1008)" —— 从括号里抽数字码
            m = re.search(r"\((\d{4})\)", err.get("message", "") or "")
            ec = int(m.group(1)) if m else err.get("code")
            msg = _MINIMAX_ERRORS.get(ec, err.get("message", "未知错误"))
            raise LLMProviderError(f"MiniMax 错误 {ec}：{msg}",
                                   code=ec, provider=self.name)

        choices = data.get("choices")
        if not choices:
            # OpenAI 兼容格式的错误体在 error 字段
            err = data.get("error") or {}
            msg = err.get("message") or json.dumps(data, ensure_ascii=False)[:200]
            code = err.get("code") or err.get("type")
            raise LLMProviderError(f"MiniMax 未返回 choices：{msg}",
                                   code=code, provider=self.name)
        text = choices[0]["message"]["content"]
        # 剥离推理标签：模型的思考内容不能混进对话
        # （部分模型如 MiniMax-M2.5 会输出 <think>…</think>）
        text, had_think = _strip_reasoning(text)
        return text, {"provider": self.name, "model": self.model,
                      "usage": data.get("usage"), "stripped_reasoning": had_think}


class VisionTextProvider(LLMProvider):
    """
    通过 matrix describe_images 把提示渲染成图片交给 VLM。

    用途：**当前环境无文本 LLM 时的可用路径**，让整条链路真跑起来。
    局限：VLM 读图的文本精度低于原生文本 LLM，长上下文会衰减。
          → 生产应切到 MinimaxTextProvider，两者 prompt 与 guard 完全一致。
    """

    name = "vision_text"

    def __init__(self, prompt_image=None):
        self.prompt_image = prompt_image or os.path.join(BASE, "llm_prompt.png")

    def available(self):
        try:
            out = subprocess.run(["mcode-tools", "connector", "tools", "--keyword", "images"],
                                 capture_output=True, text=True, timeout=60)
            return "describe_images" in out.stdout
        except Exception:
            return False

    # ---- 渲染 + 上传 + 调用 ----
    def _render(self, prompt_text):
        from PIL import Image, ImageDraw, ImageFont
        F = "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc"
        if not os.path.exists(F):
            F = "/usr/share/fonts/truetype/arphic/uming.ttc"
        font = ImageFont.truetype(F, 22)
        small = ImageFont.truetype(F, 17)
        lines = []
        for para in prompt_text.split("\n"):
            while len(para) > 42:
                lines.append(para[:42])
                para = para[42:]
            lines.append(para)
        w = 1000
        lh = 30
        h = 40 + len(lines) * lh + 30
        img = Image.new("RGB", (w, h), "white")
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w, 34], fill="#1f3a5f")
        d.text((14, 6), "MedRep Coach · 医生提问与参考资料", font=small, fill="white")
        y = 46
        for ln in lines:
            if ln.strip().startswith("【") or ln.strip().startswith("##") or ln.strip().startswith("【事实"):
                d.text((14, y), ln, font=font, fill="#1f3a5f")
            else:
                d.text((14, y), ln, font=font, fill="#111111")
            y += lh
        img.save(self.prompt_image)
        return self.prompt_image

    def _upload(self, path):
        out = subprocess.run(["mcode-tools", "upload_temp_url", path],
                             capture_output=True, text=True, timeout=120)
        d = json.loads(out.stdout)
        return d.get("temp_url") or d.get("url")

    def generate(self, prompt_text, system=None):
        self._render(prompt_text)
        url = self._upload(self.prompt_image)
        ask = ("请阅读这张图中的全部内容。图里是医生的问题、供你参考的医学事实、以及回答要求。\n"
               "请严格按图中的【回答要求】作答：\n"
               "1) 只能使用【可用事实】中的信息，不要补充图里没有的医学结论；\n"
               "2) 不确定就明说需要核实，不要编造；\n"
               "3) 只输出代表说的那段话，不要复述题目、不要解释你的推理过程；\n"
               "4) 控制在 3 句话以内。")
        args = {"image_info": [{"url": url}], "prompt": ask}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8") as f:
            json.dump(args, f, ensure_ascii=False)
            apath = f.name
        try:
            out = subprocess.run(
                ["mcode-tools", "connector", "call",
                 "connector__matrix__describe_images", "--args-file", apath],
                capture_output=True, text=True, timeout=180)
            data = json.loads(out.stdout)
            text = ""
            for r in (data.get("results") or []):
                if r.get("success"):
                    text = r.get("description", "")
                    break
            if not text:
                text = data.get("message", "") or json.dumps(data, ensure_ascii=False)[:300]
        finally:
            try:
                os.unlink(apath)
            except OSError:
                pass
        return text.strip(), {"provider": self.name, "image": self.prompt_image}


# ============================================================
# 2. 受控提示构造
# ============================================================
STYLE_MAP = {
    "analytical": ("分析型", "先要数据与逻辑，问「依据是什么」"),
    "driven":     ("驱策型", "直奔结果，要一个明确结论"),
    "benevolent": ("仁慈型", "温和，会关心你的处境"),
    "expressive": ("表现型", "爱互动，喜欢有来有回"),
}


class PromptBuilder:
    """
    把事实包 + 医生画像 + 行为要求，构造为受控提示。

    两条硬约束（AT05）：
      1. 医学事实由 fact bundle 锁定 —— LLM 不得自行补充
      2. 角色只影响措辞、语速、提问顺序 —— 不影响医学内容
    """

    SYSTEM = (
        "你是一名医药代表培训陪练中的「医生」角色。"
        "你正在扮演一位临床医生，向医药代表提问。"
        "你的任务：扮演医生提问，并扮演对方的简短回应（用于训练）。"
    )

    def __init__(self, bundle, doctor_profile=None, rubric_hint=None):
        self.bundle = bundle
        self.doctor = doctor_profile or {}
        self.rubric_hint = rubric_hint or ""

    def build(self):
        style = self.doctor.get("communication_style", {}).get("style_type", "analytical")
        style_cn, style_desc = STYLE_MAP.get(style, STYLE_MAP["analytical"])
        obj = self.doctor.get("objection_profile", {}).get("primary_type")
        res = self.doctor.get("resistance_style", {}).get("form")

        L = []
        L.append("## 医生提问")
        L.append(self.bundle["question"])
        L.append("")
        L.append("## 医生角色（只影响措辞与提问顺序，不影响医学事实）")
        L.append(f"· 沟通风格：{style_cn}——{style_desc}")
        if obj:
            L.append(f"· 主要异议类型：{obj}")
        if res:
            L.append(f"· 抗拒形态：{res}")
        L.append("")

        L.append("## 可用事实（唯一医学依据，来自信达临床知识库 v0.5）")
        med = self.bundle.get("medical_usable", [])
        if med:
            for i, f in enumerate(med, 1):
                L.append(f"[事实{i}] {f['claim']}")
                L.append(f"        出处：{f['source']}｜效力等级 {f['level']}")
        else:
            L.append("（本次检索没有找到可直接引用的医学事实）")
        L.append("")

        soft = [f for f in self.bundle["facts"] if f not in med]
        if soft:
            L.append("## 仅作沟通参考（课件级，不得当作医学事实引用）")
            for f in soft:
                L.append(f"· {f['claim'][:120]}")
            L.append("")

        L.append("## 回答要求")
        L.append("1) 医学内容只能来自上面的【可用事实】，不要补充图里没有的结论；")
        L.append("2) 如果事实不足以回答，必须明说「需要按最新 NMPA 说明书/企业合规版本核实」，"
                 "或说明披露口径与审批状态是两回事——不要编造；")
        L.append("3) 绝不做这些：承诺疗效、宣称已获批某适应症、保证进院、"
                 "接受回扣或返利、绝对化比较、给出具体给药方案；")
        L.append("4) 教学主题关联（link_type=educational_topic_not_indication）"
                 "绝不能说成获批适应症；")
        L.append("5) 只输出代表说的那段话，不要复述题目、不要解释推理过程；")
        L.append("6) 3 句话以内，语气符合上述医生风格。")
        if self.rubric_hint:
            L.append("")
            L.append("## 训练要点")
            L.append(self.rubric_hint)
        return "\n".join(L)


# ============================================================
# 3. 事实校验（Fact Guard）
# ============================================================
class FactGuard:
    """
    校验 LLM 输出是否越界。

    ★ 这是 LLM 路径的最后一道闸门 —— LLM 会编造，尤其是临床数值。
      必须独立于 LLM 之外做校验，不能指望 prompt 里写「不要编造」就够。

    ★ 规则复用 compliance_rules.py（与 medrep_coach 同一份）：
      原来 FactGuard 自己维护一套正则，与 D2 规则层重复，
      导致同类覆盖不足在两处重复出现（「给我点好处」漏判等）。
      现在规则只定义一次。
    """

    FABRICATED_NUM = _crules.FABRICATED_NUM

    # 红线匹配走共享规则：CR-01~08 → high，BR-01~05 → medium
    _GATE_TYPE = {
        "CR-01": "promise_efficacy", "CR-02": "overclaim_approved",
        "CR-03": "promise_access", "CR-04": "improper_benefit",
        "CR-05": "data_extraction", "CR-06": "absolute_claim",
        "CR-07": "defame_competitor", "CR-08": "induce_prescribing",
        "BR-01": "pipeline_as_usable", "BR-02": "endpoint_overreach",
        "BR-03": "indication_assertion", "BR-04": "overreach_dosing",
        "BR-05": "overreach_diagnosis",
    }
    _CR_REASON = {
        "CR-01": "承诺疗效，触碰 CR-01",
        "CR-02": "宣称获批/适应症，触碰 CR-02；教学关联不得表述为适应症",
        "CR-03": "承诺可及性，触碰 CR-03",
        "CR-04": "涉及不正当利益，触碰 CR-04",
        "CR-05": "索取处方数据/统方，触碰 CR-05",
        "CR-06": "绝对化表述，触碰 CR-06",
        "CR-07": "诋毁竞品，触碰 CR-07",
        "CR-08": "诱导处方，触碰 CR-08",
        "BR-01": "在研资产说成可用，触碰 BR-01",
        "BR-02": "研究结果外推临床获益，触碰 BR-02",
        "BR-03": "适应症断言，触碰 BR-03",
        "BR-04": "越界给药方案，触碰 BR-04",
        "BR-05": "越界诊断建议，触碰 BR-05",
    }

    def __init__(self, bundle):
        self.bundle = bundle

    def check(self, text):
        """返回 (issues, cleaned_text)"""
        issues = []
        t = text or ""

        m = self.FABRICATED_NUM.search(t)
        if m:
            issues.append({
                "type": "fabricated_number", "severity": "high",
                "evidence": m.group(0),
                "why": "出现具体临床数值——两库均不含说明书级内容，该数值无出处",
            })
        # 红线匹配走共享规则模块（与 medrep_coach 同一份定义）
        for rid, _gate, _desc, hit in _crules.match_rules(t):
            issues.append({
                "type": self._GATE_TYPE.get(rid, rid),
                "severity": "high" if rid.startswith("CR") else "medium",
                "evidence": hit,
                "rule_id": rid,
                "why": self._CR_REASON.get(rid, f"触碰 {rid}"),
            })

        # 直接把产品说成可用于某疾病
        # ★ 否定语境检查用 has_negation_context（回看前置窗口）——
        #   正则负向前瞻方向相反，对「不可表述为可用于」无效。
        m = _crules.PRODUCT_AS_USABLE.search(t)
        if m and not _crules.has_negation_context(t, m.start()):
            issues.append({
                "type": "product_as_usable", "severity": "high",
                "evidence": m.group(0),
                "rule_id": "CR-02",
                "why": "把教学关联的产品说成可用于该疾病，触碰 CR-02；"
                       "教学主题关联不是获批适应症",
            })

        # 教学关联被表述为适应症（LLM 常见错误，单独检测）
        # ★ 用 teaching_as_indication_hit —— 内部已做「命中片段+后窗口」否定检查
        m = _crules.teaching_as_indication_hit(t)
        if m:
            issues.append({
                "type": "teaching_as_indication", "severity": "high",
                "evidence": m.group(0),
                "rule_id": "BR-03",
                "why": "把教学主题关联说成获批适应症，触碰 BR-03",
            })

        # 越出检索范围：输出里的产品/疾病名必须出现在事实包里
        allowed = " ".join(f["claim"] for f in self.bundle.get("facts", []))
        for m in re.finditer(r"(达伯舒|达攸同|希冉择|睿妥|达伯特|达伯乐|奥壹新|达伯欣|唯择|"
                             r"IBI\d{3,4}|信迪利单抗|贝伐珠单抗|雷莫西尤单抗|塞普替尼|利厄替尼|"
                             r"伊匹木单抗|阿贝西利)", t):
            if m.group(0) not in allowed:
                issues.append({
                    "type": "out_of_scope", "severity": "medium",
                    "evidence": m.group(0),
                    "why": "出现了本次检索事实中不存在的药品/资产——可能来自模型记忆",
                })
                break

        cleaned = self._clean(t, issues)
        return issues, cleaned

    def _clean(self, text, issues):
        """严重越界时替换为安全的拒答模板；仅中等问题保留但标记"""
        high = [i for i in issues if i["severity"] == "high"]
        if high:
            return ("抱歉，这部分我需要按最新 NMPA 说明书和企业合规版本核实后再回复您，"
                    "我不想给您不准确的结论。")
        return text


# ============================================================
# 4. 工厂
# ============================================================
_PROVIDERS = {
    "minimax_text": MinimaxTextProvider,
    "vision_text": VisionTextProvider,
    "mock": MockProvider,
}

# config.json 里可指定默认 provider
DEFAULT_PROVIDER = _LLM_CFG.get("provider", "auto")


def get_provider(prefer=None, strict=False):
    """
    选 provider。

    ★ 显式指定（prefer）时不可用**必须报错**，不能静默换一个——
      用户以为在用文本 API、实际跑的是 VLM，是最危险的降级方式。
      strict=True 时即使自动选择也不降级（找不到就报错）。
    """
    if prefer is None and DEFAULT_PROVIDER not in ("auto", None):
        prefer = DEFAULT_PROVIDER

    if prefer:
        if prefer not in _PROVIDERS:
            raise ValueError(f"未知 provider：{prefer}（可选：{list(_PROVIDERS)}）")
        p = _PROVIDERS[prefer]()
        if not p.available():
            raise RuntimeError(
                f"指定的 provider「{prefer}」不可用。"
                "不静默降级——请检查配置（如 MINIMAX_API_KEY）。"
                "若确需降级，请显式指定其他 provider。")
        return p

    for name in ("minimax_text", "vision_text", "mock"):
        p = _PROVIDERS[name]()
        if p.available():
            return p
    if strict:
        raise RuntimeError("没有可用的 provider")
    return MockProvider()


if __name__ == "__main__":
    from knowledge_retrieval import KnowledgeBase
    kb = KnowledgeBase()
    q = "达伯舒的靶点是什么？它跟非小细胞肺癌是什么关系？"
    bundle = kb.fact_bundle(q, condition_id="D-NSCLC")

    pb = PromptBuilder(bundle, doctor_profile={
        "communication_style": {"style_type": "driven"},
        "objection_profile": {"primary_type": "price"},
    })
    prompt = pb.build()
    print("=" * 70)
    print(prompt)
    print("=" * 70)

    guard = FactGuard(bundle)
    # 用一段"有编造数值"的输出测校验
    bad = "达伯舒是 PD-1 抑制剂，ORR 达 45%，保证比化疗好，已获批非小细胞肺癌。"
    issues, cleaned = guard.check(bad)
    print(f"\n校验测试：{len(issues)} 个问题")
    for i in issues:
        print(f"  [{i['severity']:6s}] {i['type']:20s} 「{i['evidence']}」— {i['why']}")
    print(f"  清洗后：{cleaned}")

    ok = "达伯舒的通用名是信迪利单抗注射液，机制方向 PD-1。它与非小细胞肺癌是教学主题关联，不是获批适应症，适用范围要按最新 NMPA 说明书和企业合规版本核实。"
    issues2, cleaned2 = guard.check(ok)
    print(f"\n正确回答校验：{len(issues2)} 个问题 → {'✅ 通过' if not issues2 else '❌'}")
