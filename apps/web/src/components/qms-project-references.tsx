'use client';

import { useCallback, useEffect, useRef, useState, type FormEvent } from 'react';
import { loadProject, ProjectError, trimProjectText, type ProjectContext, type ProjectDetail, type ProjectStep } from '../lib/qms-projects';
import { loadReferencePage, mutateReference, referenceReasonValid, StaleReferenceError, type ReferenceCandidate, type ReferenceKind, type ProjectReference, type ReferenceResult } from '../lib/qms-project-references';

type Props={context:ProjectContext;project:ProjectDetail;step:ProjectStep;canManage:boolean;disabled:boolean;onChange:(project:ProjectDetail)=>void;onAccessLost:(status:number)=>void;onEditingChange:(editing:boolean)=>void};
type Draft={mode:'add';candidate:ReferenceCandidate|null;text:string;project:ProjectDetail;step:ProjectStep}|{mode:'remove';link:ProjectReference;text:string;project:ProjectDetail;step:ProjectStep};
const pageSize=50;
const sourceKey=(source:ReferenceCandidate)=>source.kind==='document'?source.document_revision_id:source.evidence_id;
const sourceName=(source:ReferenceCandidate)=>trimProjectText(source.kind==='document'?source.title:source.name)||'Unnamed source';
function csrf(){try{return decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('pm_csrf='))?.slice(8)??'');}catch{return '';}}
function feedback(cause:unknown){
 if(cause instanceof StaleReferenceError)return 'The project or step changed. Reload the latest project and review its versions before editing references.';
 if(cause instanceof ProjectError){
  if(cause.uncertain)return 'This save is unconfirmed and may have reached the server. Reload and inspect the supporting records before deciding whether to retry. Your draft was kept.';
  if(cause.status===409)return 'The project, source or reference changed. Your draft was kept. Reload the latest project before adopting refreshed versions.';
  if(cause.status===422)return 'Check the source and enter a reason of 1 to 500 characters. Your draft was kept.';
  if(cause.status===404)return 'This record is no longer available in the current scope. Your draft was kept.';
 }
 return 'Supporting records could not be verified. Your draft was kept; reload before continuing.';
}
export function QMSProjectReferences(props:Props){
 const {onEditingChange}=props;
 const [editing,setEditing]=useState<ReferenceKind|null>(null);
 const documentEditing=useCallback((active:boolean)=>setEditing(old=>active?'document':old==='document'?null:old),[]);
 const evidenceEditing=useCallback((active:boolean)=>setEditing(old=>active?'evidence':old==='evidence'?null:old),[]);
 useEffect(()=>{onEditingChange(editing!==null);return()=>onEditingChange(false);},[editing,onEditingChange]);
 return <section className="project-references" aria-label="Project supporting records"><h5>Project supporting records</h5><p className="project-help">Cite records that support this project step. A citation never verifies the step or ISO conformity. Accepted evidence is accepted in its source implementation; its attached document is not re-evaluated here.</p>
  <ReferencePanel {...props} kind="document" disabled={props.disabled||editing==='evidence'} onEditingChange={documentEditing}/>
  <ReferencePanel {...props} kind="evidence" disabled={props.disabled||editing==='document'} onEditingChange={evidenceEditing}/>
 </section>;
}
function ReferencePanel({context,project,step,canManage,disabled,onChange,onAccessLost,onEditingChange,kind}:Props&{kind:ReferenceKind}){
 const [result,setResult]=useState<ReferenceResult|null>(null),[completedRead,setCompletedRead]=useState(''),[error,setError]=useState(''),[revision,setRevision]=useState(0),[offset,setOffset]=useState(0);
 const [draft,setDraft]=useState<Draft|null>(null),[candidates,setCandidates]=useState<ReferenceResult|null>(null),[completedSources,setCompletedSources]=useState(''),[search,setSearch]=useState(''),[appliedSearch,setAppliedSearch]=useState(''),[sourceOffset,setSourceOffset]=useState(0);
 const [busy,setBusy]=useState(false),[reloading,setReloading]=useState(false),[blocked,setBlocked]=useState(false),[refreshed,setRefreshed]=useState<ProjectDetail|null>(null),[notice,setNotice]=useState('');
 const operation=useRef<AbortController|null>(null),everRead=useRef(false);
 const editing=Boolean(draft),adding=draft?.mode==='add';
 const readKey=JSON.stringify([context,project.id,project.row_version,step.id,step.row_version,kind,offset,revision]);
 const sourcesKey=JSON.stringify([context,project.id,project.row_version,step.id,step.row_version,kind,appliedSearch,sourceOffset,revision,adding]);
 const loading=completedRead!==readKey,sourceLoading=adding&&completedSources!==sourcesKey;
 useEffect(()=>{onEditingChange(editing);return()=>onEditingChange(false);},[editing,onEditingChange]);
 useEffect(()=>()=>operation.current?.abort(),[]);
 const fail=useCallback((cause:unknown)=>{
  if(cause instanceof ProjectError&&(cause.contextLost||[401,403].includes(cause.status))){setResult(null);setCandidates(null);setDraft(null);onAccessLost(cause.status===401?401:403);return;}
  setError(feedback(cause));if(cause instanceof StaleReferenceError||cause instanceof ProjectError&&(cause.status===409||cause.uncertain))setBlocked(true);
 },[onAccessLost]);
 const accept=useCallback((value:ReferenceResult)=>{if(value.kind==='restricted'&&everRead.current){fail(new ProjectError(403));return;}if(value.kind==='loaded')everRead.current=true;setResult(value);},[fail]);
 useEffect(()=>{
  const controller=new AbortController();
  void loadReferencePage(context,project,step,kind,{offset},controller.signal).then(value=>{if(!controller.signal.aborted)accept(value);}).catch(cause=>{if(!controller.signal.aborted){setResult(null);fail(cause);}}).finally(()=>{if(!controller.signal.aborted)setCompletedRead(readKey);});
  return()=>controller.abort();
 },[context,project,step,kind,offset,revision,readKey,accept,fail]);
 useEffect(()=>{
  if(!adding)return;
  const controller=new AbortController();
  void loadReferencePage(context,project,step,kind,{candidates:true,search:appliedSearch,offset:sourceOffset},controller.signal).then(value=>{if(controller.signal.aborted)return;if(value.kind==='restricted'){fail(new ProjectError(403));return;}setCandidates(value);}).catch(cause=>{if(!controller.signal.aborted){setCandidates(null);fail(cause);}}).finally(()=>{if(!controller.signal.aborted)setCompletedSources(sourcesKey);});
  return()=>controller.abort();
 },[adding,context,project,step,kind,appliedSearch,sourceOffset,revision,sourcesKey,fail]);
 const title=kind==='document'?'Document revisions':'Accepted evidence';
 const rows=result?.kind==='loaded'?result.page.items.filter((x):x is ProjectReference=>'id'in x):[];
 const sources=candidates?.kind==='loaded'?candidates.page.items.filter((x):x is ReferenceCandidate=>!('id'in x)):[];
 const writable=canManage&&result?.kind==='loaded'&&result.canManage&&project.status==='open'&&!disabled;
 const matching=draft?.mode==='add'&&draft.candidate?rows.some(x=>x.status==='active'&&(draft.candidate!.kind==='document'?x.kind==='document'&&x.document_revision_id===sourceKey(draft.candidate!):x.kind==='evidence'&&x.evidence_id===sourceKey(draft.candidate!))):false;
 const removedAlready=draft?.mode==='remove'&&rows.some(x=>x.id===draft.link.id&&x.status==='removed');
 const invalidReason=Boolean(draft?.text)&&!referenceReasonValid(draft!.text);
 function startAdd(){setDraft({mode:'add',candidate:null,text:'',project,step});setCandidates(null);setSearch('');setAppliedSearch('');setSourceOffset(0);setError('');setNotice('');setBlocked(false);setRefreshed(null);}
 function cancel(){setDraft(null);setCandidates(null);setError('');setBlocked(false);setRefreshed(null);setNotice('');}
 async function save(event:FormEvent){
  event.preventDefault();if(!draft||!writable||blocked||operation.current)return;
  if(!referenceReasonValid(draft.text)||draft.mode==='add'&&!draft.candidate){setError('Select a source and enter a reason of 1 to 500 characters. Your draft was kept.');return;}
  const controller=new AbortController();operation.current=controller;setBusy(true);setError('');setRefreshed(null);
  try{
   const command=draft.mode==='add'?{kind:'add' as const,candidate:draft.candidate!,rationale:draft.text}:{kind:'remove' as const,link:draft.link,reason:draft.text};
   const value=await mutateReference(context,draft.project,draft.step,command,csrf(),controller.signal);
   if(controller.signal.aborted)return;onChange(value.project);setDraft(null);setCandidates(null);setOffset(0);setRevision(x=>x+1);setBlocked(false);setNotice(draft.mode==='add'?'Supporting record saved. The step remains unverified.':'Reference removed. Its snapshot and rationale remain in history.');
  }catch(cause){if(!controller.signal.aborted)fail(cause);}finally{if(!controller.signal.aborted){operation.current=null;setBusy(false);}}
 }
 async function reload(){
  if(operation.current)return;const controller=new AbortController();operation.current=controller;setReloading(true);setRefreshed(null);setError('');
  try{
   const latest=await loadProject(context,project.id,controller.signal);const latestStep=latest.steps.find(x=>x.id===step.id);if(!latestStep)throw new ProjectError(409,false,true);
   const value=await loadReferencePage(context,latest,latestStep,kind,{offset:0},controller.signal);if(controller.signal.aborted)return;
   if(value.kind==='restricted'&&everRead.current)throw new ProjectError(403);
   onChange(latest);accept(value);setOffset(0);setRefreshed(latest);setNotice('Latest records loaded. Your reference draft is unchanged. Inspect history, then explicitly adopt refreshed versions if another attempt is needed.');
  }catch(cause){if(!controller.signal.aborted)fail(cause);}finally{if(!controller.signal.aborted){operation.current=null;setReloading(false);}}
 }
 function adopt(){
  if(!draft||!refreshed||matching||removedAlready)return;const latestStep=refreshed.steps.find(x=>x.id===step.id)!;
  if(draft.mode==='remove'){const current=rows.find(x=>x.id===draft.link.id&&x.status==='active');if(!current){setError('The reference is absent or removed. Inspect history before cancelling this draft.');return;}setDraft({...draft,project:refreshed,step:latestStep,link:current});}
  else setDraft({...draft,project:refreshed,step:latestStep});
  setBlocked(false);setRefreshed(null);setError('');setNotice('Refreshed project and step versions adopted. Review the selected source before saving.');
 }
 function changeSources(nextOffset:number,nextSearch=appliedSearch){setDraft(old=>old?.mode==='add'?{...old,candidate:null}:old);setCandidates(null);setSourceOffset(nextOffset);setAppliedSearch(nextSearch);setRevision(x=>x+1);}
 return <section className="project-reference-kind" aria-label={title} aria-busy={loading||busy||reloading}><div className="project-observation-title"><h6>{title}</h6><button type="button" className="secondary-action compact-action" disabled={busy||reloading||disabled||editing} onClick={()=>setRevision(x=>x+1)}>Refresh supporting records</button></div>
  {loading&&<p role="status">Loading {title.toLowerCase()}…</p>}
  {result?.kind==='restricted'&&<p className="project-access-note">Restricted: {kind==='document'?'documents.read':'control_instances.read'} is required for this unit.</p>}
  {result?.kind==='loaded'&&<>
   <p className="project-help">Observed <time dateTime={result.page.observed_at}>{new Date(result.page.observed_at).toLocaleString()}</time> · project version {result.page.project_version}, step version {result.page.step_version}. Source state is an observation, not verification.</p>
   {!loading&&!rows.length&&<p>{offset?'No references on this page.':'No supporting records have been linked for this source kind.'}</p>}
   <ul className="project-reference-list">{rows.map(link=><li key={link.id} className="project-reference-card"><div className="project-observation-title"><strong>{trimProjectText(link.snapshot_code)||'Unnamed code'} · {trimProjectText(link.snapshot_name)||'Unnamed source'}</strong><span className="project-label">{link.status==='active'?'Active reference':'Removed reference'}</span></div>
    <p className="project-help">{link.kind==='document'?`Cited revision ${trimProjectText(link.snapshot_revision)||'Unnamed revision'} · document version ${link.linked_document_version}`:`Implementation version ${link.linked_instance_version}`} · target version {link.linked_target_version} · reference version {link.row_version}</p>
    <p className="project-notes">{link.rationale}</p><p className={['active','accepted'].includes(link.current_target_state)?'project-help':'project-reconcile'}>Current source: {link.current_target_state}</p>
    {!['active','accepted'].includes(link.current_target_state)&&<p className="project-help">The source changed or is unavailable. This historical snapshot remains the cited record; it does not establish current applicability.</p>}
    {link.kind==='document'&&<><p className="project-reference-hash">SHA-256: {link.file_sha256}</p><a className="secondary-action compact-action" href={`/api/identity/documents/${link.document_id}/revisions/${link.document_revision_id}/file`}>Download cited revision</a></>}
    <p className="project-help">Linked <time dateTime={link.created_at}>{new Date(link.created_at).toLocaleString()}</time> · command project/step versions {link.source_project_version}/{link.source_step_version}</p>
    {link.status==='removed'&&<><p className="project-notes">{link.removal_reason}</p><p className="project-help">Removed <time dateTime={link.removed_at!}>{new Date(link.removed_at!).toLocaleString()}</time>. The original citation is retained.</p></>}
    {link.status==='active'&&canManage&&result.canManage&&project.status==='open'&&<button type="button" className="secondary-action compact-action" disabled={!writable||editing||loading} onClick={()=>{setDraft({mode:'remove',link,text:'',project,step});setBlocked(false);setRefreshed(null);setError('');setNotice('');}}>Remove reference</button>}
   </li>)}</ul>
   {(offset>0||result.page.has_more)&&<nav className="project-actions" aria-label={`${title} history pages`}><button type="button" className="secondary-action compact-action" disabled={offset===0||loading||busy||editing||disabled} onClick={()=>setOffset(Math.max(0,offset-pageSize))}>Previous references</button><span className="project-help">Rows {offset+1}–{offset+rows.length}</span><button type="button" className="secondary-action compact-action" disabled={!result.page.has_more||offset+pageSize>1000000||loading||busy||editing||disabled} onClick={()=>setOffset(offset+pageSize)}>Next references</button></nav>}
   {!draft&&canManage&&result.canManage&&project.status==='open'&&<button type="button" className="secondary-action compact-action" disabled={!writable||loading||blocked} onClick={startAdd}>Add supporting record</button>}
  </>}
  {project.status==='archived'&&<p className="project-help">This project is archived. Supporting-record history remains available; restore the project before adding or removing a citation.</p>}
  {draft&&<form className="project-form" aria-label={`${title} reference draft`} onSubmit={save}>
   <h6>{draft.mode==='add'?'Cite an existing source':'Remove this reference'}</h6>
   {draft.mode==='add'&&<>
    <p className="project-help">Choose a {kind==='document'?'released, clean document revision':'record already accepted in an active implementation'} from this unit. Source approval and project-step verification remain separate.</p>
    <div className="project-reference-search"><label>Search sources<input value={search} maxLength={320} disabled={!writable||busy||reloading} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();changeSources(0,search);}}}/></label><button type="button" className="secondary-action compact-action" disabled={!writable||busy||reloading||sourceLoading} onClick={()=>changeSources(0,search)}>Search sources</button></div>
    {sourceLoading&&<p role="status">Loading eligible sources…</p>}
    {candidates?.kind==='loaded'&&<><fieldset className="project-reference-picker" disabled={!writable||busy||reloading||sourceLoading}><legend>Eligible sources in this unit</legend>{!sources.length&&<p>No eligible sources on this page. Try another search or page.</p>}{sources.map(source=><label className="project-reference-choice" key={sourceKey(source)}><input type="radio" name={`${kind}-source`} checked={draft.candidate!==null&&sourceKey(draft.candidate)===sourceKey(source)} onChange={()=>setDraft({...draft,candidate:source})}/><span>{trimProjectText(source.code)||'Unnamed code'} · {sourceName(source)}<small>{source.kind==='document'?`Revision ${trimProjectText(source.revision)||'Unnamed revision'} · document/target versions ${source.document_version}/${source.revision_version}`:`Implementation/target versions ${source.instance_version}/${source.evidence_version}`}</small></span></label>)}</fieldset>
     <nav className="project-actions" aria-label={`${title} source pages`}><button type="button" className="secondary-action compact-action" disabled={!writable||sourceOffset===0||sourceLoading||busy||reloading} onClick={()=>changeSources(Math.max(0,sourceOffset-pageSize))}>Previous sources</button><span className="project-help">Source rows {sourceOffset+1}–{sourceOffset+sources.length}{candidates.page.has_more?' · more available':''}</span><button type="button" className="secondary-action compact-action" disabled={!writable||!candidates.page.has_more||sourceOffset+pageSize>1000000||sourceLoading||busy||reloading} onClick={()=>changeSources(sourceOffset+pageSize)}>Next sources</button></nav>
    </>}
    {draft.candidate&&<p className="project-help">Selected snapshot: {sourceName(draft.candidate)}. Selection is retained during reconciliation; search or page changes clear it.</p>}
   </>}
   {draft.mode==='remove'&&<p className="project-help">Removing {trimProjectText(draft.link.snapshot_name)||'Unnamed source'} retains its original snapshot and rationale in history.</p>}
   <label>{draft.mode==='add'?'Supporting rationale':'Removal reason'}<textarea required rows={3} maxLength={1000} value={draft.text} aria-invalid={invalidReason} disabled={busy||reloading||disabled} onChange={e=>setDraft({...draft,text:e.target.value})}/></label><p className="project-help">1–500 Unicode characters after boundary whitespace. Captured project/step versions: {draft.project.row_version}/{draft.step.row_version}.</p>
   {blocked&&<div className="project-reconcile"><p>Your draft is retained. Reload and inspect current records before another attempt. No write is retried automatically.</p>{refreshed&&<><p>Refreshed project version {refreshed.row_version}, step version {refreshed.steps.find(x=>x.id===step.id)?.row_version}.</p>{matching?<p>An active matching reference is already present. Review the history before cancelling this draft.</p>:removedAlready?<p>This reference is already removed. Review its retained history before cancelling this draft.</p>:<button type="button" className="secondary-action compact-action" disabled={busy||reloading||!writable} onClick={adopt}>Use refreshed versions for reference draft</button>}</>}</div>}
   <div className="project-actions"><button type="submit" className="primary-action compact-action" disabled={!writable||busy||reloading||blocked||sourceLoading||draft.mode==='add'&&!draft.candidate}>{busy?'Saving…':draft.mode==='add'?'Save supporting record':'Confirm removal'}</button><button type="button" className="secondary-action compact-action" disabled={busy||reloading} onClick={cancel}>Cancel reference editing</button>{blocked&&<button type="button" className="secondary-action compact-action" disabled={busy||reloading||disabled} onClick={()=>void reload()}>Reload latest, keep reference draft</button>}</div>
  </form>}
  {error&&<p className="project-feedback" role="alert">{error}</p>}{notice&&<p className="project-feedback" role="status">{notice}</p>}
  {!draft&&blocked&&<button type="button" className="secondary-action compact-action" disabled={busy||reloading||disabled} onClick={()=>void reload().then(()=>setBlocked(false))}>Reload current project for references</button>}
 </section>;
}
