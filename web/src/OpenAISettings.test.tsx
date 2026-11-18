// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {OpenAISettings} from './OpenAISettings';

afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('keeps the key ephemeral and saves configuration without starting analysis',async()=>{
  const calls:{url:string;body?:Record<string,unknown>}[]=[];
  vi.stubGlobal('fetch',vi.fn(async(url:string,init?:RequestInit)=>{
    const body=init?.body?JSON.parse(String(init.body)):undefined;
    calls.push({url,body});
    return new Response(JSON.stringify({configured:Boolean(body),key_configured:Boolean(body),model:body?.model??'',analysis_enabled:false}),{headers:{'Content-Type':'application/json'}});
  }));
  render(<OpenAISettings/>);
  expect(calls).toHaveLength(0);
  fireEvent.click(screen.getByRole('button',{name:'Configurazione OpenAI'}));
  await waitFor(()=>expect((screen.getByLabelText('Modello API') as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('Modello API'),{target:{value:'synthetic-model'}});
  fireEvent.change(screen.getByLabelText('Chiave API'),{target:{value:'synthetic-api-key'}});
  fireEvent.click(screen.getByRole('button',{name:'Salva configurazione'}));
  await screen.findByRole('status');
  expect((screen.getByLabelText('Chiave API') as HTMLInputElement).value).toBe('');
  expect(calls[1]).toEqual({url:'/api/openai/config',body:{model:'synthetic-model',api_key:'synthetic-api-key'}});
  expect(calls.every(c=>c.url==='/api/openai/config')).toBe(true);
  expect(localStorage.length).toBe(0);
});
