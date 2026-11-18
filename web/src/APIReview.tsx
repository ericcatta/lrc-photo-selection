import {useEffect,useState,type ReactNode} from 'react';
import {api,photoPath,servicePath,type Service} from './api';

type Job={plan_id:string;status:string;completed:number;total:number;error:string|null};
type Usage={job:Job|null;spent_usd:number;reserved_usd:number;budget_usd:number;remaining_usd:number;usage?:{input_tokens:number;output_tokens:number};receipts?:{request_id:string;plan_id:string;response_id:string|null;model:string;usage:{input_tokens:number;output_tokens:number}|null;cost_usd:number|null;reserved_usd:number}[];cost_basis?:string};
type Estimate={plan_id:string;service_id:string;revision:number;model:string;instructions:string;criteria:string[];photos:{id:string;filename:string;preview_sha256:string;cached:boolean}[];photo_count:number;uncached_count:number;cached_count:number;estimated_cost_usd:number;reserve_usd:number;budget_usd:number;spent_usd:number;reserved_usd:number;remaining_usd:number;can_confirm:boolean;pricing:{input_per_million:number;output_per_million:number;verified_at:string;source:string};warnings:string[]};
const usd=(value:number)=>new Intl.NumberFormat('it-CH',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4}).format(value);
const active=(job:Job|null|undefined)=>Boolean(job&&['queued','running','cancel_requested'].includes(job.status));
const jobLabel:Record<string,string>={estimated:'Stima pronta',queued:'In coda',running:'In corso',cancel_requested:'Interruzione richiesta',completed:'Completata',paused:'In pausa',cancelled:'Interrotta'};
const validUsage=(usage:unknown):usage is {input_tokens:number;output_tokens:number}=>Boolean(usage&&typeof usage==='object'&&Number.isFinite((usage as {input_tokens?:number}).input_tokens)&&Number.isFinite((usage as {output_tokens?:number}).output_tokens));
const describe=(e:unknown)=>e instanceof Error?e.message:'Operazione non completata.';

