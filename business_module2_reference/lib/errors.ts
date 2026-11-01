export class Module2Error extends Error {
  constructor(public code: string, message: string, public status = 400) { super(message); }
}
export function invalid(message: string): never { throw new Module2Error('INVALID_INPUT', message); }
export function object(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) invalid('需要 JSON 对象。');
  return value as Record<string, unknown>;
}
export function text(value: unknown, max = 200): string {
  if (typeof value !== 'string' || !value.trim() || value.length > max) invalid('字段不能为空或超过长度限制。');
  return value;
}
export function list(value: unknown, max = 100): unknown[] {
  if (!Array.isArray(value) || value.length > max) invalid('列表不合法或超过长度限制。');
  return value;
}
export function strings(value: unknown, max = 100): string[] {
  const result = list(value, max).map(v => text(v));
  if (new Set(result).size !== result.length) invalid('标识或枚举值不能重复。');
  return result;
}
export function unique(values: { id: string }[]) {
  if (new Set(values.map(v => v.id)).size !== values.length) invalid('对象标识不能重复。');
}
