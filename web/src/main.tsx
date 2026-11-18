import { createRoot } from 'react-dom/client';
import { useEffect, useState } from 'react';
import { api, ApiError, photoPath, servicePath, type Plan, type Photo, type State, type Service, type Summary, type Settings, type Preset } from './api';
import './style.css';

const labels: Record<State,string> = {candidate:'Candidata',preferred:'Preferita',alternative:'Alternativa',excluded:'Esclusa',review:'Da rivedere'};
const states = Object.keys(labels) as State[];
const running = (s:Service) => s.job?.status === 'running' || s.job?.status === 'queued' || s.status === 'applying';
const message = (e:unknown) => e instanceof Error ? e.message : 'Operazione non completata.';
function Preview({service, photo, zoom}: {service:Service; photo:Photo; zoom?:number}) {
  return <div className={'preview'+(zoom ? ' zoom' : '')}>{photo.preview_ready ? <img style={zoom ? {width: zoom + '%', maxWidth:'none'} : undefined} src={'/api'+photoPath(service.id,photo.id)+'/preview'} loading={zoom?'eager':'lazy'} alt={photo.filename}/> : <span>Anteprima non disponibile</span>}</div>;
}

export function App() {
  const [services,setServices] = useState<Summary[]>([]);
  const [presets,setPresets] = useState<Preset[]>([]);
  const [service,setService] = useState<Service|null>(null);
  const [login,setLogin] = useState(false);
  const [token,setToken] = useState('');
  const [error,setError] = useState('');
  const [busy,setBusy] = useState(false);
  async function load() {
    const [all,available] = await Promise.all([api<Summary[]>('/services'),api<Preset[]>('/presets')]);
    setServices(all); setPresets(available); setLogin(false);
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
    try { await load(); if(service) await open(service.id); }
    catch(e) { setError(message(e)); }
  }
  async function open(id:string) {
    setBusy(true); setError('');
    try { setService(await api<Service>(servicePath(id))); }
    catch(e) { setError(message(e)); }
    finally {setBusy(false);}
  }
  return <div className="layout"><aside><div className="brand">Prima selezione<small>Lightroom Classic · Locale</small></div>{!login && <><div className="sidehead"><strong>Servizi</strong><button onClick={refresh} disabled={busy}>Aggiorna</button></div><nav aria-label="Servizi">{services.map(s => <button key={s.id} className={service?.id === s.id ? 'active' : ''} onClick={()=>void open(s.id)} disabled={busy}><strong>{s.title}</strong><small>{s.photo_count} foto</small></button>)}</nav></>}</aside><main>{error && <p role="alert" className="warning">{error}</p>}{login ? <form className="panel empty" onSubmit={e=>{e.preventDefault();void connect(token);}}><h1>Apri la sessione locale</h1><p>Apri l’app dal plugin Lightroom oppure incolla il token di accesso.</p><label>Token<input type="password" value={token} onChange={e=>setToken(e.target.value)} autoComplete="off" required/></label><button className="primary" disabled={busy}>Accedi</button></form> : service ? <Workspace key={service.id} service={service} update={setService} presets={presets} setPresets={setPresets}/> : <section className="panel empty"><h1>{services.length?'Apri un servizio':'Importa un servizio da Lightroom'}</h1><p>{services.length?'Scegli un servizio dalla barra laterale.':'In Lightroom seleziona le foto, esegui “Prepara servizio” e poi premi Aggiorna.'}</p></section>}</main></div>;
}

