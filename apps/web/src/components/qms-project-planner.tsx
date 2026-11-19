"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { FolderKanban, RefreshCw } from "lucide-react";
import { journeys, type GuideJourney } from "../lib/guided-journeys";
import { loadProject, loadProjectIndex, mutateProject, projectTextFits, trimProjectText, ProjectError, ProjectCatalogError, type Project, type ProjectCommand, type ProjectContext, type ProjectDetail, type ProjectIndex, type ProjectMember, type ProjectStep } from "../lib/qms-projects";

type Shared = {context:ProjectContext; project:ProjectDetail|null; canManage:boolean; onChange:(p:ProjectDetail|null)=>void; onAccessLost:(status:number)=>void};
function csrf(){try {const s=document.cookie.split('; ').find(v=>v.startsWith('pm_csrf='));return s?decodeURIComponent(s.slice(8)):'';}catch{return '';}}
function message(cause:unknown){
  if(cause instanceof ProjectCatalogError)return 'This project uses an incompatible guide catalog. Update the application or ask support to review the catalog version before editing. The original project has been retained.';
  if(cause instanceof ProjectError){
    if(cause.uncertain)return 'The save could not be confirmed. It may have reached the server. Reload and inspect the project before retrying.';
    if(cause.status===409)return 'This project changed, or its scope is no longer valid. Your draft has been kept. Reload the current project before reconciling it.';
    if(cause.status===422)return 'The server rejected these values. Check the fields and the required notes.';
    if(cause.status===404)return 'This project is no longer available in your current scope.';
    if([401,403].includes(cause.status))return 'Project access changed. Previous project information was cleared.';
  }
  return 'The project could not be verified. No success has been confirmed; refresh access before continuing.';
}
function MemberOptions({members,current}:{members:ProjectMember[];current?:string|null}){
 return <><option value="">Unassigned</option>{current&&!members.some(m=>m.id===current)&&<option value={current}>Previously assigned member · {current.slice(0,8)}</option>}{members.map(m=><option value={m.id} key={m.id}>{m.display_name} · {m.role}</option>)}</>;
}
function useCommand(context:ProjectContext,onChange:Shared['onChange'],onAccessLost:Shared['onAccessLost']){
 const [busy,setBusy]=useState(false),[error,setError]=useState(''),[conflict,setConflict]=useState(false);
 const request=useRef<AbortController|null>(null),sequence=useRef(0);
 useEffect(()=>()=>{sequence.current++;request.current?.abort();},[]);
 async function run(command:ProjectCommand){
  if(request.current&&!request.current.signal.aborted)return false;
  const controller=new AbortController();request.current=controller;const token=++sequence.current;setBusy(true);setError('');setConflict(false);
  try{const result=await mutateProject(context,command,csrf(),controller.signal);if(controller.signal.aborted||token!==sequence.current)return false;onChange(result);return true;}
  catch(cause){if(controller.signal.aborted||token!==sequence.current)return false;
   if(cause instanceof ProjectError&&(cause.contextLost||[401,403,404].includes(cause.status)))onAccessLost(cause.status===401?401:403);
   else{const rejectedCreate=command.kind==='create'&&cause instanceof ProjectError&&cause.status===409&&!cause.uncertain;setError(rejectedCreate?'Creation was rejected because the code, assignment or scope conflicts. Your draft is kept; correct the values before trying again.':message(cause));setConflict(!rejectedCreate&&cause instanceof ProjectError&&(cause.status===409||cause.uncertain));}return false;
  }finally{if(!controller.signal.aborted&&token===sequence.current){setBusy(false);request.current=null;}}
 }
 return{busy,error,conflict,run,clear:()=>{setError('');setConflict(false);}};
}

