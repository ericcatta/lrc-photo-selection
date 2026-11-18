export type State = 'candidate' | 'preferred' | 'alternative' | 'excluded' | 'review';
export type Preset = { id: string; name: string; version: number; criteria: string[] };
export type Settings = { target:number; preset_id:string; preset_version:number; mode:'local'|'hybrid'; instructions:string; camera_offsets:Record<string,number>; preset_snapshot?:Preset };
export type Summary = { id:string; title:string; photo_count:number; archived?:boolean; revision:number; status:string };
export type Photo = { id:string; uuid:string; local_id:number; filename:string; camera:string; captured_at:number|null; baseline_rating:number; baseline_edit_time:number|null; preview_ready:boolean };
export type Decision = { state:State; locked:boolean };
export type Group = { id:string; members:string[]; representative:string|null; reason:string };
export type Face = {x:number;y:number;width:number;height:number;confidence:number};
export type Service = Omit<Summary,'photo_count'> & { catalog_id:string; requires_analysis?:boolean;confirmed_batch_id?:string;can_undo?:boolean; can_redo?:boolean; interpretations?:{records:Record<string,{faces?:{observations?:Face[];error?:string|null}}> ;comparisons?:{photo_id:string;other_photo_id:string;cosine_similarity:number;reason:string}[]}; settings:Settings; photos:Photo[]; decisions:Record<string,Decision>; proposal:{selected:string[];added_candidates?:string[];groups:Group[];reasons:Record<string,string>;warnings:string[];engine:string;stale?:boolean}|null; job:{status:string;completed:number;total:number;error:string|null}|null; receipts:{batch_id:string;results:{photo_id:string;status:string;reason:string;before:number|null;after:number|null}[]}[]; criteria:{text:string;status:string;reason:string}[]; selected_ids?:string[] };
export type Plan = {batch_id:string;service_id:string;catalog_id:string;revision:number;warnings:string[];items:{photo_id:string;filename?:string;uuid:string;local_id:number;expected_rating:number;expected_edit_time:number|null;target_rating:1}[]};
export class ApiError extends Error {
  constructor(public status:number, public detail:unknown) {
    super(typeof detail==='string'?detail:(detail as {message?:string}|null)?.message??'La richiesta non è stata completata.');
  }
}
export async function api<T>(path:string, method='GET', body?:unknown):Promise<T> {
  const res=await fetch('/api'+path,{method,credentials:'same-origin',cache:'no-store',...(body===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
  if(!res.ok){ const error=await res.json().catch(()=>null); throw new ApiError(res.status,error?.detail); }
  return res.status===204?undefined as T:res.json();
}
export const servicePath=(id:string)=>'/services/'+encodeURIComponent(id);
export const photoPath=(sid:string,pid:string)=>servicePath(sid)+'/photos/'+encodeURIComponent(pid);
