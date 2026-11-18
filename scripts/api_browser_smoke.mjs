// Synthetic integration smoke only. Requires locally installed Chrome and built web assets.
import {spawn} from 'node:child_process';
import {mkdir,mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const pause=ms=>new Promise(r=>setTimeout(r,ms));
await mkdir('.build',{recursive:true});
const profile=await mkdtemp(join(tmpdir(),'lrc-screenshot-chrome-'));
const backend=spawn('.venv/bin/python',['scripts/api_smoke_fixture.py','--port','18766'],{stdio:'ignore'});
let chrome,ws;
try {
  let ready=false;
  for(let i=0;i<100;i++) {try{ready=(await fetch('http://127.0.0.1:18766/health')).ok;}catch{}if(ready)break;await pause(100);}
  if(!ready)throw new Error('Synthetic backend failed to start');
  chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',[
    '--headless=new','--remote-debugging-port=0','--user-data-dir='+profile,'--no-first-run',
    '--no-default-browser-check','--disable-extensions','--disable-background-networking','--disable-sync','about:blank'
  ],{stdio:'ignore'});
  let port;
  for(let i=0;i<200;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];}catch{}if(port)break;await pause(100);}
  if(!port)throw new Error('Chrome headless did not expose the capture endpoint');
  const target=await (await fetch('http://127.0.0.1:'+port+'/json/new?about:blank',{method:'PUT'})).json();
  ws=new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve,reject)=>{ws.addEventListener('open',resolve,{once:true});ws.addEventListener('error',reject,{once:true});});
  let next=0;const pending=new Map();
  ws.addEventListener('message',e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const {resolve,reject,timer}=pending.get(m.id);clearTimeout(timer);pending.delete(m.id);m.error?reject(new Error(JSON.stringify(m.error))):resolve(m.result);}});
  function call(method,params={}){return new Promise((resolve,reject)=>{const id=++next;const timer=setTimeout(()=>{pending.delete(id);reject(new Error('Timeout '+method));},15000);pending.set(id,{resolve,reject,timer});ws.send(JSON.stringify({id,method,params}));});}
  const evaluate=async expression=>(await call('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true})).result?.value;
  await call('Page.enable');
  await call('Emulation.setDeviceMetricsOverride',{width:1500,height:1400,deviceScaleFactor:1,mobile:false});
  await call('Page.navigate',{url:'http://127.0.0.1:18766/#token=synthetic-ui-test-only'});
  const waitFor=async(expression)=>{for(let i=0;i<100;i++){if(await evaluate('Boolean('+expression+')'))return;await pause(100);}throw new Error('UI condition not reached: '+expression);};
  const click=async text=>{const found=await evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!b||b.disabled)return false;b.click();return true;})()`);if(!found)throw new Error('Button unavailable: '+text);};
  const request=async path=>await evaluate(`fetch('/api'+${JSON.stringify(path)}).then(r=>r.json())`);
  await waitFor("[...document.querySelectorAll('.service-switch option')].some(o=>o.value==='synthetic-ui')");
  await evaluate("(()=>{const s=document.querySelector('.service-switch select');s.value='synthetic-ui';s.dispatchEvent(new Event('change',{bubbles:true}));})()");
  await waitFor("[...document.querySelectorAll('button')].some(b=>b.textContent==='Stima e rivedi invio a OpenAI'&&!b.disabled)");
  await click('Stima e rivedi invio a OpenAI');
  await waitFor("document.querySelector('dialog[open] input[type=number]')&&!document.querySelector('dialog[open] fieldset').disabled");
  if(await evaluate("[...document.querySelectorAll('dialog label')].find(l=>l.textContent.startsWith('Budget complessivo del servizio'))?.querySelector('input').value!==''"))throw new Error('Budget should remain optional and blank');
  await click('Calcola stima senza inviare foto');
  await waitFor("document.querySelector('.api-estimate')");
  const before=await request('/synthetic-transport-status');
  if(before.mock_calls!==0)throw new Error('Unexpected transport count before confirmation: '+JSON.stringify(before));
  const original=await evaluate("document.querySelector('.api-original-prompt').textContent");
  if(original!=='  Conserva le forme sintetiche blu.\nPreferisci varianti differenti!  \n')throw new Error('Original text changed');
  if(await evaluate("!([...document.querySelectorAll('button')].find(b=>b.textContent==='Conferma e invia a OpenAI')?.disabled)"))throw new Error('Confirmation not gated by acknowledgement');
  await evaluate("Promise.all([...document.images].map(i=>i.decode().catch(()=>{}))).then(()=>true)");
  const review=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile('.build/api-review-before-confirm.png',Buffer.from(review.data,'base64'));
  await evaluate("(()=>{const label=[...document.querySelectorAll('dialog label')].find(l=>l.textContent.includes('Confermo l’invio a OpenAI'));label.querySelector('input').click();})()");
  await click('Conferma e invia a OpenAI');
  await waitFor("document.querySelector('dialog[open]')?.textContent.includes('Completata')");
  const after=await request('/synthetic-transport-status');
  if(after.mock_calls!==3||!after.original_text_preserved||after.real_network_calls!==0)throw new Error('Unexpected simulated transport: '+JSON.stringify({after,status:await request('/services/synthetic-ui/api-status')}));
  const status=await request('/services/synthetic-ui/api-status');
  if(status.job.status!=='completed'||status.spent_usd<=0||status.reserved_usd!==0)throw new Error('Usage ledger incorrect');
  await evaluate("(()=>{const e=[...document.querySelectorAll('dialog label')].find(l=>l.textContent.startsWith('Numero finale OpenAI')).querySelector('input');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'2');e.dispatchEvent(new Event('input',{bubbles:true}));})()");
  await click('Aggiorna numero finale senza nuove chiamate');
  await waitFor("document.querySelector('.selection-count')?.textContent.includes('2 proposte')");
  const reselection=await request('/synthetic-transport-status');
  if(reselection.mock_calls!==3)throw new Error('Reselect triggered another API call');
  const final=await call('Page.captureScreenshot' ,{format:'png',captureBeyondViewport:false});
  await writeFile('.build/api-review-completed.png',Buffer.from(final.data,'base64'));
  await call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  const mobile=await evaluate('({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth,dialog:document.querySelector("dialog").scrollWidth,dialogWidth:document.querySelector("dialog").clientWidth})');
  if(mobile.scroll>mobile.width||mobile.dialog>mobile.dialogWidth)throw new Error('API dialog overflows: '+JSON.stringify(mobile));
  const mobileImage=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});
  await writeFile('.build/api-review-mobile.png',Buffer.from(mobileImage.data,'base64'));
  console.log(JSON.stringify({estimateNoTransmission:true,explicitConfirmation:true,originalTextPreserved:true,mockCalls:after.mock_calls,usageRecorded:true,optionalBudget:true,reselectionWithoutNetwork:true,realNetworkCalls:0,mobile,screenshots:['.build/api-review-before-confirm.png','.build/api-review-completed.png','.build/api-review-mobile.png']}));
  await call('Browser.close').catch(()=>{});
} finally {
  if(ws)ws.close();
  if(chrome)chrome.kill('SIGTERM');
  backend.kill('SIGTERM');
}
