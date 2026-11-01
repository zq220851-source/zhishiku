import assert from 'node:assert/strict';
import { test } from 'node:test';
import { mkdtempSync, rmSync } from 'node:fs';
import path from 'node:path';
import { tmpdir } from 'node:os';
import { gate, body } from '../lib/http';

test('HTTP gate checks loopback Host and exact Origin, rejecting forwarded or cross-site access', () => {
  const request = (host: string, origin: string) => new Request('http://localhost:3202/api/module2', { method: 'POST', headers: { host, origin } });
  gate(request('127.0.0.1:3202', 'http://127.0.0.1:3202'));
  assert.throws(() => gate(request('evil.example', 'http://evil.example')), { code: 'LOCAL_ONLY' });
  assert.throws(() => gate(request('127.0.0.1:3202', 'https://evil.example')), { code: 'ORIGIN_REJECTED' });
});
test('request bodies reject malformed and oversized JSON', async () => {
  await assert.rejects(body(new Request('http://localhost', { method: 'POST', headers: { 'content-type': 'application/json' }, body: '{' })), { code: 'INVALID_INPUT' });
  await assert.rejects(body(new Request('http://localhost', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ text: 'x'.repeat(180001) }) })), { code: 'BODY_TOO_LARGE' });
});
test('route integrates signed sessions, owner isolation, actual persistence and configuration failure', async () => {
  const directory = mkdtempSync(path.join(tmpdir(), 'module2-http-'));
  process.env.MODULE2_DATABASE_PATH = path.join(directory, 'test.sqlite');
  process.env.MODULE2_MODEL_DATA_AUTHORIZED = 'true';
  process.env.MODULE2_MODEL_BASE_URL = ''; process.env.MODULE2_MODEL_NAME = ''; process.env.MODULE2_MODEL_API_KEY = '';
  const { GET, POST } = await import('../app/api/module2/route');
  const request = (value?: unknown, cookie = '', key = 'test-key') => new Request('http://127.0.0.1:3202/api/module2', { method: value === undefined ? 'GET' : 'POST', headers: { host: '127.0.0.1:3202', origin: 'http://127.0.0.1:3202', cookie, 'content-type': 'application/json', 'idempotency-key': key }, ...(value === undefined ? {} : { body: JSON.stringify(value) }) });
  try {
    assert.equal((await GET(request())).status, 401);
    const one = await POST(request({ action: 'session' })), two = await POST(request({ action: 'session' }));
    const cookie = one.headers.get('set-cookie')!.split(';')[0], other = two.headers.get('set-cookie')!.split(';')[0];
    assert.notEqual(cookie, other);
    const creation = await POST(request({ action: 'createTask', ownerId: 'forged' }, cookie));
    assert.equal(creation.status, 201);
    const task = (await creation.json()).data;
    assert.notEqual(task.ownerId, 'forged');
    assert.equal((await (await POST(request({ action: 'createTask' }, cookie))).json()).data.id, task.id);
    const forgedRead = request(undefined, other);
    const url = new URL(forgedRead.url); url.searchParams.set('taskId', task.id);
    assert.equal((await GET(new Request(url, forgedRead))).status, 404);
    const input = { action: 'saveRaw', taskId: task.id, raw: { text: '他问终点是什么意思。', confirmed: true, exchangeOccurred: true } };
    assert.equal((await POST(request(input, other))).status, 404);
    const saved = (await (await POST(request(input, cookie))).json()).data;
    const analyzed = (await (await POST(request({ action: 'analyze', feedbackId: saved.id, expectedVersion: 1 }, cookie))).json()).data;
    assert.equal(analyzed.state, 'FAILED'); assert.equal(analyzed.errorCode, 'MODEL_NOT_CONFIGURED'); assert.equal(analyzed.analysis, undefined);
    assert.equal(analyzed.versions[0].text, input.raw.text);
    const bootstrap = (await (await GET(request(undefined, cookie))).json()).data;
    assert.equal(bootstrap.model.configured, false); assert.equal(bootstrap.model.apiKey, undefined);
    const tampered = cookie.slice(0, -1) + (cookie.endsWith('a') ? 'b' : 'a');
    assert.equal((await GET(request(undefined, tampered))).status, 401);
    assert.equal((await POST(request({ action: 'publish', role: 'PUBLISHER' }, cookie))).status, 400);
    assert.equal((await POST(request({ action: 'switchRole', role: 'ROOT' }, cookie))).status, 400);
    assert.equal((await POST(request({ action: 'switchRole', role: 'MEDICAL_REVIEWER' }))).status, 401);
    const riskInput = { ...input, raw: { ...input.raw, text: '虚构测试：疑似不良反应。' } };
    const riskFeedback = (await (await POST(request(riskInput, cookie, 'risk-input'))).json()).data;
    assert.equal(riskFeedback.state, 'RESTRICTED');
    const employeeView = (await (await GET(request(undefined, cookie))).json()).data;
    const ticket = employeeView.risks[0]; assert.equal(ticket.state, 'OPEN'); assert.equal(ticket.rawText, undefined);
    assert.equal((await POST(request({ action: 'updateRisk', riskId: ticket.id, state: 'RECEIVED', expectedRevision: 1, role: 'MEDICAL_REVIEWER' }, cookie))).status, 403);
    const switched = await POST(request({ action: 'switchRole', role: 'MEDICAL_REVIEWER', ownerId: 'forged' }, other));
    const medicalCookie = switched.headers.get('set-cookie')!.split(';')[0];
    const medicalView = (await (await GET(request(undefined, medicalCookie))).json()).data;
    assert.equal(medicalView.actor.role, 'MEDICAL_REVIEWER'); assert.equal(medicalView.risks.length, 1);
    assert.equal(medicalView.tasks.length, 0); // Assigned ticket does not grant access to another employee's task collection.
    assert.equal((await POST(request({ action: 'createTask' }, medicalCookie))).status, 403);
    const riskUrl = new URL(request().url); riskUrl.searchParams.set('riskId', ticket.id);
    assert.equal((await GET(new Request(riskUrl, request(undefined, cookie)))).status, 403);
    const rawDetail = (await (await GET(new Request(riskUrl, request(undefined, medicalCookie)))).json()).data;
    assert.equal(rawDetail.rawText, riskInput.raw.text);
    const received = await POST(request({ action: 'updateRisk', riskId: ticket.id, state: 'RECEIVED', expectedRevision: 1 }, medicalCookie, 'receipt'));
    assert.equal((await received.json()).data.state, 'RECEIVED');
    const updatedEmployee = (await (await GET(request(undefined, cookie))).json()).data;
    assert.equal(updatedEmployee.risks[0].state, 'RECEIVED');

  } finally {
    (globalThis as typeof globalThis & { module2Service?: { store: { close(): void } } }).module2Service?.store.close();
    delete (globalThis as typeof globalThis & { module2Service?: unknown }).module2Service;
    rmSync(directory, { recursive: true, force: true });
  }
});
