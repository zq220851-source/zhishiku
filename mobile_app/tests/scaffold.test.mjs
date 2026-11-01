import test from 'node:test';import assert from 'node:assert/strict';import fs from 'node:fs';
const source=fs.readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');
const config=fs.readFileSync(new URL('../capacitor.config.ts',import.meta.url),'utf8');
test('supports Android+iOS using Capacitor webDir',()=>{assert.match(config,/webDir:\s*'dist'/);assert.match(config,/cn.medrep.coach/)});
test('API uses bearer only and avoids local storage for token',()=>{assert.match(source,/Bearer/);assert.match(source,/credentials:'omit'/);assert.doesNotMatch(source,/localStorage|sessionStorage|Preferences/)});
test('mobile endpoints match Phase 6 backend',()=>{for(const x of ['auth/login','auth/me','auth/logout','state/ui/personal_notes'])assert.ok(source.includes(x))});
test('HTTPS enforced outside loopback',()=>assert.match(source,/url\.protocol === 'https:'/));
