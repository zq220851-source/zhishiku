// SPA adapter. Original character and splash sources stay byte-for-byte intact.
import {Stage} from './character/stage.js';
import {runSplash} from './src/splash/splash.js';
import {prefs, reducedMotion} from './src/app/prefs.js';

export function mountOriginal(host, dock, onFailure) {
  let stage, disposed=false, playing=false, frame=0;
  try { stage=new Stage(host,{look:prefs.get('look')}); }
  catch { onFailure(); return ()=>{}; }
  const position=()=>{
    if(disposed||playing)return;
    const r=dock.getBoundingClientRect();
    Object.assign(host.style,{width:r.width+'px',height:r.height+'px',transform:`translate3d(${r.left}px,${r.top}px,0)`,opacity:'1'});
    stage._resize();
  };
  const pet={host,stage,brain:stage.brain,greet(){},
    enterSplash(k=1){
      playing=true;host.classList.add('in-splash');stage.brain.facing=0;
      const s=Math.min(innerWidth*.8,innerHeight*.5,440),w=s*.88;
      const r={w:w*k,h:s*k,x:(innerWidth-w)/2-w*(k-1)/2,y:innerHeight*.47-s*.6-s*(k-1)/2};
      Object.assign(host.style,{width:r.w+'px',height:r.h+'px',transform:`translate3d(${r.x}px,${r.y}px,0)`});stage._resize();return r;
    },
    exitSplash(){playing=false;host.classList.remove('in-splash');position();}
  };
  const replay=()=>{if(!playing&&!disposed&&!reducedMotion()){stage.brain.setState('awake',{quick:true});runSplash({pet},'force');}};
  const gesture=()=>stage.brain.play('glassesNudge',{essential:true});
  const motion=()=>{stage.brain.reducedMotion=reducedMotion();};motion();
  const voice=e=>{if(playing||disposed)return;if(e.detail.state)stage.brain.setState(e.detail.state);if(e.detail.level!==undefined)stage.brain.setVoiceLevel(e.detail.level);};
  addEventListener('medrep:voice',voice);
  const unsubscribe=prefs.subscribe(motion);
  const observer=new ResizeObserver(position);observer.observe(dock);
  addEventListener('resize',position);addEventListener('scroll',position,true);
  addEventListener('medrep:replay',replay);dock.addEventListener('click',gesture);
  position();
  frame=requestAnimationFrame(()=>{if(!disposed&&!reducedMotion()&&!new URLSearchParams(location.search).has('nosplash'))replay();});
  return ()=>{
    disposed=true;removeEventListener('medrep:voice',voice);cancelAnimationFrame(frame);observer.disconnect();unsubscribe();
    removeEventListener('resize',position);removeEventListener('scroll',position,true);removeEventListener('medrep:replay',replay);dock.removeEventListener('click',gesture);
    // Original splash owns its listeners. Let its skip handler complete before destroying Stage.
    if(document.body.classList.contains('splashing')){dispatchEvent(new KeyboardEvent('keydown',{key:'Escape'}));setTimeout(()=>stage.destroy(),450);}else stage.destroy();
  };
}
