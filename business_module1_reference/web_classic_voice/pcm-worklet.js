class PCMRecorder extends AudioWorkletProcessor {
  constructor(){super();this.frame=new Float32Array(2048);this.offset=0;}
  process(inputs){
    const channel=inputs[0]?.[0];
    if(channel)for(let i=0;i<channel.length;i++){
      this.frame[this.offset++]=channel[i];
      if(this.offset===this.frame.length){this.port.postMessage(this.frame);this.offset=0;}
    }
    return true;
  }
}
registerProcessor('pcm-recorder',PCMRecorder);
