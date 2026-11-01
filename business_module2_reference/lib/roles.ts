import type { Role } from './types';
export const ROLES: readonly Role[] = ['EMPLOYEE', 'TRAINING_REVIEWER', 'MEDICAL_REVIEWER', 'PUBLISHER'];
export const roleNames: Record<Role, string> = { EMPLOYEE: '员工', TRAINING_REVIEWER: '培训审核', MEDICAL_REVIEWER: '医学审核', PUBLISHER: '发布管理' };