type MetadataDraft={code:string;name:string;scope_summary:string;coordinator_user_id:string;target_date:string;journey_key:GuideJourney['id'];expectedVersion:number};
export function QMSProjectPlanner({context,project,onChange,onAccessLost,onManageChange,onMembersChange,onEditingChange,locked,journeyId}:Omit<Shared,'canManage'>&{onManageChange:(allowed:boolean)=>void;onMembersChange:(members:ProjectMember[])=>void;onEditingChange:(editing:boolean)=>void;locked:boolean;journeyId:GuideJourney['id']}){
 const [index,setIndex]=useState<ProjectIndex|null>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[revision,setRevision]=useState(0),[notice,setNotice]=useState('');
 const [draft,setDraft]=useState<MetadataDraft|null>(null),[editingId,setEditingId]=useState<string|null>(null),[statusDraft,setStatusDraft]=useState<{targetStatus:Project['status'];reason:string;version:number}|null>(null);
 const [selectedLoading,setSelectedLoading]=useState(false),[reloadConfirmed,setReloadConfirmed]=useState(false);
 const detailRequest=useRef<AbortController|null>(null),detailSequence=useRef(0);
 const command=useCommand(context,p=>{onChange(p);if(p)setIndex(old=>old?.kind==='loaded'?{...old,projects:[p,...old.projects.filter(x=>x.id!==p.id)]}:old);},onAccessLost);
 useEffect(()=>()=>{detailSequence.current++;detailRequest.current?.abort();},[]);
 useEffect(()=>{
  const controller=new AbortController();
  void loadProjectIndex(context,controller.signal).then(v=>{if(controller.signal.aborted)return;setIndex(v);onManageChange(v.kind==='loaded'&&v.canManage);onMembersChange(v.kind==='loaded'?v.members:[]);setLoading(false);}).catch(cause=>{if(controller.signal.aborted)return;setIndex(null);onManageChange(false);onMembersChange([]);setLoading(false);setError(message(cause));onChange(null);if(cause instanceof ProjectError&&(cause.contextLost||[401,403,404].includes(cause.status)))onAccessLost(cause.status===401?401:403);});
  return()=>controller.abort();
 },[context,revision,onManageChange,onMembersChange,onChange,onAccessLost]);
 useEffect(()=>{onEditingChange(Boolean(draft||statusDraft));return()=>onEditingChange(false);},[draft,statusDraft,onEditingChange]);
 const canManage=index?.kind==='loaded'&&index.canManage;
 async function open(id:string,keepDraft=false){
  detailRequest.current?.abort();const controller=new AbortController();detailRequest.current=controller;const token=++detailSequence.current;
  if(!keepDraft){setDraft(null);setStatusDraft(null);command.clear();onChange(null);}setSelectedLoading(true);setError('');setNotice('');setReloadConfirmed(false);
  try{const p=await loadProject(context,id,controller.signal);if(controller.signal.aborted||token!==detailSequence.current)return;onChange(p);setReloadConfirmed(keepDraft);}
  catch(cause){if(controller.signal.aborted||token!==detailSequence.current)return;onChange(null);setError(message(cause));if(cause instanceof ProjectError&&(cause.contextLost||[401,403,404].includes(cause.status)))onAccessLost(cause.status===401?401:403);}
  finally{if(!controller.signal.aborted&&token===detailSequence.current)setSelectedLoading(false);}
 }
 function edit(p:Project|null){setEditingId(p?.id??null);setDraft({code:p?.code??'',name:p?.name??'',scope_summary:p?.scope_summary??'',coordinator_user_id:p?.coordinator_user_id??'',target_date:p?.target_date??'',journey_key:p?.journey_key??journeyId,expectedVersion:p?.row_version??1});setStatusDraft(null);setNotice('');command.clear();setReloadConfirmed(false);}
 async function save(event:FormEvent){event.preventDefault();if(!draft)return;
  const input={code:trimProjectText(draft.code),name:trimProjectText(draft.name),scope_summary:draft.scope_summary,coordinator_user_id:draft.coordinator_user_id||null,target_date:draft.target_date||null,journey_key:draft.journey_key};
  if(!input.code||!input.name){setNotice('Enter a code and name containing text.');return;}
  if(!projectTextFits(input.code,40)||!projectTextFits(input.name,160)||!projectTextFits(input.scope_summary,4000)){setNotice('Use up to 40 characters for code, 160 for name and 4000 for scope. Your draft was kept.');return;}
  const cmd:ProjectCommand=editingId?{kind:'update',id:editingId,expectedVersion:draft.expectedVersion,changes:{name:input.name,scope_summary:input.scope_summary,coordinator_user_id:input.coordinator_user_id,target_date:input.target_date}}:{kind:'create',input};
  if(await command.run(cmd)){setDraft(null);setNotice(editingId?'Project updated.':'Project saved. Its step plan is now stored for this unit.');}
 }
 const members=index?.kind==='loaded'?index.members:[];
 return <section className="qms-project-planner" aria-labelledby="project-planning-heading" aria-busy={loading||selectedLoading||command.busy}>
  <header className="project-panel-heading"><div><p className="eyebrow">A PLAN YOU CAN RESUME</p><h3 id="project-planning-heading"><FolderKanban aria-hidden="true" size={20}/>Project planning</h3></div><button className="secondary-action compact-action" disabled={locked||Boolean(draft)||Boolean(statusDraft)||loading||selectedLoading||command.busy} onClick={()=>{setLoading(true);setIndex(null);setError('');setNotice('');onManageChange(false);onChange(null);setRevision(x=>x+1);}}><RefreshCw aria-hidden="true" size={16}/>Refresh project access</button></header>
  <p className="project-help">Save the scope, people and step follow-up for this journey. Planning notes and reported work are separate from accepted evidence and ISO conformity.</p>
  {loading&&<div className="project-skeleton" role="status">Loading project access…<span/><span/></div>}
  {error&&<p role="alert">{error}</p>}
  {index?.kind==='restricted'&&<p className="project-access-note">Project reading requires <strong>projects.read</strong> for this unit. The company owner can grant that responsibility in Permissions. The six guides remain available below.</p>}
  {index?.kind==='loaded'&&<>
   <div className="project-toolbar"><label htmlFor="project-selector">Saved project<select id="project-selector" disabled={locked||selectedLoading||command.busy||Boolean(draft)||Boolean(statusDraft)} value={project?.id??''} onChange={e=>{if(e.target.value)void open(e.target.value);else{detailRequest.current?.abort();detailSequence.current++;onChange(null);setNotice('');}}}><option value="">Browse guides without a project</option>{index.projects.map(p=><option key={p.id} value={p.id}>{p.code} · {p.name}{p.status==='archived'?' · Archived':''}</option>)}</select></label>{canManage&&<button type="button" className="primary-action compact-action" disabled={locked||command.busy||selectedLoading||Boolean(draft)||Boolean(statusDraft)} onClick={()=>edit(null)}>New project</button>}</div>
   {index.limited&&<p className="project-help">First 50 projects only. This list may be partial.</p>}
   {!index.projects.length&&<p>No saved projects were found in this unit. {canManage?'Create one to resume the guide with your team.':'A project manager can create one.'}</p>}
   {project&&<div className="project-summary"><div><span className="project-label">{project.code} · {project.status==='archived'?'Archived plan':'Open plan'}</span><h4>{project.name}</h4><p>{project.scope_summary||'No scope description recorded.'}</p></div><dl><div><dt>Coordinator</dt><dd>{members.find(m=>m.id===project.coordinator_user_id)?.display_name??(project.coordinator_user_id?'Assigned company member':'Unassigned')}</dd></div><div><dt>Target date</dt><dd>{project.target_date??'Not set'}</dd></div><div><dt>Catalog / version</dt><dd>{project.catalog_version} · {project.row_version}</dd></div></dl><p className="project-help">{project.steps.filter(s=>s.status==='in_progress').length} in progress · {project.steps.filter(s=>s.status==='blocked').length} blocked · {project.steps.filter(s=>s.status==='reported').length} reported, unverified · {project.steps.filter(s=>s.status==='feature_pending').length} product gaps</p>
    <div className="project-actions"><button className="secondary-action compact-action" disabled={locked||command.busy||selectedLoading} onClick={()=>void open(project.id,true)}>Reload current project</button>{canManage&&<><button className="secondary-action compact-action" disabled={locked||project.status==='archived'||command.busy||Boolean(draft)||Boolean(statusDraft)} onClick={()=>edit(project)}>Edit project</button><button className="secondary-action compact-action" disabled={locked||command.busy||Boolean(draft)||Boolean(statusDraft)} onClick={()=>{setStatusDraft({targetStatus:project.status==='open'?'archived':'open',reason:'',version:project.row_version});setNotice('');command.clear();}}>{project.status==='open'?'Archive project':'Restore project'}</button></>}</div>
   </div>}
   {draft&&canManage&&<form className="project-form" onSubmit={save} aria-label={editingId?'Edit project':'New project'}><h4>{editingId?'Edit project':'Create a saved project'}</h4><div className="project-fields">
    <label>Code<input required maxLength={80} value={draft.code} aria-invalid={!projectTextFits(trimProjectText(draft.code),40)} disabled={Boolean(editingId)||command.busy} onChange={e=>setDraft({...draft,code:e.target.value})}/></label>
    <label>Name<input required maxLength={320} value={draft.name} aria-invalid={!projectTextFits(trimProjectText(draft.name),160)} disabled={command.busy} onChange={e=>setDraft({...draft,name:e.target.value})}/></label>
    <label>Journey<select value={draft.journey_key} disabled={Boolean(editingId)||command.busy} onChange={e=>setDraft({...draft,journey_key:e.target.value as GuideJourney['id']})}>{journeys.map(j=><option key={j.id} value={j.id}>{j.title}</option>)}</select></label>
    <label>Coordinator<select value={draft.coordinator_user_id} disabled={command.busy} onChange={e=>setDraft({...draft,coordinator_user_id:e.target.value})}><MemberOptions members={members} current={draft.coordinator_user_id}/></select></label>
    <label>Target date<input type="date" value={draft.target_date} disabled={command.busy} onChange={e=>setDraft({...draft,target_date:e.target.value})}/></label>
   </div><label>Scope and boundaries<textarea maxLength={8000} rows={3} value={draft.scope_summary} aria-invalid={!projectTextFits(draft.scope_summary,4000)} disabled={command.busy} onChange={e=>setDraft({...draft,scope_summary:e.target.value})}/></label><p className="project-help">Assignment records accountability. It grants no project, unit or QMS permissions. The unit and journey are fixed after creation.{index.membersLimited?' Showing the first 100 active company members.':''}</p>
   {command.conflict&&editingId&&project&&reloadConfirmed&&<div className="project-reconcile"><p>Current server version {project.row_version}: {project.name}. Scope: {project.scope_summary||'No description'}. Your draft above is unchanged.</p><button className="secondary-action compact-action" type="button" onClick={()=>{setDraft({...draft,expectedVersion:project.row_version});command.clear();setReloadConfirmed(false);}}>Use current version for this draft</button></div>}
   <div className="project-actions"><button className="primary-action compact-action" disabled={command.busy||selectedLoading||command.conflict||Boolean(editingId&&project?.status==='archived')} type="submit">{command.busy?'Saving…':editingId?'Save project changes':'Create project'}</button><button className="secondary-action compact-action" disabled={command.busy} type="button" onClick={()=>{setDraft(null);command.clear();}}>Cancel editing</button>{command.conflict&&editingId&&<button className="secondary-action compact-action" type="button" disabled={selectedLoading} onClick={()=>void open(editingId,true)}>Reload latest, keep draft</button>}</div>
   </form>}
   {statusDraft&&project&&canManage&&<form className="project-form" aria-label="Project status decision" onSubmit={async e=>{e.preventDefault();const reason=trimProjectText(statusDraft.reason);if(!reason||!projectTextFits(reason,500)){setNotice('Enter a reason of up to 500 characters. Your draft was kept.');return;}if(await command.run({kind:'status',id:project.id,expectedVersion:statusDraft.version,targetStatus:statusDraft.targetStatus,reason})){setStatusDraft(null);setNotice('Project status saved. History was retained.');}}}><label>Reason for {statusDraft.targetStatus==='archived'?'archiving':'restoring'}<textarea required maxLength={1000} value={statusDraft.reason} aria-invalid={!projectTextFits(trimProjectText(statusDraft.reason),500)} onChange={e=>setStatusDraft({...statusDraft,reason:e.target.value})}/></label><div className="project-actions"><button className="primary-action compact-action" disabled={command.busy||command.conflict}>Save status decision</button><button className="secondary-action compact-action" type="button" disabled={command.busy} onClick={()=>{setStatusDraft(null);command.clear();}}>Cancel decision</button></div>{command.conflict&&<p>Your reason was kept. Cancel this decision, reload the project and review its current status before starting another decision.</p>}</form>}
   {command.error&&<p className="project-feedback" role="alert">{command.error}</p>}
   {notice&&<p className="project-feedback" role="status">{notice}</p>}
  </>}
 </section>;
}

