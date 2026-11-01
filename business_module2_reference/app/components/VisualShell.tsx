'use client';
import {useEffect} from 'react';
export function VisualShell(){
 useEffect(()=>{
  if(document.querySelector('script[data-coach-visual]'))return;
  const script=document.createElement('script');script.type='module';script.src='http://127.0.0.1:8892/visual/coach.js';script.dataset.coachVisual='true';document.body.append(script);
 },[]);
 return null;
}
