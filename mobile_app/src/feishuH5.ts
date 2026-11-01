/** Optional Feishu Workbench H5 login. This module never handles App Secret.
 * User identity comes ONLY from backend verification of a one-time Feishu auth code.
 */
type CodeResult = { code?: string };
type FeishuFailure = { errno?: number; errString?: string };
type CodeCallbacks = { success: (data: CodeResult) => void; fail: (err: FeishuFailure) => void };
type TT = {
  requestAccess?: (args: CodeCallbacks & { appID: string; scopeList: string[] }) => void;
  requestAuthCode?: (args: CodeCallbacks & { appId: string }) => void;
};
type SDK = { ready: (fn: () => void) => void; error?: (fn: (reason: unknown) => void) => void };
declare global { interface Window { h5sdk?: SDK; tt?: TT } }
const appId = import.meta.env.VITE_FEISHU_APP_ID?.trim() ?? '';

export function canFeishuSSO():boolean {
  return Boolean(appId && typeof navigator !== 'undefined' && /feishu|lark/i.test(navigator.userAgent));
}

async function getSDK(): Promise<SDK> {
  if (window.h5sdk) return window.h5sdk;
  // Versioned Feishu JS SDK. Never insert App Secret or model API keys in the browser.
  const src = 'https://lf-scm-cn.feishucdn.com/lark/op/h5-js-sdk-1.5.44.js';
  return new Promise<SDK>((resolve,reject)=>{
    const script=document.createElement('script');
    const timeout=window.setTimeout(()=>{script.remove(); reject(new Error('飞书 SDK 加载超时'));},12000);
    script.src=src; script.async=true;
    script.onload=()=>{window.clearTimeout(timeout);window.h5sdk ? resolve(window.h5sdk):reject(new Error('无法初始化飞书 SDK'));};
    script.onerror=()=>{window.clearTimeout(timeout);reject(new Error('飞书 SDK 下载失败'));};
    document.head.appendChild(script);
  });
}

export async function acquireFeishuCode(): Promise<string> {
  if(!canFeishuSSO()) throw new Error('请在飞书工作台内打开，并配置 VITE_FEISHU_APP_ID');
  const sdk = await getSDK();
  return new Promise<string>((resolve,reject)=>{
    let settled=false;
    const timer=window.setTimeout(()=>fail(new Error('飞书身份授权超时')),20000);
    function complete(code?:string){if(settled)return;settled=true;window.clearTimeout(timer);
      code&&code.length>=5?resolve(code):reject(new Error('飞书未返回有效授权码'));}
    function fail(e:unknown){if(settled)return;settled=true;window.clearTimeout(timer);
      reject(e instanceof Error?e:new Error('飞书授权失败，请检查应用可用范围'));}
    sdk.error?.(()=>fail(new Error('飞书 SDK 初始化失败')));
    sdk.ready(()=>{
      const tt=window.tt;
      if(!tt) return fail(new Error('当前环境不支持飞书身份接口'));
      const legacy=()=>{
        if(!tt.requestAuthCode) return fail(new Error('飞书客户端版本过低，不支持免登录'));
        tt.requestAuthCode({appId,success:r=>complete(r.code),fail:()=>fail(new Error('飞书客户端拒绝授权'))});
      };
      if (!tt.requestAccess) return legacy();
      tt.requestAccess({appID:appId,scopeList:[],success:r=>complete(r.code),
        fail:err=>err.errno===103?legacy():fail(new Error('飞书登录授权失败'))});
    });
  });
}
