import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Store } from '../lib/store';
import { Service } from '../lib/service';
import { mainFixture } from '../lib/fixture';
import type { Actor } from '../lib/types';
const employee: Actor = { id: 'employee-a', role: 'EMPLOYEE' };
const medical: Actor = { id: 'reviewer', role: 'MEDICAL_REVIEWER' };
const publisher: Actor = { id: 'admin', role: 'PUBLISHER' };
function setup(raw = '虚构测试：用药后疑似不良反应。') {
  const store = new Store(':memory:'), service = new Service(store);
  const task = service.createTask(employee, mainFixture(), 'task');
  const feedback = service.saveRaw(employee, task.id, { text: raw, confirmed: true, exchangeOccurred: true }, 'raw');
  return { store, service, task, feedback };
}
test('save isolates and routes risks atomically without requiring a model; repeated analysis does not duplicate delivery', async () => {
  const { store, service, feedback } = setup(); let calls = 0;
  try {
    assert.equal(feedback.state, 'RESTRICTED');
    const inbox = service.risks.list(medical); assert.equal(inbox.length, 1); assert.equal(inbox[0].state, 'OPEN');
    assert.equal(service.risks.list(employee).length, 1); assert.equal(service.risks.list(publisher).length, 0);
    const detail = service.risks.detail(medical, inbox[0].id);
    assert.equal(detail.rawText, feedback.versions[0].text); assert.equal(detail.rawVersion, 1);
    await service.analyze(employee, feedback.id, 1, async () => { calls++; return {}; }, 'unused');
    await service.analyze(employee, feedback.id, 1, async () => { calls++; return {}; }, 'unused');
    assert.equal(calls, 0); assert.equal(service.risks.list(medical).length, 1);
    assert.equal(store.db.prepare("SELECT COUNT(*) AS n FROM events WHERE type='RISK_ROUTED'").get()?.n, 1);
    assert.ok(!JSON.stringify(store.db.prepare('SELECT * FROM events').all()).includes(detail.rawText));
  } finally { store.close(); }
});
test('test policy routes safety and privacy separately; raw detail and processing require the assigned responsibility', () => {
  const { store, service } = setup('虚构测试：用药后疑似不良反应，未经授权的资料。');
  try {
    assert.equal(service.risks.list(employee).length, 2);
    assert.equal(service.risks.list({ ...employee, id: 'other' }).length, 0);
    const m = service.risks.list(medical)[0], p = service.risks.list(publisher)[0];
    assert.throws(() => service.risks.detail(employee, m.id), { code: 'FORBIDDEN' });
    assert.throws(() => service.risks.detail(publisher, m.id), { code: 'FORBIDDEN' });
    assert.throws(() => service.risks.update(employee, m.id, 'RECEIVED', 1, '', 'forged'), { code: 'FORBIDDEN' });
    assert.throws(() => service.risks.update(medical, p.id, 'RECEIVED', 1, '', 'forged'), { code: 'FORBIDDEN' });
    assert.equal(service.risks.list({ id: 'trainer', role: 'TRAINING_REVIEWER' }).length, 0);
    assert.ok(!('rawText' in service.risks.list(employee)[0]));
  } finally { store.close(); }
});
test('receipt, processing and resolution enforce transition, revision, reason, idempotency and separate audit decisions', () => {
  const { store, service, feedback } = setup();
  try {
    const risk = service.risks.list(medical)[0];
    assert.throws(() => service.risks.update(medical, risk.id, 'RESOLVED', 1, 'skip', 'skip'), { code: 'INVALID_TRANSITION' });
    const received = service.risks.update(medical, risk.id, 'RECEIVED', 1, '', 'receive');
    assert.equal(received.revision, 2);
    assert.equal(service.risks.update(medical, risk.id, 'RECEIVED', 1, '', 'receive').revision, 2);
    assert.throws(() => service.risks.update(medical, risk.id, 'IN_PROGRESS', 1, '', 'stale'), { code: 'VERSION_CONFLICT' });
    assert.throws(() => service.risks.update(medical, risk.id, 'RECEIVED', 1, 'changed', 'receive'), { code: 'IDEMPOTENCY_CONFLICT' });
    service.risks.update(medical, risk.id, 'IN_PROGRESS', 2, '', 'start');
    assert.throws(() => service.risks.update(medical, risk.id, 'RESOLVED', 3, '', 'no-note'), { code: 'INVALID_INPUT' });
    const resolved = service.risks.update(medical, risk.id, 'RESOLVED', 3, '测试接收箱内处理完成，不代表正式企业报告。', 'resolve');
    assert.equal(resolved.state, 'RESOLVED');
    assert.equal(service.getFeedback(employee, feedback.id).state, 'RESTRICTED');
    assert.equal(service.risks.detail(medical, risk.id).history.length, 4);
    const records = store.db.prepare("SELECT metadata FROM events WHERE type='RISK_RECEIVED'").all() as { metadata: string }[];
    assert.equal(JSON.parse(records[0].metadata).role, 'MEDICAL_REVIEWER');
    assert.throws(() => store.db.prepare('DELETE FROM risk_routes').run(), /immutable/);
  } finally { store.close(); }
});
test('editing original feedback cannot erase or silently resolve a routed historical risk', () => {
  const { store, service, feedback, task } = setup();
  try {
    const original = service.risks.list(medical)[0];
    service.saveRaw(employee, task.id, { text: '修订为普通讨论。', confirmed: true, exchangeOccurred: true, expectedVersion: 1 }, 'edit', feedback.id);
    const detail = service.risks.detail(medical, original.id);
    assert.equal(detail.superseded, true); assert.equal(detail.rawVersion, 1); assert.equal(detail.state, 'OPEN');
    assert.equal(detail.rawText, feedback.versions[0].text);
  } finally { store.close(); }
});
test('normal safety evidence discussion does not create a report case', () => {
  const { store, service, feedback } = setup('讨论虚构研究的安全性证据及局限。');
  try { assert.equal(feedback.state, 'SAVED'); assert.equal(service.risks.list(medical).length, 0); }
  finally { store.close(); }
});

test('routing failure rolls back raw submission and isolation instead of losing a required handoff', () => {
  const store = new Store(':memory:'), service = new Service(store);
  try {
    const task = service.createTask(employee, mainFixture(), 'task');
    store.db.exec("CREATE TRIGGER force_route_failure BEFORE INSERT ON risk_routes BEGIN SELECT RAISE(ABORT,'test routing failure'); END;");
    assert.throws(() => service.saveRaw(employee, task.id, { text: '疑似不良反应。', confirmed: true, exchangeOccurred: true }, 'raw'), /test routing failure/);
    assert.equal(service.feedback(employee, task.id).length, 0);
    assert.equal(service.risks.list(medical).length, 0);
    assert.equal(store.db.prepare('SELECT COUNT(*) AS n FROM frozen_raw').get()?.n, 0);
    store.db.exec('DROP TRIGGER force_route_failure');
    service.saveRaw(employee, task.id, { text: '疑似不良反应。', confirmed: true, exchangeOccurred: true }, 'raw');
    assert.equal(service.risks.list(medical).length, 1);
  } finally { store.close(); }
});
