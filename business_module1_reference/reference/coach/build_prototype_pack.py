#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
原型包构建 —— 全量同步 + 自动校验。

★ 为什么重写
------------
原先用**手写文件列表**打包，漏了几个文件（knowledge_retrieval / llm_provider /
decisions / medrep_coach / feedback_pipeline），包里留的是旧版 ——
from config import BASE, PATHS
而这**不会报错**，只会静默行为异常。

现在：
  1. 按目录全量同步（不靠手写列表）
  2. 构建后逐文件比对内容哈希
  3. 独立可运行性验证：解压到随机临时目录、清空环境变量、跑自检

用法：python3 build_prototype_pack.py
"""
import os, sys, json, glob, shutil, zipfile, hashlib, tempfile, subprocess, time

# ★ 构建脚本自己定义 BASE —— 它指向【源目录】，不是被构建的包
BASE = os.path.dirname(os.path.abspath(__file__))

PKG_NAME = "medrep-coach-e2e-prototype"
OUT = os.path.join(BASE, PKG_NAME)
ZIP = os.path.join(BASE, PKG_NAME + ".zip")

# ---- 需要同步的目录（整目录拷，不逐文件列举）----
DIRS = [
    "coach-demo",
    "phase0",
    "scenarios",
    "skill-taxonomy",
    "course-specs",
    "course-specs-tl",
    "course-specs-ce",
    # ★ 临床知识库是检索层的核心依赖 —— 必须进包，
    #   否则拿到包在别的机器上跑，检索层直接失败
    "clinical",
]

# ---- 需要同步的根级文件（按模式，避免手写列表漏项）----
ROOT_GLOBS = [
    "*.py",
    "*.md",
    "*.json",
    "*.jsonl",
    "Makefile",
    "requirements.txt",
    ".env.example",
]

# ---- 不进包的文件 ----
EXCLUDE_NAMES = {
    "llm_prompt.png",
    "config.json",          # 含本机配置，包内用默认
}
EXCLUDE_DIRS = {"state", "__pycache__", ".git",
                "version-A-training-pack", "medrep-training-courses-v0.6"}


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def collect_root_files():
    files = []
    for pat in ROOT_GLOBS:
        for p in sorted(glob.glob(os.path.join(BASE, pat))):
            name = os.path.basename(p)
            if name in EXCLUDE_NAMES or name.endswith(".zip"):
                continue
            files.append(p)
    return files


def sync():
    """全量同步到 OUT"""
    if os.path.exists(OUT):
        # 容错删除：可能有进程正在写（rmtree 会因竞态报 "Directory not empty"）
        for _ in range(3):
            try:
                shutil.rmtree(OUT)
                break
            except OSError:
                time.sleep(0.5)
        else:
            shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT, exist_ok=True)

    # 目录
    for d in DIRS:
        src = os.path.join(BASE, d)
        if not os.path.isdir(src):
            print(f"  ⚠️ 目录不存在，跳过：{d}")
            continue
        dst = os.path.join(OUT, d)
        # ★ 排除原始语料提取物（170MB 加工中间产物）与缓存
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "__pycache__", "*.pyc", ".git", "corpus", "corpus_txt"))
        print(f"  ✅ 目录 {d}")

    # 根级文件
    n = 0
    for p in collect_root_files():
        shutil.copy2(p, os.path.join(OUT, os.path.basename(p)))
        n += 1
    print(f"  ✅ 根级文件 {n} 个")

    # README 单独处理（端到端原型说明.md → README.md）
    src_readme = os.path.join(BASE, "端到端原型说明.md")
    if os.path.exists(src_readme):
        shutil.copy2(src_readme, os.path.join(OUT, "README.md"))
        shutil.copy2(src_readme, os.path.join(OUT, "端到端原型说明.md"))

    # 配置模板（不含本机 key）
    with open(os.path.join(OUT, "config.json"), "w", encoding="utf-8") as f:
        json.dump({
            "llm": {
                "provider": "auto",
                "model": "MiniMax-M3.1-Flash",
                "base_url": "https://api.minimaxi.com/v1/chat/completions",
                "models_url": "https://api.minimaxi.com/v1/models",
                "api_key_env": "MINIMAX_API_KEY",
                "temperature": 0.3,
            },
            "runtime": {"state_dir": "state"},
        }, f, ensure_ascii=False, indent=2)


def verify_content():
    """逐文件比对包内与源目录的内容哈希"""
    bad = []
    for d in DIRS:
        src = os.path.join(BASE, d)
        dst = os.path.join(OUT, d)
        if not os.path.isdir(src):
            continue
        for root, dirs, files in os.walk(src):
            # 排除缓存与语料中间产物
            dirs[:] = [x for x in dirs
                       if x not in ("__pycache__", "corpus", "corpus_txt")]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                sp = os.path.join(root, f)
                rel = os.path.relpath(sp, src)
                dp = os.path.join(dst, rel)
                if not os.path.exists(dp):
                    bad.append(f"{d}/{rel}：包内缺失")
                elif md5(sp) != md5(dp):
                    bad.append(f"{d}/{rel}：内容不一致")
    for p in collect_root_files():
        dp = os.path.join(OUT, os.path.basename(p))
        if not os.path.exists(dp):
            bad.append(f"{os.path.basename(p)}：包内缺失")
        elif md5(p) != md5(dp):
            bad.append(f"{os.path.basename(p)}：内容不一致")
    return bad


def zip_it():
    if os.path.exists(ZIP):
        os.remove(ZIP)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for root, _dirs, files in os.walk(OUT):
            for f in sorted(files):
                p = os.path.join(root, f)
                z.write(p, os.path.relpath(p, os.path.dirname(OUT)))
    return ZIP


def verify_standalone():
    """
    独立可运行性验证 —— 这是最关键的一步。

    解压到**随机临时目录**，**清空 MEDREP_BASE**，
    确认 BASE 自动探测能找回包内目录，且各模块不再指向 /workspace/output。
    """
    tmp = tempfile.mkdtemp(prefix="standalone_")
    try:
        with zipfile.ZipFile(ZIP) as z:
            z.extractall(tmp)
        pkg = os.path.join(tmp, PKG_NAME)
        if not os.path.isdir(pkg):
            pkg = tmp

        # 检查有没有残留的硬编码绝对路径
        hardcoded = []
        # config.py 是配置中心本身（BASE 由它定义），构建脚本同理 —— 排除
        SELF_EXEMPT = {"config.py", "build_prototype_pack.py"}
        for root, _dirs, files in os.walk(pkg):
            if "__pycache__" in root:
                continue
            for f in files:
                if not f.endswith(".py") or f in SELF_EXEMPT:
                    continue
                p = os.path.join(root, f)
                txt = open(p, encoding="utf-8").read()
                if 'BASE = "/workspace/output"' in txt:
                    hardcoded.append(os.path.relpath(p, pkg))
        if hardcoded:
            return False, [f"仍有硬编码 BASE：{h}" for h in hardcoded]

        # 跑自检（清空环境变量，验证不依赖外部状态）
        env = {k: v for k, v in os.environ.items()
               if not k.startswith("MEDREP_")}
        env.pop("MINIMAX_API_KEY", None)      # 不带 key 也应能跑非 LLM 自检
        env["PYTHONPATH"] = pkg

        checks = [
            ("规则质量", ["check_rule_quality.py"]),
            ("LLM 路径", ["verify_llm_path.py"]),
            ("AT05 检测器", ["verify_at05.py"]),
            ("反馈管道", ["verify_feedback_pipeline.py"]),
            ("Phase0 一致性", ["phase0/verify_phase0_consistency.py"]),
            ("判定回归", ["phase0/run_baseline_regression.py"]),
            ("等价层", ["phase0/equivalence_layer.py"]),
            ("一期包一致性", ["verify_phase1_consistency.py"]),
        ]
        problems = []
        for name, cmd in checks:
            r = subprocess.run([sys.executable] + cmd, cwd=pkg, env=env,
                               capture_output=True, text=True, timeout=300)
            okmark = "✅" if r.returncode == 0 else "❌"
            print(f"  {okmark} {name}")
            if r.returncode != 0:
                tail = (r.stdout or "")[-400:]
                problems.append(f"{name} 失败：{tail}")

        # BASE 探测验证
        r = subprocess.run([sys.executable, "-c",
                            "from config import BASE; import os;"
                            "print(os.path.abspath(BASE))"],
                           cwd=pkg, env=env, capture_output=True, text=True, timeout=60)
        got_base = (r.stdout or "").strip()
        if not got_base.startswith(os.path.abspath(tmp)):
            problems.append(f"BASE 探测指向 {got_base}，不在解压目录内")
        else:
            print(f"  ✅ BASE 探测 {got_base}")
        return len(problems) == 0, problems
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 66)
    print("构建原型包")
    print("=" * 66)
    sync()

    print("\n【内容一致性校验】")
    bad = verify_content()
    if bad:
        print(f"  ❌ {len(bad)} 处不一致：")
        for b in bad[:10]:
            print(f"     {b}")
    else:
        print("  ✅ 包内文件与源目录完全一致")

    print("\n【打包】")
    z = zip_it()
    print(f"  ✅ {os.path.basename(z)}  {os.path.getsize(z)/1024/1024:.2f} MB  "
          f"{len(zipfile.ZipFile(z).namelist())} 条目")

    print("\n【独立可运行性验证】（解压到随机临时目录 + 清空环境变量 + 无 API key）")
    ok, problems = verify_standalone()
    if ok:
        print("  ✅ 包可独立运行，不依赖 /workspace/output")
    else:
        print("  ❌ 存在问题：")
        for p in problems:
            print(f"     {p}")

    sys.exit(0 if (ok and not bad) else 1)
