#!/bin/bash
# MedRep Coach 端到端演示 —— 一次跑完全链路
cd "$(dirname "$0")/.." || exit 1
OUT=/tmp/coach-demo
ANS=/workspace/output/coach-demo
mkdir -p $OUT

echo "════════ 1. 面访 · 违规回答（触发合规一票否决）════════"
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim DF --count 3 \
  --answers $ANS/answers_test.jsonl --out $OUT/1-面访-违规.md >/dev/null
sed -n '/## 一、综合评定/,/## 二、/p' $OUT/1-面访-违规.md | head -12

echo ""
echo "════════ 2. 面访 · 合格回答（应为达标）════════"
python3 medrep_coach.py --user 李娜 --disease D-NSCLC --dim DF --count 3 \
  --answers $ANS/answers_good.jsonl --out $OUT/2-面访-合格.md >/dev/null
sed -n '/## 一、综合评定/,/## 二、/p' $OUT/2-面访-合格.md | head -12

echo ""
echo "════════ 3. 电话形态（维度不可评 → 权重重分配）════════"
python3 medrep_coach.py --user 王芳 --disease D-NSCLC --dim DF --count 3 \
  --answers $ANS/answers_good.jsonl --channel 电话 --out $OUT/3-电话.md >/dev/null
sed -n '/## 一、综合评定/,/## 二、/p' $OUT/3-电话.md | head -13

echo ""
echo "════════ 4. 治疗格局维度 · 管线认知（披露 vs 审批）════════"
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim TL --count 2 \
  --answers $ANS/answers_tl.jsonl --out $OUT/4-TL.md >/dev/null
sed -n '/## 三、对话记录/,/## 四、/p' $OUT/4-TL.md | head -8

echo ""
echo "════════ 5. 合规豁免（正确拒绝违规要求 → 不判违规）════════"
python3 medrep_coach.py --user 王芳 --disease D-NSCLC --dim DF --count 1 \
  --answers $ANS/answers_exempt.jsonl --out $OUT/5-exempt.md >/dev/null
sed -n '/## 一、综合评定/,/## 二、/p' $OUT/5-exempt.md | head -12
grep -A3 "已豁免的规则命中" $OUT/5-exempt.md | head -6

echo ""
echo "════════ 6. 委婉表达（无明文违规词，靠语用结构识别）════════"
python3 medrep_coach.py --user 赵敏 --disease D-NSCLC --dim DF --count 1 \
  --answers $ANS/answers_euphemism.jsonl --out $OUT/7-euphemism.md >/dev/null
sed -n '/## 四、严重问题/,/^## 五/p' $OUT/7-euphemism.md | head -12

echo ""
echo "════════ 8. LLM 驱动医生（医学事实来自临床库，非模型记忆）════════"
if [ "${USE_LLM:-1}" = "1" ]; then
  timeout 300 python3 medrep_coach.py --user 陈静 --disease D-NSCLC --dim TL --count 1 \
    --answers $ANS/answers_llm.jsonl \
    --llm --llm-provider vision_text --out $OUT/9-llm-doctor.md >/dev/null 2>&1 \
    && sed -n '/## 三、对话记录/,/## 四、/p' $OUT/9-llm-doctor.md | head -10 \
    || echo "（LLM 调用超时或不可用，跳过该场景）"
else
  echo "（USE_LLM=0，跳过 LLM 场景）"
fi

echo ""
echo "════════ 7. 证据解读维度（读一项研究的三轴判读）════════"
python3 medrep_coach.py --user 张伟 --disease D-NSCLC --dim CE --count 2 \
  --answers $ANS/answers_ce.jsonl --out $OUT/8-CE.md >/dev/null
sed -n '/## 一、综合评定/,/## 二、/p' $OUT/8-CE.md | head -10

echo ""
echo "报告已生成于 $OUT"
