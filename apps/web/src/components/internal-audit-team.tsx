"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

type Audit = { id: string; unit_id: string; code: string; state: string; row_version: number; lead_auditor_user_id?:string|null };
type TeamMember = {id:string;audit_id:string;unit_id:string;user_id:string;display_name_snapshot:string;team_role:string;responsibilities:string;status:string;row_version:number;withdrawal_reason:string};
type Person = {id:string;display_name:string};
const api = "/api/identity";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
class AccessError extends Error { constructor(readonly status: number) { super(String(status)); } }
const unavailable = (cause: unknown) => cause instanceof AccessError && [401,403,404].includes(cause.status);
function failure(cause: unknown) {
  if (cause instanceof AccessError) {
    if ([401,403,404].includes(cause.status)) return "The audit or your access is unavailable. Refresh your responsibilities.";
    if (cause.status === 409) return "The audit, person or team assignment changed. Refresh audit team before another submission. The lead auditor cannot be an audited participant.";
    if (cause.status === 422) return "Review the person, team role and responsibilities.";
  }
  return "Team assignment could not be confirmed. Refresh audit team and review the record before submitting again.";
}
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(api+path,{credentials:"include",signal});
  if (response.status!==200) throw new AccessError(response.status);
  return await response.json() as T;
}
function valid(row:TeamMember,audit:Audit){return row&&typeof row==="object"&&typeof row.id==="string"&&uuid.test(row.id)&&row.audit_id===audit.id&&row.unit_id===audit.unit_id&&typeof row.user_id==="string"&&uuid.test(row.user_id)&&typeof row.display_name_snapshot==="string"&&row.display_name_snapshot.length>0&&typeof row.responsibilities==="string"&&["auditor","auditee"].includes(row.team_role)&&["active","withdrawn"].includes(row.status)&&typeof row.withdrawal_reason==="string"&&Number.isInteger(row.row_version)&&row.row_version>0;}
function TeamPersonPicker({disabled,onAccess}:{disabled:boolean;onAccess:(status:number)=>void}) {
 const [value,setValue]=useState(""),[label,setLabel]=useState("Selected person outside this page"),[search,setSearch]=useState(""),[query,setQuery]=useState({search:"",offset:0}),[rows,setRows]=useState<Person[]>([]),[loading,setLoading]=useState(true),[error,setError]=useState(""),[next,setNext]=useState(false);
 const callback=useRef(onAccess);useEffect(()=>{callback.current=onAccess},[onAccess]);
 useEffect(()=>{const controller=new AbortController();const timer=window.setTimeout(()=>{setRows([]);setLoading(true);setError("");const params=new URLSearchParams({search:query.search,offset:String(query.offset),limit:"21"});void read<Person[]>("/organization/members?"+params,controller.signal).then(data=>{if(controller.signal.aborted)return;if(!Array.isArray(data)||data.some(row=>!row||typeof row.id!=="string"||!uuid.test(row.id)||typeof row.display_name!=="string"))throw new Error("Invalid member directory");setRows(data.slice(0,20));setNext(data.length>20)}).catch(cause=>{if(!controller.signal.aborted){setError(failure(cause));if(unavailable(cause))callback.current((cause as AccessError).status)}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});},0);return()=>{window.clearTimeout(timer);controller.abort()};},[query]);
 return <div className="ia-reference-picker ncr-wide"><div className="ia-reference-toolbar"><label>Find team person<input maxLength={160} value={search} disabled={disabled} onChange={event=>setSearch(event.target.value)}/></label><button type="button" className="secondary-action compact-action" disabled={disabled||loading} onClick={()=>setQuery({search:search.trim(),offset:0})}>Search team people</button></div><input type="hidden" name="user_id" value={value}/><label>Team person<select aria-label="Team person" required value={value} disabled={disabled||loading} onChange={event=>{setValue(event.target.value);const row=rows.find(row=>row.id===event.target.value);if(row)setLabel(row.display_name)}}><option value="">Choose an active company member</option>{value&&!rows.some(row=>row.id===value)&&<option value={value}>{label}</option>}{rows.map(row=><option key={row.id} value={row.id}>{row.display_name}</option>)}</select></label>{loading&&<p role="status">Loading team people…</p>}{error&&<p role="alert">{error}</p>}<nav className="ia-reference-pages" aria-label="Team person choices"><button type="button" className="secondary-action compact-action" disabled={disabled||loading||query.offset===0} onClick={()=>setQuery({...query,offset:Math.max(0,query.offset-20)})}>Previous people</button><span>Page {Math.floor(query.offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={disabled||loading||!next||query.offset+20>10000} onClick={()=>setQuery({...query,offset:query.offset+20})}>More people</button></nav></div>;
}

export function InternalAuditTeam({audit,capabilities,disabled,onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged}: {
  audit:Audit;capabilities:string[];disabled:boolean;onBusyChange:(busy:boolean)=>void;onVersionChange:(version:number)=>void;onAuditRefreshed:(audit:unknown)=>void;onAccessChanged:(status:number)=>void;
}) {
  const heading=useId();
  const canRead=capabilities.includes("audits.read"), canManage=canRead&&capabilities.includes("audits.manage")&&["draft","planned"].includes(audit.state);
  const [rows,setRows]=useState<TeamMember[]>([]),[offset,setOffset]=useState(0),[status,setStatus]=useState("active"),[next,setNext]=useState(false),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState(""),[blocked,setBlocked]=useState(false),[refresh,setRefresh]=useState(0);
  const [editor,setEditor]=useState<{row:TeamMember|null}|null>(null),[withdraw,setWithdraw]=useState<TeamMember|null>(null);
  const epoch=useRef(0),operation=useRef(0),pending=useRef(false);
  const callbacks=useRef({onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged});
  useEffect(()=>{callbacks.current={onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged}},[onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged]);
  const source=useRef(audit); useEffect(()=>{source.current=audit},[audit]);
  useEffect(()=>{
    const requests=epoch,mutations=operation,posting=pending,notify=callbacks;
    return()=>{++requests.current;++mutations.current;if(posting.current)notify.current.onBusyChange(false)};
  },[]);
  useEffect(()=>{
    const controller=new AbortController(),token=++epoch.current;
    const current=()=>!controller.signal.aborted&&token===epoch.current;
    const timer=window.setTimeout(()=>{
      setRows([]);setNext(false);if(!canRead){setLoading(false);return}setLoading(true);
      const params=new URLSearchParams({status,limit:"21",offset:String(offset)});
      void read<TeamMember[]>(`/internal-audits/audits/${audit.id}/team-members?${params}`,controller.signal).then(data=>{
        if(!current())return;
        if(!Array.isArray(data)||data.some(row=>!valid(row,source.current)))throw new Error("Mismatched member");
        setRows(data.slice(0,20));setNext(data.length>20);
      }).catch(cause=>{if(current()){setError(failure(cause));if(unavailable(cause))callbacks.current.onAccessChanged((cause as AccessError).status)}}).finally(()=>{if(current())setLoading(false)});
    },0);
    return()=>{window.clearTimeout(timer);controller.abort()};
  },[audit.id,audit.unit_id,canRead,status,offset,refresh]);
  async function reconcile(){
    if(pending.current||disabled)return;
    const token=++operation.current;
    setLoading(true);setError("");
    try{
      const row=await read<Audit>(`/internal-audits/audits/${audit.id}`);
      if(token!==operation.current)return;
      if(row.id!==audit.id||row.unit_id!==audit.unit_id||!Number.isInteger(row.row_version))throw new Error("Mismatched audit");
      callbacks.current.onAuditRefreshed(row);setEditor(null);setWithdraw(null);setBlocked(false);setNotice("");setOffset(0);setRefresh(v=>v+1);
    }catch(cause){if(token===operation.current){setError(failure(cause));setLoading(false);if(unavailable(cause))callbacks.current.onAccessChanged((cause as AccessError).status)}}
  }
  async function mutate(path:string,method:"POST"|"PATCH",body:Record<string,unknown>,expected:TeamMember|null,withdrawal=false){
    if(pending.current||disabled||loading||blocked||!canManage)return;
    const token=++operation.current;
    const parentVersion=audit.row_version;
    pending.current=true;setBusy(true);callbacks.current.onBusyChange(true);setError("");setNotice("");
    let responseReceived=false;
    try{
      const cookie=document.cookie.split("; ").find(item=>item.startsWith("pm_csrf="));const csrf=cookie?decodeURIComponent(cookie.slice(8)):"";
      const response=await fetch(api+path,{method,credentials:"include",headers:{"Content-Type":"application/json","X-CSRF-Token":csrf},body:JSON.stringify({...body,expected_audit_version:parentVersion})});
      responseReceived=true;if(token!==operation.current)return;
      if(!response.ok){if([401,403,404].includes(response.status)){setRows([]);setEditor(null);setWithdraw(null);callbacks.current.onAccessChanged(response.status);return}if(response.status===409)setBlocked(true);throw new AccessError(response.status)}
      setBlocked(true);
      if(response.status!==(expected?200:201))throw new Error("Unconfirmed command");
      const result=await response.json() as {member:TeamMember;audit_version:number};
      if(token!==operation.current)return;
      if(!valid(result.member,audit)||result.audit_version!==parentVersion+1||(expected?result.member.id!==expected.id||result.member.row_version!==expected.row_version+1:result.member.row_version!==1)||result.member.status!==(withdrawal?"withdrawn":"active")||result.member.user_id!==(expected?expected.user_id:body.user_id))throw new Error("Unconfirmed member");
      callbacks.current.onVersionChange(result.audit_version);setBlocked(false);setEditor(null);setWithdraw(null);setNotice(withdrawal?"Team assignment retired. Its history remains available.":"Audit team assignment saved.");setOffset(0);setRefresh(v=>v+1);
    }catch(cause){if(token===operation.current){if(!responseReceived)setBlocked(true);setError(failure(cause))}}
    finally{if(token===operation.current){pending.current=false;setBusy(false);callbacks.current.onBusyChange(false)}}
  }
  if(!canRead)return null;
  return <section className="ncr-read-section" aria-labelledby={heading} aria-busy={busy||loading}><div className="related-capas-heading"><div><h4 id={heading}>Audit team</h4><p>Plan participants and responsibilities. Assignment does not grant access or confirm independence.</p></div><button type="button" aria-label="Refresh audit team" className="icon-button" disabled={busy||disabled} onClick={()=>void reconcile()}><RefreshCw size={16} aria-hidden="true"/></button></div>
    {error&&<p role="alert" className="denied-state">{error}</p>}{notice&&<p role="status">{notice}</p>}{blocked&&<p role="status" className="ia-planning-note">Submission is locked. Refresh audit team and review the latest version before another change.</p>}
    <label>Team history<select aria-label="Team history" value={status} disabled={busy||disabled} onChange={event=>{setStatus(event.target.value);setOffset(0);setEditor(null);setWithdraw(null);setError("")}}><option value="active">Active assignments</option><option value="withdrawn">Former assignments</option></select></label>
    {loading?<div className="related-capa-loading" role="status" aria-label="Loading audit member"><span aria-hidden="true"/></div>:rows.length?<ul className="related-capa-list">{rows.map(row=><li key={row.id}><div><strong>{row.display_name_snapshot}</strong><span className="ia-scope-summary">{row.responsibilities}</span><small>{row.user_id===audit.lead_auditor_user_id&&row.team_role==="auditor"?"Lead auditor":row.team_role==="auditor"?"Auditor":"Audited participant"}</small>{row.status==="withdrawn"&&<small>Withdrawn: {row.withdrawal_reason}</small>}<small>Version {row.row_version}</small>{canManage&&row.status==="active"&&<div className="ncr-form-actions"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setEditor({row});setWithdraw(null)}}>Edit team member {row.display_name_snapshot}</button><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setWithdraw(row);setEditor(null)}}>Remove team member {row.display_name_snapshot}</button></div>}</div></li>)}</ul>:!error&&<p className="qms-history-caption">No {status} member items on this page.</p>}
    <nav className="related-capa-pages" aria-label="Audit team pages"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous team members</button><span>Page {Math.floor(offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||!next||offset+20>1_000_000} onClick={()=>setOffset(offset+20)}>More team members</button></nav>
    {canManage&&!editor&&!withdraw&&<button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked||loading} onClick={()=>setEditor({row:null})}><Plus size={16} aria-hidden="true"/>Add team member</button>}
    {editor&&<form className="ncr-editor" aria-label={editor.row?"Edit audit team member":"Add audit team member"} onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);const person=editor.row?.user_id??String(data.get("user_id")??"");if(!uuid.test(person)){setError("Choose an active company member before saving.");return}void mutate(`/internal-audits/audits/${audit.id}/team-members${editor.row?"/"+editor.row.id:""}`,editor.row?"PATCH":"POST",{team_role:String(data.get("team_role")??"auditor"),responsibilities:String(data.get("responsibilities")??""),...(editor.row?{expected_version:editor.row.row_version}:{user_id:person})},editor.row)}}><fieldset disabled={busy||disabled} className="ncr-editor-content"><div className="ncr-form-grid">{editor.row?<p className="qms-history-caption ncr-wide">Assigned person: {editor.row.display_name_snapshot}. Retire this assignment to choose another person.</p>:<TeamPersonPicker disabled={busy||disabled} onAccess={onAccessChanged}/>}<label>Team role<select aria-label="Team role" name="team_role" defaultValue={editor.row?.team_role??"auditor"}><option value="auditor">Auditor</option><option value="auditee">Audited participant</option></select></label><label className="ncr-wide">Responsibilities<textarea aria-label="Responsibilities" name="responsibilities" maxLength={4000} rows={3} defaultValue={editor.row?.responsibilities??""}/></label></div><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Save team assignment</button><button type="button" className="secondary-action compact-action" onClick={()=>setEditor(null)}>Cancel team editing</button></div></fieldset></form>}
    {withdraw&&<form className="ncr-transition" aria-label="Remove audit team member" onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);void mutate(`/internal-audits/audits/${audit.id}/team-members/${withdraw.id}/withdraw`,"POST",{expected_version:withdraw.row_version,reason:String(data.get("reason")??"").trim()},withdraw,true)}}><h4>Withdraw {withdraw.display_name_snapshot}</h4><p className="qms-history-caption">History is preserved. Audit version {audit.row_version} · Assignment version {withdraw.row_version}.</p><fieldset disabled={busy||disabled}><label>Removal reason<textarea aria-label="Removal reason" name="reason" required maxLength={500} rows={2}/></label><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Confirm team removal</button><button type="button" className="secondary-action compact-action" onClick={()=>setWithdraw(null)}>Keep team member</button></div></fieldset></form>}
  </section>;
}
