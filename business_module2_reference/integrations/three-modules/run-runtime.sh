#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
M2="$ROOT/medrep_coach_with_ai_rules/module2"
M1="$ROOT/module1_source"
M3="$ROOT/medrep-daily"
bash "$M2/integrations/three-modules/run-all.sh" >/dev/null
export MEDREP_TEST_BRIDGE_ENABLED=1
export MEDREP_TEST_CLOCK=2026-11-02T09:03:00Z
if curl -fsS --max-time 1 http://127.0.0.1:8799/health >/dev/null 2>&1 || curl -fsS --max-time 1 http://127.0.0.1:8798/health >/dev/null 2>&1; then
  echo '测试端口已被占用，拒绝连接不明来源服务' >&2; exit 1
fi
PYTHONPATH="$M1:$M1/tests" python3 "$M1/bridge_test_service.py" > "$ROOT/shared_exchange/m1-http.log" 2>&1 &
M1PID=$!
node "$M3/integrations/medrep-coach/serve-local.mjs" > "$ROOT/shared_exchange/m3-http.log" 2>&1 &
M3PID=$!
cleanup(){ kill "$M1PID" "$M3PID" 2>/dev/null || true; wait "$M1PID" "$M3PID" 2>/dev/null || true; }
trap cleanup EXIT
for i in {1..30}; do
 if curl -fsS --max-time 1 http://127.0.0.1:8799/health >/dev/null 2>&1 && curl -fsS --max-time 1 http://127.0.0.1:8798/health >/dev/null 2>&1; then break; fi
 sleep .2
done
curl -fsS --max-time 1 http://127.0.0.1:8799/health >/dev/null
curl -fsS --max-time 1 http://127.0.0.1:8798/health >/dev/null
TS_EXEC=''
if command -v tsx >/dev/null 2>&1; then
 TS_EXEC='tsx'
else
 TS_EXEC='node -r /opt/nvm/versions/node/v22.16.0/lib/node_modules/ts-node/register/transpile-only'
fi
(cd "$M2"; TS_NODE_COMPILER_OPTIONS='{"module":"CommonJS","moduleResolution":"node"}' $TS_EXEC "$M2/integrations/three-modules/run-runtime.ts")
