#!/bin/zsh
cd "${0:A:h}"
exec .venv/bin/python scripts/start_voice_local.py --port 8791
