"use client";

import { Plus, RefreshCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

type Audit = { id: string; unit_id: string; code: string; state: string; row_version: number };
type Criterion = { id: string; audit_id: string; unit_id: string; sequence: number; title: string; requirement: string; reference: string; source_type: string; scope_id: string | null; status: string; row_version: number; withdrawal_reason: string };
type ScopeOption = { id:string; unit_id:string; audit_id:string; sequence:number; title:string; status:string };
const api = "/api/identity";
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
class AccessError extends Error { constructor(readonly status: number) { super(String(status)); } }
const unavailable = (cause: unknown) => cause instanceof AccessError && [401,403,404].includes(cause.status);
function failure(cause: unknown) {
  if (cause instanceof AccessError) {
    if ([401,403,404].includes(cause.status)) return "The audit or your access is unavailable. Refresh your responsibilities.";
    if (cause.status === 409) return "The audit, criterion order or linked scope changed. Refresh criterion before another submission.";
    if (cause.status === 422) return "Review the title, source reference, requirement and linked scope.";
  }
  return "Criterion could not be confirmed. Refresh criterion and review the record before submitting again.";
}
async function read<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(api+path,{credentials:"include",signal});
  if (response.status!==200) throw new AccessError(response.status);
  return await response.json() as T;
}
function valid(row: Criterion, audit: Audit) {
  return row && typeof row === "object" && typeof row.id === "string" && uuid.test(row.id) && row.audit_id===audit.id && row.unit_id===audit.unit_id && typeof row.title === "string" && typeof row.requirement === "string" && typeof row.reference === "string" && ["internal","standard","regulation","customer"].includes(row.source_type) && typeof row.withdrawal_reason === "string" && (row.scope_id===null||typeof row.scope_id==="string"&&uuid.test(row.scope_id)) && Number.isInteger(row.row_version) && row.row_version>0 && Number.isInteger(row.sequence) && ["active","withdrawn"].includes(row.status);
}
function CriterionScopePicker({audit,initial,disabled,onAccess}:{audit:Audit;initial:string|null;disabled:boolean;onAccess:(status:number)=>void}) {
  const [value,setValue]=useState(initial??""),[label,setLabel]=useState("Selected scope outside this page"),[offset,setOffset]=useState(0),[rows,setRows]=useState<ScopeOption[]>([]),[next,setNext]=useState(false),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const callback=useRef(onAccess);useEffect(()=>{callback.current=onAccess},[onAccess]);
  useEffect(()=>{const controller=new AbortController();const timer=window.setTimeout(()=>{setRows([]);setLoading(true);setError("");void read<ScopeOption[]>(`/internal-audits/audits/${audit.id}/scopes?status=active&limit=21&offset=${offset}`,controller.signal).then(data=>{
    if(controller.signal.aborted)return;
    if(!Array.isArray(data)||data.some(row=>!row||!uuid.test(row.id)||row.audit_id!==audit.id||row.unit_id!==audit.unit_id||row.status!=="active"||typeof row.title!=="string"||!Number.isInteger(row.sequence)))throw new Error("Mismatched audit scope");
    setRows(data.slice(0,20));setNext(data.length>20);
  }).catch(cause=>{if(!controller.signal.aborted){setError(failure(cause));if(unavailable(cause))callback.current((cause as AccessError).status)}}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});},0);return()=>{window.clearTimeout(timer);controller.abort()};},[audit.id,audit.unit_id,offset]);
  return <div className="ia-reference-picker ncr-wide"><input type="hidden" name="scope_id" value={value}/><label>Applies to scope (optional)<select aria-label="Applies to scope (optional)" value={value} disabled={disabled||loading} onChange={event=>{setValue(event.target.value);const row=rows.find(row=>row.id===event.target.value);if(row)setLabel(row.sequence+" · "+row.title)}}><option value="">Whole audit</option>{value&&!rows.some(row=>row.id===value)&&<option value={value}>{label}</option>}{rows.map(row=><option key={row.id} value={row.id}>{row.sequence} · {row.title}</option>)}</select></label>{loading&&<p role="status">Loading audit scope choices…</p>}{error&&<p role="alert">{error}</p>}<nav className="ia-reference-pages" aria-label="Criterion scope choices"><button type="button" className="secondary-action compact-action" disabled={disabled||loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous scope choices</button><span>Page {Math.floor(offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={disabled||loading||!next||offset+20>1_000_000} onClick={()=>setOffset(offset+20)}>More scope choices</button></nav></div>;
}

export function InternalAuditCriteria({audit,capabilities,disabled,onBusyChange,onVersionChange,onAuditRefreshed,onAccessChanged}: {
  audit:Audit;capabilities:string[];disabled:boolean;onBusyChange:(busy:boolean)=>void;onVersionChange:(version:number)=>void;onAuditRefreshed:(audit:unknown)=>void;onAccessChanged:(status:number)=>void;
}) {
  const heading=useId();
  const canRead=capabilities.includes("audits.read"), canManage=canRead&&capabilities.includes("audits.manage")&&["draft","planned"].includes(audit.state);
  const [rows,setRows]=useState<Criterion[]>([]),[offset,setOffset]=useState(0),[status,setStatus]=useState("active"),[next,setNext]=useState(false),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState(""),[blocked,setBlocked]=useState(false),[refresh,setRefresh]=useState(0);
  const [editor,setEditor]=useState<{row:Criterion|null}|null>(null),[withdraw,setWithdraw]=useState<Criterion|null>(null);
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
      void read<Criterion[]>(`/internal-audits/audits/${audit.id}/criteria?${params}`,controller.signal).then(data=>{
        if(!current())return;
        if(!Array.isArray(data)||data.some(row=>!valid(row,source.current)))throw new Error("Mismatched criterion");
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
  async function mutate(path:string,method:"POST"|"PATCH",body:Record<string,unknown>,expected:Criterion|null,withdrawal=false){
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
      const result=await response.json() as {criterion:Criterion;audit_version:number};
      if(token!==operation.current)return;
      if(!valid(result.criterion,audit)||result.audit_version!==parentVersion+1||(expected?result.criterion.id!==expected.id||result.criterion.row_version!==expected.row_version+1:result.criterion.row_version!==1)||result.criterion.status!==(withdrawal?"withdrawn":"active"))throw new Error("Unconfirmed criterion");
      callbacks.current.onVersionChange(result.audit_version);setBlocked(false);setEditor(null);setWithdraw(null);setNotice(withdrawal?"Criterion withdrawn. Its history remains available.":"Audit criterion saved.");setOffset(0);setRefresh(v=>v+1);
    }catch(cause){if(token===operation.current){if(!responseReceived)setBlocked(true);setError(failure(cause))}}
    finally{if(token===operation.current){pending.current=false;setBusy(false);callbacks.current.onBusyChange(false)}}
  }
  if(!canRead)return null;
  return <section className="ncr-read-section" aria-labelledby={heading} aria-busy={busy||loading}><div className="related-capas-heading"><div><h4 id={heading}>Audit criteria</h4><p>Record what will be evaluated and the source reference. Independence review remains separate.</p></div><button type="button" aria-label="Refresh audit criteria" className="icon-button" disabled={busy||disabled} onClick={()=>void reconcile()}><RefreshCw size={16} aria-hidden="true"/></button></div>
    {error&&<p role="alert" className="denied-state">{error}</p>}{notice&&<p role="status">{notice}</p>}{blocked&&<p role="status" className="ia-planning-note">Submission is locked. Refresh audit criteria and review the latest version before another change.</p>}
    <label>Criterion history<select aria-label="Criterion history" value={status} disabled={busy||disabled} onChange={event=>{setStatus(event.target.value);setOffset(0);setEditor(null);setWithdraw(null);setError("")}}><option value="active">Active criterion</option><option value="withdrawn">Withdrawn criterion</option></select></label>
    {loading?<div className="related-capa-loading" role="status" aria-label="Loading audit criterion"><span aria-hidden="true"/></div>:rows.length?<ul className="related-capa-list">{rows.map(row=><li key={row.id}><div><strong>{row.sequence} · {row.title}</strong><span className="ia-criterion-summary">{row.requirement}</span><small>{row.source_type} · {row.reference}</small><small>{row.scope_id?"Linked audit scope recorded":"Applies to the whole audit"}</small>{row.status==="withdrawn"&&<small>Withdrawn: {row.withdrawal_reason}</small>}<small>Version {row.row_version}</small>{canManage&&row.status==="active"&&<div className="ncr-form-actions"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setEditor({row});setWithdraw(null)}}>Edit criterion {row.sequence}</button><button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked} onClick={()=>{setWithdraw(row);setEditor(null)}}>Withdraw criterion {row.sequence}</button></div>}</div></li>)}</ul>:!error&&<p className="qms-history-caption">No {status} criterion items on this page.</p>}
    <nav className="related-capa-pages" aria-label="Audit criteria pages"><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||offset===0} onClick={()=>setOffset(Math.max(0,offset-20))}>Previous criteria</button><span>Page {Math.floor(offset/20)+1}</span><button type="button" className="secondary-action compact-action" disabled={busy||disabled||loading||!next||offset+20>1_000_000} onClick={()=>setOffset(offset+20)}>More criteria</button></nav>
    {canManage&&!editor&&!withdraw&&<button type="button" className="secondary-action compact-action" disabled={busy||disabled||blocked||loading} onClick={()=>setEditor({row:null})}><Plus size={16} aria-hidden="true"/>Add criterion</button>}
    {editor&&<form className="ncr-editor" aria-label={editor.row?"Edit audit criterion":"Add audit criterion"} onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);const title=String(data.get("title")??"").trim();if(!title)return;void mutate(`/internal-audits/audits/${audit.id}/criteria${editor.row?"/"+editor.row.id:""}`,editor.row?"PATCH":"POST",{sequence:Number(data.get("sequence")),title,requirement:String(data.get("requirement")??"").trim(),source_type:String(data.get("source_type")??"internal"),reference:String(data.get("reference")??"").trim(),scope_id:data.get("scope_id")||null,...(editor.row?{expected_version:editor.row.row_version}:{})},editor.row)}}><fieldset disabled={busy||disabled} className="ncr-editor-content"><div className="ncr-form-grid"><label>Criterion order<input type="number" name="sequence" min={1} max={10000} required defaultValue={editor.row?.sequence??10}/></label><label>Criterion title<input name="title" required maxLength={160} defaultValue={editor.row?.title??""}/></label><label>Source type<select aria-label="Source type" name="source_type" defaultValue={editor.row?.source_type??"internal"}><option value="internal">Internal requirement</option><option value="standard">Standard reference</option><option value="customer">Customer requirement</option><option value="regulation">Regulatory reference</option></select></label><label>Source reference<input name="reference" required maxLength={240} defaultValue={editor.row?.reference??""} placeholder="Procedure, edition, clause or contract reference"/></label><label className="ncr-wide">Requirement<textarea aria-label="Requirement" name="requirement" required maxLength={4000} rows={3} defaultValue={editor.row?.requirement??""}/></label><p className="qms-history-caption ncr-wide">Use your own wording. Reference metadata does not verify a standard or import its licensed text.</p><CriterionScopePicker key={editor.row?.id??"new"} audit={audit} initial={editor.row?.scope_id??null} disabled={busy||disabled} onAccess={onAccessChanged}/></div><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Save audit criterion</button><button type="button" className="secondary-action compact-action" onClick={()=>setEditor(null)}>Cancel criterion editing</button></div></fieldset></form>}
    {withdraw&&<form className="ncr-transition" aria-label="Withdraw audit criterion" onSubmit={event=>{event.preventDefault();const data=new FormData(event.currentTarget);void mutate(`/internal-audits/audits/${audit.id}/criteria/${withdraw.id}/withdraw`,"POST",{expected_version:withdraw.row_version,reason:String(data.get("reason")??"").trim()},withdraw,true)}}><h4>Withdraw {withdraw.sequence} · {withdraw.title}</h4><p className="qms-history-caption">History is preserved. Audit version {audit.row_version} · Criterion version {withdraw.row_version}.</p><fieldset disabled={busy||disabled}><label>Criterion withdrawal reason<textarea aria-label="Criterion withdrawal reason" name="reason" required maxLength={500} rows={2}/></label><div className="ncr-form-actions"><button type="submit" className="primary-action compact-action" disabled={blocked||loading}>Confirm criterion withdrawal</button><button type="button" className="secondary-action compact-action" onClick={()=>setWithdraw(null)}>Keep criterion item</button></div></fieldset></form>}
  </section>;
}
