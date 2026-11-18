import { useState } from 'react';
import { api } from './api';

type Configuration = {configured:boolean;key_configured:boolean;model:string;analysis_enabled:boolean;error?:string|null};

export function OpenAISettings() {
  const [open,setOpen]=useState(false);
  const [configuration,setConfiguration]=useState<Configuration|null>(null);
  const [model,setModel]=useState('');
  const [key,setKey]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  const [saved,setSaved]=useState(false);
  async function show() {
    if(open){setOpen(false);setKey('');return;}
    setOpen(true);setBusy(true);setError('');setSaved(false);
    try {const result=await api<Configuration>('/openai/config');setConfiguration(result);setModel(result.model);}
    catch(e){setError(e instanceof Error?e.message:'Configurazione non disponibile.');}
    finally{setBusy(false);}
  }
  async function save() {
    setBusy(true);setError('');setSaved(false);
    const submittedKey=key;
    setKey('');
    try {
      const result=await api<Configuration>('/openai/config','PUT',{model,...(submittedKey?{api_key:submittedKey}:{})});
      setConfiguration(result);setSaved(true);
    } catch(e){setError(e instanceof Error?e.message:'Configurazione non salvata.');}
    finally{setBusy(false);}
  }
  return <section className="openai-settings">
    <button className="text-button" type="button" aria-expanded={open} onClick={()=>void show()}>Configurazione OpenAI</button>
    {open&&<form onSubmit={e=>{e.preventDefault();void save();}}>
      <h2>API OpenAI facoltative</h2>
      <p className="hint">La chiave viene conservata nel portachiavi macOS dal backend locale.</p>
      <label>Modello API<input value={model} maxLength={200} placeholder="Identificativo del modello visivo" disabled={busy} onChange={e=>setModel(e.target.value)}/></label>
      <label>Chiave API<input type="password" value={key} autoComplete="off" spellCheck={false} placeholder={configuration?.key_configured?'Già salvata · inserisci solo per sostituirla':'Inserisci la chiave API'} disabled={busy} onChange={e=>setKey(e.target.value)}/></label>
      <button type="submit" disabled={busy||!model.trim()||(!configuration?.key_configured&&!key)}>Salva configurazione</button>
      {saved&&<p role="status">Configurazione salvata; invio foto richiede stima e budget per servizio.</p>}
      <p className="hint">L’analisi API non è ancora abilitata. Salvare la configurazione non invia fotografie, non verifica il credito e non acquista crediti.</p>
      {configuration?.error&&<p className="warning">{configuration.error}</p>}
      {error&&<p className="warning" role="alert">{error}</p>}
    </form>}
  </section>;
}
