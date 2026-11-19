// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import type { Preset, Service } from './api';

const preset: Preset = {id:'wedding',name:'Matrimonio',version:1,criteria:['Preservare varianti'],subject_query:'uccelli',instructions:'Conserva varianti del volo'};
let service: Service;
let calls: {path:string;method:string;body:Record<string,any>|undefined}[];
function json(value:unknown,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});}

beforeEach(()=>{
  history.replaceState(null,'','/');
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','');}});
  service={id:'synthetic',title:'TEST SINTETICO',catalog_id:'fake',revision:1,status:'ready',
    settings:{target:2,preset_id:'wedding',preset_version:1,preset_snapshot:preset,mode:'local',instructions:'',service_criteria:[],subject_query:'',camera_offsets:{}},
    photos:[0,1].map(i=>({id:'p'+i,uuid:'u'+i,local_id:i,filename:'sintetica-'+i+'.jpg',camera:'Simulata',captured_at:0,baseline_rating:i?3:0,baseline_edit_time:1,preview_ready:false})),
    decisions:{},proposal:null,job:null,receipts:[],criteria:[]};
  calls=[];
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const path=String(input).replace('/api','');
    const method=init?.method??'GET';
    const body=init?.body?JSON.parse(String(init.body)):undefined;
    calls.push({path,method,body});
    if(path==='/session')return json({ok:true});
    if(path==='/services')return json([{id:service.id,title:service.title,photo_count:2,revision:service.revision,status:service.status,archived:service.archived},{id:'second',title:'SECONDO SINTETICO',photo_count:2,revision:1,status:'ready'}]);
    if(path==='/capabilities')return json({features:false,instructions:true});
    if(path==='/presets'&&method==='POST')return json({...body,id:'new-preset',version:1});
    if(path==='/presets/wedding'&&method==='PUT')return json({...body,id:'wedding',version:2});
    if(path==='/presets')return json([preset]);
    if(path.endsWith('/accept-shortlist'))return json({...service,revision:service.revision+1});
    if(path==='/services/synthetic')return json(service);
    if(path.endsWith('/settings')){service={...service,revision:service.revision+1,settings:{...body.settings,preset_snapshot:preset}};return json(service);}
    if(path.includes('/decisions/')){
      if(body.state==='excluded'&&!body.confirm_last)return json({detail:{code:'last_candidate',message:'Confermare ultima candidata?'}},409);
      service={...service,revision:service.revision+1,decisions:{...service.decisions,[path.split('/').at(-1)!]:{state:body.state,locked:body.locked}}};return json(service);
    }
    if(path.endsWith('/replace')||path.endsWith('/undo')||path.endsWith('/redo')){
      const undone=path.endsWith('/undo');
      const selected=undone?'p0':'p1';
      service={...service,revision:service.revision+1,selected_ids:[selected],can_undo:!undone,can_redo:undone,
        decisions:undone?{}:{p0:{state:'alternative',locked:false},p1:{state:'preferred',locked:false}},
        proposal:{...service.proposal!,groups:[{...service.proposal!.groups[0],representative:selected}]}};
      return json(service);
    }
    if(path.endsWith('/analyze'))return json({...service,job:{status:'completed',completed:2,total:2,error:null}});
    if(path.endsWith('/rating-plan/confirm')){service={...service,confirmed_batch_id:body.batch_id};return json({batch_id:body.batch_id});}
    if(path.endsWith('/archive')){service={...service,revision:service.revision+1,archived:body.archived};return json(service);}
    if(path.endsWith('/rating-plan'))return json({batch_id:'b',service_id:service.id,catalog_id:'fake',revision:service.revision,warnings:[],items:[{photo_id:'p0',uuid:'u0',local_id:0,expected_rating:0,expected_edit_time:1,target_rating:1}]});
    throw new Error('Unexpected endpoint '+path);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
async function workspace(){render(<App/>);await screen.findByRole('option',{name:/TEST SINTETICO/});fireEvent.change(screen.getByLabelText('Servizio'),{target:{value:'synthetic'}});await screen.findByRole('heading',{name:'TEST SINTETICO'});}

describe('Revisione senza dati reali',()=>{
  it('applica il preset alla bozza e mantiene i criteri modificabili per il servizio',async()=>{
    service={...service,settings:{...service.settings,preset_id:'',preset_version:0,preset_snapshot:null,service_criteria:[],subject_query:''}};
    await workspace();
    fireEvent.change(screen.getByLabelText('Parti da un preset'),{target:{value:'wedding:1'}});
    expect((screen.getByLabelText('Istruzioni per la selezione') as HTMLTextAreaElement).value).toBe('Conserva varianti del volo\n\nPreservare varianti\nSoggetto da privilegiare: uccelli');
    expect(screen.queryByLabelText('Criteri del servizio, uno per riga')).toBeNull();
    fireEvent.change(screen.getByLabelText('Istruzioni per la selezione'),{target:{value:'Conservare il volo'}});
    fireEvent.click(screen.getByRole('button',{name:'Salva criteri'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
    expect(calls.find(c=>c.path.endsWith('/settings'))?.body?.settings).toMatchObject({instructions:'Conservare il volo',service_criteria:[],subject_query:''});
    expect(calls.some(c=>c.path.startsWith('/presets')&&c.method!=='GET')).toBe(false);
    fireEvent.click(screen.getByRole('button',{name:'Rimuovi preset e criteri'}));
    expect((screen.getByLabelText('Istruzioni per la selezione') as HTMLTextAreaElement).value).toBe('');
  });
  it('filtra la proposta senza cambiare decisioni o stelle',async()=>{
    service={...service,proposal:{selected:['p0','p1'],shortlist:['p1'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
    await workspace();
    expect((screen.getByLabelText('Mostra') as HTMLSelectElement).value).toBe('proposal');
    expect(screen.getAllByRole('article')).toHaveLength(1);
    expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
    expect(calls.some(c=>c.method!=='GET')).toBe(false);
  });
  it('salva un nuovo preset dalle istruzioni e dai criteri del servizio',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Istruzioni per la selezione'),{target:{value:'Conserva una foto per azione'}});
    fireEvent.click(screen.getByRole('button',{name:'Salva come nuovo preset'}));
    const dialog=await screen.findByRole('dialog',{name:'Nuovo preset'});
    expect((within(dialog).getByLabelText('Istruzioni del preset') as HTMLTextAreaElement).value).toBe('Conserva una foto per azione');
    fireEvent.change(within(dialog).getByLabelText('Nome'),{target:{value:'Azioni'}});
    fireEvent.click(within(dialog).getByRole('button',{name:'Salva preset'}));
    await waitFor(()=>expect(calls.some(c=>c.path==='/presets'&&c.method==='POST')).toBe(true));
    expect(calls.find(c=>c.path==='/presets'&&c.method==='POST')?.body).toMatchObject({name:'Azioni',instructions:'Conserva una foto per azione',criteria:[]});
  });
  it('richiede conferma prima di adottare la proposta senza applicare stelle',async()=>{
    service={...service,proposal:{selected:['p0','p1'],shortlist:['p1'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
    await workspace();
    fireEvent.click(screen.getByRole('button',{name:'Conferma selezione'}));
    const dialog=await screen.findByRole('dialog',{name:'Usa la proposta come selezione'});
    expect(calls.some(c=>c.path.endsWith('/accept-shortlist'))).toBe(false);
    fireEvent.click(within(dialog).getByRole('button',{name:'Conferma candidate'}));
    await waitFor(()=>expect(calls.find(c=>c.path.endsWith('/accept-shortlist'))?.body).toEqual({revision:1,confirm_last:true}));
    expect(calls.some(c=>c.path.includes('/rating-'))).toBe(false);
  });
  it('salva criteri senza avviare implicitamente l’analisi',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Candidate locali'),{target:{value:'1'}});
    fireEvent.click(screen.getByRole('button',{name:'Salva criteri'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
    expect(calls.some(c=>c.path.endsWith('/analyze'))).toBe(false);
    await waitFor(()=>expect((screen.getByRole('button',{name:'Avvia selezione'}) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button',{name:'Avvia selezione'}));
    await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/analyze'))).toBe(true));
  });
  it('sincronizza slider e numero preciso senza avviare la selezione',async()=>{
    await workspace();
    const slider=screen.getByRole('slider',{name:'Regola numero di candidate'}) as HTMLInputElement;
    const number=screen.getByLabelText('Candidate locali') as HTMLInputElement;
    expect(slider.min).toBe('1');expect(slider.max).toBe('2');
    fireEvent.change(slider,{target:{value:'1'}});
    expect(number.value).toBe('1');
    expect(screen.getByText('Da salvare')).toBeTruthy();
    fireEvent.change(number,{target:{value:'2'}});
    expect(slider.value).toBe('2');
    fireEvent.change(number,{target:{value:'3'}});
    expect((screen.getByRole('button',{name:'Avvia selezione'}) as HTMLButtonElement).disabled).toBe(true);
    expect(calls.some(c=>c.path.endsWith('/settings')||c.path.endsWith('/analyze'))).toBe(false);
  });
  it('richiede conferma per ultima candidata anche prima di una analisi',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Stato sintetica-0.jpg'),{target:{value:'excluded'}});
    const dialog=await screen.findByRole('dialog',{name:'Ultima candidata del gruppo'});
    expect(service.decisions.p0).toBeUndefined();
    fireEvent.click(within(dialog).getByRole('button',{name:'Conferma modifica'}));
    await waitFor(()=>expect(service.decisions.p0?.state).toBe('excluded'));
    await screen.findByText(/1 candidate su 2 foto/);
  });
  it('prepara soltanto il piano stelle e non applica rating dal browser',async()=>{
    await workspace();
    fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
    fireEvent.click(screen.getByRole('button',{name:'Rivedi le stelle'}));
    const dialog=await screen.findByRole('dialog',{name:'Rivedi le stelle'});
    expect(within(dialog).getByText(/Selezione manuale, nessuna analisi eseguita/)).toBeTruthy();
    fireEvent.click(within(dialog).getByRole('button',{name:'Prepara anteprima delle modifiche'}));
    await within(dialog).findByText('1 modifiche proposte');
    expect(calls.some(c=>c.path.endsWith('/rating-plan/confirm'))).toBe(false);
    fireEvent.click(within(dialog).getByRole('button',{name:'Conferma elenco per Lightroom'}));
    await within(dialog).findByText('Piano confermato · b');
    expect(calls.find(c=>c.path.endsWith('/rating-plan/confirm'))?.body).toEqual({batch_id:'b'});
    expect(calls.some(c=>c.path.endsWith('/rating-plan/claim')||c.path.endsWith('/rating-receipts'))).toBe(false);
  });
  it('include le foto da rivedere nel conteggio delle candidate',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Stato sintetica-0.jpg'),{target:{value:'review'}});
    await waitFor(()=>expect(service.decisions.p0?.state).toBe('review'));
    expect(screen.getByText(/2 candidate su 2 foto/)).toBeTruthy();
  });
  it('mostra il confronto soltanto dopo due scelte e offre lo zoom',async()=>{
    await workspace();
    const choices=screen.getAllByRole('checkbox',{name:'Confronta'});
    fireEvent.click(choices[0]);fireEvent.click(choices[1]);
    fireEvent.click(screen.getByRole('button',{name:'Confronta (2/2)'}));
    const dialog=await screen.findByRole('dialog',{name:'Confronta le anteprime'});
    fireEvent.change(within(dialog).getByRole('slider'),{target:{value:'200'}});
    expect(within(dialog).getByText('Zoom 200%')).toBeTruthy();
  });
  it('protegge la bozza al cambio di servizio dopo un aggiornamento concorrente',async()=>{
    await workspace();
    const confirm=vi.spyOn(window,'confirm').mockReturnValue(false);
    try {
      fireEvent.change(screen.getByLabelText('Candidate locali'),{target:{value:'1'}});
      fireEvent.change(screen.getByLabelText('Servizio'),{target:{value:'second'}});
      expect(confirm).toHaveBeenCalled();
      expect(calls.some(c=>c.path.endsWith('/second'))).toBe(false);
      service={...service,revision:2,settings:{...service.settings,instructions:'Aggiornate altrove'}};
      fireEvent.click(screen.getByRole('button',{name:'Aggiorna'}));
      await screen.findByText('I criteri salvati sono cambiati.');
      expect((screen.getByLabelText('Candidate locali') as HTMLInputElement).value).toBe('1');
      fireEvent.click(screen.getByRole('button',{name:'Carica i criteri salvati'}));
      expect((screen.getByLabelText('Candidate locali') as HTMLInputElement).value).toBe('2');
    } finally {confirm.mockRestore();}
  });
  it('riapre un servizio archiviato conservando la revisione',async()=>{
    await workspace();
    fireEvent.click(screen.getByText('Opzioni del servizio'));
    fireEvent.click(screen.getByRole('button',{name:'Archivia servizio'}));
    await screen.findByText(/Servizio archiviato/);
    fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
    expect((screen.getByRole('button',{name:'Rivedi le stelle'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'Riapri servizio'}));
    await waitFor(()=>expect(service.archived).toBe(false));
    expect(calls.filter(c=>c.path.endsWith('/archive')).map(c=>c.body?.revision)).toEqual([1,2]);
  });
  it('applica le scorciatoie al provino e lascia i campi modificabili alla tastiera',async()=>{
    await workspace();
    fireEvent.keyDown(document.body,{key:'ArrowRight'});
    const first=screen.getAllByRole('article')[0];
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(screen.getByLabelText('Istruzioni per la selezione'),{key:'x'});
    fireEvent.keyDown(screen.getByLabelText('Candidate locali'),{key:'ArrowRight'});
    expect(document.activeElement).toBe(first);
    expect(calls.some(c=>c.path.includes('/decisions/'))).toBe(false);
    fireEvent.keyDown(first,{key:'x'});
    await screen.findByRole('dialog',{name:'Ultima candidata del gruppo'});
    expect(calls.find(c=>c.path.endsWith('/decisions/p0'))?.body).toMatchObject({state:'excluded'});
  });
  it('scambia la rappresentante con una richiesta e usa la cronologia del servizio',async()=>{
    service={...service,selected_ids:['p0'],proposal:{selected:['p0'],groups:[{id:'g',members:['p0','p1'],representative:'p0',reason:'Anteprime identiche'}],reasons:{},warnings:[],engine:'test'}};
    await workspace();
    const alternative=screen.getAllByRole('article')[1];
    fireEvent.click(within(alternative).getByText('Motivo'));
    fireEvent.click(within(alternative).getByRole('button',{name:'Sostituisci la rappresentante'}));
    await waitFor(()=>expect((screen.getByLabelText('Stato sintetica-1.jpg') as HTMLSelectElement).value).toBe('preferred'));
    fireEvent.click(screen.getByRole('button',{name:'Annulla decisione'}));
    await waitFor(()=>expect((screen.getByLabelText('Stato sintetica-0.jpg') as HTMLSelectElement).value).toBe('candidate'));
    fireEvent.click(screen.getByRole('button',{name:'Ripristina decisione'}));
    await waitFor(()=>expect((screen.getByLabelText('Stato sintetica-1.jpg') as HTMLSelectElement).value).toBe('preferred'));
    const mutations=calls.filter(c=>c.method==='POST');
    expect(mutations.map(c=>c.path.split('/').at(-1))).toEqual(['replace','undo','redo']);
    expect(mutations.map(c=>c.body)).toEqual([{revision:1,from_photo_id:'p0',to_photo_id:'p1'},{revision:2},{revision:3}]);
  });
  it('interrompe gli aggiornamenti periodici quando arriva la ricevuta Lightroom',async()=>{
    service={...service,confirmed_batch_id:'b'};
    const intervals=vi.spyOn(window,'setInterval');
    const clear=vi.spyOn(window,'clearInterval');
    try {
      await workspace();
      const index=intervals.mock.calls.findIndex(([,ms])=>ms===1200);
      expect(index).toBeGreaterThanOrEqual(0);
      const [poll]=intervals.mock.calls[index];
      const timer=intervals.mock.results[index].value;
      service={...service,revision:2,confirmed_batch_id:undefined,receipts:[{batch_id:'b',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1}]}]};
      await act(async()=>{(poll as ()=>void)();});
      await screen.findByRole('heading',{name:'Esiti Lightroom'});
      expect(clear).toHaveBeenCalledWith(timer);
      expect(intervals.mock.calls.filter(([,ms])=>ms===1200)).toHaveLength(1);
    } finally {intervals.mockRestore();clear.mockRestore();}
  });
  it('mostra la risoluzione e ritaglia i volti rilevati con origine in basso',async()=>{
    service={...service,photos:service.photos.map(p=>({...p,preview_ready:true})),interpretations:{records:{p0:{faces:{observations:[
      {x:0.125,y:0.5,width:0.25,height:0.25,confidence:0.9},
      {x:0,y:0,width:2,height:0.25,confidence:0.9},
    ]}}}}};
    await workspace();
    const choices=screen.getAllByRole('checkbox',{name:'Confronta'});
    fireEvent.click(choices[0]);fireEvent.click(choices[1]);
    fireEvent.click(screen.getByRole('button',{name:'Confronta (2/2)'}));
    const dialog=await screen.findByRole('dialog',{name:'Confronta le anteprime'});
    const preview=within(dialog).getByRole('img',{name:'sintetica-0.jpg'});
    Object.defineProperties(preview,{naturalWidth:{value:1200},naturalHeight:{value:800}});
    fireEvent.load(preview);
    expect(within(dialog).getByText(/Anteprima 1200 × 800 px/)).toBeTruthy();
    fireEvent.click(within(dialog).getByText('Dettagli dei volti rilevati'));
    const [crop]=within(dialog).getAllByRole('img',{name:/Volto rilevato/}) as HTMLImageElement[];
    expect(within(dialog).getAllByRole('img',{name:/Volto rilevato/})).toHaveLength(1);
    expect(crop.style.left).toBe('-50%');
    expect(crop.style.top).toBe('-100%');
    expect(crop.getAttribute('src')).toBe(preview.getAttribute('src'));
  });
  it('rimuove il token dal frammento URL dopo la connessione',async()=>{
    history.replaceState(null,'','/#token=synthetic-connection-token');
    render(<App/>);
    await screen.findByRole('option',{name:/TEST SINTETICO/});
    expect(location.hash).toBe('');
    expect(calls[0].path).toBe('/session');
  });
});


it('nasconde gli avvisi della proposta precedente dopo una modifica ai criteri',async()=>{
  const obsolete='Il motore iniziale riconosce solo anteprime identiche';
  service={...service,requires_analysis:true,proposal:{selected:['p0','p1'],groups:[],reasons:{},warnings:[obsolete],engine:'exact-preview-v1',stale:true}};
  await workspace();
  expect(screen.queryByText(obsolete)).toBeNull();
  expect(screen.getByText(/Impostazioni o foto aggiornate/).textContent).toContain('Avvia la selezione per ottenere una nuova proposta');
  expect(screen.getByText(/Risultati precedenti ·/)).toBeTruthy();
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('mostra avanzamento e contesto dei risultati precedenti durante una nuova analisi',async()=>{
  const obsolete='Vecchia quantità superata';
  service={...service,status:'analyzing',job:{status:'running',completed:1,total:2,error:null},proposal:{selected:['p0','p1'],groups:[],reasons:{},warnings:[obsolete],engine:'exact-preview-v1'}};
  await workspace();
  expect(screen.queryByText(obsolete)).toBeNull();
  expect(screen.getByText(/Analisi in corso · 1 \/ 2/).textContent).toContain('proposta precedente');
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});


it('riunisce i criteri precedenti in un solo testo mantenendo intatto il prefisso originale',async()=>{
  const original='  Solo uccelli\nPreferisci ali aperte!  \n';
  service={...service,settings:{...service.settings,instructions:original,service_criteria:['Conservare varianti'],subject_query:'uccelli in volo'}};
  await workspace();
  const text=screen.getByLabelText('Istruzioni per la selezione') as HTMLTextAreaElement;
  expect(text.value.startsWith(original)).toBe(true);
  expect(text.value).toContain('Conservare varianti');
  expect(text.value).toContain('Soggetto da privilegiare: uccelli in volo');
  expect(screen.queryByLabelText('Criteri del servizio, uno per riga')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Salva criteri'}));
  await waitFor(()=>expect(calls.some(c=>c.path.endsWith('/settings'))).toBe(true));
  expect(calls.find(c=>c.path.endsWith('/settings'))?.body?.settings).toMatchObject({instructions:text.value,service_criteria:[],subject_query:''});
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('rende tutte le foto filtrate scorribili e navigabili oltre la precedente pagina di 48',async()=>{
  const template=service.photos[0];
  service={...service,photos:Array.from({length:60},(_,i)=>({...template,id:'p'+i,uuid:'u'+i,local_id:i,filename:'scroll-'+i+'.jpg',preview_ready:true}))};
  await workspace();
  const cards=screen.getAllByRole('article');
  expect(cards).toHaveLength(60);
  expect(screen.queryByRole('button',{name:/Mostra altre foto/})).toBeNull();
  expect(screen.getByAltText('scroll-59.jpg').getAttribute('loading')).toBe('lazy');
  act(()=>cards[47].focus());
  fireEvent.keyDown(cards[47],{key:'ArrowRight'});
  expect(document.activeElement).toBe(cards[48]);
  fireEvent.change(screen.getByLabelText('Stato'),{target:{value:'excluded'}});
  expect(screen.queryAllByRole('article')).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('Stato'),{target:{value:'all'}});
  expect(screen.getAllByRole('article')).toHaveLength(60);
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});

it('mostra tutte le foto e l’errore dopo un’analisi fallita con una vecchia shortlist',async()=>{
  const template=service.photos[0];
  const photos=Array.from({length:160},(_,i)=>({...template,id:'p'+i,uuid:'u'+i,local_id:i,filename:'failed-'+i+'.jpg',preview_ready:true}));
  service={...service,photos,requires_analysis:true,job:{status:'failed',completed:160,total:160,error:'150 risposte su 160 non valide. Rivedi la configurazione del modello.'},proposal:{selected:photos.map(p=>p.id),shortlist:['p0','p1'],groups:[],reasons:{},warnings:['Vecchio avviso non valido'],engine:'old-test',stale:true}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(160);
  expect(screen.getByText('160 foto disponibili · 160 candidate correnti')).toBeTruthy();
  expect(screen.queryByText(/2 proposte da rivedere/)).toBeNull();
  expect(screen.queryByRole('checkbox',{name:'Proposta da rivedere (2)'})).toBeNull();
  expect(screen.queryByRole('button',{name:'Usa questa proposta (2)'})).toBeNull();
  const gallery=screen.getByRole('region',{name:'Area di revisione'});
  expect(within(gallery).getByRole('alert').textContent).toContain('150 risposte su 160 non valide');
  expect(screen.queryByText('Vecchio avviso non valido')).toBeNull();
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('mostra l’errore iniziale senza trasformare le candidate in zero selezionate',async()=>{
  service={...service,requires_analysis:true,job:{status:'failed',completed:0,total:2,error:'Analisi non avviata: istruzioni da chiarire.'},proposal:null};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('2 foto disponibili · 2 candidate correnti')).toBeTruthy();
  const gallery=screen.getByRole('region',{name:'Area di revisione'});
  expect(within(gallery).getByRole('alert').textContent).toContain('Analisi non avviata');
  expect(calls.some(c=>c.path.endsWith('/analyze')||c.path.endsWith('/api-confirm'))).toBe(false);
});

it('include le incerte nella proposta e nel filtro da rivedere senza applicare decisioni',async()=>{
  service={...service,job:{status:'completed_with_warnings',completed:2,total:2,error:null},proposal:{selected:['p0','p1'],shortlist:['p0','p1'],review_ids:['p1'],shortlist_reasons:{p1:'Risposta non valida: conservata per revisione.'},groups:[],reasons:{},warnings:['Una foto conservata per revisione.'],engine:'synthetic'}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('Da rivedere · inclusa nella proposta')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Stato'),{target:{value:'review'}});
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});

function workflow(phase:NonNullable<Service['workflow']>['phase'],path:'local'|'hybrid'|'openai'='local'):NonNullable<Service['workflow']>{
  return {schema_version:1,path,phase,local_completed:false,proposal_ready:false,proposal_accepted:false,requires_analysis:false,confirmed_batch_id:null,active_batch_id:null,selected_count:2,target:2,outcome:null};
}
it('riprende la fase indicata dal servizio e naviga senza avviare operazioni',async()=>{
  service={...service,workflow:workflow('review'),proposal:{selected:['p0','p1'],shortlist:['p0','p1'],groups:[],reasons:{},warnings:['Dettaglio tecnico sintetico'],engine:'test'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Conferma selezione'})).toBeTruthy();
  expect(screen.queryByRole('heading',{name:'Configura la selezione'})).toBeNull();
  const navigation=screen.getByRole('navigation',{name:'Passaggi della selezione'});
  fireEvent.click(within(navigation).getByRole('button',{name:/Configura/}));
  expect(screen.getByRole('heading',{name:'Configura la selezione'})).toBeTruthy();
  fireEvent.click(within(navigation).getByRole('button',{name:/Rivedi/}));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
  expect(screen.getByText('Dettaglio tecnico sintetico').closest('details')?.open).toBe(false);
});
it('distingue i tre percorsi senza avviare analisi al cambio di scelta',async()=>{
  await workspace();
  const path=screen.getByLabelText('Percorso');
  expect(within(path).getAllByRole('option').map(x=>x.textContent)).toEqual(['Solo locale','Locale + OpenAI','Direttamente OpenAI']);
  fireEvent.change(path,{target:{value:'openai'}});
  expect(screen.getByRole('button',{name:'Continua alla stima OpenAI'})).toBeTruthy();
  expect(screen.getByLabelText('Selezione finale OpenAI')).toBeTruthy();
  expect(screen.queryByLabelText('Candidate locali')).toBeNull();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('guida il percorso ibrido dalla proposta locale verso OpenAI o revisione locale',async()=>{
  service={...service,workflow:workflow('analyze','hybrid'),settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},proposal:{selected:['p0','p1'],shortlist:['p0','p1'],groups:[],reasons:{},warnings:[],engine:'test'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Continua con OpenAI'})).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Usa il risultato locale'}));
  expect(screen.getByRole('button',{name:'Conferma selezione'})).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('indica come riprendere un invio interrotto senza far partire nuove chiamate',async()=>{
  service={...service,workflow:workflow('analyze','hybrid'),settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},job:{kind:'openai',status:'interrupted',completed:15,total:18,error:'Risposta non valida'}};
  await workspace();
  expect(screen.getByRole('button',{name:'Prepara la ripresa'})).toBeTruthy();
  expect(screen.getByText(/Analisi interrotta: 15 di 18/)).toBeTruthy();
  expect(calls.some(c=>c.method!=='GET')).toBe(false);
});
it('non mostra una ricevuta storica come completamento della selezione corrente',async()=>{
  service={...service,workflow:workflow('review'),receipts:[{batch_id:'old',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1}]}]};
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/5Esito/}));
  expect(screen.getByText(/Nessuna ricevuta Lightroom disponibile/)).toBeTruthy();
  expect(screen.queryByText('1 stelle applicate')).toBeNull();
});
it('mantiene il target API separato e mostra un esito parziale dopo la ricevuta',async()=>{
  service={...service,workflow:{...workflow('outcome','hybrid'),target:1,outcome:{applied:1,skipped:0,conflict:1,uncertain:0,total:2}},selected_ids:['p0'],settings:{...service.settings,target:2},proposal:{selected:['p0'],shortlist:['p0'],shortlist_accepted:true,api_target:1,api_plan_id:'api',groups:[],reasons:{},warnings:[],engine:'test'},receipts:[{batch_id:'latest',results:[{photo_id:'p0',status:'applied',reason:'',before:0,after:1},{photo_id:'p1',status:'conflict',reason:'Valutazione cambiata',before:3,after:3}]}]};
  await workspace();
  expect(screen.getByText(/Esito parziale:/)).toBeTruthy();
  expect(screen.queryByText(/sotto il numero richiesto/)).toBeNull();
});

it('spiega che un piano senza nuove stelle non richiede applicazione',async()=>{
  const original=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const result=await original(input,init);
    if(!String(input).endsWith('/rating-plan'))return result;
    const plan=await result.json();return json({...plan,items:[]});
  }));
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
  fireEvent.click(screen.getByRole('button',{name:'Rivedi le stelle'}));
  const dialog=await screen.findByRole('dialog',{name:'Rivedi le stelle'});
  fireEvent.click(within(dialog).getByRole('button',{name:'Prepara anteprima delle modifiche'}));
  await within(dialog).findByText(/Nessuna modifica necessaria/);
  expect(within(dialog).queryByRole('button',{name:'Conferma elenco per Lightroom'})).toBeNull();
  expect(calls.some(x=>x.path.endsWith('/rating-plan/confirm'))).toBe(false);
});
it('impedisce la conferma di un piano stelle superato',async()=>{
  const original=globalThis.fetch;
  vi.stubGlobal('fetch',vi.fn(async(input:string,init?:RequestInit)=>{
    const result=await original(input,init);
    if(!String(input).endsWith('/rating-plan'))return result;
    const plan=await result.json();return json({...plan,revision:0});
  }));
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/4Lightroom/}));
  fireEvent.click(screen.getByRole('button',{name:'Rivedi le stelle'}));
  const dialog=await screen.findByRole('dialog',{name:'Rivedi le stelle'});
  fireEvent.click(within(dialog).getByRole('button',{name:'Prepara anteprima delle modifiche'}));
  await within(dialog).findByText(/Piano superato/);
  expect(within(dialog).queryByRole('button',{name:'Conferma elenco per Lightroom'})).toBeNull();
  expect(calls.some(x=>x.path.endsWith('/rating-plan/confirm'))).toBe(false);
});
it('porta il focus al titolo del passaggio e lascia il provino raggiungibile',async()=>{
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:/3Rivedi/}));
  const heading=screen.getByRole('heading',{name:'Rivedi'});
  await waitFor(()=>expect(document.activeElement).toBe(heading));
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
});

it('mostra zero proposte senza sostituirle con le candidate precedenti e lascia tutte le foto rivedibili',async()=>{
  service={...service,workflow:workflow('review'),selected_ids:['p0','p1'],proposal:{selected:['p0','p1'],shortlist:[],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  expect(screen.getByText('0 proposte da rivedere · 2 foto disponibili')).toBeTruthy();
  expect(screen.getByText(/Nessuna foto selezionata\. Tutte le foto sono visibili/)).toBeTruthy();
  expect(screen.queryByText(/Rivedi le 2 foto selezionate/)).toBeNull();
  expect((screen.getByRole('button',{name:'Conferma selezione'}) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getAllByText('Non selezionata')).toHaveLength(2);
  expect((screen.getByLabelText('Mostra') as HTMLSelectElement).value).toBe('all');
  expect(screen.getByRole('button',{name:'Rivedi i criteri'})).toBeTruthy();
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
});
it('include manualmente una foto da una proposta vuota e conferma il conteggio effettivo',async()=>{
  service={...service,workflow:workflow('review'),selected_ids:['p0','p1'],proposal:{selected:['p0','p1'],shortlist:[],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  fireEvent.click(screen.getByRole('button',{name:'Includi sintetica-1.jpg'}));
  await screen.findByText('Inclusa manualmente');
  expect(screen.getByText('1 proposte da rivedere · 2 foto disponibili')).toBeTruthy();
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect((screen.getByLabelText('Mostra') as HTMLSelectElement).value).toBe('all');
  expect((screen.getByRole('button',{name:'Conferma selezione'}) as HTMLButtonElement).disabled).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Conferma selezione'}));
  const dialog=await screen.findByRole('dialog',{name:'Usa la proposta come selezione'});
  expect(within(dialog).getByText(/Conferma 1 foto nella selezione, comprese le tue modifiche manuali/)).toBeTruthy();
  expect(calls.find(x=>x.path.endsWith('/decisions/p1'))?.body).toEqual({revision:1,state:'candidate',locked:false,confirm_last:false});
  expect(calls.some(x=>x.path.includes('/rating-')||x.path.endsWith('/api-confirm'))).toBe(false);
});
it('sovrappone le decisioni manuali alla proposta nei filtri e nelle etichette',async()=>{
  service={...service,workflow:workflow('review'),decisions:{p0:{state:'excluded',locked:false},p1:{state:'candidate',locked:false}},proposal:{selected:['p0','p1'],shortlist:['p0'],groups:[],reasons:{},warnings:[],engine:'synthetic'}};
  await workspace();
  expect(screen.getAllByRole('article')).toHaveLength(1);
  expect(screen.getByText('sintetica-1.jpg')).toBeTruthy();
  expect(screen.getByText('1 proposte da rivedere · 2 foto disponibili')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Mostra'),{target:{value:'all'}});
  expect(screen.getAllByRole('article')).toHaveLength(2);
  expect(screen.getByText('Inclusa manualmente')).toBeTruthy();
  expect(screen.getByText('Esclusa manualmente')).toBeTruthy();
  expect(screen.getByRole('button',{name:'Includi sintetica-0.jpg'})).toBeTruthy();
  expect(screen.getByRole('button',{name:'Escludi sintetica-1.jpg'})).toBeTruthy();
});
it('rende visibile il motivo di un’analisi bloccata e offre la correzione dei criteri',async()=>{
  service={...service,workflow:{...workflow('configure','hybrid'),blocked:true,blocked_reasons:['Indica se desideri una selezione generale.']},settings:{...service.settings,mode:'hybrid',workflow_path:'hybrid'},job:{kind:'openai',status:'blocked',completed:0,total:2,error:'Istruzioni da chiarire'}};
  await workspace();
  const reason=screen.getByText('Indica se desideri una selezione generale.');
  expect(reason.closest('[role=alert]')).toBeTruthy();
  expect(reason.closest('details')).toBeNull();
  expect(screen.getByRole('heading',{name:'Configura la selezione'})).toBeTruthy();
  expect(calls.some(x=>x.method!=='GET')).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Prepara una nuova stima OpenAI'}));
  await waitFor(()=>expect(calls.some(x=>x.path.endsWith('/api-status'))).toBe(true));
  expect(calls.some(x=>x.path.endsWith('/analyze')||x.path.endsWith('/api-confirm'))).toBe(false);
});
