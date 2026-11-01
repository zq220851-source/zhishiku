/** SERVER-ONLY integration building block for Next.js Route Handlers.
 * Do not import into Client Components. Do not make protected V2 routes public
 * until both identity and record-owner checks are enforced before DB reads/writes.
 */
import 'server-only';

export type PlatformActor = {
  id: string;
  tenant_id: string;
  display_name: string;
  role: 'employee' | 'manager' | 'medical_reviewer' | 'admin';
};

export class PlatformAccessDenied extends Error {}

function internalBase(): string {
  const value = process.env.PLATFORM_INTERNAL_URL;
  if (!value || !/^http:\/\/(?:127\.0\.0\.1|localhost|platform)(?::\d+)?$/.test(value)) {
    // Use private service DNS and authenticated TLS if hosts live on different networks.
    throw new PlatformAccessDenied('Private platform service is not configured');
  }
  return value;
}

async function platformFetch(path: string, init: RequestInit): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${internalBase()}${path}`, {
      ...init, cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(3000),
    });
  } catch {
    throw new PlatformAccessDenied('Identity service unavailable');
  }
  return response;
}

export async function requirePlatformActor(request: Request): Promise<PlatformActor> {
  const cookie = (request.headers.get('cookie') || '').split(';').map(x => x.trim())
    .find(x => x.startsWith('medrep_sid='));
  if (!cookie) throw new PlatformAccessDenied('Not authenticated');
  const result = await platformFetch('/v1/auth/me', { headers: { Cookie: cookie } });
  if (!result.ok) throw new PlatformAccessDenied('Session expired');
  const body: { user?: Partial<PlatformActor> } = await result.json();
  const actor = body?.user;
  if (!actor?.id || !actor?.tenant_id || !actor.role) throw new PlatformAccessDenied('Invalid platform identity');
  return actor as PlatformActor;
}

function moduleHeaders(module: 'coach' | 'review' | 'daily'): HeadersInit {
  const keyNames = {coach: 'COACH_SERVICE_KEY', review:'REVIEW_SERVICE_KEY', daily:'DAILY_SERVICE_KEY'};
  const token = process.env[keyNames[module]];
  if (!token || token.length < 32) throw new PlatformAccessDenied('Module credential missing');
  return {'x-medrep-module': module, 'x-medrep-service-key': token};
}

export async function registerOwnedRecord(
  actor: PlatformActor, module: 'coach'|'review'|'daily', kind: string, ref: string,
): Promise<void> {
  const response = await platformFetch('/v1/internal/records', {
    method:'POST', headers: {...moduleHeaders(module), 'content-type':'application/json'},
    body: JSON.stringify({owner_user_id:actor.id, object_kind:kind, external_ref:ref}),
  });
  if (!response.ok) throw new PlatformAccessDenied('Record ownership registration rejected');
}

export async function requireRecordOwner(
  actor: PlatformActor, module: 'coach'|'review'|'daily', kind: string, ref: string,
): Promise<void> {
  const qs = new URLSearchParams({object_kind:kind, external_ref:ref});
  const response = await platformFetch(`/v1/internal/records/owner?${qs}`, {headers:moduleHeaders(module)});
  if (!response.ok) throw new PlatformAccessDenied('Record owner not found');
  const body = await response.json();
  if (body?.owner_user_id !== actor.id) throw new PlatformAccessDenied('Record access denied');
}
