# MedRep Coach —— 统一入口
#
#   make env      查看环境与配置
#   make check    跑全部自检（8 套）
#   make demo     端到端演示（8 场景）
#   make feedback 复盘链路演示
#   make train    跑一次训练（规则引擎）
#   make llm      跑一次训练（真实 LLM）
#   make key      诊断 API key
#   make pack     构建原型包（含独立可运行性验证）
#   make clean    清理运行状态

PY ?= python3
USER ?= 张伟
DISEASE ?= D-NSCLC
DIM ?= DF
COUNT ?= 2
ANSWERS ?= coach-demo/answers_good.jsonl

.PHONY: env check check-rule check-llm check-at05 check-feedback check-phase0 \
        check-phase1 check-baseline check-equiv demo feedback train llm key \
        pack pack-phase0 clean help

help:
	@grep -E '^#   ' Makefile | sed 's/^#   //'

env:
	@$(PY) config.py

check: check-rule check-llm check-at05 check-feedback check-phase0 check-phase1 check-baseline check-equiv
	@echo ""
	@echo "══════════════════════════════"
	@echo "  全部自检通过"
	@echo "══════════════════════════════"

check-rule:
	@$(PY) check_rule_quality.py

check-llm:
	@$(PY) verify_llm_path.py

check-at05:
	@$(PY) verify_at05.py

check-feedback:
	@$(PY) verify_feedback_pipeline.py

check-phase0:
	@$(PY) phase0/verify_phase0_consistency.py

check-phase1:
	@$(PY) verify_phase1_consistency.py

check-baseline:
	@$(PY) phase0/run_baseline_regression.py

check-equiv:
	@$(PY) phase0/equivalence_layer.py

demo:
	@bash coach-demo/demo.sh

feedback:
	@$(PY) feedback_demo.py

train:
	@$(PY) medrep_coach.py --user $(USER) --disease $(DISEASE) --dim $(DIM) \
		--count $(COUNT) --answers $(ANSWERS)

llm:
	@$(PY) medrep_coach.py --user $(USER) --disease $(DISEASE) --dim $(DIM) \
		--count $(COUNT) --answers $(ANSWERS) --llm

key:
	@$(PY) check_llm_key.py

# 构建交付包（含内容一致性校验 + 独立可运行性验证）
pack:
	@$(PY) build_prototype_pack.py

pack-phase0:
	@$(PY) build_phase0_pack.py

clean:
	@rm -rf state llm_prompt.png
	@echo "已清理运行状态"
