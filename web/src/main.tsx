import { createRoot } from 'react-dom/client';
import { useEffect, useRef, useCallback, useState, type CSSProperties } from 'react';
import { api, ApiError, photoPath, servicePath, type Plan, type Face, type Photo, type State, type Service, type Summary, type Settings, type Preset } from './api';
import './style.css';
import { OpenAISettings } from './OpenAISettings';
import { APIReview } from './APIReview';

const labels: Record<State,string> = {candidate:'Candidata',preferred:'Preferita',alternative:'Alternativa',excluded:'Esclusa',review:'Da rivedere'};
const states = Object.keys(labels) as State[];
const running = (s:Service) => s.job?.status === 'running' || s.job?.status === 'queued' || s.status === 'applying';
const message = (e:unknown) => e instanceof Error ? e.message : 'Operazione non completata.';
function Preview({service, photo, zoom}: {service:Service; photo:Photo; zoom?:number}) {
  return <div className={'preview'+(zoom ? ' zoom' : '')}>{photo.preview_ready ? <img style={zoom ? {width: zoom + '%', maxWidth:'none'} : undefined} src={'/api'+photoPath(service.id,photo.id)+'/preview'} loading={zoom?'eager':'lazy'} alt={photo.filename}/> : <span>Anteprima non disponibile</span>}</div>;
}

export function App() {
  const [services,setServices] = useState<Summary[]>([]);
  const [features,setFeatures]=useState(false);
  const [instructionsAvailable,setInstructionsAvailable]=useState(false);
  const [presets,setPresets] = useState<Preset[]>([]);
  const [service,setService] = useState<Service|null>(null);
  const [login,setLogin] = useState(false);
  const [token,setToken] = useState('');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function load() {
    const [all,available] = await Promise.all([api<Summary[]>('/services'),api<Preset[]>('/presets')]);
    setServices(all); setPresets(available); setLogin(false);
    void api<{features:boolean;instructions?:boolean}>('/capabilities').then(x=>{setFeatures(x.features);setInstructionsAvailable(Boolean(x.instructions));}).catch(()=>{setFeatures(false);setInstructionsAvailable(false);});
  }
  async function connect(value:string) {
    setBusy(true); setError('');
    try { await api('/session','POST',{token:value}); setToken(''); await load(); }
    catch(e) {setLogin(true); setError(message(e));}
    finally {setBusy(false);}
  }
  useEffect(() => {
    const fragment = new URLSearchParams(location.hash.slice(1));
    const initial = fragment.get('token');
    if (initial) { history.replaceState(null,'',location.pathname+location.search); void connect(initial); }
    else void load().catch(e => { if(e instanceof ApiError && [401,403].includes(e.status)) setLogin(true); else setError(message(e)); });
  },[]);
  async function refresh() {
    setError('');
    try { await load(); if(service) updateService(await api<Service>(servicePath(service.id))); }
    catch(e) { setError(message(e)); }
  }
  const dirty=useRef(false);
  const updateService=useCallback((next:Service)=>setService(prev=>prev?.id===next.id&&prev.revision<=next.revision?next:prev),[]);
  async function open(id:string) {
    if(id!==service?.id&&dirty.current&&!window.confirm('Scartare i criteri non salvati?'))return;
    setBusy(true); setError('');
    try { setService(await api<Service>(servicePath(id))); }
    catch(e) { setError(message(e)); }
    finally {setBusy(false);}
  }
  return <div className="app-shell">
    <header className="appbar">
      <div className="brand"><strong>Selezione</strong><span>Estensione per Lightroom Classic</span></div>
      {!login && <div className="service-controls">
        <label className="service-switch">Servizio
          <select value={service?.id ?? ''} disabled={busy} onChange={e => {if(e.target.value)void open(e.target.value);}}>
            <option value="" disabled>{services.length ? 'Scegli un servizio' : 'Nessun servizio importato'}</option>
            {services.map(item => <option key={item.id} value={item.id}>{item.title} · {item.photo_count} foto{item.archived?' · Archiviato':''}</option>)}
          </select>
        </label>
        <button onClick={refresh} disabled={busy}>Aggiorna</button>
      </div>}
      <span className="local-status">{service?.settings.mode==='hybrid'?'Ibrida · invio da confermare':'Solo locale'}</span>
    </header>
    <main>
      {!login&&<OpenAISettings/>}
      {error && <p role="alert" className="warning">{error}</p>}
      {login ? <form className="panel empty" onSubmit={e => {e.preventDefault();void connect(token);}}>
        <p className="eyebrow">Connessione al plugin</p><h1>Apri la sessione locale</h1>
        <p>Apri l’app dal plugin Lightroom oppure incolla il token di accesso.</p>
        <label>Token<input type="password" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off" required/></label>
        <button className="primary" disabled={busy}>Accedi</button>
      </form> : service ? <Workspace key={service.id} service={service} update={updateService} presets={presets} setPresets={setPresets} dirty={dirty} refreshSummaries={load} features={features} instructionsAvailable={instructionsAvailable}/> :
      <section className="panel empty"><p className="eyebrow">Da Lightroom alla selezione</p>
        <h1>{services.length?'Apri un servizio':'Importa un servizio da Lightroom'}</h1>
        <p>{services.length?'Scegli un servizio nel menu in alto.':'In Lightroom seleziona le foto, esegui “Prepara servizio” e poi premi Aggiorna.'}</p>
      </section>}
    </main>
  </div>;
}

