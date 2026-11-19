import { journeys, type GuideJourney } from "./guided-journeys";

export const projectCatalogVersion = "guided-qms-v1";
export type ProjectContext = { tenantId: string; userId: string; unitId: string };
export type Project = { id:string; tenant_id:string; unit_id:string; code:string; name:string; journey_key:GuideJourney["id"]; catalog_version:typeof projectCatalogVersion; scope_summary:string; coordinator_user_id:string|null; target_date:string|null; status:"open"|"archived"; row_version:number; created_by_user_id:string; created_at:string; updated_at:string };
export type ProjectStep = { id:string; tenant_id:string; unit_id:string; project_id:string; step_key:string; position:number; status:"not_started"|"in_progress"|"blocked"|"reported"|"feature_pending"; notes:string; assignee_user_id:string|null; target_date:string|null; row_version:number; updated_by_user_id:string; updated_at:string };
export type ProjectDetail = Project & { steps:ProjectStep[] };
export type ProjectMember = {id:string;display_name:string;role:string};
export type ProjectIndex = {kind:"restricted"} | {kind:"loaded";projects:Project[];limited:boolean;members:ProjectMember[];membersLimited:boolean;canManage:boolean};
type ProjectChanges = Partial<Pick<Project,"name"|"scope_summary"|"coordinator_user_id"|"target_date">>;
type StepChanges = Partial<Pick<ProjectStep,"status"|"notes"|"assignee_user_id"|"target_date">>;
export type ProjectCommand = {kind:"create";input:Pick<Project,"code"|"name"|"journey_key"|"scope_summary"|"coordinator_user_id"|"target_date">} | {kind:"update";id:string;expectedVersion:number;changes:ProjectChanges} | {kind:"status";id:string;expectedVersion:number;targetStatus:Project["status"];reason:string} | {kind:"step";id:string;stepId:string;expectedVersion:number;expectedStepVersion:number;changes:StepChanges};
export class ProjectError extends Error {
  constructor(public status:number, public uncertain=false, public contextLost=false) { super(uncertain?"The save could not be confirmed. Refresh before trying again.":"Project access or response could not be verified."); this.name="ProjectError"; }
}
export class ProjectCatalogError extends ProjectError {
  catalogMismatch = true;
  constructor(){super(409);this.name="ProjectCatalogError";}
}
const obj=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==="object"&&!Array.isArray(v);
const uuid=(v:unknown):v is string=>typeof v==="string"&&/^[a-f\d]{8}(-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(v);
const positive=(v:unknown):v is number=>typeof v==="number"&&Number.isSafeInteger(v)&&v>0;
// Match the project's API/SQL blank set; keep internal whitespace and notes unchanged.
const projectBlankPoints=new Set([9,10,11,12,13,28,29,30,31,32,133,160,5760,8192,8193,8194,8195,8196,8197,8198,8199,8200,8201,8202,8232,8233,8239,8287,12288,65279]);
export function trimProjectText(value:string){
 let start=0,end=value.length;
 while(start<end&&projectBlankPoints.has(value.charCodeAt(start)))start++;
 while(end>start&&projectBlankPoints.has(value.charCodeAt(end-1)))end--;
 return value.slice(start,end);
}
// API and PostgreSQL limits count Unicode characters, not UTF-16 code units.
export const projectTextFits=(value:string,max:number)=>value.length<=max*2&&Array.from(value).length<=max;
const str=(v:unknown,max:number,min=0):v is string=>typeof v==="string"&&projectTextFits(v,max)&&trimProjectText(v).length>=min;
const nullableUuid=(v:unknown)=>v===null||uuid(v);
const date=(v:unknown)=>v===null||typeof v==="string"&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&Number.isFinite(Date.parse(v))&&new Date(v).toISOString().slice(0,10)===v;
const instant=(v:unknown)=>typeof v==="string"&&/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(v)&&Number.isFinite(Date.parse(v));
const unique=(rows:{id:string}[])=>new Set(rows.map(x=>x.id.toLowerCase())).size===rows.length;
const invalid=()=>new ProjectError(409,false,true);
function abort(signal?:AbortSignal){if(signal?.aborted)throw new DOMException("Project request cancelled.","AbortError");}
function validateContext(c:ProjectContext){if(![c.tenantId,c.userId,c.unitId].every(uuid))throw invalid();}
function parseProject(v:unknown,c:ProjectContext):Project{
  if(obj(v)&&v.tenant_id===c.tenantId&&v.unit_id===c.unitId&&(v.catalog_version!==projectCatalogVersion||!journeys.some(j=>j.id===v.journey_key)))throw new ProjectCatalogError();
  if(!obj(v)||!uuid(v.id)||v.tenant_id!==c.tenantId||v.unit_id!==c.unitId||!str(v.code,40,1)||!str(v.name,160,1)||!journeys.some(j=>j.id===v.journey_key)||v.catalog_version!==projectCatalogVersion||!str(v.scope_summary,4000)||!nullableUuid(v.coordinator_user_id)||!date(v.target_date)||!['open','archived'].includes(v.status as string)||!positive(v.row_version)||!uuid(v.created_by_user_id)||!instant(v.created_at)||!instant(v.updated_at))throw invalid();
  return v as Project;
}
export function parseProjectDetail(v:unknown,c:ProjectContext):ProjectDetail{
  validateContext(c);const project=parseProject(v,c);if(!obj(v)||!Array.isArray(v.steps))throw invalid();
  const catalog=journeys.find(j=>j.id===project.journey_key)!.steps;
  if(v.steps.length!==catalog.length)throw new ProjectCatalogError();
  const steps=v.steps.map((s:unknown,i:number)=>{
    if(!obj(s)||!uuid(s.id)||s.tenant_id!==c.tenantId||s.unit_id!==c.unitId||s.project_id!==project.id||!positive(s.row_version)||!str(s.notes,2000)||!nullableUuid(s.assignee_user_id)||!date(s.target_date)||!uuid(s.updated_by_user_id)||!instant(s.updated_at)||typeof s.status!=="string")throw invalid();
    if(s.step_key!==catalog[i].id||s.position!==i+1)throw new ProjectCatalogError();
    if(catalog[i].productGap?s.status!=="feature_pending":!["not_started","in_progress","blocked","reported"].includes(s.status))throw invalid();
    if(["blocked","reported"].includes(s.status)&&!trimProjectText(s.notes))throw invalid();
    return s as ProjectStep;
  });if(!unique(steps))throw invalid();return {...project,steps};
}
async function read(path:string,signal:AbortSignal|undefined,request:typeof fetch,tenantHeader?:string):Promise<unknown>{
  abort(signal);const r=await request('/api/identity'+path,{credentials:'include',cache:'no-store',signal});abort(signal);
  if(r.status!==200)throw new ProjectError(r.status);
  if(tenantHeader&&r.headers.get('X-Tenant-ID')!==tenantHeader)throw invalid();
  const v:unknown=await r.json();abort(signal);return v;
}
async function identity(c:ProjectContext,signal:AbortSignal|undefined,request:typeof fetch){
  const v=await read('/auth/me',signal,request);if(!obj(v)||v.id!==c.userId||v.current_tenant_id!==c.tenantId)throw invalid();
}
async function access(c:ProjectContext,signal:AbortSignal|undefined,request:typeof fetch){
  validateContext(c);await identity(c,signal,request);
  const unit=await read('/organization/units/'+c.unitId,signal,request);
  if(!obj(unit)||unit.id!==c.unitId||unit.tenant_id!==c.tenantId||unit.status!=='active')throw invalid();
  const v=await read('/qms-access/effective?unit_id='+c.unitId,signal,request);
  if(!obj(v)||v.unit_id!==c.unitId||!Array.isArray(v.capabilities)||!v.capabilities.every(x=>typeof x==='string'&&/^[a-z_]+\.[a-z_]+$/.test(x)&&x.length<=64)||new Set(v.capabilities).size!==v.capabilities.length)throw invalid();
  return {canRead:v.capabilities.includes('projects.read'),canManage:v.capabilities.includes('projects.read')&&v.capabilities.includes('projects.manage')};
}
export async function loadProjectIndex(c:ProjectContext,signal?:AbortSignal,request:typeof fetch=fetch):Promise<ProjectIndex>{
  const permissions=await access(c,signal,request);
  if(!permissions.canRead){await identity(c,signal,request);return{kind:'restricted'};}
  const rows=await read(`/qms-projects?unit_id=${c.unitId}&limit=50&offset=0`,signal,request);
  if(!Array.isArray(rows)||rows.length>50)throw invalid();const projects=rows.map(v=>parseProject(v,c));if(!unique(projects))throw invalid();
  let members:ProjectMember[]=[];
  if(permissions.canManage){const raw=await read('/organization/members?limit=100&offset=0',signal,request,c.tenantId);
    if(!Array.isArray(raw)||raw.length>100||!raw.every(v=>obj(v)&&uuid(v.id)&&str(v.display_name,160,1)&&typeof v.role==='string'&&['owner','admin','member','auditor'].includes(v.role)))throw invalid();members=raw;if(!unique(members))throw invalid();
  }
  await identity(c,signal,request);abort(signal);
  return{kind:'loaded',projects,limited:projects.length===50,members,membersLimited:members.length===100,canManage:permissions.canManage};
}
export async function loadProject(c:ProjectContext,id:string,signal?:AbortSignal,request:typeof fetch=fetch):Promise<ProjectDetail>{
  if(!uuid(id))throw invalid();const p=await access(c,signal,request);if(!p.canRead)throw new ProjectError(403);
  const result=parseProjectDetail(await read('/qms-projects/'+id,signal,request),c);if(result.id!==id)throw invalid();
  await identity(c,signal,request);abort(signal);return result;
}
export async function mutateProject(c:ProjectContext,command:ProjectCommand,csrf:string,signal?:AbortSignal,request:typeof fetch=fetch):Promise<ProjectDetail>{
  if(!/^[A-Za-z0-9_-]{20,256}$/.test(csrf))throw new ProjectError(403);
  const permissions=await access(c,signal,request);if(!permissions.canManage)throw new ProjectError(403);
  let path='/qms-projects',method='POST',body:object;
  if(command.kind==='create'){body={...command.input,unit_id:c.unitId};}
  else{
    if(!uuid(command.id)||!positive(command.expectedVersion))throw invalid();path+='/'+command.id;
    if(command.kind==='status'){path+='/status';body={expected_version:command.expectedVersion,target_status:command.targetStatus,reason:command.reason};}
    else if(command.kind==='step'){
      if(!uuid(command.stepId)||!positive(command.expectedStepVersion))throw invalid();path+='/steps/'+command.stepId;method='PATCH';body={...command.changes,expected_project_version:command.expectedVersion,expected_version:command.expectedStepVersion};
    }else{method='PATCH';body={...command.changes,expected_version:command.expectedVersion};}
  }
  abort(signal);let sent=false;
  try{
    sent=true;const r=await request('/api/identity'+path,{method,credentials:'include',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body),signal});
    if(!r.ok){if(r.status<500)sent=false;throw new ProjectError(r.status);}
    if(r.status!==(command.kind==='create'?201:200))throw new ProjectError(r.status,true);
    abort(signal);const result=parseProjectDetail(await r.json(),c);
    if(command.kind==='create'){
      if(result.row_version!==1||result.status!=='open'||Object.entries(command.input).some(([k,v])=>result[k as keyof Project]!==v))throw invalid();
    }else{
      if(result.id!==command.id||result.row_version!==command.expectedVersion+1)throw invalid();
      if(command.kind==='update'&&Object.entries(command.changes).some(([k,v])=>result[k as keyof Project]!==v))throw invalid();
      if(command.kind==='status'&&result.status!==command.targetStatus)throw invalid();
      if(command.kind==='step'){const step=result.steps.find(s=>s.id===command.stepId);if(!step||step.row_version!==command.expectedStepVersion+1||Object.entries(command.changes).some(([k,v])=>step[k as keyof ProjectStep]!==v))throw invalid();}
    }
    await identity(c,signal,request);abort(signal);return result;
  }catch(cause){
    if(sent)throw new ProjectError(cause instanceof ProjectError?cause.status:0,true,cause instanceof ProjectError&&cause.contextLost);
    if(cause instanceof ProjectError)throw cause;throw new ProjectError(0,false);
  }
}
