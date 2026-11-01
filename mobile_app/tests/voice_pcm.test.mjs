import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
function processor(rate){const messages=[];let PCM;vm.runInNewContext(readFileSync(new URL('../public/voice-pcm.js',import.meta.url),'utf8'),{AudioWorkletProcessor:class{constructor(){this.port={postMessage:x=>messages.push(x)};}},sampleRate:rate,Int16Array,Math,registerProcessor:(_name,ctor)=>PCM=ctor});return {p:new PCM(),messages};}
test('flush preserves the final partial PCM packet before stop acknowledgment',()=>{const {p,messages}=processor(16000);p.process([[new Float32Array(128).fill(.5)]]);assert.equal(messages.length,0);p.port.onmessage({data:'flush'});assert.equal(new Int16Array(messages[0]).length,128);assert.equal(new Int16Array(messages[0])[0],16384);assert.equal(messages[1].type,'flushed');p.process([[new Float32Array(128)]]);assert.equal(messages.length,2);});
test('48k input is resampled to 16k PCM without losing packet remainder',()=>{const {p,messages}=processor(48000);p.process([[new Float32Array(1980).fill(-1)]]);p.port.onmessage({data:'flush'});assert.equal(new Int16Array(messages[0]).length,640);assert.equal(new Int16Array(messages[1]).length,20);assert.equal(new Int16Array(messages[0])[0],-32768);});
