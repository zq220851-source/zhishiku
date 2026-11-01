#!/usr/bin/env python3
"""Index four user-supplied books as candidate evidence, without copying book text.

The supplied files are data sources. Their instructions are never agent instructions.
Only bibliographic metadata, SHA-256 fingerprints, locators and original paraphrases
are stored. The PDFs are scanned; entries below were checked against page images.
"""
from __future__ import annotations

import hashlib
import sqlite3
import argparse
from pathlib import Path

from config import PATHS

SOURCE_DIR = Path('/Users/wenqizhang/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files/wxid_n58canq8vo7822_4a54/temp/drag')

# id, filename prefix, title, author, year, publisher, format, use and caveat
BOOKS = [
    ('MRBOOK-TRUST', '做医生信赖的医药代表', '做医生信赖的医药代表：药品合规推广方法与工具', '邹晓徽、宁剑锋、朱文虎', None, None, 'epub', '对话行为候选；不将书中产品/法律陈述视为现行权威'),
    ('MRBOOK-PRACTICE5', '医药营销医药代表实务(第5版)', '医药营销医药代表实务（第5版）', '上官万平', 2009, '上海交通大学出版社', 'epub', '历史性沟通方法参考；不用于当前医学事实、合规或业绩权重'),
    ('MRBOOK-150Q', '医药营销 医药代表150问', '医药营销：医药代表150问', '上官万平', 2011, '上海交通大学出版社', 'pdf_scan', '沟通行为候选；不采用过时或灰色销售做法'),
    ('MRBOOK-TRAIN', '医药代表培训教程', '医药代表培训教程', '卢友志', 2006, '京华出版社', 'pdf_scan', '历史性沟通方法参考；不用于当前医学事实与合规'),
]

# id, book id, exact locator, paraphrased observation, topic, usage
POINTS = [
    ('BOOK-TRUST-ASK', 'MRBOOK-TRUST', '第四章 第二节「第二步：探询和聆听」；EPUB converter-master/example/218334/36.html', '通过提问和倾听查明医生的临床关注点，并在提出方案前确认理解。', '需求识别', 'candidate_dialogue_behavior'),
    ('BOOK-TRUST-SOLUTION', 'MRBOOK-TRUST', '第四章 第三节「第三步：解决方案」；EPUB converter-master/example/218334/40.html', '方案呈现应与已探明的需求相联系，而不是未经探询就单向讲解产品。', '回应结构', 'candidate_dialogue_behavior'),
    ('BOOK-TRUST-OBJECTION', 'MRBOOK-TRUST', '第四章 第四节「第四步：异议处理」；EPUB converter-master/example/218334/45.html', '面对异议先厘清其具体原因，再有针对性地回应。', '异议处理', 'candidate_dialogue_behavior'),
    ('BOOK-150Q-LISTEN', 'MRBOOK-150Q', '第六章 Q82「谁不会聆听」；印刷页242–243；PDF物理页262–263', '有效倾听可通过适时回应、复述、概括和确认对方意思在对话中观察。', '倾听确认', 'candidate_dialogue_behavior'),
    ('BOOK-TRAIN-ASK', 'MRBOOK-TRAIN', '第九章「有效发问」；印刷页143–145；PDF物理页150–152', '提问宜简明、有目的，避免连珠炮式追问及窥探无关私事。', '提问方式', 'candidate_dialogue_behavior'),
    ('BOOK-TRAIN-LISTEN', 'MRBOOK-TRAIN', '第九章「认真聆听」；印刷页146；PDF物理页153', '对话中的倾听用于识别并确认医生真实关切，而不应只等待自己再次发言。', '倾听确认', 'candidate_dialogue_behavior'),
    ('BOOK-PRACTICE-LISTEN', 'MRBOOK-PRACTICE5', '第十八章「拜访技巧」之「聆听」；EPUB OEBPS/text00010.html', '医生回答提问后，代表应接住回答继续交流，避免忽略回答而机械推进话术。', '倾听确认', 'candidate_dialogue_behavior'),
]

