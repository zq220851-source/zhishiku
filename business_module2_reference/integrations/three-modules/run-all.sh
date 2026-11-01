#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
M2="$ROOT/medrep_coach_with_ai_rules/module2"
if [ -x "$ROOT/medrep_coach_with_ai_rules/node_modules/.bin/tsx" ]; then
  "$ROOT/medrep_coach_with_ai_rules/node_modules/.bin/tsx" "$M2/integrations/three-modules/run.ts"
elif command -v tsx >/dev/null 2>&1; then
  tsx "$M2/integrations/three-modules/run.ts"
elif [ -f /opt/nvm/versions/node/v22.16.0/lib/node_modules/ts-node/register/transpile-only.js ]; then
  (cd "$M2"; TS_NODE_COMPILER_OPTIONS='{"module":"CommonJS","moduleResolution":"node"}' node -r /opt/nvm/versions/node/v22.16.0/lib/node_modules/ts-node/register/transpile-only "$M2/integrations/three-modules/run.ts")
else
  echo '需要安装项目依赖，执行根目录 npm install 后重新运行' >&2; exit 1
fi

python3 "$M2/integrations/three-modules/build-demo.py"
python3 "$M2/integrations/three-modules/audit.py"
