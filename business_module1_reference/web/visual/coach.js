// Shared presentation only. Module APIs and ownership remain with each application.
const base=new URL('.',import.meta.url).href;
const page=document.body.dataset.module||({'8892':'1','3302':'2','8787':'3'}[location.port])||'1';
const copy={
 '1':['LEARN / PREPARE / PRACTICE','准备与演练','学习 · 访前预测 · 演练','准备与演练'],
 '2':['REFLECT / CONNECT / GROW','复盘与成长','复盘 · 五层更新 · 方法进化','复盘与成长'],
 '3':['READ / DISCOVER / CONNECT','知识与前沿','日报 · 医生学术搜索','知识与前沿']
}[page];
if(!document.querySelector('.coach-shell')){
 const shell=document.createElement('div');shell.className='coach-shell';
 shell.innerHTML=`<header class="coach-top topbar"><a class="coach-brand" href="http://127.0.0.1:8892/"><i aria-hidden="true"></i>MedRep <strong>Coach</strong></a><nav class="coach-modules" aria-label="三个模块">${Object.entries(copyForNav()).map(([id,n])=>`<a href="http://127.0.0.1:${{1:8892,2:3302,3:8787}[id]}/" ${id===page?'aria-current="page"':''}>${n}</a>`).join('')}</nav><button class="coach-replay" type="button" title="重播开屏动画">重播开屏 <span aria-hidden="true">↗</span></button></header><section class="coach-hero"><div><p class="coach-kicker">${copy[0]}</p><h1>${copy[1].replace('，','，<br class="coach-mobile-break">')}</h1><p class="coach-description">${copy[2]}</p></div><div class="coach-companion"><button id="mascot-open" aria-label="和小博士打招呼" title="点击和小博士打招呼"><span class="coach-orbit"></span><img id="mascot-fallback" src="${base}mascot.png" alt="戴眼镜、穿白大褂的小博士"></button><p><span class="coach-live-dot"></span>小博士，陪你一起准备</p><span id="pet-status" role="status"></span></div></section></div>`;
 document.body.prepend(shell);document.body.classList.add('coach-ui','module-'+page);
 const host=document.createElement('div');host.id='original-pet';host.className='original-pet';host.setAttribute('aria-hidden','true');document.body.append(host);
 const mini=document.createElement('button');mini.className='coach-mini';mini.setAttribute('aria-label','和小博士打招呼');mini.title='小博士';document.body.append(mini);
 import('./pet.js').then(({mountPet})=>mountPet({host,dock:document.getElementById('mascot-open'),mini,status:document.getElementById('pet-status')})).catch(()=>{document.body.classList.remove('has-native-pet');host.style.display='none';mini.style.display='none';document.getElementById('pet-status').textContent='3D 暂未加载，显示备用形象';document.querySelector('.coach-replay').disabled=true;});
}
function copyForNav(){return {'1':'准备与演练','2':'复盘与成长','3':'知识与前沿'};}