function Workspace({service:s,update,presets,setPresets}:{service:Service;update:(s:Service)=>void;presets:Preset[];setPresets:(p:Preset[])=>void}) {
  const path=servicePath(s.id);
  const [draft,setDraft]=useState<Settings>(s.settings);
  const [pending,setPending]=useState(false);
  const [error,setError]=useState('');
  const [filter,setFilter]=useState<State|'all'>('all');
  const [group,setGroup]=useState('');
  const [compare,setCompare]=useState<string[]>([]);
  const [showCompare,setShowCompare]=useState(false);
  const [zoom,setZoom]=useState(100);
  const [limit,setLimit]=useState(48);
  const [plan,setPlan]=useState<Plan|null>(null);
  const [showRating,setShowRating]=useState(false);
  const [presetEdit,setPresetEdit]=useState(false);
  const [presetName,setPresetName]=useState('');
  const [presetCriteria,setPresetCriteria]=useState('');
  const [presetBase,setPresetBase]=useState<Preset|null>(null);
  const [coverage,setCoverage]=useState<{photo:Photo;state:State;locked:boolean}|null>(null);
  useEffect(()=>{if(!running(s)&&!plan)return;let current=true;const timer=window.setInterval(()=>{void api<Service>(path).then(next=>{if(current)update(next);}).catch(e=>{if(current)setError(message(e));});},1200);return()=>{current=false;clearInterval(timer);};},[path,s.status,s.job?.status,plan]);
  const busy=pending||running(s);
  const proposed=new Set(s.proposal?.selected??[]);
  const decision=(p:Photo)=>s.decisions[p.id]??{state:s.proposal&&!proposed.has(p.id)?'alternative' as const:'candidate' as const,locked:false};
  const selectedIds=new Set(s.selected_ids??s.photos.filter(p=>['candidate','preferred','review'].includes(decision(p).state)).map(p=>p.id));
  const cameras=[...new Set(s.photos.map(p=>p.camera).filter(Boolean))];
  const photoMap=new Map(s.photos.map(p=>[p.id,p]));
  const groups=s.proposal?.groups??[];
  const groupMap=new Map(groups.flatMap(g=>g.members.map(id=>[id,g] as const)));
  const visible=s.photos.filter(p=>(filter==='all'||decision(p).state===filter)&&(!group||groupMap.get(p.id)?.id===group));
  const draftChanged=JSON.stringify(draft)!==JSON.stringify(s.settings);
  const requestSettings=()=>({target:draft.target,preset_id:draft.preset_id,preset_version:draft.preset_version,mode:draft.mode,instructions:draft.instructions,camera_offsets:draft.camera_offsets});
  async function action(work:()=>Promise<void>) {
    setPending(true);setError('');
    try{await work();}catch(e){setError(message(e));if(e instanceof ApiError&&e.status===409){try{const latest=await api<Service>(path);update(latest);}catch{ /* preserve original error */ }}}
    finally{setPending(false);}
  }
  async function save(start:boolean) {await action(async()=>{
    let current=s;
    if(draftChanged){current=await api<Service>(path+'/settings','PUT',{revision:s.revision,settings:requestSettings()});update(current);setDraft(current.settings);}
    if(start)update(await api<Service>(path+'/analyze','POST',{revision:current.revision}));
  });}
  async function decide(photo:Photo,state:State,locked:boolean,confirm_last=false){await action(async()=>{
    try{const next=await api<Service>(path+'/decisions/'+encodeURIComponent(photo.id),'PATCH',{revision:s.revision,state,locked,confirm_last}); update(next);setCoverage(null);}
    catch(e){if(e instanceof ApiError&&e.status===409&&!confirm_last&&(e.detail as {code?:string})?.code==='last_candidate'){setCoverage({photo,state,locked});return;}throw e;}
  });}
  function chooseCompare(id:string){setCompare(prev=>prev.includes(id)?prev.filter(x=>x!==id):prev.length===2?[prev[1],id]:[...prev,id]);}
  function editPreset(base:Preset|null){setPresetBase(base);setPresetName(base?.name??'');setPresetCriteria(base?.criteria.join('\n')??'');setPresetEdit(true);}
  async function savePreset(){await action(async()=>{const values={name:presetName.trim(),criteria:presetCriteria.split('\n').map(x=>x.trim()).filter(Boolean)};const p=presetBase?await api<Preset>('/presets/'+encodeURIComponent(presetBase.id),'PUT',{...values,version:presetBase.version}):await api<Preset>('/presets','POST',values);setPresets([...presets.filter(x=>x.id!==p.id),p]);setPresetEdit(false);});}
  const offer=presets.find(p=>p.id===draft.preset_id&&p.version===draft.preset_version);
  const snapshot=draft.preset_snapshot;
  const valid=Number.isInteger(draft.target)&&draft.target>=1&&draft.target<=s.photos.length;
  return <><header className="top"><div><p className="eyebrow">Servizio fotografico</p><h1>{s.title}</h1><p>{selectedIds.size} candidate su {s.photos.length} foto · revisione {s.revision}</p></div><button className="primary" disabled={busy||s.proposal?.stale||!selectedIds.size||draftChanged||s.status!=='ready'} onClick={()=>{setPlan(null);setShowRating(true);}}>Rivedi le stelle</button></header>
    {error&&<p role="alert" className="warning">{error}</p>}
    {s.status==='applying'&&<p role="status" className="warning">Applicazione stelle in corso. Completa o riprendi dal plugin.</p>}
    <form className="panel config" onSubmit={e=>{e.preventDefault();void save(true);}}><h2>Configura la selezione</h2><fieldset disabled={busy}><div className="fields"><label>Numero di candidate <input type="number" min={1} max={s.photos.length} value={Number.isNaN(draft.target)?'':draft.target} required onChange={e=>setDraft({...draft,target:e.target.valueAsNumber})}/></label><label>Preset <select value={draft.preset_id+':'+draft.preset_version} onChange={e=>{const p=presets.find(x=>x.id+':'+x.version===e.target.value); if(p)setDraft({...draft,preset_id:p.id,preset_version:p.version,preset_snapshot:p});}}>{!offer&&<option value={draft.preset_id+':'+draft.preset_version}>{snapshot?.name??draft.preset_id} · v{draft.preset_version} (salvato)</option>}{presets.map(p=><option key={p.id} value={p.id+':'+p.version}>{p.name} · v{p.version}</option>)}</select></label><label>Modalità<select value={draft.mode} onChange={e=>setDraft({...draft,mode:e.target.value as Settings['mode']})}><option value="local">Locale</option><option value="hybrid" disabled>Ibrida (non disponibile)</option></select></label></div><p>La proposta può superare il numero richiesto per preservare la copertura.</p><div className="actions"><button type="button" onClick={()=>editPreset(null)}>Nuovo preset</button>{offer&&<button type="button" onClick={()=>editPreset(offer)}>Modifica preset</button>}</div>{(offer??snapshot)?.criteria?.length ? <ul>{(offer??snapshot)?.criteria.map((x,i)=><li key={i}>{x}</li>)}</ul>:null}<label>Istruzioni per questo servizio<textarea rows={3} value={draft.instructions} onChange={e=>setDraft({...draft,instructions:e.target.value})}/></label>{cameras.length>0&&<details><summary>Offset fotocamere (secondi)</summary><p>Salvati nell’app. Il motore iniziale non usa ancora la sequenza temporale per raggruppare.</p><div className="fields">{cameras.map(c=><label key={c}>{c}<input type="number" step="1" value={draft.camera_offsets[c]??0} onChange={e=>setDraft({...draft,camera_offsets:{...draft.camera_offsets,[c]:Number(e.target.value)}})}/></label>)}</div></details>}<div className="actions"><button type="button" disabled={!draftChanged||!valid} onClick={()=>void save(false)}>Salva criteri</button><button className="primary" disabled={!valid||draft.mode!=='local'||s.status!=='ready'}>Avvia selezione</button></div></fieldset></form>
    {s.criteria.length>0&&<section className="panel"><h2>Verifica dei criteri</h2><ul>{s.criteria.map((c,i)=><li key={i}><strong>{c.text}</strong> · {({partial:'Parzialmente supportato',unsupported:'Non supportato',supported:'Supportato',ambiguous:'Ambiguo'} as Record<string,string>)[c.status]??c.status}. {c.reason}</li>)}</ul></section>}
    {s.job&&<section className="panel" aria-live="polite"><h2>Analisi locale</h2><p>{({running:'In corso',queued:'In coda',completed:'Completata',interrupted:'Interrotta',failed:'Non riuscita'} as Record<string,string>)[s.job.status]??s.job.status} · {s.job.completed} / {s.job.total}</p>{s.job.status==='running'&&<progress value={s.job.completed} max={s.job.total||1}/>} {s.job.error&&<p className="warning">{s.job.error}</p>}</section>}
    {s.proposal?.stale&&<p className="warning">I criteri sono cambiati. Riavvia la selezione per aggiornare la proposta.</p>}
    {s.proposal?.warnings.map((w,i)=><p key={i} className="warning">{w}</p>)}
    {selectedIds.size<s.settings.target&&<p className="warning">La revisione corrente è sotto il numero richiesto ({s.settings.target}).</p>}
    <section className="review"><div className="reviewhead"><h2>Rivedi le foto</h2><div className="actions"><label>Stato<select value={filter} onChange={e=>{setFilter(e.target.value as State|'all');setLimit(48);}}><option value="all">Tutte</option>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select></label>{groups.length>0&&<label>Gruppo<select value={group} onChange={e=>{setGroup(e.target.value);setLimit(48);}}><option value="">Tutti</option>{groups.map((g,i)=><option key={g.id} value={g.id}>Gruppo {i+1} · {g.members.length} foto</option>)}</select></label>}<button disabled={compare.length!==2} onClick={()=>{setZoom(100);setShowCompare(true);}}>Confronta ({compare.length}/2)</button></div></div>
    {visible.length===0&&<p>Nessuna foto corrisponde ai filtri.</p>}
    <div className="grid">{visible.slice(0,limit).map(p=>{const d=decision(p);const g=groupMap.get(p.id);return <article className="card" key={p.id}><Preview service={s} photo={p}/><div className="cardbody"><strong title={p.filename}>{p.filename}</strong><small>{p.camera||'Fotocamera non indicata'} · {p.baseline_rating} stelle all’importazione</small>{g&&<p>{g.representative===p.id?'Rappresentante del gruppo':('Rappresentata da '+(photoMap.get(g.representative)?.filename??'altra foto'))} · {g.reason}</p>}{s.proposal?.reasons[p.id]&&<p>{s.proposal.reasons[p.id]}</p>}<div className="actions"><label className="sr" htmlFor={'state-'+p.id}>Stato {p.filename}</label><select id={'state-'+p.id} value={d.state} disabled={busy} onChange={e=>void decide(p,e.target.value as State,d.locked)}>{states.map(x=><option key={x} value={x}>{labels[x]}</option>)}</select><label className="check"><input type="checkbox" checked={d.locked} disabled={busy} onChange={e=>void decide(p,d.state,e.target.checked)}/>Blocca</label><label className="check"><input type="checkbox" checked={compare.includes(p.id)} onChange={()=>chooseCompare(p.id)}/>Confronta</label></div></div></article>;})}</div>
    {visible.length>limit&&<button onClick={()=>setLimit(limit+48)}>Mostra altre foto ({visible.length-limit})</button>}</section>
    {s.receipts.length>0&&<section className="panel"><h2>Esiti Lightroom</h2>{s.receipts.map(r=><details key={r.batch_id}><summary>{r.results.filter(i=>i.status==='applied').length} stelle applicate · {r.results.length} foto verificate</summary><ul>{r.results.map(i=><li key={i.photo_id}>{photoMap.get(i.photo_id)?.filename??i.photo_id}: {({applied:'Applicata',skipped:'Saltata',conflict:'Conflitto',uncertain:'Da verificare'} as Record<string,string>)[i.status]??i.status} — {i.reason}</li>)}</ul></details>)}</section>}
    {showCompare&&<Modal title="Confronta le anteprime" close={()=>setShowCompare(false)}><label>Zoom {zoom}%<input type="range" min={100} max={300} step={10} value={zoom} onChange={e=>setZoom(e.target.valueAsNumber)}/></label><div className="comparison">{compare.map(id=>{const p=photoMap.get(id);return p&&<figure key={id}><Preview service={s} photo={p} zoom={zoom}/><figcaption>{p.filename}</figcaption></figure>;})}</div></Modal>}
    {showRating&&<Modal title="Rivedi le stelle" close={()=>setShowRating(false)}><p>{selectedIds.size} candidate su {s.photos.length} foto. {s.proposal?'La proposta include le decisioni manuali.':'Selezione manuale, nessuna analisi eseguita.'}</p><p>Il plugin può assegnare una stella alle candidate idonee con zero stelle. Prima dell’applicazione occorre verificare che la scrittura automatica dei metadati su file sia disabilitata.</p>{plan?<><p role="status"><strong>{plan.items.length} modifiche proposte</strong> · revisione {plan.revision}</p>{plan.warnings.map((w,i)=><p className="warning" key={i}>{w}</p>)}{plan.items.length>0&&<><p>Apri “Applica stelle” nel plugin con il catalogo del servizio. Controlla la scrittura automatica dei metadati e conferma il riepilogo in Lightroom.</p><ul className="planlist">{plan.items.map(i=><li key={i.photo_id}>{photoMap.get(i.photo_id)?.filename??i.photo_id} · ID {i.local_id} · {i.expected_rating} → 1 ★</li>)}</ul></>}</>:<button className="primary" disabled={busy} onClick={()=>void action(async()=>setPlan(await api<Plan>(path+'/rating-plan','POST',{revision:s.revision})))}>Prepara anteprima delle modifiche</button>}{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
    {presetEdit&&<Modal title={presetBase?'Modifica preset':'Nuovo preset'} close={()=>setPresetEdit(false)}><form onSubmit={e=>{e.preventDefault();void savePreset();}}><label>Nome<input value={presetName} onChange={e=>setPresetName(e.target.value)} required/></label><label>Criteri, uno per riga<textarea rows={5} value={presetCriteria} onChange={e=>setPresetCriteria(e.target.value)}/></label><p>I servizi esistenti mantengono la revisione salvata.</p><button className="primary" disabled={busy||!presetName.trim()}>Salva preset</button>{error&&<p role="alert" className="warning">{error}</p>}</form></Modal>}
    {coverage&&<Modal title="Ultima candidata del gruppo" close={()=>setCoverage(null)}><p>Questo gruppo rimarrà senza candidate dopo la modifica di {coverage.photo.filename}.</p><button className="primary" disabled={busy} onClick={()=>void decide(coverage.photo,coverage.state,coverage.locked,true)}>Conferma modifica</button>{error&&<p role="alert" className="warning">{error}</p>}</Modal>}
  </>;
}
function Modal({title,close,children}:{title:string;close:()=>void;children:React.ReactNode}) {
  const [dialog,setDialog]=useState<HTMLDialogElement|null>(null);
  useEffect(()=>{if(dialog&&!dialog.open)dialog.showModal();},[dialog]);
  return <dialog ref={setDialog} onCancel={e=>{e.preventDefault();close();}} aria-label={title}><header className="reviewhead"><h2>{title}</h2><button onClick={close}>Chiudi</button></header>{children}</dialog>;
}
const root = document.getElementById('root');
if (root) createRoot(root).render(<App/>);
