import {Stage} from './character/stage.js';
import {runSplash} from './src/splash/splash.js';
import {reducedMotion} from './src/app/prefs.js';
export function mountPet({host,dock,mini,status}){
 const stage=new Stage(host,{look:{glasses:'browline',outfit:'labcoat'}});
 let busy=false,floating=false;
 stage.brain.reducedMotion=reducedMotion();
 document.body.classList.add('has-native-pet');
 function position(instant=false){
  if(busy)return;
  const r=(floating?mini:dock).getBoundingClientRect();
  host.style.transition=instant?'none':'';
  host.style.width=r.width+'px';host.style.height=r.height+'px';
  host.style.transform=`translate3d(${r.left}px,${r.top}px,0)`;
  host.style.opacity='1';stage._resize();
  if(instant)requestAnimationFrame(()=>host.style.transition='');
 }
 const pet={host,stage,brain:stage.brain,greet(){},enterSplash(k=1){
  host.classList.add('in-splash');stage.brain.facing=0;
  const s=Math.min(innerWidth*.8,innerHeight*.5,440),w=s*.88;
  const r={w:w*k,h:s*k,x:(innerWidth-w*k)/2,y:innerHeight*.47-s*.6-s*(k-1)/2};
  host.style.transition='none';host.style.width=r.w+'px';host.style.height=r.h+'px';host.style.transform=`translate3d(${r.x}px,${r.y}px,0)`;void host.offsetWidth;stage._resize();return r;
 },exitSplash({instant=false}={}){busy=false;host.classList.remove('in-splash');position(instant);}};
 function play(){if(busy)return;busy=true;stage.brain.setState('awake',{quick:true});runSplash({pet},'force');const observer=new MutationObserver(()=>{if(!document.querySelector('.splash')){busy=false;position();observer.disconnect();}});observer.observe(document.body,{childList:true});}
 document.querySelector('.coach-replay').onclick=play;
 const greet=()=>{if(!busy)stage.brain.play('glassesNudge',{essential:true});};dock.onclick=greet;mini.onclick=greet;
 new IntersectionObserver(([e])=>{floating=!e.isIntersecting;mini.classList.toggle('visible',floating);position();},{threshold:.15}).observe(dock);
 addEventListener('scroll',()=>position(true),{passive:true});addEventListener('resize',()=>position(true));
 new ResizeObserver(()=>position(true)).observe(dock);
 // Let the original character respond to real UI activity, with no invented dialogue.
 let previousBusy=false;
 new MutationObserver(()=>{const processing=!!document.querySelector('main[aria-busy="true"],#connected-refresh:disabled')||/正在处理/.test(document.getElementById('notice')?.textContent||'');if(processing!==previousBusy&&!busy){previousBusy=processing;stage.brain.setState(processing?'thinking':'awake',{quick:true});}}).observe(document.body,{subtree:true,attributes:true,attributeFilter:['disabled','aria-busy'],childList:true,characterData:true});
 const voice=document.getElementById('voice-status');
 if(voice)new MutationObserver(()=>{if(!busy)stage.brain.setState(/聆听|听你|录音/.test(voice.textContent)?'listening':'awake',{quick:true});}).observe(voice,{childList:true,subtree:true,characterData:true});
 position(true);status.textContent='';
 // A shared window name survives switching the three local module ports in this tab.
 const seen=window.name==='medrep-coach-opened';
 window.name='medrep-coach-opened';
 if(!seen&&!reducedMotion()&&!new URLSearchParams(location.search).has('nosplash'))requestAnimationFrame(play);
}
