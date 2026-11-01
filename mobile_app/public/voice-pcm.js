class VoicePCM extends AudioWorkletProcessor {
 constructor(){super();this.output=new Int16Array(640);this.index=0;this.position=0;this.sum=0;this.samples=0;this.stopped=false;this.port.onmessage=e=>{if(e.data==='flush'){this.stopped=true;if(this.index)this.port.postMessage(this.output.slice(0,this.index).buffer);this.port.postMessage({type:'flushed'});}};}
 process(inputs){if(this.stopped)return true;const channel=inputs[0]?.[0];if(channel)for(const value of channel){this.sum+=value;this.samples++;this.position+=16000;if(this.position>=sampleRate){this.position-=sampleRate;const f=Math.max(-1,Math.min(1,this.sum/this.samples));this.output[this.index++]=Math.round(f*(f<0?32768:32767));this.sum=0;this.samples=0;if(this.index===640){this.port.postMessage(this.output.buffer,[this.output.buffer]);this.output=new Int16Array(640);this.index=0;}}}return true;}
}
registerProcessor('voice-pcm',VoicePCM);
