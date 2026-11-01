import { DatabaseSync } from 'node:sqlite';
import { mkdirSync, chmodSync } from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { Module2Error } from './errors';

export const digest = (value: unknown) => createHash('sha256').update(JSON.stringify(value)).digest('hex');
export class Store {
  readonly db: DatabaseSync;
  constructor(filename = process.env.MODULE2_DATABASE_PATH || path.join(process.cwd(), '.data/module2.sqlite')) {
    if (filename !== ':memory:') mkdirSync(path.dirname(filename), { recursive: true, mode: 0o700 });
    this.db = new DatabaseSync(filename);
    if (filename !== ':memory:') chmodSync(filename, 0o600);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;
      CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, kind TEXT NOT NULL, owner TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY AUTOINCREMENT, entity_id TEXT NOT NULL, actor TEXT NOT NULL, type TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS requests (scope TEXT NOT NULL, key TEXT NOT NULL, hash TEXT NOT NULL, entity_id TEXT NOT NULL, PRIMARY KEY(scope,key));
      CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'event is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'event is immutable'); END;
      CREATE TABLE IF NOT EXISTS frozen_raw (id TEXT PRIMARY KEY, feedback_id TEXT NOT NULL, owner TEXT NOT NULL, version INTEGER NOT NULL, payload TEXT NOT NULL, UNIQUE(feedback_id,version));
      CREATE TRIGGER IF NOT EXISTS raw_no_update BEFORE UPDATE ON frozen_raw BEGIN SELECT RAISE(ABORT,'raw is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS raw_no_delete BEFORE DELETE ON frozen_raw BEGIN SELECT RAISE(ABORT,'raw is immutable'); END;
      CREATE TABLE IF NOT EXISTS frozen_plans (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
      CREATE TRIGGER IF NOT EXISTS plans_no_update BEFORE UPDATE ON frozen_plans BEGIN SELECT RAISE(ABORT,'plan is immutable'); END;
      CREATE TRIGGER IF NOT EXISTS plans_no_delete BEFORE DELETE ON frozen_plans BEGIN SELECT RAISE(ABORT,'plan is immutable'); END;`);
  }
  transaction<T>(fn: () => T): T {
    this.db.exec('BEGIN IMMEDIATE');
    try { const result = fn(); this.db.exec('COMMIT'); return result; }
    catch (error) { this.db.exec('ROLLBACK'); throw error; }
  }
  get<T>(id: string, kind: string, owner: string): T {
    const row = this.db.prepare('SELECT payload FROM entities WHERE id=? AND kind=? AND owner=?').get(id, kind, owner) as { payload: string } | undefined;
    if (!row) throw new Module2Error('NOT_FOUND', '任务或复盘不存在。', 404);
    return JSON.parse(row.payload) as T;
  }
  list<T>(kind: string, owner: string): T[] {
    return (this.db.prepare('SELECT payload FROM entities WHERE kind=? AND owner=? ORDER BY rowid DESC').all(kind, owner) as { payload: string }[]).map(r => JSON.parse(r.payload) as T);
  }
  put(id: string, kind: string, owner: string, value: unknown) {
    this.db.prepare('INSERT INTO entities VALUES(?,?,?,1,?) ON CONFLICT(id) DO UPDATE SET revision=revision+1,payload=excluded.payload WHERE entities.kind=excluded.kind AND entities.owner=excluded.owner').run(id, kind, owner, JSON.stringify(value));
  }
  event(entity: string, actor: string, type: string, metadata: unknown = {}) {
    this.db.prepare('INSERT INTO events(entity_id,actor,type,metadata,created_at) VALUES(?,?,?,?,?)').run(entity, actor, type, JSON.stringify(metadata), new Date().toISOString());
  }
  idempotent<T>(scope: string, key: string, input: unknown, run: () => { id: string; value: T }, read: (id: string) => T): T {
    if (!/^[a-zA-Z0-9_-]{1,128}$/.test(key)) throw new Module2Error('INVALID_INPUT', '缺少有效请求标识。');
    return this.transaction(() => {
      const hash = digest(input);
      const prior = this.db.prepare('SELECT hash,entity_id FROM requests WHERE scope=? AND key=?').get(scope, key) as { hash: string; entity_id: string } | undefined;
      if (prior) {
        if (prior.hash !== hash) throw new Module2Error('IDEMPOTENCY_CONFLICT', '该请求标识已用于不同内容。', 409);
        return read(prior.entity_id);
      }
      const result = run();
      this.db.prepare('INSERT INTO requests VALUES(?,?,?,?)').run(scope, key, hash, result.id);
      return result.value;
    });
  }
  close() { this.db.close(); }
}
