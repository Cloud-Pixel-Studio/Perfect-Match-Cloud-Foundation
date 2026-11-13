"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

type Audit = {id:string;unit_id:string;code:string;state:string;row_version:number;planned_start:string;planned_end:string};
type AgendaItem={id:string;audit_id:string;unit_id:string;sequence:number;title:string;objective:string;method:string;location:string;starts_at:string;ends_at:string;scope_id:string|null;auditor_team_member_id:string;auditee_team_member_id:string|null;auditor_name:string;auditee_name:string|null;status:string;row_version:number;withdrawal_reason:string};
type Ref={id:string;audit_id:string;unit_id:string;status:string;title?:string;sequence?:number;display_name_snapshot?:string;team_role?:string};
const methods=["interview","observation","document_review","sampling","meeting","other"];
const toInput=(value:string)=>new Date(value).toISOString().slice(0,16);
const inputUTC=(value:string)=>{const time=Date.parse(value+"Z");return Number.isFinite(time)?new Date(time).toISOString():null};
const timeLabel=(value:string)=>new Date(value).toLocaleString("en-US",{timeZone:"UTC",year:"numeric",month:"short",day:"numeric",hour:"2-digit",minute:"2-digit",hourCycle:"h23"})+" UTC";
const api = "/api/identity";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
class AccessError extends Error { constructor(readonly status: number) { super(String(status)); } }
const unavailable = (cause: unknown) => cause instanceof AccessError && [401,403,404].includes(cause.status);
function failure(cause: unknown) {
  if (cause instanceof AccessError) {
    if ([401,403,404].includes(cause.status)) return "The audit or your access is unavailable. Refresh your responsibilities.";
    if (cause.status === 409) return "The audit, order, timing or linked records changed. Refresh agenda before another submission. Check participant overlaps and planned dates.";
    if (cause.status === 422) return "Review the activity, UTC minute times and assigned auditor.";
  }
  return "Agenda activity could not be confirmed. Refresh agenda and review the record before submitting again.";
}
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(api+path,{credentials:"include",signal});
  if (response.status!==200) throw new AccessError(response.status);
  return await response.json() as T;
}
function valid(row:AgendaItem,audit:Audit){return row&&typeof row==="object"&&typeof row.id==="string"&&uuid.test(row.id)&&row.audit_id===audit.id&&row.unit_id===audit.unit_id&&typeof row.title==="string"&&typeof row.objective==="string"&&typeof row.location==="string"&&methods.includes(row.method)&&typeof row.starts_at==="string"&&typeof row.ends_at==="string"&&Number.isFinite(Date.parse(row.starts_at))&&Date.parse(row.starts_at)<Date.parse(row.ends_at)&&typeof row.auditor_team_member_id==="string"&&uuid.test(row.auditor_team_member_id)&&typeof row.auditor_name==="string"&&row.auditor_name.length>0&&(row.scope_id===null||typeof row.scope_id==="string"&&uuid.test(row.scope_id))&&(row.auditee_team_member_id===null||typeof row.auditee_team_member_id==="string"&&uuid.test(row.auditee_team_member_id))&&typeof row.withdrawal_reason==="string"&&Date.parse(row.starts_at)%60000===0&&Date.parse(row.ends_at)%60000===0&&(row.status==="withdrawn"||(Date.parse(row.starts_at)>=Date.parse(audit.planned_start+"T00:00Z")&&Date.parse(row.ends_at)<=Date.parse(audit.planned_end+"T00:00Z")+86400000))&&Number.isInteger(row.sequence)&&row.sequence>0&&row.sequence<=10000&&Number.isInteger(row.row_version)&&row.row_version>0&&["active","withdrawn"].includes(row.status);}
function AgendaReference({audit,kind,initial,initialLabel,disabled,onAccess}:{audit:Audit;kind:"scope"|"auditor"|"auditee";initial:string|null;initialLabel?:string;disabled:boolean;onAccess:(status:number)=>void}){
 const [value,setValue]=useState(initial??""),[label,setLabel]=useState(initialLabel??"Selected reference outside this page"),[offset,setOffset]=useState(0),[rows,setRows]=useState<Ref[]>([]),[next,setNext]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState("");const callback=useRef(onAccess);useEffect(()=>{callback.current=onAccess},[onAccess]);
 useEffect(()=>{const controller=new AbortController();const timer=window.setTimeout(()=>{setRows([]);setLoading(true);setError("");const params=new URLSearchParams({status:"active",limit:"21",offset:String(offset)});if(kind!=="scope")params.set("team_role",kind);void read<Ref[]>(`/internal-audits/audits/${audit.id}/${kind==="scope"?"scopes":"team-members"}?${params}`,controller.signal).then(data=>{if(controller.signal.aborted)return;if(!Array.isArray(data)||data.some(row=>!row||typeof row.id!=="string"||!uuid.test(row.id)||row.audit_id!==audit.id||row.unit_id!==audit.unit_id||row.status!=="active"||(kind==="scope"?typeof row.title!=="string"||!Number.isInteger(row.sequence):typeof row.display_name_snapshot!=="string"||row.team_role!==kind)))throw new Error("Mismatched agenda reference");setRows(data.slice(0,20));setNext(data.length>20)}).catch(cause=>{if(!controller.signal.aborted){setError(failure(cause));if(unavailable(cause))callback.current((cause as AccessError).status)}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});},0);return()=>{window.clearTimeout(timer);controller.abort()};},[audit.id,audit.unit_id,kind,offset]);
 const title=kind==="scope"?"Agenda scope (optional)":kind==="auditor"?"Assigned auditor":"Audited participant (optional)";const name=kind==="scope"?"scope_id":kind==="auditor"?"auditor_team_member_id":"auditee_team_member_id";const labelFor=(row:Ref)=>kind==="scope"?row.sequence+" · "+row.title:String(row.display_name_snapshot);
 return <div className="ia-reference-picker ncr-wide"><input type="hidden" name={name} value={value}/><label>{title}<select aria-label={title} required={kind==="auditor"} value={value} disabled={disabled||loading} onChange={event=>{setValue(event.target.value);const row=rows.find(row=>row.id===event.target.value);if(row)setLabel(labelFor(row))}}><option value="">{kind==="scope"?"Whole audit":kind==="auditor"?"Choose a planned auditor":"No audited participant"}</option>{value&&!rows.some(row=>row.id===value)&&<option value={value}>{label}</option>}{rows.map(row=><option key={row.id} value={row.id}>{labelFor(row)}</option>)}</select></label>{loading&&<p role="status">Loading {kind} choices…</p>}{!loading&&!rows.length&&<p className="qms-history-caption">No {kind} choices on this page. Plan participants in Audit team before assigning them here.</p>}{error&&<p role="alert">{error}</p>}<nav className="ia-reference-pages" aria-label={`Agenda ${kind} choices`}><button type="button" className="secondary-action compact-action" disabled={disabled||loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous {kind} choices</button><span>Page {Math.floor(offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={disabled||loading||!next||offset+20>1_000_000} onClick={()=>setOffset(offset+20)}>More {kind} choices</button></nav></div>;
}

export function InternalAuditAgenda({audit,capabilities,disabled,onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged}: {
  audit:Audit;capabilities:string[];disabled:boolean;onBusyChange:(busy:boolean)=>void;onVersionChange:(version:number)=>void;onAuditRefreshed:(audit:unknown)=>void;onAccessChanged:(status:number)=>void;
}) {
  const heading=useId();
  const canRead=capabilities.includes("audits.read"), canManage=canRead&&capabilities.includes("audits.manage")&&["draft","planned"].includes(audit.state);
  const [rows,setRows]=useState<AgendaItem[]>([]),[offset,setOffset]=useState(0),[status,setStatus]=useState("active"),[next,setNext]=useState(false),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState(""),[blocked,setBlocked]=useState(false),[refresh,setRefresh]=useState(0);
  const [editor,setEditor]=useState<{row:AgendaItem|null}|null>(null),[withdraw,setWithdraw]=useState<AgendaItem|null>(null);
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
      void read<AgendaItem[]>(`/internal-audits/audits/${audit.id}/agenda?${params}`,controller.signal).then(data=>{
        if(!current())return;
        if(!Array.isArray(data)||data.some(row=>!valid(row,source.current)))throw new Error("Mismatched activity");
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
  async function mutate(path:string,method:"POST"|"PATCH",body:Record<string,unknown>,expected:AgendaItem|null,withdrawal=false){
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
      const result=await response.json() as {item:AgendaItem;audit_version:number};
      if(token!==operation.current)return;
      if(!valid(result.item,audit)||result.audit_version!==parentVersion+1||(expected?result.item.id!==expected.id||result.item.row_version!==expected.row_version+1:result.item.row_version!==1)||result.item.status!==(withdrawal?"withdrawn":"active"))throw new Error("Unconfirmed activity");
      if(!withdrawal&&(result.item.auditor_team_member_id!==body.auditor_team_member_id||result.item.auditee_team_member_id!==body.auditee_team_member_id||result.item.scope_id!==body.scope_id||result.item.sequence!==body.sequence||result.item.title!==body.title||result.item.method!==body.method||Date.parse(result.item.starts_at)!==Date.parse(String(body.starts_at))||Date.parse(result.item.ends_at)!==Date.parse(String(body.ends_at))))throw new Error("Unconfirmed agenda values");
      callbacks.current.onVersionChange(result.audit_version);setBlocked(false);setEditor(null);setWithdraw(null);setNotice(withdrawal?"Agenda activity withdrawn. Its history remains available.":"Audit activity saved.");setOffset(0);setRefresh(v=>v+1);
    }catch(cause){if(token===operation.current){if(!responseReceived)setBlocked(true);setError(failure(cause))}}
    finally{if(token===operation.current){pending.current=false;setBusy(false);callbacks.current.onBusyChange(false)}}
  }
  if(!canRead)return null;
  return <section className="ncr-read-section" aria-labelledby={heading} aria-busy={busy||loading}><div className="related-capas-heading"><div><h4 id={heading}>Audit agenda</h4><p>Plan activities within the audit dates. All times are UTC, to the minute. Planning does not authorize execution.</p></div><button type="button" aria-label="Refresh audit agenda" className="icon-button" disabled={busy||disabled} onClick={()=>void reconcile()}><RefreshCw size={16} aria-hidden="true"/></button></div>
    {error&&<p role="alert" className="denied-state">{error}</p>}{notice&&<p role="status">{notice}</p>}{blocked&&<p role="status" className="ia-planning-note">Submission is locked. Refresh audit agenda and review the latest version before another change.</p>}
    <label>Agenda history<select aria-label="Agenda history" value={status} disabled={busy||disabled} onChange={event=>{setStatus(event.target.value);setOffset(0);setEditor(null);setWithdraw(null);setError("")}}><option value="active">Active agenda</option><option value="withdrawn">Withdrawn activities</option></select></label>
    {loading?<div className="related-capa-loading" role="status" aria-label="Loading audit activity"><span aria-hidden="true"/></div>:rows.length?<ul className="related-capa-list">{rows.map(row=><li key={row.id}><div><strong>{row.sequence} · {row.title}</strong><span className="ia-scope-summary">{row.objective}</span><small>{timeLabel(row.starts_at)} → {timeLabel(row.ends_at)}</small><small>Auditor: {row.auditor_name}{row.auditee_name?" · Audited participant: "+row.auditee_name:""}</small><small>{row.method.replaceAll("_"," ")}{row.location?" · "+row.location:""}</small><small>{row.scope_id?"Linked audit scope recorded":"Whole audit"}</small>{row.status==="withdrawn"&&<small>Withdrawn: {row.withdrawal_reason}</small>}<small>Version {row.row_version}</small>{canManage&&row.status==="active"&&<div className="ncr-form-actions"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setEditor({row});setWithdraw(null)}}>Edit activity {row.sequence}</button><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setWithdraw(row);setEditor(null)}}>Withdraw activity {row.sequence}</button></div>}</div></li>)}</ul>:!error&&<p className="qms-history-caption">No {status} activity items on this page.</p>}
    <nav className="related-capa-pages" aria-label="Audit agenda pages"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous activities</button><span>Page {Math.floor(offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||!next||offset+20>1_000_000} onClick={()=>setOffset(offset+20)}>More activities</button></nav>
    {canManage&&!editor&&!withdraw&&<button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked||loading} onClick={()=>setEditor({row:null})}><Plus size={16} aria-hidden="true"/>Add agenda activity</button>}
    {editor&&<form className="ncr-editor" aria-label={editor.row?"Edit agenda activity":"Add agenda activity"} onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);const title=String(data.get("title")??"").trim(),starts=inputUTC(String(data.get("starts_at")??"")),ends=inputUTC(String(data.get("ends_at")??"")),auditor=String(data.get("auditor_team_member_id")??"");if(!title||!starts||!ends||!uuid.test(auditor)){setError("Choose a planned auditor and complete the UTC times.");return}void mutate(`/internal-audits/audits/${audit.id}/agenda${editor.row?"/"+editor.row.id:""}`,editor.row?"PATCH":"POST",{sequence:Number(data.get("sequence")),title,objective:String(data.get("objective")??""),location:String(data.get("location")??""),method:String(data.get("method")??"sampling"),starts_at:starts,ends_at:ends,scope_id:data.get("scope_id")||null,auditor_team_member_id:auditor,auditee_team_member_id:data.get("auditee_team_member_id")||null,...(editor.row?{expected_version:editor.row.row_version}:{})},editor.row)}}><fieldset disabled={busy||disabled} className="ncr-editor-content"><div className="ncr-form-grid"><label>Agenda order<input type="number" name="sequence" required min={1} max={10000} defaultValue={editor.row?.sequence??10}/></label><label>Activity title<input name="title" required maxLength={160} defaultValue={editor.row?.title??""}/></label><label>Starts (UTC)<input type="datetime-local" name="starts_at" required step={60} min={audit.planned_start+"T00:00"} max={audit.planned_end+"T23:59"} defaultValue={editor.row?toInput(editor.row.starts_at):audit.planned_start+"T09:00"}/></label><label>Ends (UTC)<input type="datetime-local" name="ends_at" required step={60} min={audit.planned_start+"T00:00"} max={toInput(new Date(Date.parse(audit.planned_end+"T00:00Z")+86400000).toISOString())} defaultValue={editor.row?toInput(editor.row.ends_at):audit.planned_start+"T10:00"}/></label><label>Method<select aria-label="Method" name="method" defaultValue={editor.row?.method??"sampling"}>{methods.map(method=><option key={method} value={method}>{method.replaceAll("_"," ")}</option>)}</select></label><label>Location<input name="location" maxLength={240} defaultValue={editor.row?.location??""}/></label><label className="ncr-wide">Activity objective<textarea aria-label="Activity objective" name="objective" maxLength={4000} rows={3} defaultValue={editor.row?.objective??""}/></label>{(["auditor","auditee","scope"] as const).map(kind=><AgendaReference key={kind+"-"+(editor.row?.id??"new")} audit={audit} kind={kind} initial={editor.row?(kind==="scope"?editor.row.scope_id:kind==="auditor"?editor.row.auditor_team_member_id:editor.row.auditee_team_member_id):null} initialLabel={editor.row?(kind==="auditor"?editor.row.auditor_name:kind==="auditee"?editor.row.auditee_name??undefined:undefined):undefined} disabled={busy||disabled} onAccess={onAccessChanged}/>)}</div><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Save agenda activity</button><button type="button" className="secondary-action compact-action" onClick={()=>setEditor(null)}>Cancel agenda editing</button></div></fieldset></form>}
    {withdraw&&<form className="ncr-transition" aria-label="Withdraw agenda activity" onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);void mutate(`/internal-audits/audits/${audit.id}/agenda/${withdraw.id}/withdraw`,"POST",{expected_version:withdraw.row_version,reason:String(data.get("reason")??"").trim()},withdraw,true)}}><h4>Withdraw {withdraw.sequence} · {withdraw.title}</h4><p className="qms-history-caption">History is preserved. Audit version {audit.row_version} · Activity version {withdraw.row_version}.</p><fieldset disabled={busy||disabled}><label>Activity withdrawal reason<textarea aria-label="Activity withdrawal reason" name="reason" required maxLength={500} rows={2}/></label><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Confirm agenda withdrawal</button><button type="button" className="secondary-action compact-action" onClick={()=>setWithdraw(null)}>Keep agenda activity</button></div></fieldset></form>}
  </section>;
}
