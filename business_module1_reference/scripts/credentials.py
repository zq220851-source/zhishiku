"""Read an explicitly selected private config without executing shell code."""
import os
from pathlib import Path

def configure(path):
    pairs={}
    for line in Path(path).read_text().splitlines():
        line=line.strip()
        if not line or line.startswith('#') or '=' not in line:continue
        key,value=line.removeprefix('export ').split('=',1)
        pairs[key.strip()]=value.strip().strip('"').strip("'")
    aliases={'MODULE2_MODEL_API_KEY':'OPENAI_NEXT_API_KEY','MODULE2_MODEL_NAME':'MEDREP_CHAT_MODEL'}
    for key in ['OPENAI_NEXT_API_KEY','MEDREP_CHAT_MODEL','MEDREP_CHAT_API_URL']:
        if pairs.get(key):os.environ[key]=pairs[key]
    for old,new in aliases.items():
        if pairs.get(old):os.environ[new]=pairs[old]
    base=pairs.get('MODULE2_MODEL_BASE_URL')
    if base:os.environ['MEDREP_CHAT_API_URL']=base.rstrip('/')+'/chat/completions'
