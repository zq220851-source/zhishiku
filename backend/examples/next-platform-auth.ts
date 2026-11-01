/** Integration TEMPLATE for server-side Next.js routes (not wired into V2).
 * Both the mobile Web and the platform API must be served under the SAME origin.
 * User-provided header IDs/roles are never trusted.
 */
export type PlatformUser = {
  id: string;
  display_name: string;
  tenant_id: string;
  role: 'employee' | 'manager' | 'medical_reviewer' | 'admin';
};

export async function requirePlatformUser(request: Request): Promise<PlatformUser> {
  const base = process.env.PLATFORM_INTERNAL_URL;
  if (!base || !/^http:\/\/[a-zA-Z0-9_.-]+:\d+$/.test(base)) {
    throw new Error('Platform identity service is not configured');
  }
  const sid = request.headers.get('cookie')?.split(';').map(x => x.trim())
    .find(x => x.startsWith('medrep_sid='));
  if (!sid) throw new Error('Not authenticated');
  const response = await fetch(base + '/v1/auth/me', {
    headers: { cookie: sid }, cache: 'no-store', signal: AbortSignal.timeout(3000),
  });
  if (!response.ok) throw new Error('Not authenticated');
  const data = await response.json();
  if (!data?.user?.id || !data?.user?.tenant_id) throw new Error('Invalid platform identity');
  return data.user as PlatformUser;
}

// Example: const actor = await requirePlatformUser(request);
// Then use actor.id for ownership queries and role checks BEFORE business DB I/O.
// Do not simply remove existing local-only guards and leave the routes unprotected.