export function ProjectStepPlan({context,project,canManage,onChange,onAccessLost,stepKey,members,onEditingChange}:{context:ProjectContext;project:ProjectDetail;canManage:boolean;onChange:Shared['onChange'];onAccessLost:Shared['onAccessLost'];stepKey:string;members?:ProjectMember[];onEditingChange:(editing:boolean)=>void}){
 const step=project.steps.find(s=>s.step_key===stepKey);
 return step?<StepEditor key={`${project.id}:${step.id}`} {...{context,project,canManage,onChange,onAccessLost,step,members:members??[],onEditingChange}}/>:null;
}
function StepEditor({context,project,canManage,onChange,onAccessLost,step,members,onEditingChange}:Omit<Shared,'project'>&{project:ProjectDetail;step:ProjectStep;members:ProjectMember[];onEditingChange:(editing:boolean)=>void}){
 const [draft,setDraft]=useState<{status:ProjectStep['status'];notes:string;assignee_user_id:string;target_date:string;version:number;projectVersion:number}|null>(null),[notice,setNotice]=useState(''),[reloading,setReloading]=useState(false),[reconciled,setReconciled]=useState(false);
 const request=useRef<AbortController|null>(null);useEffect(()=>()=>request.current?.abort(),[]);
 const command=useCommand(context,onChange,onAccessLost);
 useEffect(()=>{onEditingChange(Boolean(draft));return()=>onEditingChange(false);},[draft,onEditingChange]);
 const labels:Record<ProjectStep['status'],string>={not_started:'Not started',in_progress:'In progress',blocked:'Blocked',reported:'Work reported · pending verification',feature_pending:'Product feature pending'};
 async function reload(){request.current?.abort();const controller=new AbortController();request.current=controller;setReloading(true);try{const p=await loadProject(context,project.id,controller.signal);if(controller.signal.aborted)return;onChange(p);setReconciled(true);}catch(cause){if(controller.signal.aborted)return;if(cause instanceof ProjectError&&(cause.contextLost||[401,403,404].includes(cause.status)))onAccessLost(cause.status===401?401:403);else setNotice(message(cause));}finally{if(!controller.signal.aborted)setReloading(false);}}
 return <section className="project-step-plan" aria-labelledby="project-step-plan-heading"><div className="project-observation-title"><h5 id="project-step-plan-heading">Saved project follow-up</h5><span className="project-label">{labels[step.status]}</span></div><p className="project-help">This is the project’s planning record. Reported work remains unverified; operational records below cover the whole unit.</p><dl className="project-step-values"><div><dt>Assignee</dt><dd>{members.find(m=>m.id===step.assignee_user_id)?.display_name??(step.assignee_user_id?'Assigned company member':'Unassigned')}</dd></div><div><dt>Target date</dt><dd>{step.target_date??'Not set'}</dd></div></dl><p className="project-notes">{step.notes||'No follow-up notes recorded.'}</p>
  {!draft&&canManage&&project.status==='open'&&<button className="secondary-action compact-action" type="button" onClick={()=>{setDraft({status:step.status,notes:step.notes,assignee_user_id:step.assignee_user_id??'',target_date:step.target_date??'',version:step.row_version,projectVersion:project.row_version});setNotice('');command.clear();setReconciled(false);}}>Update step follow-up</button>}
  {project.status==='archived'&&<p className="project-help">This plan is archived. Restore it before changing follow-up.</p>}
  {draft&&canManage&&<form className="project-form" aria-label="Step follow-up" onSubmit={async(e)=>{e.preventDefault();if(!projectTextFits(draft.notes,2000)||(['blocked','reported'].includes(draft.status)&&!trimProjectText(draft.notes))){setNotice('Enter follow-up notes of up to 2000 characters; blocked or reported work requires text. Your draft was kept.');return;}if(await command.run({kind:'step',id:project.id,stepId:step.id,expectedVersion:draft.projectVersion,expectedStepVersion:draft.version,changes:{status:draft.status,notes:draft.notes,assignee_user_id:draft.assignee_user_id||null,target_date:draft.target_date||null}})){setDraft(null);setNotice('Step follow-up saved. This is not an evidence acceptance.');}}}>
   <label>Work status<select value={draft.status} disabled={command.busy||step.status==='feature_pending'} onChange={e=>setDraft({...draft,status:e.target.value as ProjectStep['status']})}>{(step.status==='feature_pending'?['feature_pending']:['not_started','in_progress','blocked','reported']).map(s=><option key={s} value={s}>{labels[s as ProjectStep['status']]}</option>)}</select></label>
   <label>Follow-up notes<textarea maxLength={4000} aria-invalid={!projectTextFits(draft.notes,2000)} rows={4} required={['blocked','reported'].includes(draft.status)} disabled={command.busy} value={draft.notes} onChange={e=>setDraft({...draft,notes:e.target.value})}/></label>
   <div className="project-fields"><label>Assignee<select disabled={command.busy} value={draft.assignee_user_id} onChange={e=>setDraft({...draft,assignee_user_id:e.target.value})}><MemberOptions members={members} current={draft.assignee_user_id}/></select></label><label>Step target date<input type="date" disabled={command.busy} value={draft.target_date} onChange={e=>setDraft({...draft,target_date:e.target.value})}/></label></div><p className="project-help">Assignment does not grant permissions. Feature-pending steps retain that status.</p>
   {command.conflict&&reconciled&&<div className="project-reconcile"><p>Current server status: {labels[step.status]}. Notes: {step.notes||'None'}. Your draft is kept above.</p><button className="secondary-action compact-action" type="button" onClick={()=>{setDraft({...draft,version:step.row_version,projectVersion:project.row_version});command.clear();setReconciled(false);}}>Use current versions for this draft</button></div>}
   <div className="project-actions"><button className="primary-action compact-action" disabled={project.status==='archived'||command.busy||reloading||command.conflict}>Save step follow-up</button><button className="secondary-action compact-action" disabled={command.busy} type="button" onClick={()=>{setDraft(null);command.clear();}}>Cancel step editing</button>{command.conflict&&<button className="secondary-action compact-action" type="button" disabled={reloading} onClick={()=>void reload()}>Reload step, keep draft</button>}</div>
  </form>}
  {command.error&&<p role="alert">{command.error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>;
}
