"""Source-bound reading and retrieval, inspired by OpenMAIC/Open Notebook.

Lessons are resolved by ID, never reconstructed with top-k search. All passages
are authored source text; references with no body are not indexable evidence.
"""
import os
os.environ.setdefault("HAYSTACK_TELEMETRY_ENABLED", "false")
import hashlib
import json
import re
import threading
from knowledge import LESSONS, get_lesson


def blocks_for(lesson):
    blocks = []
    def add(path, title, value):
        if isinstance(value, (dict, list)):
            text = json.dumps(value, ensure_ascii=False, indent=2)
        else:
            text = str(value or '').strip()
        if text:
            blocks.append({'id': lesson['id'] + ':' + path, 'title': title,
                           'text': text, 'locator': path, 'status': lesson['status']})
    d = lesson.get('content')
    if d:
        add('goal', '本课目标', d.get('goal'))
        for key, title in [('hero','情境'), ('assumptions','已有基础'), ('map','知识关系'),
                           ('hook','从这个问题开始'), ('visual','图示与对照'), ('analogy','帮助理解')]:
            add(key, title, d.get(key))
        for i, item in enumerate(d.get('steps', [])):
            add(f'steps.{i}', item.get('title', '讲解'), item.get('body'))
        for i, item in enumerate(d.get('misconceptions', [])):
            add(f'misconceptions.{i}', '常见误区', item)
        add('recall', '回忆与运用', d.get('recall'))
        # Optional checks remain visible learning content, not a compulsory stage.
        for i, item in enumerate(d.get('checks', [])):
            add(f'checks.{i}', '可选自测', item)
    else:
        for i, item in enumerate(lesson['sections']):
            add(f'sections.{i}', item['title'], item['body'])
    return blocks


def snapshot(lesson_id):
    lesson = get_lesson(lesson_id)
    blocks = blocks_for(lesson)
    revision = hashlib.sha256(json.dumps(blocks, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for b in blocks:
        b['revision'] = revision
        b['url'] = '/?lesson=' + lesson_id + '#material-' + b['locator']
    return {'lesson_id': lesson_id, 'title': lesson['title'], 'revision': revision,
            'status': lesson['status'], 'blocks': blocks,
            'references': lesson['sources'], 'content': lesson.get('content'),
            'notice': lesson['notice']}


def tokenize(text):
    # Same segmentation on both sides: Chinese characters and adjacent bigrams;
    # Latin medical acronyms and numbers remain whole. No optional jieba drift.
    text = str(text).lower()
    units = re.findall(r'[a-z][a-z0-9_-]*|\d+(?:\.\d+)?|[\u3400-\u9fff]', text)
    bigrams = [a+b for a,b in zip(units, units[1:]) if re.fullmatch(r'[\u3400-\u9fff]',a) and re.fullmatch(r'[\u3400-\u9fff]',b)]
    return ' '.join(units + bigrams)


class MaterialSearch:
    """Real Haystack Pipeline; current local corpus uses BM25, not fake vectors.

    Embedding/reranking can be added after a labelled retrieval evaluation.
    No caller-supplied filters are accepted. Search is course-scoped internally.
    """
    def __init__(self):
        from haystack import Document, Pipeline
        from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
        from haystack.document_stores.in_memory import InMemoryDocumentStore
        self.store = InMemoryDocumentStore(bm25_tokenization_regex=r'(?u)\b\w+\b')
        docs = []
        for key in LESSONS:
            snap = snapshot(key)
            for block in snap['blocks']:
                docs.append(Document(id=block['id'], content=tokenize(block['title']+' '+block['text']),
                                     meta={'lesson_id':key,'revision':snap['revision'],'block':block}))
        self.store.write_documents(docs)
        self.pipeline = Pipeline()
        self.pipeline.add_component('retrieve', InMemoryBM25Retriever(document_store=self.store))
        self.lock = threading.Lock()

    def search(self, lesson_id, query, limit=5):
        if lesson_id not in LESSONS:
            raise ValueError('课程不存在')
        if not isinstance(query, str) or not 1 <= len(query.strip()) <= 300:
            raise ValueError('请输入1—300字的问题')
        # The complete filter is authored here. Runtime input cannot replace it.
        data = {'query':tokenize(query), 'top_k':min(max(int(limit),1),10),
                'filters':{'field':'meta.lesson_id','operator':'==','value':lesson_id}}
        with self.lock:
            results = self.pipeline.run({'retrieve':data})['retrieve']['documents']
        # BM25 can include zero-score rows; those are not relevant evidence.
        return [dict(d.meta['block'], score=round(d.score,4)) for d in results if d.score and d.score > 0]


_search = None
_search_lock = threading.Lock()
def search_materials(lesson_id, query, limit=5):
    global _search
    with _search_lock:
        if _search is None:
            _search = MaterialSearch()
    return _search.search(lesson_id, query, limit)