function unifiedSettings(settings:Settings):Settings {
  const criteria=settings.service_criteria??settings.preset_snapshot?.criteria??[];
  const additions=[...criteria,...(settings.subject_query?[`Soggetto da privilegiare: ${settings.subject_query}`]:[])];
  return {...settings,instructions:settings.instructions+(additions.length?(settings.instructions?'\n\n':'')+additions.join('\n'):''),service_criteria:[],subject_query:''};
}

function Workspace({service:s,update,presets,setPresets,dirty,refreshSummaries,features,instructionsAvailable}:{service:Service;update:(s:Service)=>void;presets:Preset[];setPresets:(p:Preset[])=>void;dirty:{current:boolean};refreshSummaries:()=>Promise<void>;features:boolean;instructionsAvailable:boolean}) {
  const path=servicePath(s.id);
  const [draft,setDraft]=useState<Settings>(()=>unifiedSettings(s.settings));
  const [base,setBase]=useState(()=>unifiedSettings(s.settings));

  const [focused,setFocused]=useState('');
  const [chronological,setChronological]=useState(false);
  const [linked,setLinked]=useState(true);
  const comparison=useRef<HTMLDivElement>(null);
  const mirrored=useRef<HTMLElement|null>(null);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  const [filter,setFilter]=useState<State|'all'>('all');
  const [shortlistOnly,setShortlistOnly]=useState(Boolean(s.proposal?.shortlist));
  const shortlistKey=JSON.stringify(s.proposal?.shortlist);
  useEffect(()=>{setShortlistOnly(Boolean(s.proposal?.shortlist));},[shortlistKey]);
  const [presetChoice,setPresetChoice]=useState(s.settings.preset_id?s.settings.preset_id+':'+s.settings.preset_version:'');
  const [group,setGroup]=useState('');
  const [compare,setCompare]=useState<string[]>([]);
  const [showCompare,setShowCompare]=useState(false);
  const [zoom,setZoom]=useState(100);
  const [thumbnailSize,setThumbnailSize]=useState(230);
  const [plan,setPlan]=useState<Plan|null>(null);
  const [showRating,setShowRating]=useState(false);
  const [showAccept,setShowAccept]=useState(false);
  const [presetEdit,setPresetEdit]=useState(false);
  const [presetName,setPresetName]=useState('');
  const [presetInstructions,setPresetInstructions]=useState('');
  const [presetBase,setPresetBase]=useState<Preset|null>(null);
  const [coverage,setCoverage]=useState<{photo:Photo;state:State;locked:boolean}|null>(null);
  const planReceived=plan!==null&&s.receipts.some(r=>r.batch_id===plan.batch_id);
  const confirmed=plan!==null&&s.confirmed_batch_id===plan.batch_id;
  const polling=running(s)||Boolean(s.confirmed_batch_id);
  useEffect(()=>{
    if(!polling)return;
    let current=true, requested=false;
    const timer=window.setInterval(()=>{
      if(requested)return;
      requested=true;
      void api<Service>(path).then(next=>{if(current)update(next);})
        .catch(e=>{if(current)setError(message(e));}).finally(()=>{requested=false;});
    },1200);
    return()=>{current=false;clearInterval(timer);};
  },[path,polling,s.revision,s.status,update]);
  const busy=pending||running(s)||!!s.archived||s.status!=='ready';
  const proposed=new Set([...(s.proposal?.selected??[]),...(s.proposal?.added_candidates??[])]);
  const reviewIds=new Set(s.proposal?.stale?[]:s.proposal?.review_ids??[]);
  const decision=(p:Photo)=>s.decisions[p.id]??{state:reviewIds.has(p.id)?'review' as const:s.proposal&&!proposed.has(p.id)?'alternative' as const:'candidate' as const,locked:false};
  const selectedIds=new Set(s.selected_ids??s.photos.filter(p=>['candidate','preferred','review'].includes(decision(p).state)).map(p=>p.id));
  const cameras=[...new Set(s.photos.map(p=>p.camera).filter(Boolean))];
  const photoMap=new Map(s.photos.map(p=>[p.id,p]));
  const suggestions=new Map(s.interpretations?.comparisons?.map(x=>[x.photo_id,x.other_photo_id]));
  const groups=s.proposal?.groups??[];
  const groupMap=new Map(groups.flatMap(g=>g.members.map(id=>[id,g] as const)));
  const shortlist=new Set(s.proposal?.shortlist??[]);
  const failedProposal=s.job?.status==='failed';
  const visible=s.photos.filter(p=>(failedProposal||!shortlistOnly||shortlist.has(p.id))&&(filter==='all'||decision(p).state===filter)&&(!group||groupMap.get(p.id)?.id===group));
  if(chronological)visible.sort((a,b)=>{
    const time=(p:Photo)=>p.captured_at===null?Infinity:p.captured_at+(s.settings.camera_offsets[p.camera]??0);
    return time(a)-time(b)||a.id.localeCompare(b.id);
  });
  const needsUnifiedSave=Boolean((s.settings.service_criteria??s.settings.preset_snapshot?.criteria??[]).length||s.settings.subject_query);
  const draftChanged=JSON.stringify(draft)!==JSON.stringify(base)||needsUnifiedSave;
  const settingsChanged=JSON.stringify(base)!==JSON.stringify(unifiedSettings(s.settings));
  const staleDraft=settingsChanged&&draftChanged;
  useEffect(()=>{
    if(settingsChanged&&!draftChanged){setBase(unifiedSettings(s.settings));setDraft(unifiedSettings(s.settings));}
  },[settingsChanged,draftChanged,s.settings]);
  useEffect(()=>{
    dirty.current=draftChanged;
    if(!draftChanged)return;
    const warn=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue='';};
    window.addEventListener('beforeunload',warn);
    return()=>{dirty.current=false;window.removeEventListener('beforeunload',warn);};
  },[dirty,draftChanged]);
  const requestSettings=()=>({target:draft.target,preset_id:draft.preset_id,preset_version:draft.preset_version,mode:draft.mode,instructions:draft.instructions,subject_query:'',service_criteria:[],camera_offsets:draft.camera_offsets});
  async function action(work:()=>Promise<void>) {
    setPending(true);setError('');
    try{await work();}catch(e){setError(message(e));if(e instanceof ApiError&&e.status===409){try{const latest=await api<Service>(path);update(latest);}catch{ /* preserve original error */ }}}
    finally{setPending(false);}
  }
  async function save(start:boolean) {await action(async()=>{
    if(staleDraft)return;
    let current=s;
    if(draftChanged){current=await api<Service>(path+'/settings','PUT',{revision:s.revision,settings:requestSettings()});update(current);setDraft(unifiedSettings(current.settings));setBase(unifiedSettings(current.settings));}
    if(start)update(await api<Service>(path+'/analyze','POST',{revision:current.revision}));
  });}
  async function decide(photo:Photo,state:State,locked:boolean,confirm_last=false){await action(async()=>{
    try{const next=await api<Service>(path+'/decisions/'+encodeURIComponent(photo.id),'PATCH',{revision:s.revision,state,locked,confirm_last}); update(next);setCoverage(null);}
    catch(e){if(e instanceof ApiError&&e.status===409&&!confirm_last&&(e.detail as {code?:string})?.code==='last_candidate'){setCoverage({photo,state,locked});return;}throw e;}
  });}
  const changeHistory=(direction:'undo'|'redo')=>action(async()=>{
    update(await api<Service>(path+'/'+direction,'POST',{revision:s.revision}));
  });
  const replace=(from:string,to:string)=>action(async()=>{
    update(await api<Service>(path+'/replace','POST',{revision:s.revision,from_photo_id:from,to_photo_id:to}));
  });
  const archive=()=>action(async()=>{
    update(await api<Service>(path+'/archive','PUT',{revision:s.revision,archived:!s.archived}));
    await refreshSummaries();
  });
  function mirrorScroll(source:HTMLElement) {
    if(!linked)return;
    if(mirrored.current===source){mirrored.current=null;return;}
    const target=Array.from(comparison.current?.querySelectorAll<HTMLElement>('.zoom')??[]).find(el=>el!==source);
    if(!target)return;
    const left=source.scrollLeft/Math.max(1,source.scrollWidth-source.clientWidth)*(target.scrollWidth-target.clientWidth);
    const top=source.scrollTop/Math.max(1,source.scrollHeight-source.clientHeight)*(target.scrollHeight-target.clientHeight);
    if(Math.abs(target.scrollLeft-left)<1&&Math.abs(target.scrollTop-top)<1)return;
    mirrored.current=target;target.scrollLeft=left;target.scrollTop=top;
  }
  useEffect(()=>{
    function onKey(e:KeyboardEvent) {
      const element=e.target instanceof HTMLElement?e.target:null;
      if(e.defaultPrevented||e.repeat||element?.closest('input,textarea,select,button,[contenteditable],dialog')||showRating||showAccept||showCompare||presetEdit||coverage)return;
      const key=e.key.toLowerCase();
      if((e.metaKey||e.ctrlKey)&&key==='z'&&!e.altKey){
        if(!busy&&(e.shiftKey?s.can_redo:s.can_undo)){e.preventDefault();void changeHistory(e.shiftKey?'redo':'undo');}
        return;
      }
      if(e.metaKey||e.ctrlKey||e.altKey)return;
      if(key==='v'&&compare.length===2){e.preventDefault();setZoom(100);setShowCompare(true);return;}
      const cards=visible;
      const index=cards.findIndex(p=>p.id===focused);
      if(key==='arrowleft'||key==='arrowright'){
        const photo=cards[Math.min(cards.length-1,Math.max(0,index+(key==='arrowleft'?-1:1)))];
        if(photo){e.preventDefault();document.getElementById('photo-'+photo.id)?.focus();}
        return;
      }
      const photo=cards[index];
      if(!photo)return;
      if(key==='c'){e.preventDefault();chooseCompare(photo.id);}
      if(!busy&&(key==='m'||key==='x')){e.preventDefault();void decide(photo,key==='m'?'candidate':'excluded',decision(photo).locked);}
    }
    window.addEventListener('keydown',onKey);
    return()=>window.removeEventListener('keydown',onKey);
  });
  function chooseCompare(id:string){setCompare(prev=>prev.includes(id)?prev.filter(x=>x!==id):prev.length===2?[prev[1],id]:[...prev,id]);}
  function editPreset(base:Preset|null){setPresetBase(base);setPresetName(base?.name??'');setPresetInstructions(draft.instructions);setPresetEdit(true);}
  async function savePreset(){await action(async()=>{const values={name:presetName.trim(),subject_query:'',instructions:presetInstructions,criteria:[]};const p=presetBase?await api<Preset>('/presets/'+encodeURIComponent(presetBase.id),'PUT',{...values,version:presetBase.version}):await api<Preset>('/presets','POST',values);setPresets([...presets.filter(x=>x.id!==p.id),p]);applyPreset(p);setPresetEdit(false);});}
  const offer=presets.find(p=>p.id+':'+p.version===presetChoice);
  function applyPreset(p:Preset){setPresetChoice(p.id+':'+p.version);setDraft(unifiedSettings({...draft,preset_id:p.id,preset_version:p.version,preset_snapshot:p,service_criteria:[...p.criteria],subject_query:p.subject_query??'',instructions:p.instructions??''}));}
  const snapshot=draft.preset_snapshot;
  const analysisInProgress=s.status==='analyzing'||s.job?.status==='running'||s.job?.status==='queued';
  const outdatedProposal=Boolean(s.requires_analysis||s.proposal?.stale||draftChanged);
  const currentProposal=!analysisInProgress&&!outdatedProposal;
  const valid=Number.isInteger(draft.target)&&draft.target>=1&&draft.target<=s.photos.length;
  return <>
    <div className="workspace">
      <header className="top">
        <div className="service-heading"><p className="eyebrow">Servizio importato</p><h1>{s.title}</h1><p className="selection-count">{!currentProposal&&s.proposal&&!failedProposal?'Risultati precedenti · ':''}{failedProposal?`${s.photos.length} foto disponibili · ${selectedIds.size} candidate correnti`:s.proposal?.shortlist&&!s.proposal.shortlist_accepted ? `${shortlist.size} proposte da rivedere · ${s.photos.length} foto disponibili` : `${selectedIds.size} candidate su ${s.photos.length} foto`}</p></div>
        <div className="run-actions"><button disabled={pending||running(s)||draftChanged||s.status!=='ready'} onClick={()=>void archive()}>{s.archived?'Riapri servizio':'Archivia servizio'}</button>
        <button className="primary" disabled={busy||Boolean(s.proposal?.shortlist&&!s.proposal.shortlist_accepted)||s.requires_analysis||s.proposal?.stale||!selectedIds.size||draftChanged||s.status!=='ready'} onClick={()=>{setPlan(null);setShowRating(true);}}>Rivedi le stelle <span aria-hidden="true">→</span></button></div>
      </header>
      <section className="gallery" aria-label="Area di revisione">
        {error&&<p role="alert" className="warning">{error}</p>}
        {s.archived&&<p role="status" className="warning">Servizio archiviato. Riaprilo per continuare la revisione.</p>}
        {s.status==='applying'&&<p role="status" className="warning">Applicazione stelle in corso. Completa o riprendi dal plugin.</p>}
        {failedProposal?<p role="alert" className="warning">{s.job?.error??'Analisi non riuscita: nessuna nuova proposta valida.'} Tutte le foto restano disponibili per la revisione. Nessun tentativo viene avviato automaticamente.</p>:analysisInProgress?<p role="status" className="warning">Analisi in corso · {s.job?.completed??0} / {s.job?.total??s.photos.length}. {s.proposal?'I risultati visibili appartengono alla proposta precedente.':'La nuova proposta sarà disponibile al termine.'}</p>:outdatedProposal?<p role="status" className="warning">Impostazioni o foto aggiornate. Avvia la selezione per ottenere una nuova proposta; i risultati precedenti non descrivono i criteri attuali.</p>:s.proposal?.warnings.map((w,i)=><p key={i} className="warning">{w}</p>)}
        {currentProposal&&selectedIds.size<s.settings.target&&<p className="warning">La revisione corrente è sotto il numero richiesto ({s.settings.target}).</p>}
        <div className="reviewhead">
          <div className="review-title"><h2>Provino</h2><span>{visible.length} foto</span></div>
          <div className="review-filters">
            <label>Stato<select value={filter} onChange={e=>{setFilter(e.target.value as State|'all');}}><option value="all">Tutte</option>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select></label>
            {groups.length>0&&<label>Gruppo<select value={group} onChange={e=>{setGroup(e.target.value);}}><option value="">Tutti</option>{groups.map((g,i)=><option key={g.id} value={g.id}>Gruppo {i+1} · {g.members.length} foto</option>)}</select></label>}
            <label className="thumbnail-control">Anteprime<input aria-label="Dimensione anteprime" type="range" min={170} max={330} step={10} value={thumbnailSize} onChange={e=>setThumbnailSize(e.target.valueAsNumber)}/></label>
            <button disabled={compare.length!==2} onClick={()=>{setZoom(100);setShowCompare(true);}}>Confronta ({compare.length}/2)</button>
          </div>
        </div>
        <div className="review-history">
          {s.proposal?.shortlist&&!failedProposal&&<><button className="primary" disabled={busy||draftChanged||s.proposal.stale||!shortlist.size} onClick={()=>setShowAccept(true)}>Usa questa proposta ({shortlist.size})</button><label className="check"><input type="checkbox" checked={shortlistOnly} onChange={e=>{setShortlistOnly(e.target.checked);}}/>Proposta da rivedere ({shortlist.size})</label><span className="hint">Proposta automatica separata dalle {selectedIds.size} candidate correnti</span></>}
          <button disabled={busy||!s.can_undo} onClick={()=>void changeHistory('undo')}>Annulla decisione</button>
          <button disabled={busy||!s.can_redo} onClick={()=>void changeHistory('redo')}>Ripristina decisione</button>
          <label className="check"><input type="checkbox" checked={chronological} onChange={e=>setChronological(e.target.checked)}/>Ordine cronologico</label>
          <details><summary>Scorciatoie</summary><p>← → Naviga · M Mantieni · X Escludi · C Seleziona per confronto · V Apri confronto · ⌘Z Annulla · ⇧⌘Z Ripristina</p></details>
        </div>
        {visible.length===0&&<p className="empty-filter">{shortlistOnly&&shortlist.size===0?'Nessuna foto proposta: rivedi istruzioni e avvisi. Tutte le foto restano disponibili disattivando il filtro.':'Nessuna foto corrisponde ai filtri.'}</p>}
        <div className="grid" style={{'--thumbnail-size': `${thumbnailSize}px`} as CSSProperties}>
          {visible.map((photo,index)=>{
            const d=decision(photo);const g=groupMap.get(photo.id);const suggestion=suggestions.get(photo.id);
            return <article className={'card state-'+d.state+(compare.includes(photo.id)?' is-compared':'')} key={photo.id} id={'photo-'+photo.id} tabIndex={0} onFocus={()=>setFocused(photo.id)}>
              <div className="photo-topline"><span>{String(index+1).padStart(2,'0')}</span><span>{labels[d.state]}{d.locked?' · Bloccata':''}</span></div>
              <Preview service={s} photo={photo}/>
              <div className="cardbody">
                {shortlist.has(photo.id)&&<span className="detail-tag">{reviewIds.has(photo.id)?'Da rivedere · inclusa nella proposta':'Nella proposta'}</span>}
                {s.proposal?.shortlist_reasons?.[photo.id]&&<p className="hint">{s.proposal.shortlist_reasons[photo.id]}</p>}
                <strong className="filename" title={photo.filename}>{photo.filename}</strong>
                <div className="photo-meta"><span title={photo.camera}>{photo.camera||'Fotocamera non indicata'}</span><span className="stars" aria-label={photo.baseline_rating+' stelle all’importazione'} title="Valutazione all’importazione">{'★'.repeat(photo.baseline_rating)}{'☆'.repeat(5-photo.baseline_rating)}</span></div>
                <div className="photo-controls">
                  <label className="sr" htmlFor={'state-'+photo.id}>Stato {photo.filename}</label>
                  <select id={'state-'+photo.id} value={d.state} disabled={busy} onChange={e=>void decide(photo,e.target.value as State,d.locked)}>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select>
                  <label className="check"><input type="checkbox" checked={d.locked} disabled={busy} onChange={e=>void decide(photo,d.state,e.target.checked)}/>Blocca</label>
                </div>
                {suggestion&&photoMap.has(suggestion)&&<button className="text-button" onClick={()=>{setCompare([photo.id,suggestion]);setZoom(100);setShowCompare(true);}}>Confronto suggerito</button>}
                <div className="photo-footer"><label className="check"><input type="checkbox" checked={compare.includes(photo.id)} onChange={()=>chooseCompare(photo.id)}/>Confronta</label>
                  {(g||s.proposal?.reasons[photo.id])&&<details className="photo-reason"><summary>Motivo</summary>
                    {g&&<p>{!g.representative?'Gruppo senza candidate':g.representative===photo.id?'Rappresentante del gruppo':('Rappresentata da '+(photoMap.get(g.representative)?.filename??'altra foto'))}</p>}
                    <p>{s.proposal?.reasons[photo.id]??g?.reason}</p>
                    {g?.representative&&selectedIds.has(g.representative)&&!selectedIds.has(photo.id)&&!d.locked&&!s.decisions[g.representative]?.locked&&<button disabled={busy} onClick={()=>void replace(g.representative!,photo.id)}>Sostituisci la rappresentante</button>}
                  </details>}
                </div>
              </div>
            </article>;
          })}
        </div>
        <footer className="gallery-footer"><span>{s.proposal?'Proposta locale · revisione manuale disponibile':'Selezione manuale · tutte le foto iniziano candidate'}</span><span>Escludere non cancella il file</span></footer>
      </section>
      <aside className="inspector" aria-label="Strumenti di selezione">
        <form className="config" onSubmit={e=>{e.preventDefault();void save(true);}}>
          <div className="panel-heading"><h2>Configura la selezione</h2>{draftChanged&&<span className="unsaved" role="status">Da salvare</span>}</div>
          {staleDraft&&<p role="alert" className="warning">I criteri salvati sono cambiati. <button type="button" onClick={()=>{setBase(unifiedSettings(s.settings));setDraft(unifiedSettings(s.settings));}}>Carica i criteri salvati</button></p>}
          <fieldset disabled={busy||staleDraft}>
            <div className="tool-section target-section">
              <div className="target-heading"><label htmlFor="target-count">Candidate locali</label><input id="target-count" type="number" min={1} max={s.photos.length} value={Number.isNaN(draft.target)?'':draft.target} required onChange={e=>setDraft({...draft,target:e.target.valueAsNumber})}/></div>
              <input aria-label="Regola numero di candidate" aria-describedby="target-help" type="range" min={1} max={s.photos.length} step={1} value={Number.isFinite(draft.target)?Math.min(s.photos.length,Math.max(1,draft.target)):1} onChange={e=>setDraft({...draft,target:e.target.valueAsNumber})}/>
              <div className="range-ends"><span>1</span><span>{s.photos.length} foto</span></div>
              <p id="target-help" className="hint">Obiettivo della selezione locale. Il numero finale OpenAI si imposta separatamente nel riepilogo di invio.</p>
            </div>
            <div className="tool-section">
              <label>Parti da un preset<select value={presetChoice} onChange={e=>{const p=presets.find(p=>p.id+':'+p.version===e.target.value);if(p)applyPreset(p);else{setPresetChoice('');setDraft({...draft,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:'',instructions:''});}}}>
                <option value="">Nessun preset · configurazione libera</option>
                {presetChoice&&!offer&&snapshot&&<option value={presetChoice}>{snapshot.name} · v{snapshot.version} (copia del servizio)</option>}
                {presets.map(p=><option key={p.id} value={p.id+':'+p.version}>{p.name} · v{p.version}</option>)}
              </select></label>
              <div className="preset-actions"><button className="text-button" type="button" onClick={()=>editPreset(null)}>Salva come nuovo preset</button>{offer&&<button className="text-button" type="button" onClick={()=>editPreset(offer)}>Aggiorna preset</button>}</div>
              <p className="hint">{snapshot ? 'Base applicata: '+snapshot.name+' · v'+snapshot.version+'. Il testo qui sotto è una copia modificabile per questo servizio.' : 'Nessun preset applicato. Puoi configurare direttamente questo servizio.'}</p>
              {snapshot&&<button className="text-button" type="button" onClick={()=>{setPresetChoice('');setDraft({...draft,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:'',instructions:''});}}>Rimuovi preset e criteri</button>}
              <label>Modalità<select value={draft.mode} onChange={e=>setDraft({...draft,mode:e.target.value as Settings['mode']})}><option value="local">Solo locale</option><option value="hybrid">Ibrida: locale + OpenAI</option></select></label>
            </div>
            <section className="tool-section">
              <h2>Istruzioni e criteri del servizio</h2>
              <label>Istruzioni per la selezione<textarea rows={5} value={draft.instructions} placeholder="Descrivi cosa vuoi conservare e cosa confrontare in questo servizio" onChange={e=>setDraft({...draft,instructions:e.target.value})}/></label>
              {!instructionsAvailable&&(draft.instructions.trim())&&<p className="warning">Il modello locale per applicare queste istruzioni non è ancora disponibile. La selezione con istruzioni sarà disponibile dopo la configurazione.</p>}
              <p className="hint">Descrivi liberamente le priorità. Riceverai la proposta e gli eventuali avvisi su richieste ambigue o in conflitto.</p>
            </section>
            {cameras.length>0&&<details className="tool-section disclosure"><summary>Sincronizzazione fotocamere</summary><p className="hint">Offset in secondi applicati all’ordine cronologico nella web app.</p><div className="camera-fields">{cameras.map(c=><label key={c}>{c}<input type="number" step="1" value={draft.camera_offsets[c]??0} onChange={e=>setDraft({...draft,camera_offsets:{...draft.camera_offsets,[c]:Number(e.target.value)}})}/></label>)}</div></details>}
            <div className="tool-section run-section"><div className="run-actions"><button type="button" disabled={!draftChanged||!valid} onClick={()=>void save(false)}>Salva criteri</button><button className="primary" disabled={!valid||s.status!=='ready'||(!instructionsAvailable&&Boolean(draft.instructions.trim()))}>{draft.mode==='hybrid'?'Avvia selezione locale':'Avvia selezione'}</button></div><p className="hint">La proposta si rivede nel provino. Le decisioni manuali e le foto conservate per copertura restano visibili.</p></div>
          </fieldset>
        </form>
        {draft.mode==='hybrid'&&<APIReview service={s} dirty={draftChanged} disabled={busy} update={update}/>}
        {s.criteria.length>0&&<details className="tool-section disclosure criteria-status"><summary>Stato dei criteri<span className="detail-tag">{s.criteria.filter(c=>c.status!=='supported').length} da verificare</span></summary><ul>{s.criteria.map((c,i)=><li key={i}><strong>{c.text}</strong><span className="criterion-status">{({partial:'Parzialmente supportato',unsupported:'Non applicato',supported:'Supportato',pending:'Da analizzare',ambiguous:'Ambiguo'} as Record<string,string>)[c.status]??c.status}</span><p>{c.reason}</p></li>)}</ul></details>}
        {features&&<section className="tool-section"><button disabled={busy} onClick={()=>void action(async()=>update(await api<Service>(path+'/features','POST',{revision:s.revision})))}>Analizza dettagli locali</button></section>}
        {s.job&&<section className="tool-section job-status" aria-live="polite"><h2>{s.job.kind==='openai'?'Analisi OpenAI':'Analisi locale'}</h2><p>{({running:'In corso',queued:'In coda',completed:'Completata',completed_with_warnings:'Completata · casi da rivedere',interrupted:'Interrotta',failed:'Non riuscita'} as Record<string,string>)[s.job.status]??s.job.status} · {s.job.completed} / {s.job.total}</p>{s.job.status==='running'&&<progress value={s.job.completed} max={s.job.total||1}/>} {s.job.error&&<p className="warning">{s.job.error}</p>}</section>}
        {s.receipts.length>0&&<section className="tool-section"><h2>Esiti Lightroom</h2>{s.receipts.map(r=><details key={r.batch_id}><summary>{r.results.filter(i=>i.status==='applied').length} stelle applicate · {r.results.length} foto verificate</summary><ul>{r.results.map(i=><li key={i.photo_id}>{photoMap.get(i.photo_id)?.filename??i.photo_id}: {({applied:'Applicata',skipped:'Saltata',conflict:'Conflitto',uncertain:'Da verificare'} as Record<string,string>)[i.status]??i.status} — {i.reason}</li>)}</ul></details>)}</section>}
      </aside>
    </div>
    {showCompare&&<Modal title="Confronta le anteprime" close={()=>setShowCompare(false)}><p className="hint">Zoom relativo alla vista. Le anteprime possono non bastare per valutare la nitidezza dell’originale.</p><label>Zoom {zoom}%<input type="range" min={100} max={300} step={10} value={zoom} onChange={e=>setZoom(e.target.valueAsNumber)}/></label><label className="check"><input type="checkbox" checked={linked} onChange={e=>{mirrored.current=null;setLinked(e.target.checked);}}/>Collega scorrimento</label><div className="comparison" ref={comparison}>{compare.map(id=>{const p=photoMap.get(id);return p&&<ComparisonPhoto key={id} service={s} photo={p} zoom={zoom} onScroll={mirrorScroll}/>;})}</div></Modal>}
    {showAccept&&<Modal title="Usa la proposta come selezione" close={()=>setShowAccept(false)}><p>Conferma {shortlist.size} foto proposte come candidate. Le altre restano accessibili tra le escluse dalla proposta; le decisioni manuali precedenti prevalgono.</p><p className="warning">Può lasciare situazioni senza candidate: verifica prima di confermare.</p><p>Nessuna stella viene applicata. La scelta può essere annullata dal provino.</p><button className="primary" disabled={busy||draftChanged||s.proposal?.stale} onClick={()=>void action(async()=>{update(await api<Service>(path+'/accept-shortlist','POST',{revision:s.revision,confirm_last:true}));setShowAccept(false);})}>Conferma candidate</button>{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
    {showRating&&<Modal title="Rivedi le stelle" close={()=>setShowRating(false)}><p>{selectedIds.size} candidate su {s.photos.length} foto. {s.proposal?'La proposta include le decisioni manuali.':'Selezione manuale, nessuna analisi eseguita.'}</p><p>Il plugin può assegnare una stella alle candidate idonee con zero stelle. Prima dell’applicazione occorre verificare che la scrittura automatica dei metadati su file sia disabilitata.</p>{plan?<><p role="status"><strong>{plan.items.length} modifiche proposte</strong> · revisione {plan.revision}</p>{plan.warnings.map((w,i)=><p className="warning" key={i}>{w}</p>)}{plan.items.length>0&&<><p>Conferma questo elenco e apri “Applica stelle” nel plugin. Controlla la scrittura automatica dei metadati e conferma in Lightroom.</p><ul className="planlist">{plan.items.map(i=><li key={i.photo_id}>{i.filename??photoMap.get(i.photo_id)?.filename??i.photo_id} · ID {i.local_id} · {i.expected_rating} → 1 ★</li>)}</ul>{planReceived?<p role="status">Operazione registrata. Consulta Esiti Lightroom.</p>:plan.revision!==s.revision?<p role="alert">Piano superato. Chiudi e prepara una nuova anteprima.</p>:confirmed?<p role="status">Piano confermato · {plan.batch_id}</p>:<button className="primary" disabled={busy||draftChanged} onClick={()=>void action(async()=>{await api(path+'/rating-plan/confirm','POST',{batch_id:plan.batch_id});update(await api<Service>(path));})}>Conferma elenco per Lightroom</button>}</>}</>:<button className="primary" disabled={busy} onClick={()=>void action(async()=>setPlan(await api<Plan>(path+'/rating-plan','POST',{revision:s.revision})))}>Prepara anteprima delle modifiche</button>}{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
    {presetEdit&&<Modal title={presetBase?'Modifica preset':'Nuovo preset'} close={()=>setPresetEdit(false)}><form onSubmit={e=>{e.preventDefault();void savePreset();}}><label>Nome<input value={presetName} onChange={e=>setPresetName(e.target.value)} required/></label><label>Istruzioni del preset<textarea rows={4} value={presetInstructions} onChange={e=>setPresetInstructions(e.target.value)}/></label><p>I servizi esistenti mantengono la revisione salvata.</p><button className="primary" disabled={busy||!presetName.trim()}>Salva preset</button>{error&&<p role="alert" className="warning">{error}</p>}</form></Modal>}
    {coverage&&<Modal title="Ultima candidata del gruppo" close={()=>setCoverage(null)}><p>Questo gruppo rimarrà senza candidate dopo la modifica di {coverage.photo.filename}.</p><button className="primary" disabled={busy} onClick={()=>void decide(coverage.photo,coverage.state,coverage.locked,true)}>Conferma modifica</button>{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
  </>;
}
function ComparisonPhoto({service,photo,zoom,onScroll}:{service:Service;photo:Photo;zoom:number;onScroll:(el:HTMLElement)=>void}) {
  const [size,setSize]=useState<{width:number;height:number}|null>(null);
  const faces=service.interpretations?.records[photo.id]?.faces?.observations?.filter(validFace)??[];
  return <figure>
    <div className="preview zoom" tabIndex={0} aria-label={'Scorri l’anteprima di '+photo.filename} onScroll={e=>onScroll(e.currentTarget)}>
      {photo.preview_ready?<img src={'/api'+photoPath(service.id,photo.id)+'/preview'} style={{width:zoom+'%',maxWidth:'none'}} alt={photo.filename}
        onLoad={e=>setSize({width:e.currentTarget.naturalWidth,height:e.currentTarget.naturalHeight})}/>:<span>Anteprima non disponibile</span>}
    </div>
    <figcaption>{photo.filename}{size&&<span className="hint"> · Anteprima {size.width} × {size.height} px</span>}</figcaption>
    {photo.preview_ready&&size&&faces.length>0&&<details className="face-details"><summary>Dettagli dei volti rilevati</summary>
      <div className="face-crops">{faces.map((face,i)=><div className="face-crop" key={i} style={{aspectRatio:face.width*size.width/(face.height*size.height)}}>
        <img alt={'Volto rilevato '+(i+1)} src={'/api'+photoPath(service.id,photo.id)+'/preview'} loading="lazy" style={{width:100/face.width+'%',height:100/face.height+'%',left:-100*face.x/face.width+'%',top:-100*(1-face.y-face.height)/face.height+'%'}}/>
      </div>)}</div>
      <p className="hint">Volti rilevati localmente, non identificati. Il rilevamento può omettere persone.</p>
    </details>}
  </figure>;
}
function validFace(face:Face) {
  return [face.x,face.y,face.width,face.height].every(Number.isFinite)&&face.x>=0&&face.y>=0&&face.width>0&&face.height>0&&face.x+face.width<=1.001&&face.y+face.height<=1.001;
}
function Modal({title,close,children}:{title:string;close:()=>void;children:React.ReactNode}) {
  const [dialog,setDialog]=useState<HTMLDialogElement|null>(null);
  useEffect(()=>{if(dialog&&!dialog.open)dialog.showModal();},[dialog]);
  return <dialog ref={setDialog} onCancel={e=>{e.preventDefault();close();}} aria-label={title}><header className="reviewhead"><h2>{title}</h2><button onClick={close}>Chiudi</button></header>{children}</dialog>;
}
const root = document.getElementById('root');
if (root) createRoot(root).render(<App/>);
