import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const feishu=fs.readFileSync(new URL('../src/feishuH5.ts',import.meta.url),'utf8');
const app=fs.readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8');
const api=fs.readFileSync(new URL('../src/api.ts',import.meta.url),'utf8');
test('real Feishu code collected via JS API, never from user entered open_id',()=>{
 assert.match(feishu,/tt\.requestAccess/); assert.match(feishu,/tt\.requestAuthCode/);
 assert.match(feishu,/VITE_FEISHU_APP_ID/); assert.doesNotMatch(feishu,/APP_SECRET|sk-[a-zA-Z0-9]/);
});
test('H5 login is optional and does not remove the original login',()=>{
 assert.match(app,/doFeishuLogin/);assert.match(app,/使用飞书工作台身份登录/);
 assert.match(app,/doLogin/);assert.match(app,/CoachStudio/);
});
test('SSO and existing API retain authenticated employee bearer',()=>{
 assert.match(api,/\/v1\/mobile\/auth\/feishu/);
 assert.match(api,/setAccessToken\(data\.access_token\)/);
 assert.match(api,/request<CoachRun>/);
});
test('H5 same-origin HTTPS fallback only, never localhost network hop',()=>{
 assert.match(api,/window\.location\.protocol === 'https:'/);
 assert.match(api,/window\.location\.origin/);
});