export function APIReview({service:s,dirty,disabled,update}:{service:Service;dirty:boolean;disabled:boolean;update:(s:Service)=>void}){
  const path=servicePath(s.id);
  const [open,setOpen]=useState(false),[budget,setBudget]=useState('0'),[selected,setSelected]=useState<string[]>([]);
  const [usage,setUsage]=useState<Usage|null>(null),[estimate,setEstimate]=useState<Estimate|null>(null);
  const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [showAll,setShowAll]=useState(false);
  const eligible=s.photos.filter(p=>p.preview_ready);
  const localReady=Boolean(s.proposal&&!s.proposal.stale&&!s.requires_analysis);
  useEffect(()=>{setEstimate(null);setAck(false);},[s.revision,dirty]);
  async function status(){const next=await api<Usage>(path+'/api-status');setUsage(next);return next;}
  useEffect(()=>{
    if(!open&&!active(usage?.job))return;
    let alive=true;
    const timer=window.setInterval(()=>{void api<Usage>(path+'/api-status').then(next=>{if(!alive)return;setUsage(next);if(!active(next.job))void api<Service>(path).then(update).catch(()=>{});}).catch(e=>{if(alive)setError(describe(e));});},1200);
    return()=>{alive=false;window.clearInterval(timer);};
  },[open,path,usage?.job?.status,update]);
  async function show(){
    setOpen(true);setError('');setEstimate(null);setAck(false);setBusy(true);
    const initial=s.proposal?.shortlist??s.selected_ids??s.photos.map(p=>p.id);
    setSelected(initial.filter(id=>eligible.some(p=>p.id===id)));
    try{const next=await status();setBudget(String(next.budget_usd??0));}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  function changeSelection(ids:string[]){setSelected(ids);setEstimate(null);setAck(false);}
  async function calculate(){
    setBusy(true);setError('');setAck(false);setEstimate(null);
    try{setEstimate(await api<Estimate>(path+'/api-estimate','POST',{revision:s.revision,budget_usd:Number(budget),photo_ids:selected}));await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  async function confirm(){
    if(!estimate||!ack||!estimate.can_confirm||dirty||estimate.revision!==s.revision)return;
    setBusy(true);setError('');
    try{await api(path+'/api-confirm','POST',{plan_id:estimate.plan_id,confirm:true});setEstimate(null);setAck(false);await status();update(await api<Service>(path));}catch(e){setError(describe(e));setEstimate(null);setAck(false);}finally{setBusy(false);}
  }
  async function cancel(){
    if(!usage?.job)return;
    setBusy(true);setError('');try{await api(path+'/api-cancel','POST',{plan_id:usage.job.plan_id});await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  const validBudget=Number.isFinite(Number(budget))&&Number(budget)>0;
  return <section className="tool-section api-review-entry">
    <button type="button" disabled={Boolean(s.archived)||dirty||!localReady} onClick={()=>void show()}>Stima e rivedi invio a OpenAI</button>
    {!localReady&&<p className="hint">Esegui prima la selezione locale. Poi scegli quali anteprime inviare, comprese eventuali alternative.</p>}
    {dirty&&<p className="hint">Salva prima i criteri del servizio.</p>}
    {open&&<ReviewDialog close={()=>{setOpen(false);setEstimate(null);setAck(false);}}>
      <div className="modal-heading"><h2 id="api-review-title">Invio a OpenAI · {s.title}</h2><button type="button" aria-label="Chiudi invio OpenAI" onClick={()=>{setOpen(false);setEstimate(null);setAck(false);}}>Chiudi</button></div>
      <p>Solo le anteprime elencate saranno inviate a OpenAI dopo la tua conferma. Nessuna stella viene applicata.</p>
      {usage&&<p>Consumo registrato: {usd(usage.spent_usd)} · Riservato o incerto: {usd(usage.reserved_usd)} · Disponibile nel budget: {usd(usage.remaining_usd)}</p>}
      {validUsage(usage?.usage)&&<p className="hint">Token registrati: {usage.usage.input_tokens} input · {usage.usage.output_tokens} output. {usage.cost_basis}</p>}
      {Boolean(usage?.receipts?.length)&&<details><summary>Registro richieste API</summary><ul>{usage?.receipts?.map(r=><li key={r.request_id}>{r.model} · {r.response_id??'esito incerto'} · {r.reserved_usd>0?'Esito/costo incerto, riserva '+usd(r.reserved_usd):r.cost_usd===null?'Costo incerto, riserva mantenuta':usd(r.cost_usd)}{validUsage(r.usage)?' · '+r.usage.input_tokens+' input / '+r.usage.output_tokens+' output':''}</li>)}</ul></details>}
      {usage?.job&&<div aria-live="polite"><p>Analisi API: {jobLabel[usage.job.status]??usage.job.status} · {usage.job.completed}/{usage.job.total}</p>{usage.job.error&&<p className="warning">{usage.job.error}</p>}{active(usage.job)&&<button type="button" disabled={busy} onClick={()=>void cancel()}>Interrompi dopo la richiesta in corso</button>}</div>}
      <fieldset disabled={busy||active(usage?.job)}>
        <label>Budget complessivo del servizio (USD)<input type="number" min="0" step="0.01" value={budget} onChange={e=>{setBudget(e.target.value);setEstimate(null);setAck(false);}}/></label>
        <p className="hint">Limite applicativo comprensivo del consumo precedente. Il saldo dei crediti OpenAI va verificato nel tuo account; nessuna ricarica viene attivata.</p>
        <div className="api-selection-actions"><button type="button" onClick={()=>changeSelection((s.proposal?.shortlist??[]).filter(id=>eligible.some(p=>p.id===id)))}>Solo proposta locale</button><button type="button" onClick={()=>changeSelection([])}>Deseleziona tutte</button><label className="check"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>Mostra anche alternative e altre foto</label></div>
        <div className="api-photo-picker">{eligible.filter(p=>showAll||selected.includes(p.id)).map(p=><label key={p.id} className="api-photo-choice"><input type="checkbox" checked={selected.includes(p.id)} onChange={e=>changeSelection(e.target.checked?[...selected,p.id]:selected.filter(id=>id!==p.id))}/><img src={'/api'+photoPath(s.id,p.id)+'/preview'} alt="" loading="lazy"/><span>{p.filename}<small>ID {p.id}</small></span></label>)}</div>
        <p>{selected.length} anteprime selezionate</p>
        <button type="button" disabled={disabled||!validBudget||!selected.length||dirty||!localReady} onClick={()=>void calculate()}>Calcola stima senza inviare foto</button>
      </fieldset>
      {estimate&&<section className="api-estimate"><h3>Riepilogo da confermare</h3><p>Modello: <strong>{estimate.model}</strong> · {estimate.photo_count} anteprime · Valutazioni nuove: {estimate.uncached_count} · Risultati in cache: {estimate.cached_count}</p><p>Stima: {usd(estimate.estimated_cost_usd)} · Riserva prudenziale: <strong>{usd(estimate.reserve_usd)}</strong> · Budget: {usd(estimate.budget_usd)}</p><p className="hint">Stima, non costo garantito. Tariffe verificate il {estimate.pricing.verified_at}: input {estimate.pricing.input_per_million} USD / milione di token; output {estimate.pricing.output_per_million} USD / milione. <a href={estimate.pricing.source} target="_blank" rel="noreferrer">Fonte tariffe</a></p>
        <details><summary>Testo originale che riceverà OpenAI</summary><pre className="api-original-prompt">{estimate.instructions}</pre>{estimate.criteria.length>0&&<><p>Criteri aggiuntivi del servizio</p><ul>{estimate.criteria.map((c,i)=><li key={i}>{c}</li>)}</ul></>}</details>
        <details><summary>Elenco esatto: {estimate.photos.length} anteprime</summary><ul>{estimate.photos.map(p=><li key={p.id}>{p.filename} · ID {p.id}{p.cached?' · risultato in cache':''}</li>)}</ul></details>
        {estimate.warnings.map((warning,i)=><p className="warning" key={i}>{warning}</p>)}
        <label className="check"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={!estimate.can_confirm||busy}/>Confermo l’invio a OpenAI di queste anteprime con il mio testo originale e questo budget.</label>
        <button className="primary" type="button" disabled={!ack||!estimate.can_confirm||busy||dirty||estimate.revision!==s.revision} onClick={()=>void confirm()}>Conferma e invia a OpenAI</button>
      </section>}
      {error&&<p className="warning" role="alert">{error}</p>}
      <p className="hint">Puoi chiudere e continuare localmente. Per riprendere l’API prepara una nuova stima e conferma: i risultati validi già ottenuti saranno riutilizzati.</p>
    </ReviewDialog>}
  </section>;
}

function ReviewDialog({children,close}:{children:ReactNode;close:()=>void}){
  const [dialog,setDialog]=useState<HTMLDialogElement|null>(null);
  useEffect(()=>{if(dialog&&!dialog.open)dialog.showModal();},[dialog]);
  return <dialog ref={setDialog} className="api-review-modal" aria-labelledby="api-review-title" onCancel={e=>{e.preventDefault();close();}}>{children}</dialog>;
}
