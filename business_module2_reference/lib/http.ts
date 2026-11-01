import { createHmac, randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { Module2Error } from './errors';
import { ROLES } from './roles';
import type { Actor, Role } from './types';

const cookieName = 'module2_test_session';
let secret: Buffer | undefined;
function key(): Buffer {
  if (secret) return secret;
  const directory = path.dirname(process.env.MODULE2_DATABASE_PATH || path.join(process.cwd(), '.data/module2.sqlite'));
  mkdirSync(directory, { recursive: true, mode: 0o700 });
  const filename = path.join(directory, 'session.key');
  try { writeFileSync(filename, randomBytes(32), { flag: 'wx', mode: 0o600 }); }
  catch (error) { if ((error as NodeJS.ErrnoException).code !== 'EEXIST') throw error; }
  secret = readFileSync(filename);
  if (secret.length !== 32) throw new Error('Invalid session key');
  return secret;
}
const sign = (payload: string) => createHmac('sha256', key()).update(payload).digest('base64url');
export function gate(request: Request) {
  const url = new URL(request.url), host = request.headers.get('host') ?? url.host;
  if (!/^(localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?$/.test(host)) throw new Module2Error('LOCAL_ONLY', '当前模块仅开放本机虚构资料测试。', 403);
  if (request.method !== 'GET' && (request.headers.get('origin') !== `${url.protocol}//${host}` || request.headers.get('sec-fetch-site') === 'cross-site')) throw new Module2Error('ORIGIN_REJECTED', '请求来源不匹配。', 403);
}
export function actor(request: Request): Actor {
  const signed=request.headers.get('x-medrep-identity');
  if(signed){
    const bridgeKey=process.env.MEDREP_MODULE2_BRIDGE_SECRET||'';
    const [payload,signature,extra]=signed.split('.');
    if(bridgeKey.length<32||!payload||!signature||extra)throw new Module2Error('UNAUTHENTICATED','内部身份无效',401);
    const expected=Buffer.from(createHmac('sha256',bridgeKey).update(payload).digest('hex')),received=Buffer.from(signature);
    if(received.length!==expected.length||!timingSafeEqual(expected,received))throw new Module2Error('UNAUTHENTICATED','内部签名无效',401);
    const data=JSON.parse(Buffer.from(payload,'base64url').toString('utf8'));
    if(typeof data.id!=='string'||!/^[a-f0-9-]{36}$/.test(data.id)||!ROLES.includes(data.role)||!Number.isSafeInteger(data.expires)||data.expires< Date.now()/1000||data.expires>Date.now()/1000+120)throw new Module2Error('UNAUTHENTICATED','内部身份过期',401);
    const scope=data.scope;
    if(scope!==undefined && (!scope || typeof scope.tenant!=='string' || typeof scope.actorId!=='string' || typeof scope.reviewer!=='boolean' || !Array.isArray(scope.teams) || scope.teams.some((t: {id:unknown;name:unknown;owners:unknown})=>!t || typeof t.id!=='string' || typeof t.name!=='string' || !Array.isArray(t.owners) || t.owners.some(x=>typeof x!=='string'))))throw new Module2Error('UNAUTHENTICATED','团队身份无效',401);
    return {id:data.id,role:data.role,scope};
  }
  const value = request.headers.get('cookie')?.split(';').map(s => s.trim()).find(s => s.startsWith(`${cookieName}=`))?.slice(cookieName.length + 1);
  if (value && value.length <= 1024) {
    const [payload, signature, extra] = value.split('.');
    if (payload && signature && !extra) {
      const expected = Buffer.from(sign(payload)), received = Buffer.from(signature);
      if (received.length === expected.length && timingSafeEqual(expected, received)) {
        try {
          const data = JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
          if (typeof data.id === 'string' && /^[a-f0-9-]{36}$/.test(data.id) && ROLES.includes(data.role) && typeof data.expires === 'number' && data.expires > Date.now()) return { id: data.id, role: data.role };
        } catch { /* Invalid sessions never fall back to a client-provided identity. */ }
      }
    }
  }
  throw new Module2Error('UNAUTHENTICATED', '测试会话已失效，请重新进入。', 401);
}
export function session(request: Request, role?: unknown): Response {
  let identity: Actor;
  try { identity = actor(request); } catch { identity = { id: randomUUID(), role: 'EMPLOYEE' }; }
  if (role !== undefined) {
    if (typeof role !== 'string' || !ROLES.includes(role as Role)) throw new Module2Error('INVALID_INPUT', '无效测试职责。');
    // Explicit test-only switch; cannot choose another identity or enterprise permissions.
    identity = { ...actor(request), role: role as Role };
  }
  const payload = Buffer.from(JSON.stringify({ ...identity, expires: Date.now() + 8 * 3600000 })).toString('base64url');
  const response = json({ mode: 'MODULE2_TEST', role: identity.role });
  response.headers.set('Set-Cookie', `${cookieName}=${payload}.${sign(payload)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=28800${new URL(request.url).protocol === 'https:' ? '; Secure' : ''}`);
  return response;
}
export function json(data: unknown, status = 200): Response { return Response.json({ data }, { status, headers: { 'Cache-Control': 'no-store' } }); }
export async function body(request: Request): Promise<unknown> {
  if (request.headers.get('content-type')?.split(';')[0] !== 'application/json') throw new Module2Error('INVALID_INPUT', '请求须使用 JSON。');
  const reader = request.body?.getReader();
  if (!reader) throw new Module2Error('INVALID_INPUT', '请求体为空。');
  let size = 0; const chunks: Uint8Array[] = [];
  try {
    for (;;) { const { done, value } = await reader.read(); if (done) break; size += value.byteLength; if (size > 180000) { await reader.cancel(); throw new Module2Error('BODY_TOO_LARGE', '请求体过大。', 413); } chunks.push(value); }
    return JSON.parse(Buffer.concat(chunks).toString('utf8'));
  } catch (error) { if (error instanceof Module2Error) throw error; throw new Module2Error('INVALID_INPUT', '请求体不是有效 JSON。'); }
  finally { reader.releaseLock(); }
}
export async function route(run: () => Promise<Response> | Response): Promise<Response> {
  try { return await run(); }
  catch (error) {
    const known = error instanceof Module2Error;
    return Response.json({ error: { code: known ? error.code : 'INTERNAL_ERROR', message: known ? error.message : '操作未完成，请重试。' } }, { status: known ? error.status : 500, headers: { 'Cache-Control': 'no-store' } });
  }
}
