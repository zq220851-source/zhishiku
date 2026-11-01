import {useEffect,useRef,useState} from 'react';
export default function OriginalCompanion(){
 const host=useRef<HTMLDivElement>(null),dock=useRef<HTMLButtonElement>(null);
 const [fallback,setFallback]=useState(false);
 const [retry,setRetry]=useState(0);
 useEffect(()=>{let disposed=false;let cleanup:(()=>void)|undefined;let timer=0;
  const key='medrep.webgl.pending';
  try{if(sessionStorage.getItem(key)){setFallback(true);return;}sessionStorage.setItem(key,'1');}catch{/* storage unavailable */}
  void import('./original/mount.js').then(({mountOriginal})=>{if(!disposed&&host.current&&dock.current){cleanup=mountOriginal(host.current,dock.current,()=>setFallback(true));timer=window.setTimeout(()=>{try{sessionStorage.removeItem(key);}catch{/* storage unavailable */}},5000);}}).catch(()=>{if(!disposed)setFallback(true);});
  return()=>{disposed=true;clearTimeout(timer);cleanup?.();try{sessionStorage.removeItem(key);}catch{/* storage unavailable */}};
 },[retry]);
 return <><button ref={dock} className="mascot-hit" aria-label="和小博士互动" title="和小博士互动">{fallback&&<img src="/mascot.png" alt="小博士备用形象"/>}</button><div ref={host} className="original-pet" aria-label="小博士 3D 形象"/>{fallback&&<small className="pet-fallback" role="status">3D 初始化未完成，当前为备用形象。<button className="outline" onClick={()=>{try{sessionStorage.removeItem('medrep.webgl.pending');}catch{/* optional */}setFallback(false);setRetry(n=>n+1);}}>重试 3D</button></small>}</>;
}
