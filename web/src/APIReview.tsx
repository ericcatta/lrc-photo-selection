import {useEffect,useState,useRef,type ReactNode} from 'react';
import {api,photoPath,servicePath,type Service} from './api';

type Job={plan_id:string;status:string;completed:number;total:number;error:string|null;final_target?:number};
type Resume={plan_id:string;photo_ids:string[];compatible:boolean;reason:string;completed:number;total:number;final_target:number};
type Usage={resume?:Resume|null;job:Job|null;spent_usd:number;reserved_usd:number;budget_usd:number|null;remaining_usd:number|null;api_target?:number;usage?:{input_tokens:number;output_tokens:number};receipts?:{request_id:string;plan_id:string;response_id:string|null;model:string;usage:{input_tokens:number;output_tokens:number}|null;cost_usd:number|null;reserved_usd:number}[];cost_basis?:string};
type Estimate={plan_id:string;service_id:string;revision:number;model:string;instructions:string;criteria:string[];photos:{id:string;filename:string;preview_sha256:string;cached:boolean}[];photo_count:number;uncached_count:number;cached_count:number;estimated_cost_usd:number;reserve_usd:number;guard_usd?:number;final_target:number;request_count?:number;interpretation_request_count?:number;collection_request_count?:number;collection_sheet_count?:number;budget_usd:number|null;spent_usd:number;reserved_usd:number;remaining_usd:number|null;can_confirm:boolean;pricing:{input_per_million:number;output_per_million:number;verified_at:string;source:string};warnings:string[]};
const usd=(value:number)=>new Intl.NumberFormat('it-CH',{style:'currency',currency:'USD',minimumFractionDigits:4,maximumFractionDigits:4}).format(value);
const active=(job:Job|null|undefined)=>Boolean(job&&['queued','running','cancel_requested'].includes(job.status));
const jobLabel:Record<string,string>={estimated:'Stima pronta',queued:'In coda',running:'In corso',cancel_requested:'Interruzione richiesta',completed:'Completata',paused:'In pausa',cancelled:'Interrotta'};
const validUsage=(usage:unknown):usage is {input_tokens:number;output_tokens:number}=>Boolean(usage&&typeof usage==='object'&&Number.isFinite((usage as {input_tokens?:number}).input_tokens)&&Number.isFinite((usage as {output_tokens?:number}).output_tokens));
const describe=(e:unknown)=>e instanceof Error?e.message:'Operazione non completata.';

