// @vitest-environment jsdom
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {APIReview} from './APIReview';
import type {Service} from './api';

let calls:{url:string;body?:Record<string,unknown>}[];
const original='  Solo uccelli\nPreferisci ali aperte.\n';
const service={id:'synthetic',title:'TEST SINTETICO',revision:4,status:'ready',settings:{mode:'hybrid',instructions:original},photos:[{id:'p0',filename:'sintetica.jpg',preview_ready:true},{id:'p1',filename:'altra.jpg',preview_ready:true}],proposal:{shortlist:['p0'],stale:false},decisions:{}} as Service;
const initial={job:null,spent_usd:0,reserved_usd:0,budget_usd:0,remaining_usd:0};
function response(value:unknown){return new Response(JSON.stringify(value),{headers:{'Content-Type':'application/json'}});}
beforeEach(()=>{
  calls=[];
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','');}});
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    if(url.endsWith('/api-status'))return response(initial);
    if(url.endsWith('/api-estimate'))return response({plan_id:'plan-1',service_id:'synthetic',revision:4,model:'gpt-5.4-mini-2026-03-17',instructions:original,criteria:['Preferisci varianti'],photos:[{id:'p0',filename:'sintetica.jpg',cached:false}],photo_count:1,uncached_count:1,cached_count:0,estimated_cost_usd:.001,reserve_usd:.002,budget_usd:1,spent_usd:0,reserved_usd:0,remaining_usd:1,can_confirm:true,pricing:{input_per_million:.75,output_per_million:4.5,verified_at:'2026-11-18',source:'https://developers.openai.com/api/docs/models/gpt-5.4-mini'},warnings:[]});
    if(url.endsWith('/api-confirm')||url.endsWith('/api-cancel'))return response(initial);
    if(url==='/api/services/synthetic')return response(service);
    throw new Error('Unexpected '+url);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('estimates locally and only sends after explicit acknowledgement and confirmation',async()=>{
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  expect(calls).toHaveLength(0);
  fireEvent.click(screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}));
  await waitFor(()=>expect((screen.getByLabelText('Budget complessivo del servizio (USD)') as HTMLInputElement).value).toBe('0'));
  expect((screen.getByRole('button',{name:'Calcola stima senza inviare foto'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Budget complessivo del servizio (USD)'),{target:{value:'1'}});
  fireEvent.click(screen.getByRole('button',{name:'Calcola stima senza inviare foto'}));
  await screen.findByRole('heading',{name:'Riepilogo da confermare'});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body).toEqual({revision:4,budget_usd:1,photo_ids:['p0']});
  expect(document.querySelector('.api-original-prompt')?.textContent).toBe(original);
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
  const submit=screen.getByRole('button',{name:'Conferma e invia a OpenAI'});
  expect((submit as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('Confermo l’invio a OpenAI di queste anteprime con il mio testo originale e questo budget.'));
  fireEvent.click(submit);
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-confirm'))?.body).toEqual({plan_id:'plan-1',confirm:true});
});
it('allows adding alternatives to the exact sample and clears the estimate on budget changes',async()=>{
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}));
  await waitFor(()=>expect((screen.getByLabelText('Budget complessivo del servizio (USD)') as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(screen.getByLabelText('Mostra anche alternative e altre foto'));
  fireEvent.click(screen.getByLabelText(/altra.jpg/));
  fireEvent.change(screen.getByLabelText('Budget complessivo del servizio (USD)'),{target:{value:'1'}});
  fireEvent.click(screen.getByRole('button',{name:'Calcola stima senza inviare foto'}));
  await screen.findByRole('heading',{name:'Riepilogo da confermare'});
  expect(calls.find(c=>c.url.endsWith('/api-estimate'))?.body?.photo_ids).toEqual(['p0','p1']);
  fireEvent.change(screen.getByLabelText('Budget complessivo del servizio (USD)'),{target:{value:'2'}});
  expect(screen.queryByRole('button',{name:'Conferma e invia a OpenAI'})).toBeNull();
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});
it('requires saved criteria and local proposal before review',()=>{
  const {rerender}=render(<APIReview service={service} dirty={true} disabled={false} update={vi.fn()}/>);
  expect((screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}) as HTMLButtonElement).disabled).toBe(true);
  rerender(<APIReview service={{...service,proposal:null}} dirty={false} disabled={false} update={vi.fn()}/>);
  expect((screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}) as HTMLButtonElement).disabled).toBe(true);
  expect(calls).toHaveLength(0);
});

it('can inspect and cancel an active API run even while the service is busy',async()=>{
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;calls.push({url,body});
    return response({...initial,job:{plan_id:'active-plan',status:url.endsWith('/api-cancel')?'cancelled':'running',completed:1,total:3,error:null}});
  }));
  render(<APIReview service={service} dirty={false} disabled={true} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}));
  const cancel=await screen.findByRole('button',{name:'Interrompi dopo la richiesta in corso'});
  fireEvent.click(cancel);
  await waitFor(()=>expect(calls.some(c=>c.url.endsWith('/api-cancel'))).toBe(true));
  expect(calls.find(c=>c.url.endsWith('/api-cancel'))?.body).toEqual({plan_id:'active-plan'});
  expect(calls.some(c=>c.url.endsWith('/api-confirm'))).toBe(false);
});
it('shows uncertain reserved cost and omits unknown token counts',async()=>{
  vi.stubGlobal('fetch',vi.fn(async()=>response({...initial,job:{plan_id:'uncertain',status:'paused',completed:0,total:1,error:'Timeout'},receipts:[{request_id:'uncertain',plan_id:'uncertain',response_id:null,model:'model',usage:{},cost_usd:0,reserved_usd:.003}],usage:{}})));
  render(<APIReview service={service} dirty={false} disabled={false} update={vi.fn()}/>);
  fireEvent.click(screen.getByRole('button',{name:'Stima e rivedi invio a OpenAI'}));
  await screen.findByText(/Esito\/costo incerto, riserva/);
  expect(screen.getByText(/Analisi API: In pausa/)).toBeTruthy();
  expect(document.body.textContent).not.toContain('undefined');
  expect(document.body.textContent).not.toContain('Token registrati:');
});
