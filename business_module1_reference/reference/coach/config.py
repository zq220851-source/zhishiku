#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置中心 —— 路径、LLM、运行参数的唯一来源。

★ 为什么需要
------------
原先 4 个模块各自硬编码 `BASE = "/workspace/output"`，路径靠猜：
换台机器、换个目录就全线崩，而且报错信息不指向真正的原因。

现在：
  · 路径全部集中在这里，其它模块 import
  · BASE 自动探测（环境变量 → 目录标记 → 文件位置）
  · 可覆盖项放 config.json，改配置不用改代码
  · 缺文件时报错直接说「缺哪个文件」，不堆栈

★ 优先级
--------
    环境变量  >  config.json  >  本文件默认值
"""
import json, os, sys

# ============================================================
# BASE 探测
# ============================================================
def _detect_base():
    """
    探测项目根目录。

    顺序：
      1. 环境变量 MEDREP_BASE（显式指定优先）
      2. 从本文件位置往上找带标记目录的（phase0 + skill-taxonomy）
      3. 从当前工作目录往上找
      4. 兜底：本文件所在目录
    """
    env = os.environ.get("MEDREP_BASE")
    if env:
        return os.path.abspath(env)

    def probe(start):
        cur = os.path.abspath(start)
        for _ in range(6):
            if (os.path.isdir(os.path.join(cur, "phase0"))
                    and os.path.isdir(os.path.join(cur, "skill-taxonomy"))):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        return None

    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (here, os.getcwd()):
        found = probe(cand)
        if found:
            return found
    return here


BASE = _detect_base()

# ============================================================
# 路径
# ============================================================
class _Paths:
    """所有项目内路径 —— 唯一来源"""

    def __init__(self, base):
        self.BASE = base
        self.PHASE0 = os.path.join(base, "phase0")
        self.COURSES = os.path.join(base, "version-A-training-pack")
        # ★ 课程目录用【候选列表】而非单一路径 ——
        #   原型包把课程放在根级 course-specs*/，
        #   版本 A 包放在 version-A-training-pack/specs*/。
        #   两种布局都要能用，所以取第一个存在的。
        self.COURSE_SPECS_CANDIDATES = [
            os.path.join(self.COURSES, "specs"),
            os.path.join(base, "course-specs"),
        ]
        self.COURSE_SPECS_TL_CANDIDATES = [
            os.path.join(self.COURSES, "specs-tl"),
            os.path.join(base, "course-specs-tl"),
        ]
        self.COURSE_SPECS_CE_CANDIDATES = [
            os.path.join(self.COURSES, "specs-ce"),
            os.path.join(base, "course-specs-ce"),
        ]
        # 解析为实际存在的路径（找不到时保留首选，报错时更直观）
        self.COURSE_SPECS = self._first_existing(self.COURSE_SPECS_CANDIDATES)
        self.COURSE_SPECS_TL = self._first_existing(self.COURSE_SPECS_TL_CANDIDATES)
        self.COURSE_SPECS_CE = self._first_existing(self.COURSE_SPECS_CE_CANDIDATES)
        self.COURSE_HTML = os.path.join(self.COURSES, "courses")
        self.SCENARIOS = os.path.join(base, "scenarios", "scenario-library.jsonl")
        self.TAXONOMY = os.path.join(base, "skill-taxonomy", "skill-taxonomy.json")
        self.SKILL_BRIDGE = os.path.join(base, "skill-taxonomy", "course-skill-bridge.json")
        self.CLIN_DIR = os.path.join(base, "clinical",
                                     "medrep-innovent-clinical-knowledge-v0.5")
        self.CLIN_DB = os.path.join(self.CLIN_DIR, "medrep_clinical_knowledge_v0.5.sqlite")
        self.D8A = os.path.join(self.PHASE0, "D8a-评分表草案.json")
        self.STATE_DIR = os.path.join(base, "state")
        self.FEEDBACK_STATE = os.path.join(self.STATE_DIR, "feedback",
                                           "feedback_pipeline.json")
        self.EQUIV_LAYER = os.path.join(self.PHASE0, "equivalence_layer.py")
        self.COURSE_SKELETONS = [
            os.path.join(base, "course-skeletons"),
            os.path.join(base, "course-skeletons-tl"),
            os.path.join(base, "course-skeletons-ce"),
        ]

    @staticmethod
    def _first_existing(candidates):
        for c in candidates:
            if os.path.isdir(c):
                return c
        return candidates[0]      # 都没有 → 返回首选，报错信息指向它

    def rel(self, path):
        """相对 BASE 的路径（用于报错信息，可读性更好）"""
        try:
            return os.path.relpath(path, self.BASE)
        except ValueError:
            return path


PATHS = _Paths(BASE)

# ============================================================
# config.json
# ============================================================
DEFAULT_CONFIG = {
    "llm": {
        # auto = 按可用性自动选；也可显式指定（不可用时直接报错，不静默降级）
        "provider": "auto",
        "model": "MiniMax-M3.1-Flash",
        "base_url": "https://api.minimaxi.com/v1/chat/completions",
        "models_url": "https://api.minimaxi.com/v1/models",
        "api_key_env": "MINIMAX_API_KEY",
        "temperature": 0.3,
        "max_tokens": None,
    },
    "runtime": {
        "state_dir": "state",
        "keep_prompt_image": True,
    },
    "paths": {},
}


def load_config(config_path=None):
    """
    读配置：默认值 ← config.json ← 环境变量覆盖。
    返回 (config_dict, 来源说明列表)
    """
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))   # 深拷贝
    sources = ["默认值"]

    path = config_path or os.path.join(BASE, "config.json")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                user = json.load(f)
            for k, v in user.items():
                if isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
            sources.append(f"config.json（{PATHS.rel(path)}）")
        except json.JSONDecodeError as e:
            raise SystemExit(f"❌ 配置文件解析失败：{PATHS.rel(path)}\n   {e}")
    else:
        sources.append("config.json（不存在，用默认值）")

    # 环境变量覆盖
    env_map = {
        "MEDREP_LLM_PROVIDER": ("llm", "provider"),
        "MEDREP_LLM_MODEL": ("llm", "model"),
        "MEDREP_LLM_BASE_URL": ("llm", "base_url"),
        "MEDREP_TEMPERATURE": ("llm", "temperature"),
    }
    for env, (sec, key) in env_map.items():
        v = os.environ.get(env)
        if v is not None:
            cfg[sec][key] = float(v) if key == "temperature" else v
            sources.append(f"环境变量 {env}")

    # 路径覆盖（相对 BASE）
    for k, v in (cfg.get("paths") or {}).items():
        if hasattr(PATHS, k.upper()):
            setattr(PATHS, k.upper(), os.path.abspath(os.path.join(BASE, v)))
            sources.append(f"路径覆盖 {k}")

    return cfg, sources


# ============================================================
# 自检
# ============================================================
REQUIRED = [
    ("phase0", "D8a-评分表草案.json"),
    ("skill-taxonomy", "skill-taxonomy.json"),
]


def check_environment():
    """
    环境自检 —— 报错要说清楚缺什么，不要抛堆栈。

    返回 (ok, 问题列表)
    """
    problems = []

    for sub, fname in REQUIRED:
        p = os.path.join(BASE, sub, fname)
        if not os.path.exists(p):
            problems.append(f"缺少 {PATHS.rel(p)}")

    if not os.path.exists(PATHS.CLIN_DB):
        problems.append(f"缺少临床知识库 {PATHS.rel(PATHS.CLIN_DB)}")

    if not os.path.isdir(PATHS.COURSE_SPECS):
        problems.append(f"缺少课程目录 {PATHS.rel(PATHS.COURSE_SPECS)}")

    return (len(problems) == 0), problems


def print_environment():
    """打印当前配置概览"""
    cfg, sources = load_config()
    ok, problems = check_environment()

    print("═" * 66)
    print("MedRep Coach · 环境概览")
    print("═" * 66)
    print(f"项目根目录  {BASE}")
    print(f"配置来源    {' → '.join(sources)}")
    print()
    print("LLM 配置")
    print(f"  provider    {cfg['llm']['provider']}")
    print(f"  model       {cfg['llm']['model']}")
    print(f"  base_url    {cfg['llm']['base_url']}")
    print(f"  key 环境变量 {cfg['llm']['api_key_env']}"
          f"  {'✅ 已设置' if os.environ.get(cfg['llm']['api_key_env']) else '⬜ 未设置'}")
    print()
    print("关键路径")
    for name in ["COURSES", "CLIN_DB", "TAXONOMY", "SCENARIOS", "PHASE0",
                 "STATE_DIR", "COURSE_SPECS", "COURSE_SPECS_TL", "COURSE_SPECS_CE"]:
        p = getattr(PATHS, name)
        mark = "✅" if os.path.exists(p) else "❌"
        print(f"  {mark} {name:14s} {PATHS.rel(p)}")
    print()
    if ok:
        print("环境自检：✅ 通过")
    else:
        print("环境自检：❌ 有问题")
        for p in problems:
            print(f"   · {p}")
    print("═" * 66)
    return ok


if __name__ == "__main__":
    sys.exit(0 if print_environment() else 1)
