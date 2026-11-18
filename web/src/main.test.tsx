// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
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
    if(path==='/services')return json([{id:service.id,title:service.title,photo_count:2,revision:service.revision,status:service.status}]);
    if(path==='/presets')return json([preset]);
    if(path==='/services/synthetic')return json(service);
    if(path.endsWith('/settings')){service={...service,revision:service.revision+1,settings:{...body.settings,preset_snapshot:preset}};return json(service);}
    if(path.includes('/decisions/')){
      if(body.state==='excluded'&&!body.confirm_last)return json({detail:{code:'last_candidate',message:'Confermare ultima candidata?'}},409);
      service={...service,revision:service.revision+1,decisions:{...service.decisions,[path.split('/').at(-1)!]:{state:body.state,locked:body.locked}}};return json(service);
    }
    if(path.endsWith('/analyze'))return json({...service,job:{status:'completed',completed:2,total:2,error:null}});
    if(path.endsWith('/rating-plan'))return json({batch_id:'b',service_id:service.id,catalog_id:'fake',revision:service.revision,warnings:[],items:[{photo_id:'p0',uuid:'u0',local_id:0,expected_rating:0,expected_edit_time:1,target_rating:1}]});
    throw new Error('Unexpected endpoint '+path);
  }));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
async function workspace(){render(<App/>);fireEvent.click(await screen.findByRole('button',{name:/TEST SINTETICO/}));await screen.findByRole('heading',{name:'Configura la selezione'});}

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
  it('rimuove il token dal frammento URL dopo la connessione',async()=>{
    history.replaceState(null,'','/#token=synthetic-connection-token');
    render(<App/>);
    await screen.findByRole('button',{name:/TEST SINTETICO/});
    expect(location.hash).toBe('');
    expect(calls[0].path).toBe('/session');
  });
});
