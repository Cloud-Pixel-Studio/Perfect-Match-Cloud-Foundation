import { parseProjectDetail, ProjectError, projectTextFits, trimProjectText, type ProjectContext, type ProjectDetail, type ProjectStep } from './qms-projects';

export type ReferenceKind = 'document'|'evidence';
type SourceScope = {tenant_id:string;unit_id:string;process_id:string;code:string};
export type DocumentCandidate = SourceScope & {kind:'document';document_id:string;document_revision_id:string;title:string;revision:string;file_sha256:string;document_version:number;revision_version:number};
export type EvidenceCandidate = SourceScope & {kind:'evidence';evidence_id:string;control_instance_id:string;name:string;instance_version:number;evidence_version:number};
export type ReferenceCandidate = DocumentCandidate|EvidenceCandidate;
type LinkCommon = {id:string;tenant_id:string;unit_id:string;project_id:string;step_id:string;target_process_id:string;snapshot_code:string;snapshot_name:string;linked_target_version:number;source_project_version:number;source_step_version:number;status:'active'|'removed';row_version:number;rationale:string;created_by_user_id:string;created_at:string;removed_by_user_id:string|null;removed_at:string|null;removal_reason:string};
export type DocumentReference = LinkCommon & {kind:'document';document_id:string;document_revision_id:string;snapshot_revision:string;file_sha256:string;linked_document_version:number;current_target_state:'active'|'changed'|'superseded'|'obsolete'|'unavailable'};
export type EvidenceReference = LinkCommon & {kind:'evidence';evidence_id:string;control_instance_id:string;linked_instance_version:number;current_target_state:'accepted'|'changed'|'implementation_archived'|'unavailable'};
export type ProjectReference = DocumentReference|EvidenceReference;
export type ReferencePage = {tenant_id:string;unit_id:string;project_id:string;step_id:string;project_status:'open'|'archived';project_version:number;step_version:number;observed_at:string;limit:number;offset:number;has_more:boolean;items:(ReferenceCandidate|ProjectReference)[]};
export type PageOptions = {candidates?:boolean;search?:string;limit?:number;offset?:number};
export type ReferenceResult = {kind:'restricted'}|{kind:'loaded';canManage:boolean;page:ReferencePage};
export type ReferenceCommand = {kind:'add';candidate:ReferenceCandidate;rationale:string}|{kind:'remove';link:ProjectReference;reason:string};
export class StaleReferenceError extends ProjectError { constructor(){super(409);this.name='StaleReferenceError';} }
const obj=(v:unknown):v is Record<string,unknown>=>v!==null&&typeof v==='object'&&!Array.isArray(v);
const uuid=(v:unknown):v is string=>typeof v==='string'&&/^[a-f\d]{8}(-[a-f\d]{4}){3}-[a-f\d]{12}$/i.test(v);
const integer=(v:unknown,min:number,max=2147483647):v is number=>typeof v==='number'&&Number.isInteger(v)&&v>=min&&v<=max;
const version=(v:unknown):v is number=>integer(v,1);
const instant=(v:unknown):v is string=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(v)&&Number.isFinite(Date.parse(v));
const text=(v:unknown,max:number):v is string=>typeof v==='string'&&projectTextFits(v,max)&&!/[\u0000\uD800-\uDBFF](?![\uDC00-\uDFFF])|(?<![\uD800-\uDBFF])[\uDC00-\uDFFF]/u.test(v);
export const referenceReasonValid=(v:string)=>text(v,1000)&&text(trimProjectText(v),500)&&Boolean(trimProjectText(v));
const reason=(v:unknown):v is string=>typeof v==='string'&&referenceReasonValid(v)&&trimProjectText(v)===v;
const invalid=()=>new ProjectError(502);
const lost=()=>new ProjectError(409,false,true);
function abort(signal?:AbortSignal){if(signal?.aborted)throw new DOMException('Reference request cancelled.','AbortError');}
function scope(v:Record<string,unknown>,c:ProjectContext){if(v.tenant_id!==c.tenantId||v.unit_id!==c.unitId)throw lost();}
function validate(c:ProjectContext,p:ProjectDetail,s:ProjectStep){
 if(![c.tenantId,c.userId,c.unitId,p.id,s.id].every(uuid))throw lost();scope(p,c);scope(s,c);
 if(s.project_id!==p.id||!p.steps.some(x=>x.id===s.id&&x.row_version===s.row_version)||!version(p.row_version)||!version(s.row_version))throw invalid();
}
async function read(path:string,signal:AbortSignal|undefined,request:typeof fetch){abort(signal);const r=await request('/api/identity'+path,{credentials:'include',cache:'no-store',signal});abort(signal);if(r.status!==200)throw new ProjectError(r.status);let raw:unknown;try{raw=await r.json();}catch{throw invalid();}abort(signal);return raw;}
async function access(c:ProjectContext,kind:ReferenceKind,signal:AbortSignal|undefined,request:typeof fetch){
 const actor=await read('/auth/me',signal,request);if(!obj(actor)||actor.id!==c.userId||actor.current_tenant_id!==c.tenantId)throw lost();
 const unit=await read('/organization/units/'+c.unitId,signal,request);if(!obj(unit)||unit.id!==c.unitId||unit.tenant_id!==c.tenantId||unit.status!=='active')throw lost();
 const v=await read('/qms-access/effective?unit_id='+c.unitId,signal,request);
 if(!obj(v)||v.unit_id!==c.unitId||!Array.isArray(v.capabilities)||!v.capabilities.every(x=>typeof x==='string'&&/^[a-z_]+\.[a-z_]+$/.test(x)&&x.length<=64)||new Set(v.capabilities).size!==v.capabilities.length)throw lost();
 if(!v.capabilities.includes('projects.read'))throw new ProjectError(403);
 return{canRead:v.capabilities.includes(kind==='document'?'documents.read':'control_instances.read'),canManage:v.capabilities.includes('projects.manage')};
}
function parseCandidate(raw:unknown,c:ProjectContext,kind:ReferenceKind):ReferenceCandidate{
 if(!obj(raw))throw invalid();scope(raw,c);
 if(!uuid(raw.process_id)||!text(raw.code,50))throw invalid();
 if(kind==='document'){
  if(!uuid(raw.document_id)||!uuid(raw.document_revision_id)||!text(raw.title,200)||!text(raw.revision,40)||typeof raw.file_sha256!=='string'||!(/^[a-f0-9]{64}$/).test(raw.file_sha256)||!version(raw.document_version)||!version(raw.revision_version)||'evidence_id' in raw)throw invalid();
 }else if(!uuid(raw.evidence_id)||!uuid(raw.control_instance_id)||!text(raw.name,160)||!version(raw.instance_version)||!version(raw.evidence_version)||'document_id' in raw)throw invalid();
 return {...raw,kind} as ReferenceCandidate;
}
function parseLink(raw:unknown,c:ProjectContext,p:ProjectDetail,s:ProjectStep,kind:ReferenceKind):ProjectReference{
 if(!obj(raw))throw invalid();scope(raw,c);if(raw.project_id!==p.id||raw.step_id!==s.id)throw lost();
 if(!uuid(raw.id)||!uuid(raw.target_process_id)||!text(raw.snapshot_code,50)||!text(raw.snapshot_name,200)||!version(raw.linked_target_version)||!version(raw.source_project_version)||!version(raw.source_step_version)||!version(raw.row_version)||!reason(raw.rationale)||!uuid(raw.created_by_user_id)||!instant(raw.created_at))throw invalid();
 if(raw.status==='active'){if(raw.removed_by_user_id!==null||raw.removed_at!==null||raw.removal_reason!=='')throw invalid();}
 else if(raw.status==='removed'){if(!uuid(raw.removed_by_user_id)||!instant(raw.removed_at)||!reason(raw.removal_reason)||Date.parse(raw.removed_at)<Date.parse(raw.created_at))throw invalid();}else throw invalid();
 if(kind==='document'){
  if(!uuid(raw.document_id)||!uuid(raw.document_revision_id)||!text(raw.snapshot_revision,40)||typeof raw.file_sha256!=='string'||!(/^[a-f0-9]{64}$/).test(raw.file_sha256)||!version(raw.linked_document_version)||!['active','changed','superseded','obsolete','unavailable'].includes(raw.current_target_state as string)||'evidence_id'in raw)throw invalid();
 }else if(!uuid(raw.evidence_id)||!uuid(raw.control_instance_id)||!version(raw.linked_instance_version)||!['accepted','changed','implementation_archived','unavailable'].includes(raw.current_target_state as string)||'document_id'in raw)throw invalid();
 return{...raw,kind} as ProjectReference;
}
export function parseReferencePage(raw:unknown,c:ProjectContext,p:ProjectDetail,s:ProjectStep,kind:ReferenceKind,options:PageOptions={}):ReferencePage{
 validate(c,p,s);if(!obj(raw))throw invalid();scope(raw,c);if(raw.project_id!==p.id||raw.step_id!==s.id)throw lost();
 if(!version(raw.project_version)||!version(raw.step_version)||!['open','archived'].includes(raw.project_status as string)||!instant(raw.observed_at)||raw.limit!==(options.limit??50)||raw.offset!==(options.offset??0)||typeof raw.has_more!=='boolean'||!Array.isArray(raw.items)||raw.items.length>(options.limit??50)||raw.has_more&&raw.items.length!==(options.limit??50))throw invalid();
 const items=raw.items.map(v=>options.candidates?parseCandidate(v,c,kind):parseLink(v,c,p,s,kind));
 const keys=items.map(x=>'id'in x?x.id:x.kind==='document'?x.document_revision_id:x.evidence_id);if(new Set(keys.map(x=>x.toLowerCase())).size!==keys.length)throw invalid();
 if(raw.project_version!==p.row_version||raw.step_version!==s.row_version||raw.project_status!==p.status)throw new StaleReferenceError();
 if(items.some(x=>'source_project_version'in x&&(x.source_project_version>p.row_version||x.source_step_version>s.row_version)))throw invalid();
 return {...raw,items} as ReferencePage;
}
function path(p:ProjectDetail,s:ProjectStep,kind:ReferenceKind){return `/qms-projects/${p.id}/steps/${s.id}/${kind}`;}
export async function loadReferencePage(c:ProjectContext,p:ProjectDetail,s:ProjectStep,kind:ReferenceKind,options:PageOptions={},signal?:AbortSignal,request:typeof fetch=fetch):Promise<ReferenceResult>{
 validate(c,p,s);if(!['document','evidence'].includes(kind)||!integer(options.limit??50,1,50)||!integer(options.offset??0,0,1000000)||!text(options.search??'',160))throw new ProjectError(422);
 const before=await access(c,kind,signal,request);
 if(!before.canRead){await access(c,kind,signal,request);return{kind:'restricted'};}
 const query=new URLSearchParams({limit:String(options.limit??50),offset:String(options.offset??0)});if(options.candidates)query.set('search',options.search??'');
 const page=parseReferencePage(await read(path(p,s,kind)+(options.candidates?'-candidates':'-links')+'?'+query,signal,request),c,p,s,kind,options);
 const after=await access(c,kind,signal,request);if(!after.canRead)throw new ProjectError(403);abort(signal);return{kind:'loaded',canManage:before.canManage&&after.canManage,page};
}
function sameFields(a:object,b:object,except:string[]){return Object.entries(a).every(([key,value])=>except.includes(key)||JSON.stringify(value)===JSON.stringify((b as Record<string,unknown>)[key]));}
export async function mutateReference(c:ProjectContext,p:ProjectDetail,s:ProjectStep,command:ReferenceCommand,csrf:string,signal?:AbortSignal,request:typeof fetch=fetch):Promise<{project:ProjectDetail;link:ProjectReference}>{
 validate(c,p,s);if(!/^[A-Za-z0-9_-]{20,256}$/.test(csrf))throw new ProjectError(403);
 const kind=command.kind==='add'?command.candidate.kind:command.link.kind;
 const permissions=await access(c,kind,signal,request);if(!permissions.canRead||!permissions.canManage)throw new ProjectError(403);
 if(p.status!=='open'||p.row_version===2147483647||s.row_version===2147483647)throw new ProjectError(409);
 const content=trimProjectText(command.kind==='add'?command.rationale:command.reason);if(!referenceReasonValid(content))throw new ProjectError(422);
 let suffix='-links';const body:Record<string,unknown>={expected_project_version:p.row_version,expected_step_version:s.row_version};
 if(command.kind==='add'){
  const source=parseCandidate(command.candidate,c,kind);body.rationale=content;
  if(source.kind==='document')Object.assign(body,{document_id:source.document_id,document_revision_id:source.document_revision_id,expected_document_version:source.document_version,expected_revision_version:source.revision_version});
  else Object.assign(body,{evidence_id:source.evidence_id,expected_instance_version:source.instance_version,expected_evidence_version:source.evidence_version});
 }else{
  const link=parseLink(command.link,c,p,s,kind);if(link.status!=='active'||link.row_version===2147483647)throw new ProjectError(409);suffix+=`/${link.id}/remove`;Object.assign(body,{expected_link_version:link.row_version,reason:content});
 }
 abort(signal);let sent=false;
 try{
  sent=true;const response=await request('/api/identity'+path(p,s,kind)+suffix,{method:'POST',credentials:'include',cache:'no-store',headers:{'Content-Type':'application/json','X-CSRF-Token':csrf},body:JSON.stringify(body),signal});
  if(!response.ok){if(response.status<500)sent=false;throw new ProjectError(response.status);}
  if(response.status!==(command.kind==='add'?201:200))throw invalid();abort(signal);
  const raw:unknown=await response.json();if(!obj(raw))throw invalid();const project=parseProjectDetail(raw.project,c),nextStep=project.steps.find(x=>x.id===s.id);if(!nextStep)throw invalid();
  const link=parseLink(raw.link,c,project,nextStep,kind);
  if(project.id!==p.id||project.row_version!==p.row_version+1||nextStep.row_version!==s.row_version+1||nextStep.updated_by_user_id!==c.userId||!sameFields(p,project,['row_version','updated_at','steps'])||project.steps.some((x,i)=>!sameFields(p.steps[i],x,x.id===s.id?['row_version','updated_at','updated_by_user_id']:[]))||link.source_project_version!==project.row_version||link.source_step_version!==nextStep.row_version)throw invalid();
  if(command.kind==='add'){
   const a=command.candidate;if(link.status!=='active'||link.row_version!==1||link.rationale!==content||link.created_by_user_id!==c.userId||link.target_process_id!==a.process_id||link.snapshot_code!==a.code)throw invalid();
   if(a.kind==='document'){if(link.kind!=='document'||link.document_id!==a.document_id||link.document_revision_id!==a.document_revision_id||link.snapshot_name!==a.title||link.snapshot_revision!==a.revision||link.file_sha256!==a.file_sha256||link.linked_document_version!==a.document_version||link.linked_target_version!==a.revision_version)throw invalid();}
   else if(link.kind!=='evidence'||link.evidence_id!==a.evidence_id||link.control_instance_id!==a.control_instance_id||link.snapshot_name!==a.name||link.linked_instance_version!==a.instance_version||link.linked_target_version!==a.evidence_version)throw invalid();
  }else if(link.id!==command.link.id||link.status!=='removed'||link.row_version!==command.link.row_version+1||link.removed_by_user_id!==c.userId||link.removal_reason!==content||!sameFields(command.link,link,['status','row_version','source_project_version','source_step_version','removed_by_user_id','removed_at','removal_reason','current_target_state']))throw invalid();
  const after=await access(c,kind,signal,request);if(!after.canRead||!after.canManage)throw new ProjectError(403);abort(signal);return{project,link};
 }catch(cause){if(sent)throw new ProjectError(cause instanceof ProjectError?cause.status:0,true,cause instanceof ProjectError&&cause.contextLost);if(cause instanceof ProjectError)throw cause;throw new ProjectError(0);}
}