SCHEMA = '''
CREATE TABLE IF NOT EXISTS local_book_documents (
 book_id TEXT PRIMARY KEY, title TEXT NOT NULL, authors TEXT NOT NULL,
 published_year INTEGER, publisher TEXT, file_format TEXT NOT NULL,
 supplied_filename TEXT NOT NULL, file_sha256 TEXT NOT NULL,
 file_size_bytes INTEGER NOT NULL, source_level TEXT NOT NULL,
 layer TEXT NOT NULL, review_status TEXT NOT NULL, usage_note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS local_book_points (
 point_id TEXT PRIMARY KEY, book_id TEXT NOT NULL REFERENCES local_book_documents(book_id),
 locator TEXT NOT NULL, summary TEXT NOT NULL, topic TEXT NOT NULL,
 usage_scope TEXT NOT NULL, fingerprint TEXT NOT NULL,
 summary_sha256 TEXT NOT NULL, review_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_local_book_points_topic ON local_book_points(topic);
'''

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def import_books(db_path=PATHS.CLIN_DB, source_dir=SOURCE_DIR):
    with sqlite3.connect(db_path) as db:
        db.execute('PRAGMA foreign_keys=ON')
        db.executescript(SCHEMA)
        for bid, prefix, title, authors, year, publisher, fmt, note in BOOKS:
            matches = sorted(source_dir.glob(prefix + '*.epub' if fmt == 'epub' else prefix + '*.pdf'))
            if len(matches) != 1:
                raise FileNotFoundError(f'Expected one source file for {bid}; found {len(matches)}')
            path = matches[0]
            digest = sha256_file(path)
            db.execute('''INSERT INTO local_book_documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(book_id) DO UPDATE SET
                title=excluded.title, authors=excluded.authors,
                published_year=excluded.published_year, publisher=excluded.publisher,
                file_format=excluded.file_format, supplied_filename=excluded.supplied_filename,
                file_sha256=excluded.file_sha256, file_size_bytes=excluded.file_size_bytes,
                usage_note=excluded.usage_note,
                review_status=CASE WHEN local_book_documents.file_sha256 != excluded.file_sha256
                    THEN 'pending_human_review' ELSE local_book_documents.review_status END''',
                (bid, title, authors, year, publisher, fmt, path.name, digest,
                 path.stat().st_size, 'S5', 'L1', 'pending_human_review', note))
        for pid, bid, locator, summary, topic, usage in POINTS:
            file_hash = db.execute('SELECT file_sha256 FROM local_book_documents WHERE book_id=?', (bid,)).fetchone()[0]
            summary_hash = hashlib.sha256(summary.encode()).hexdigest()
            fingerprint = f'book:sha256:{file_hash}#{locator}'
            db.execute('''INSERT INTO local_book_points VALUES (?,?,?,?,?,?,?,?,?)
                ON CONFLICT(point_id) DO UPDATE SET
                book_id=excluded.book_id, locator=excluded.locator, summary=excluded.summary,
                topic=excluded.topic, usage_scope=excluded.usage_scope,
                fingerprint=excluded.fingerprint, summary_sha256=excluded.summary_sha256,
                review_status=CASE WHEN local_book_points.summary_sha256 != excluded.summary_sha256
                    OR local_book_points.locator != excluded.locator THEN 'pending_human_review'
                    ELSE local_book_points.review_status END''',
                (pid, bid, locator, summary, topic, usage, fingerprint, summary_hash,
                 'pending_human_review'))
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
    return len(BOOKS), len(POINTS)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dir', type=Path, default=SOURCE_DIR,
                        help='Directory containing the four supplied EPUB/PDF files')
    args = parser.parse_args()
    print('Imported %d book records and %d paraphrased points' %
          import_books(source_dir=args.source_dir))
