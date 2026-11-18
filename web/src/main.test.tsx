// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { App } from './main';
import type { Preset, Service } from './api';

const preset: Preset = {id:'wedding',name:'Matrimonio',version:1,criteria:['Preservare varianti']};
let service: Service;
let calls: {path:string;method:string;body:Record<string,any>|undefined}[];
function json(value:unknown,status=200){return new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json'}});}

beforeEach(()=>{
  history.replaceState(null,'','/');
  Object.defineProperty(HTMLDialogElement.prototype,'showModal',{configurable:true,value:function(){this.setAttribute('open','');}});
  service={id:'synthetic',title:'TEST SINTETICO',catalog_id:'fake',revision:1,status:'ready',
    settings:{target:2,preset_id:'wedding',preset_version:1,preset_snapshot:preset,mode:'local',instructions:'',camera_offsets:{}},
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
    if(path==='/capabilities')return json({features:false});
    if(path==='/presets')return json([preset]);
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
async function workspace(){render(<App/>);await screen.findByRole('option',{name:/TEST SINTETICO/});fireEvent.change(screen.getByLabelText('Servizio'),{target:{value:'synthetic'}});await screen.findByRole('heading',{name:'Configura la selezione'});}

describe('Revisione senza dati reali',()=>{
  it('salva criteri senza avviare implicitamente l’analisi',async()=>{
    await workspace();
    fireEvent.change(screen.getByLabelText('Numero di candidate'),{target:{value:'1'}});
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
    const number=screen.getByLabelText('Numero di candidate') as HTMLInputElement;
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
      fireEvent.change(screen.getByLabelText('Numero di candidate'),{target:{value:'1'}});
      fireEvent.change(screen.getByLabelText('Servizio'),{target:{value:'second'}});
      expect(confirm).toHaveBeenCalled();
      expect(calls.some(c=>c.path.endsWith('/second'))).toBe(false);
      service={...service,revision:2,settings:{...service.settings,instructions:'Aggiornate altrove'}};
      fireEvent.click(screen.getByRole('button',{name:'Aggiorna'}));
      await screen.findByText('I criteri salvati sono cambiati.');
      expect((screen.getByLabelText('Numero di candidate') as HTMLInputElement).value).toBe('1');
      fireEvent.click(screen.getByRole('button',{name:'Carica i criteri salvati'}));
      expect((screen.getByLabelText('Numero di candidate') as HTMLInputElement).value).toBe('2');
    } finally {confirm.mockRestore();}
  });
  it('riapre un servizio archiviato conservando la revisione',async()=>{
    await workspace();
    fireEvent.click(screen.getByRole('button',{name:'Archivia servizio'}));
    await screen.findByText(/Servizio archiviato/);
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
    fireEvent.keyDown(screen.getByLabelText('Istruzioni per questo servizio'),{key:'x'});
    fireEvent.keyDown(screen.getByLabelText('Numero di candidate'),{key:'ArrowRight'});
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
