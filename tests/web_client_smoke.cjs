/* Optional: node tests/web_client_smoke.cjs. Simulated DOM/transport, not a browser. */
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const path = require('node:path');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
class Element {
  constructor(value='') { this.value=value; this.textContent=''; this.disabled=false; this.hidden=false; this.listeners={}; }
  addEventListener(name,callback) { this.listeners[name]=callback; }
  replaceChildren(...options) { this.options=options; this.value=options[0]?.value ?? ''; }
}
const ids=['model','provider','temperature','temperature-value','max-tokens','prompt','prompt-form','send','stop','response','error','status','request-detail','ttft','speed','input-count','output-count','cost','cost-caption','usage-badge','usage-note','total'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()]));
elements.provider.value='openai'; elements.temperature.value='0.7';elements['max-tokens'].value='512';
const document={getElementById:id=>elements[id],createElement:()=>new Element()};
let mode='success';
const telemetry={input_tokens:11,output_tokens:5,total_tokens:16,ttft_ms:20,tokens_per_second:5,
  usage_source:'provider',cached_input_tokens:0,cache_write_input_tokens:0,stop_reason:'stop'};
const encoder=new TextEncoder();
const frame=(event,payload)=>encoder.encode(`event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`);
async function fetchMock(url,options) {
 if(url==='/api/models')return {ok:true,json:async()=>[{id:'gpt-4o-mini',provider:'openai'},{id:'claude-haiku-4-5-20251001',provider:'anthropic'}]};
 assert.equal(options.method,'POST');
 let streamController;
 const response={ok:true,body:new ReadableStream({start(c){streamController=c;}})};
 options.signal.addEventListener('abort',()=>streamController.error(new DOMException('Aborted','AbortError')));
 if(mode==='error') { streamController.enqueue(frame('error',{type:'AuthenticationError',message:'Set your local .env key.'}));streamController.close();return response; }
 streamController.enqueue(frame('chunk',{delta_text:'First ',is_final:false,telemetry:null}));
 if(mode==='stop')return response;
 setTimeout(()=>{
  // Split in the middle of UTF-8 to exercise the incremental decoder.
  const bytes=frame('chunk',{delta_text:'<script>unsafe()</script> café',is_final:true,telemetry,display_cost_usd:'0.000005'});
  const split=bytes.indexOf(0xc3)+1;
  streamController.enqueue(bytes.slice(0,split));streamController.enqueue(bytes.slice(split));streamController.close();
 },30);
 return response;
}
const context={document,fetch:fetchMock,AbortController,TextDecoder,console};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../src/web/app.js'),'utf8'),context);
async function submit(){return elements['prompt-form'].listeners.submit({preventDefault(){}});}
(async()=>{
 await sleep(0);assert.equal(elements.model.value,'gpt-4o-mini');
 elements.prompt.value='test';const pending=submit();await sleep(5);
 assert.equal(elements.response.textContent,'First ');assert.equal(elements.status.textContent,'Streaming…');
 assert.equal(elements.stop.disabled,false);await pending;
 assert.equal(elements.response.textContent,'First <script>unsafe()</script> café');
 assert.equal(elements.cost.textContent,'$0.000005');assert.equal(elements['usage-badge'].textContent,'FINAL');
 assert.equal(elements.send.disabled,false);
 elements.provider.value='anthropic';elements.provider.listeners.change();
 assert.equal(elements.model.value,'claude-haiku-4-5-20251001');
 mode='stop';const stopped=submit();await sleep(5);elements.stop.listeners.click();await stopped;
 assert.equal(elements.status.textContent,'Stopped · partial results');assert.equal(elements['usage-badge'].textContent,'INCOMPLETE');
 mode='error';await submit();assert.match(elements.error.textContent,/AuthenticationError/);
 assert.equal(elements['usage-badge'].textContent,'INCOMPLETE');assert.equal(elements.send.disabled,false);
 console.log('Client smoke checks passed: progressive text, split UTF-8, metrics, provider switch, Stop, error recovery. Simulated DOM and transport.');
})().catch(error=>{console.error(error);process.exitCode=1;});
