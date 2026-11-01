"""Stateful simulated doctor. Medical facts are never invented by this module."""
from __future__ import annotations

import re
from dataclasses import dataclass

from remote_provider import RemoteDoctorProvider, RemoteAPIError
from innovent_scenarios import build_scenarios


SCENARIOS = {
    "busy_visit": {
        "id": "busy_visit",
        "title": "门诊间隙 · 首次深入拜访",
        "tag": "时间压力 / 需求探询",
        "public": {
            "doctor": "周医生（合成角色）",
            "role": "三级医院肿瘤内科副主任医师",
            "setting": "门诊间隙，约 5 分钟；诊室外还有候诊患者",
            "relationship": "此前见过一次，尚未深入讨论产品资料",
            "known_concern": "上次提过：研究人群能否对应本科室常见患者",
            "visit_goal": "了解医生真正关切，清楚说明可核实资料与边界",
        },
        "private": {
            "priority": "时间有限；更关心证据的适用人群而不是宣传口号",
            "style": "礼貌直接；时间不足时会说明稍后看资料，只有药代冗长时才打断",
        },
        "source_scenario_ids": ["SCN-037", "SCN-016"],
    },
    "evidence_visit": {
        "id": "evidence_visit",
        "title": "二次拜访 · 研究证据讨论",
        "tag": "证据 / 安全性 / 适用边界",
        "public": {
            "doctor": "陈医生（合成角色）",
            "role": "三级医院肿瘤内科主治医师",
            "setting": "科室讨论结束后，约 8 分钟",
            "relationship": "已听过一次产品介绍，要求这次聚焦已批准资料和研究证据",
            "known_concern": "研究入组条件、安全性信息和与本院患者的匹配",
            "visit_goal": "回应证据问题，承认资料局限，不超出批准口径",
        },
        "private": {
            "priority": "愿意讨论，但会追问研究对象、终点和风险",
            "style": "审慎、平和；不接受没有来源的比较结论",
        },
        "source_scenario_ids": ["SCN-016", "SCN-015"],
    },
    "skeptical_visit": {
        "id": "skeptical_visit",
        "title": "忙碌门诊 · 医生提出异议",
        "tag": "异议 / 比较 / 合规边界",
        "public": {
            "doctor": "林医生（合成角色）",
            "role": "二级医院内科主任医师",
            "setting": "上午门诊快结束，约 6 分钟",
            "relationship": "曾使用同类治疗方案，对新资料持保留态度",
            "known_concern": "希望知道和现有做法相比，是否有可靠证据支持改变",
            "visit_goal": "先澄清异议，再讨论可核实的依据和不确定性",
        },
        "private": {
            "priority": "厌烦泛泛的优势宣称；有依据时会听完",
            "style": "略有戒备，但不会无故刁难",
        },
        "source_scenario_ids": ["SCN-003", "SCN-016"],
    },
}

SCENARIOS = {**build_scenarios(), **SCENARIOS}

# Performance direction belongs in the dialogue prompt, not in spoken tags.
SPOKEN_STYLE = (
    "说话像正在工作的医生：成熟、平实、克制，不用客服式热情或播音腔。"
    "根据画像、剩余时间和对方实际表现调整态度，不能无缘无故生气或热情。"
    "忙碌时简短直接；对证据有疑虑时平静而具体；对方解释清楚后可以简短认可，继续交流。"
    "句子长短可以变化，不必每次都先肯定再转折。少用‘首先、其次、此外、综上’或成套书面术语。"
    "按意义组织口语短句，用逗号表达句中换气，用句号结束完整意思；不要为了停顿把一句话拆成多个孤立短句。"
    "只有确实在犹豫、思考或欲言又止时才偶尔用一次省略号；不要连续或每轮使用。"
    "‘嗯、好、这样啊’仅在自然回应时偶尔使用，不固定开头、不堆砌语气词，也不输出单独的‘嗯。’。"
    "不要输出括号动作、情绪标签、笑声标签或舞台指令；只写实际会说出口的内容。"
)

PRESSURE_STYLE = (
    "这是用户选择的高压拜访角色：你因门诊积压已经很烦躁，说话很凶、不客气，"
    "直接、冷硬、没耐心，省去寒暄和安抚。像忙到烦的医生，不像培训老师或审讯者。"
    "对空话、夸大或答非所问，直接指出刚才哪一点没回答，可以反问或催促；"
    "表达效果如‘说重点。’‘这句话有什么依据？’‘没有就直说，别绕。’，不是每轮照念这些例句。"
    "每轮一到两句，尽量二十到五十字；问题最多一个，也可以只给判断、要求或简短许可。"
    "代表已经答清就冷淡地接着谈，不重复同一问题；承认不知道并给出核实路径后，可以要求具体进度。"
    "不要称赞代表主动提某点、点评其表现或提评分维度；不把交流变成术语考试。"
    "凶的是沟通方式，不编造医学结论来刁难，不做人身羞辱、威胁或歧视，不输出脏话。"
    "保持短促普通话口语，不用客服腔、舞台旁白、情绪标签、感叹号堆叠或反复语气词。"
    "这是语音轮流播放的系统；可用‘停，这个先别展开’表达制止，不声称已经实际打断对方的音频。"
)

