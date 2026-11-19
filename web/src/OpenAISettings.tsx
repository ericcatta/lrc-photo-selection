import { useState } from 'react';
import { api } from './api';

type AvailableModel={id:string;label:string;input_per_million:number|null;output_per_million:number|null;available:boolean|null;supported?:boolean;pricing_known?:boolean;compatibility?:'verified'|'family';compatibility_note?:string};
type ModelList={models:AvailableModel[];checked_at:string|null;stale?:boolean;error?:string|null};
type Configuration = {configured:boolean;key_configured:boolean;model:string;analysis_enabled:boolean;error?:string|null};

export function OpenAISettings() {
  const [open,setOpen]=useState(false);
  const [configuration,setConfiguration]=useState<Configuration|null>(null);
  const [model,setModel]=useState('');
  const [models,setModels]=useState<ModelList>({models:[],checked_at:null});
  const [key,setKey]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [saved,setSaved]=useState(false);
  async function show() {
    if(open){setOpen(false);setKey('');return;}
    setOpen(true);setBusy(true);setError('');setSaved(false);
    try {const [result,list]=await Promise.all([api<Configuration>('/openai/config'),api<ModelList>('/openai/models')]);setConfiguration(result);setModel(result.model);setModels(list);}
    catch(e){setError(e instanceof Error?e.message:'Configurazione non disponibile.');}
    finally{setBusy(false);}
  }
  async function save() {
    setBusy(true);setError('');setSaved(false);
    const submittedKey=key;
    setKey('');
    try {
      const result=await api<Configuration>('/openai/config','PUT',{model,...(submittedKey?{api_key:submittedKey}:{})});
      setConfiguration(result);if(submittedKey)setModels(await api<ModelList>('/openai/models'));setSaved(true);
    } catch(e){setError(e instanceof Error?e.message:'Configurazione non salvata.');}
    finally{setBusy(false);}
  }
  async function refreshModels(){
    setBusy(true);setError('');try{setModels(await api<ModelList>('/openai/models/refresh','POST',{}));}catch(e){setError(e instanceof Error?e.message:'Verifica modelli non riuscita.');}finally{setBusy(false);}
  }
  const selectedModel=models.models.find(item=>item.id===model);
  const priceKnown=selectedModel?.pricing_known!==false&&typeof selectedModel?.input_per_million==='number'&&typeof selectedModel?.output_per_million==='number';
  const compatible=models.models.find(item=>item.id===model&&item.supported!==false&&(item.available!==false||Boolean(key)));
  return <section className="openai-settings">
    <button className="text-button" type="button" aria-expanded={open} onClick={()=>void show()}>Configurazione OpenAI</button>
    {open&&<form onSubmit={e=>{e.preventDefault();void save();}}>
      <h2>API OpenAI facoltative</h2>
      <p className="hint">La chiave viene conservata nel portachiavi macOS dal backend locale.</p>
      <label>Modello API<select value={model} disabled={busy} onChange={e=>setModel(e.target.value)}><option value="">Scegli un modello</option>{model&&!models.models.some(item=>item.id===model)&&<option value={model}>{model} · aggiorna l’elenco per verificare l’accesso</option>}{models.models.filter(item=>item.supported!==false).map(item=><option key={item.id} value={item.id} disabled={item.available===false}>{item.label} · {item.available===true?'disponibile':item.available===false?'non disponibile':'accesso da verificare'}{item.pricing_known===false||item.input_per_million===null||item.output_per_million===null?' · costo non disponibile':''}</option>)}{models.models.some(item=>item.supported===false)&&<optgroup label="Modelli non compatibili con l’analisi fotografica">{models.models.filter(item=>item.supported===false).map(item=><option key={item.id} value={item.id} disabled>{item.label}</option>)}</optgroup>}</select></label>
      <button type="button" disabled={busy||!configuration?.key_configured} onClick={()=>void refreshModels()}>Verifica modelli disponibili</button>
      <p className="hint">La verifica aggiorna l’elenco dal tuo account OpenAI senza inviare foto. Sono selezionabili i modelli compatibili con l’analisi fotografica, anche quando la tariffa non è disponibile. I modelli non compatibili restano separati e non selezionabili.{models.checked_at?' Ultima verifica: '+models.checked_at+'.':''}{models.stale?' Elenco da aggiornare.':''}</p>
      {selectedModel&&<div className="model-details"><p className="hint">{selectedModel.compatibility==='family'?'Compatibilità dedotta dalla famiglia del modello; la disponibilità effettiva viene verificata dall’API all’invio.':'Modello compatibile con l’analisi delle anteprime fotografiche.'}{selectedModel.compatibility_note?' '+selectedModel.compatibility_note:''}</p>{priceKnown?<p className="hint">Tariffa disponibile: input {selectedModel.input_per_million} USD / milione di token · output {selectedModel.output_per_million} USD / milione di token.</p>:<p className="warning">Costo non disponibile per questo modello. Puoi selezionarlo, ma prima dell’invio dovrai confermare che non sono disponibili una stima e un limite di spesa verificabile.</p>}</div>}
      {models.error&&<p className="warning">{models.error}</p>}
      <label>Chiave API<input type="password" value={key} autoComplete="off" spellCheck={false} placeholder={configuration?.key_configured?'Già salvata · inserisci solo per sostituirla':'Inserisci la chiave API'} disabled={busy} onChange={e=>setKey(e.target.value)}/></label>
      <button type="submit" disabled={busy||!compatible||(!configuration?.key_configured&&!key)}>Salva configurazione</button>
      {saved&&<p role="status">Configurazione salvata. Il prossimo passo è preparare la stima e confermare l’invio.</p>}
      <p className="hint">Salvare la configurazione non invia fotografie. Scegli un percorso con OpenAI e conferma il riepilogo di invio. Il budget complessivo è facoltativo. Il saldo crediti non viene verificato e non vengono acquistati crediti.</p>
      {configuration?.error&&<p className="warning">{configuration.error}</p>}
      {error&&<p className="warning" role="alert">{error}</p>}
    </form>}
  </section>;
}
