"""Run the preserved hospital-visit voice UI with private server configuration.

The original reference files stay unchanged. This is the original visit engine,
not the newer course workflow; both remain available through separate entries.
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.credentials import configure

parser = argparse.ArgumentParser()
parser.add_argument('--config-from', default=str(ROOT / '.env.local'))
parser.add_argument('--port', type=int, default=8894)
args = parser.parse_args()
configure(args.config_from)
sys.path.insert(0, str(ROOT / 'reference/coach/voice-demo'))
import server

server.HERE = ROOT / 'web_classic_voice'
sys.argv = [sys.argv[0], '--port', str(args.port)]
server.main()
