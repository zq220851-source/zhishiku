export type Role = 'employee' | 'manager' | 'medical_reviewer' | 'admin';
export interface Staff { id:string; display_name:string; role:Role; tenant_id:string }
export interface SavedState<T> { value:T|null; revision:number }
export type Screen = 'home'|'coach'|'review'|'daily'|'notes'|'account';