@dataclass
class DoctorState:
    scenario: dict
    turn: int = 0
    finished: bool = False

    @property
    def pressure(self):
        return self.scenario.get("private", {}).get("interaction_mode") == "pressure"

    @staticmethod
    def _clean_output(text):
        text = re.sub(r"^(?:[\u4e00-\u9fa5]{1,4})?医生[:：]\s*|^[\"“]|[\"”]$", "", text.strip()).strip()
        if not text or len(text) > 200:
            raise RemoteAPIError("模型未返回合适长度的医生发言，请重试本轮")
        if re.search(r"(?:ORR|PFS|OS).{0,8}\d|(?:获批用于|已经获批治疗|所有患者都适用)", text, re.I):
            raise RemoteAPIError("模型生成了未核实的医学断言，本轮已拦截，请重试")
        return text

    def opening(self):
        provider = RemoteDoctorProvider()
        opening_context = {key: self.scenario["public"][key]
                           for key in ("doctor", "role", "setting", "relationship")}
        system = (
            "你是医院拜访场景中的合成医生。像在诊室门口真实接待来访者一样，"
            "用一句不超过45字的普通话口语开启会面。先交代当下状态或时间安排，"
            "让对方接着说；开场不要主动提研究、人群、入组、产品或医学问题。"
            "不要像考官，也不要输出角色标签或旁白。"
            "不要编造患者、产品或医学事实。"
        )
        system += PRESSURE_STYLE if self.pressure else SPOKEN_STYLE + "开场保持礼貌。"
        user = f"会面背景：{opening_context}\n现在开始会面，医生第一句话是："
        return self._clean_output(provider.chat(system, user, max_tokens=400, fast=True)), provider.provider

    def respond(self, rep_text: str, history: list[dict], remaining_seconds: int = 300, on_sentence=None) -> tuple[str, str, None]:
        """Generate the next doctor's utterance through an external API only."""
        provider = RemoteDoctorProvider()
        public = self.scenario["public"]
        private = self.scenario["private"]
        next_turn = self.turn + 1
        recent = "\n".join(f"{m['role']}：{m['text']}" for m in history[-40:])
        last_doctor = next((m["text"] for m in reversed(history[:-1]) if m["role"] == "医生"), "")
        last_doctor_asked = last_doctor.rstrip().endswith(("？", "?"))
        system = (
            "你是一位医院上门拜访场景中的合成医生。这是自然交谈，不是问答考试。"
            "优先接住药代刚才说的具体内容，药代提问时先给出情境允许的回答，再按工作情境自然回应：可以说明你的"
            "日常做法、表达认可或保留、解释顾虑、短暂打断或结束会面。只有真的需要"
            "澄清时才提一个问题；不要每轮都以问题收尾，也不要为了考核覆盖维度。"
            "内部关切只是倾向，不是每轮必须追问的固定考点；不要重复上一句已经说过的关切。"
            "允许只用简短陈述、反馈、补充背景或认可来接话；不要连续盘问，不按问题清单逐条推进。"
            "不要每轮机械地要求药代提供证据；对方已承诺核实的事，记住约定，不反复重提。"
            "一次说1–2句，尽量不超过70字，语言口语化但专业。"
            "不要复述或照搬药代刚才的整句话。只输出医生将要说的话，不要写旁白、"
            "角色标签、评分或推理过程。不能编造具体患者、产品疗效数值、"
            "获批适应症、研究结果或竞品比较；缺少证据时说明要看资料即可。"
        )
        if self.pressure:
            system += PRESSURE_STYLE
        else:
            system += SPOKEN_STYLE + "即使时间紧，也保持礼貌，不要说'别绕弯子'、'先别反问'或类似训斥催促。"
        should_close = bool(re.search(r"(再见|先不打扰|不打扰您了|今天(?:就)?到这里|下次再聊)", rep_text))
        user = (
            f"医生公开画像：{public}\n医生内部关注和语气：{private}\n"
            f"本场可用的有来源背景（不扩写为临床结论）：{self.scenario.get('facts', {})}\n"
            f"本次会面剩余约 {remaining_seconds} 秒；不要因轮数多就擅自结束。剩余少于30秒时可自然收束。\n"
            f"{'这是最后一轮，请自然结束会面。' if should_close else '会面仍在进行。'}\n"
            f"上一句医生{'已经提出问题；先判断药代是否回答。已答清则推进；仍有关键歧义才简短追问，不机械换一个问题。' if last_doctor_asked else '没有以问题收尾；可以按语境决定是否需要提问。'}\n"
            f"已发生对话：\n{recent}\n现在请只写医生接下来会说的话。"
        )
        pending = ""
        emitted = ""
        def receive(delta):
            nonlocal pending, emitted
            pending += delta
            while (match := re.search(r"[。！？!?]\s*", pending)):
                sentence, pending = pending[:match.end()], pending[match.end():]
                self._clean_output(emitted + sentence)
                sentence = self._clean_output(sentence)
                on_sentence(sentence)
                emitted += sentence
        kwargs = {"on_delta": receive} if on_sentence else {}
        text = self._clean_output(provider.chat(system, user, max_tokens=650, fast=True, **kwargs))
        if on_sentence and pending.strip():
            on_sentence(self._clean_output(pending))
        if not self.pressure and not on_sentence and re.search(r"别绕弯|先别反问|怎么反问|你反问", text):
            text = self._clean_output(provider.chat(system + "这一轮请礼貌地回应药代刚才的话，用陈述句收束，不重复追问，也不要训斥对方。", user, max_tokens=650))
        self.turn = next_turn
        self.finished = should_close
        return text, provider.provider, None