export function APIReview({service:s,dirty,disabled,update,openRequest=0,hideEntry=false,entryLabel}:{service:Service;dirty:boolean;disabled:boolean;update:(s:Service)=>void;openRequest?:number;hideEntry?:boolean;entryLabel?:string}){
  const path=servicePath(s.id);
  const openedRequest=useRef(0);
  const summary=useRef<HTMLElement>(null);
  const budgetDetails=useRef<HTMLDetailsElement>(null);
  const budgetInput=useRef<HTMLInputElement>(null);
  function editBudget(){if(budgetDetails.current)budgetDetails.current.open=true;budgetInput.current?.focus();}
  const [open,setOpen]=useState(false),[budget,setBudget]=useState(''),[selected,setSelected]=useState<string[]>([]);
  const [usage,setUsage]=useState<Usage|null>(null),[estimate,setEstimate]=useState<Estimate|null>(null);
  const [ack,setAck]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const [showAll,setShowAll]=useState(false);
  const [target,setTarget]=useState(s.proposal?.api_target??s.settings.target);
  const eligible=s.photos.filter(p=>p.preview_ready);
  const readyForAPI=s.status==='ready'||s.status==='analyzing'||active(usage?.job);
  const validTarget=Number.isInteger(target)&&target>=1&&target<=s.photos.length;
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
    const initial=s.settings.workflow_path==='openai'?s.photos.map(p=>p.id):s.proposal?.shortlist??s.selected_ids??s.photos.map(p=>p.id);
    setSelected(initial.filter(id=>eligible.some(p=>p.id===id)));
    try{const next=await status();if(next.resume?.compatible){setSelected(next.resume.photo_ids.filter(id=>eligible.some(p=>p.id===id)));}setBudget(next.budget_usd==null?'':String(next.budget_usd));const currentTarget=next.job&&s.proposal?.api_plan_id===next.job.plan_id?s.proposal.api_target:undefined;setTarget(currentTarget??(next.resume?.compatible?next.resume.final_target:undefined)??next.job?.final_target??next.api_target??s.proposal?.api_target??Math.min(s.settings.target,eligible.length||1));}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  useEffect(()=>{if(openRequest>0&&openedRequest.current!==openRequest){openedRequest.current=openRequest;void show();}},[openRequest]);
  useEffect(()=>{if(estimate)summary.current?.focus();},[estimate]);
  function changeSelection(ids:string[]){setSelected(ids);setEstimate(null);setAck(false);}
  async function calculate(){
    setBusy(true);setError('');setAck(false);setEstimate(null);
    try{setEstimate(await api<Estimate>(path+'/api-estimate','POST',{revision:s.revision,budget_usd:budget.trim()?Number(budget):null,photo_ids:selected,target}));await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
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
  async function reselect(){
    if(!usage?.job||!validTarget)return;setBusy(true);setError('');try{update(await api<Service>(path+'/api-reselect','POST',{revision:s.revision,plan_id:usage.job.plan_id,target}));await status();}catch(e){setError(describe(e));}finally{setBusy(false);}
  }
  const validBudget=!budget.trim()||(Number.isFinite(Number(budget))&&Number(budget)>0);
  return <section className="tool-section api-review-entry">
    <button hidden={hideEntry} type="button" disabled={Boolean(s.archived)||dirty||!readyForAPI} onClick={()=>void show()}>{entryLabel??"Stima e rivedi invio a OpenAI"}</button>
    <p hidden={hideEntry} className="hint">Puoi inviare direttamente le anteprime importate oppure partire dalla proposta locale. Scegli le foto e conferma sempre il riepilogo prima dell’invio.</p>
    {dirty&&<p className="hint">Salva prima i criteri del servizio.</p>}
    {open&&<ReviewDialog close={()=>{setOpen(false);setEstimate(null);setAck(false);}}>
      <div className="modal-heading"><h2 id="api-review-title">Invio a OpenAI · {s.title}</h2><button type="button" aria-label="Chiudi invio OpenAI" onClick={()=>{setOpen(false);setEstimate(null);setAck(false);}}>Chiudi</button></div>
      <p>Solo le anteprime elencate e i provini da esse derivati saranno inviati a OpenAI dopo la tua conferma. Nessuna stella viene applicata.</p>
      {usage&&<p>Consumo registrato: {usd(usage.spent_usd)} · Riservato o incerto: {usd(usage.reserved_usd)}{usage.remaining_usd==null?' · Nessun budget complessivo impostato':' · Disponibile nel budget: '+usd(usage.remaining_usd)}</p>}
      <details><summary>Consumi e registro richieste</summary>{validUsage(usage?.usage)&&<p className="hint">Token registrati: {usage.usage.input_tokens} input · {usage.usage.output_tokens} output. {usage.cost_basis}</p>}
      {Boolean(usage?.receipts?.length)&&<details><summary>Registro richieste API</summary><ul>{usage?.receipts?.map(r=><li key={r.request_id}>{r.model} · {r.response_id??'esito incerto'} · {r.reserved_usd>0?'Esito/costo incerto, riserva '+usd(r.reserved_usd):r.cost_usd===null?'Costo incerto, riserva mantenuta':usd(r.cost_usd)}{validUsage(r.usage)?' · '+r.usage.input_tokens+' input / '+r.usage.output_tokens+' output':''}</li>)}</ul></details>}
      </details>
      {usage?.resume&&<p role="status" className={usage.resume.compatible?"hint":"warning"}>{usage.resume.compatible?`Ripresa del campione precedente: ${usage.resume.completed} valutazioni completate su ${usage.resume.total}. La stima verifica quali risultati possono essere riutilizzati.`:usage.resume.reason}</p>}
      {usage?.job&&<div aria-live="polite"><p>Analisi API: {jobLabel[usage.job.status]??usage.job.status} · {usage.job.completed}/{usage.job.total}</p>{usage.job.error&&<p className="warning">{usage.job.error}</p>}{active(usage.job)&&<button type="button" disabled={busy} onClick={()=>void cancel()}>Interrompi dopo la richiesta in corso</button>}</div>}
      <fieldset disabled={busy||active(usage?.job)}>
        <label>Numero finale OpenAI<input type="number" min={1} max={s.photos.length} value={Number.isNaN(target)?'':target} onChange={e=>{setTarget(e.target.valueAsNumber);setEstimate(null);setAck(false);}}/></label>
        <p className="hint">Indipendente dalle candidate locali. Dopo l’analisi puoi cambiarlo riutilizzando le valutazioni, senza nuovi invii.</p>
        {usage?.job?.status==='completed'&&<button type="button" disabled={!validTarget||dirty||disabled} onClick={()=>void reselect()}>Aggiorna numero finale senza nuove chiamate</button>}
        <details ref={budgetDetails}><summary>{budget.trim()&&Number.isFinite(Number(budget))?'Budget facoltativo attivo: '+usd(Number(budget)):'Budget complessivo facoltativo'}</summary><label>Budget complessivo del servizio (USD)<input ref={budgetInput} type="number" min="0" step="0.01" placeholder="Nessun limite aggiuntivo" value={budget} onChange={e=>{setBudget(e.target.value);setEstimate(null);setAck(false);}}/></label><p className="hint">Puoi lasciarlo vuoto: la conferma autorizza solo il limite prudenziale della stima corrente. Un budget impostato comprende anche il consumo precedente. Il saldo crediti OpenAI non viene verificato.</p></details>
        <details open={!estimate}><summary>Campione da analizzare · {selected.length} anteprime</summary><div className="api-selection-actions"><button type="button" onClick={()=>changeSelection(eligible.map(p=>p.id))}>Tutte le anteprime importate</button><button type="button" onClick={()=>changeSelection((s.proposal?.shortlist??[]).filter(id=>eligible.some(p=>p.id===id)))}>Solo proposta locale</button><button type="button" onClick={()=>changeSelection([])}>Deseleziona tutte</button><label className="check"><input type="checkbox" checked={showAll} onChange={e=>setShowAll(e.target.checked)}/>Mostra anche alternative e altre foto</label></div>
        <div className="api-photo-picker">{eligible.filter(p=>showAll||selected.includes(p.id)).map(p=><label key={p.id} className="api-photo-choice"><input type="checkbox" checked={selected.includes(p.id)} onChange={e=>changeSelection(e.target.checked?[...selected,p.id]:selected.filter(id=>id!==p.id))}/><img src={'/api'+photoPath(s.id,p.id)+'/preview'} alt="" loading="lazy"/><span>{p.filename}<small>ID {p.id}</small></span></label>)}</div>
        <p>{selected.length} anteprime selezionate</p></details>
        <button type="button" disabled={disabled||!validBudget||!validTarget||!selected.length||dirty||!readyForAPI} onClick={()=>void calculate()}>Calcola stima senza inviare foto</button>
        {(!validTarget||!selected.length||!validBudget||dirty||disabled||!readyForAPI)&&<p className="hint" role="status">{dirty?'Salva i criteri prima di preparare la stima.':!validTarget?`Scegli una quantità da 1 a ${s.photos.length}.`:!selected.length?'Seleziona almeno un’anteprima.':!validBudget?'Lascia il budget vuoto oppure inserisci un importo maggiore di zero.':'Attendi il completamento dell’operazione in corso.'}</p>}
      </fieldset>
      {estimate&&<section ref={summary} tabIndex={-1} className="api-estimate"><h3>Riepilogo da confermare</h3><p>Modello: <strong>{estimate.model}</strong> · {estimate.photo_count} anteprime · Obiettivo finale: {estimate.final_target} · Valutazioni nuove: {estimate.uncached_count} · Risultati in cache: {estimate.cached_count}</p><p>Richieste stimate: {estimate.request_count??estimate.uncached_count}{estimate.interpretation_request_count?' · '+estimate.interpretation_request_count+' per interpretare il testo':''}{estimate.collection_request_count?' · '+estimate.collection_request_count+' per confrontare l’insieme':''}</p>{Boolean(estimate.collection_request_count)&&<p className="hint">Il confronto globale usa tutte le anteprime confermate in {estimate.collection_sheet_count??0} provini derivati, insieme alle valutazioni delle singole foto. Non include altre foto.</p>}<p>Stima: {usd(estimate.estimated_cost_usd)} · Riserva prudenziale: <strong>{usd(estimate.reserve_usd)}</strong> · Limite autorizzato per questo invio: {usd(estimate.guard_usd??estimate.reserve_usd)}{estimate.budget_usd==null?'':' · Budget complessivo: '+usd(estimate.budget_usd)}</p><p className="hint">Stima, non costo garantito. Tariffe verificate il {estimate.pricing.verified_at}: input {estimate.pricing.input_per_million} USD / milione di token; output {estimate.pricing.output_per_million} USD / milione. <a href={estimate.pricing.source} target="_blank" rel="noreferrer">Fonte tariffe</a></p>
        <details><summary>Testo originale che riceverà OpenAI</summary><pre className="api-original-prompt">{estimate.instructions}</pre>{estimate.criteria.length>0&&<><p>Criteri aggiuntivi del servizio</p><ul>{estimate.criteria.map((c,i)=><li key={i}>{c}</li>)}</ul></>}</details>
        <details><summary>Elenco esatto: {estimate.photos.length} anteprime</summary><ul>{estimate.photos.map(p=><li key={p.id}>{p.filename} · ID {p.id}{p.cached?' · risultato in cache':''}</li>)}</ul></details>
        <details><summary>Dettagli e limiti della stima</summary>{estimate.warnings.map((warning,i)=><p className="hint" key={i}>{warning}</p>)}</details>
        {!estimate.can_confirm&&<div className="warning" role="alert" id="api-confirm-blocker">
          <p>Invio bloccato: il budget disponibile ({usd(estimate.remaining_usd??0)}) è inferiore alla riserva necessaria ({usd(estimate.reserve_usd)}). Puoi ridurre le anteprime oppure modificare il budget facoltativo, lasciandolo vuoto se non vuoi un limite complessivo. Poi ricalcola la stima e conferma l’invio.</p>
          <button type="button" disabled={busy} onClick={editBudget}>Modifica budget facoltativo</button>
        </div>}
        <label className="check"><input aria-describedby={!estimate.can_confirm?'api-confirm-blocker':undefined} type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)} disabled={!estimate.can_confirm||busy}/>Confermo l’invio a OpenAI di queste anteprime con il mio testo originale e il limite di costo indicato.</label>
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
