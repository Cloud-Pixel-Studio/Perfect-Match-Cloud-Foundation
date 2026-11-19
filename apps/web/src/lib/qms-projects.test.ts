import { describe, expect, it } from "vitest";
import { journeys } from "./guided-journeys";
import { isAllowedIdentityPath } from "./identity-path";
import { loadProjectIndex, loadProject, mutateProject, parseProjectDetail, ProjectError } from "./qms-projects";

const tenantId="10000000-0000-4000-8000-000000000001", userId="20000000-0000-4000-8000-000000000001", unitId="30000000-0000-4000-8000-000000000001", id="40000000-0000-4000-8000-000000000001", other="90000000-0000-4000-8000-000000000001";
const context={tenantId,userId,unitId};
const now="2026-11-18T12:00:00Z";
const base={id,tenant_id:tenantId,unit_id:unitId,code:"QMS-001",name:"Initial implementation",journey_key:"initial",catalog_version:"guided-qms-v1",scope_summary:"Quality laboratory",coordinator_user_id:userId,target_date:"2027-01-31",status:"open",row_version:1,created_by_user_id:userId,created_at:now,updated_at:now};
function detail(){return {...base,steps:journeys[0].steps.map((s,i)=>({id:`50000000-0000-4000-8000-${String(i+1).padStart(12,"0")}`,tenant_id:tenantId,unit_id:unitId,project_id:id,step_key:s.id,position:i+1,status:s.productGap?"feature_pending":"not_started",notes:"",assignee_user_id:null,target_date:null,row_version:1,updated_by_user_id:userId,updated_at:now}))};}
type Options={caps?:unknown;list?:unknown;record?:unknown;unit?:unknown;members?:unknown;after?:unknown;status?:number;target?:string;header?:string;onRead?:(path:string)=>void;mutation?:unknown};
function fixture(o:Options={}){
 const calls:{path:string;init?:RequestInit}[]=[];let identities=0;
 const request:typeof fetch=async(url,init)=>{
  const path=String(url).replace("/api/identity","");calls.push({path,init});o.onRead?.(path);
  if(o.status&&(!o.target||path.startsWith(o.target)))return Response.json({detail:"PRIVATE DIAGNOSTIC"},{status:o.status});
  if(path==="/auth/me")return Response.json(identities++===0?{id:userId,current_tenant_id:tenantId}:o.after??{id:userId,current_tenant_id:tenantId});
  if(path.startsWith("/qms-access/effective"))return Response.json({unit_id:unitId,capabilities:o.caps??["projects.read","projects.manage"]});
  if(path.startsWith("/organization/units/"))return Response.json(o.unit??{id:unitId,tenant_id:tenantId,status:"active"});
  if(path.startsWith("/organization/members"))return Response.json(o.members??[{id:userId,display_name:"Coordinator",role:"owner"}],{headers:{"X-Tenant-ID":o.header??tenantId}});
  if(init?.method&&init.method!=="GET")return Response.json(o.mutation??{...detail(),row_version:2},{status:init.method==="POST"&&path==="/qms-projects"?201:200});
  return Response.json(path.includes("?")?o.list??[base]:o.record??detail());
 };return{request,calls};
}

describe("scoped QMS project client",()=>{
 it("allows only the normal scoped proxy routes",()=>{expect(isAllowedIdentityPath(["qms-projects",id,"steps",other])).toBe(true);expect(isAllowedIdentityPath(["qms-projects",".."])).toBe(false);});
 it("checks identity/scope/capabilities before reading projects and verifies actor afterwards",async()=>{
  const f=fixture(),signal=new AbortController().signal;const v=await loadProjectIndex(context,signal,f.request);
  expect(v).toMatchObject({kind:"loaded",canManage:true,limited:false,projects:[base],members:[{id:userId,display_name:"Coordinator",role:"owner"}]});
  expect(f.calls[0].path).toBe("/auth/me");expect(f.calls.at(-1)?.path).toBe("/auth/me");
  expect(f.calls.some(c=>c.path==="/qms-projects?unit_id="+unitId+"&limit=50&offset=0")).toBe(true);
  for(const c of f.calls)expect(c.init).toMatchObject({credentials:"include",cache:"no-store",signal});
 });
 it.each([[],["projects.manage"],["processes.manage"]].map(caps=>({caps})))("never reads projects without explicit read grant: %j",async ({caps})=>{
  const f=fixture({caps});expect(await loadProjectIndex(context,undefined,f.request)).toMatchObject({kind:"restricted"});expect(f.calls.some(c=>c.path.startsWith("/qms-projects"))).toBe(false);
 });
 it("does not fetch the member directory or allow management with a read-only grant",async()=>{const f=fixture({caps:["projects.read"]});expect(await loadProjectIndex(context,undefined,f.request)).toMatchObject({canManage:false,members:[]});expect(f.calls.some(c=>c.path.includes("/members"))).toBe(false);});
 it("loads only a complete, version-compatible ordered project plan",async()=>{const f=fixture();expect(await loadProject(context,id,undefined,f.request)).toEqual(detail());});
 it.each([
  {...base,tenant_id:other},{...base,unit_id:other},{...base,id:"../escape"},{...base,row_version:true},{...base,row_version:0},{...base,status:["open"]},{...base,journey_key:"unknown"},{...base,catalog_version:"future"},{...base,target_date:"2026-02-30"},{...base,created_at:"yesterday"},{...base,name:""},{...base,coordinator_user_id:""},
 ])("rejects malformed and foreign project metadata",async row=>{const f=fixture({list:[row]});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toBeInstanceOf(ProjectError);});
 it.each([{},[base,base],Array.from({length:51},()=>base)].map(list=>({list})))("rejects invalid project lists",async ({list})=>{const f=fixture({list});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toBeInstanceOf(ProjectError);});
 it("marks a full page as a partial list",async()=>{const f=fixture({list:Array.from({length:50},(_,i)=>({...base,id:`40000000-0000-4000-8000-${String(i+1).padStart(12,"0")}`,code:`QMS-${i}`}))});expect(await loadProjectIndex(context,undefined,f.request)).toMatchObject({limited:true});});
 it.each(["tenant_id","unit_id","project_id","step_key","position","status","row_version","assignee_user_id","target_date"])("rejects invalid step %s",field=>{const d=detail();(d.steps[0] as Record<string,unknown>)[field]=field.endsWith("_id")?other:field==="position"?2:field==="row_version"?true:field==="target_date"?"2026-02-30":"invalid";if(field==="assignee_user_id") (d.steps[0] as Record<string,unknown>)[field]="bad";expect(()=>parseProjectDetail(d,context)).toThrow(ProjectError);});
 it("rejects missing/duplicated/reordered catalog steps and completed product gaps",()=>{
  for(const alter of [(d:ReturnType<typeof detail>)=>d.steps.pop(),(d:ReturnType<typeof detail>)=>d.steps[1]=d.steps[0],(d:ReturnType<typeof detail>)=>d.steps.reverse(),(d:ReturnType<typeof detail>)=>d.steps[1].status="reported"]){const d=detail();alter(d);expect(()=>parseProjectDetail(d,context)).toThrow(ProjectError);}
 });
 it.each(["blocked","reported"])("requires a meaningful note for %s",status=>{const d=detail();d.steps[0].status=status;d.steps[0].notes=" ";expect(()=>parseProjectDetail(d,context)).toThrow(ProjectError);});
 it.each([401,403])("clears whole loads on HTTP%s without exposing upstream bodies",async status=>{const f=fixture({status,target:"/qms-projects"});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toMatchObject({status});await expect(loadProject(context,id,undefined,f.request)).rejects.not.toThrow("PRIVATE");});
 it.each([{id:other,current_tenant_id:tenantId},{id:userId,current_tenant_id:other}])("rejects post-read identity changes",async after=>{const f=fixture({after});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toMatchObject({status:409});});
 it.each([{id:other,tenant_id:tenantId,status:"active"},{id:unitId,tenant_id:other,status:"active"},{id:unitId,tenant_id:tenantId,status:"archived"}])("rejects inaccessible or changed units",async unit=>{const f=fixture({unit});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toBeInstanceOf(ProjectError);});
 it("rejects a foreign member directory response",async()=>{const f=fixture({header:other});await expect(loadProjectIndex(context,undefined,f.request)).rejects.toMatchObject({status:409});});
 it("ignores a late result even when transport does not honor cancellation",async()=>{const controller=new AbortController();const f=fixture({onRead:path=>{if(path.startsWith("/qms-projects"))controller.abort();}});await expect(loadProjectIndex(context,controller.signal,f.request)).rejects.toMatchObject({name:"AbortError"});});
 it("uses CSRF and explicit versions and never retries a mutation",async()=>{
  const command={kind:"update" as const,id,expectedVersion:1,changes:{name:"Revised scope"}};
  const capture=fixture({mutation:{...detail(),row_version:2,name:"Revised scope"}});
  expect(await mutateProject(context,command,"x".repeat(40),undefined,capture.request)).toMatchObject({row_version:2,name:"Revised scope"});
  const write=capture.calls.filter(c=>c.init?.method==="PATCH");expect(write).toHaveLength(1);expect(write[0].init?.headers).toMatchObject({"X-CSRF-Token":"x".repeat(40)});expect(JSON.parse(write[0].init?.body as string)).toEqual({expected_version:1,name:"Revised scope"});
 });
 it("does not send a mutation without CSRF or manage responsibility",async()=>{for(const caps of [["projects.read"],["projects.manage"]]){const f=fixture({caps});await expect(mutateProject(context,{kind:"update",id,expectedVersion:1,changes:{name:"New"}},"x".repeat(40),undefined,f.request)).rejects.toMatchObject({status:403});expect(f.calls.some(c=>c.init?.method==="PATCH")).toBe(false);}const f=fixture();await expect(mutateProject(context,{kind:"update",id,expectedVersion:1,changes:{name:"New"}},"",undefined,f.request)).rejects.toBeInstanceOf(ProjectError);expect(f.calls.some(c=>c.init?.method==="PATCH")).toBe(false);});
 it("distinguishes rejected conflicts from an unconfirmed committed response",async()=>{
  const a=fixture({status:409,target:"/qms-projects"});await expect(mutateProject(context,{kind:"update",id,expectedVersion:1,changes:{name:"New"}},"x".repeat(40),undefined,a.request)).rejects.toMatchObject({status:409,uncertain:false});
  const b=fixture({mutation:{...detail(),tenant_id:other}});await expect(mutateProject(context,{kind:"update",id,expectedVersion:1,changes:{name:"New"}},"x".repeat(40),undefined,b.request)).rejects.toMatchObject({uncertain:true});
 });
});

it("does not treat an HTTP206 partial response as a complete project index",async()=>{
 const f=fixture();const request:typeof fetch=(url,init)=>String(url).includes('/qms-projects?')?Promise.resolve(Response.json([base],{status:206})):f.request(url,init);
 await expect(loadProjectIndex(context,undefined,request)).rejects.toMatchObject({status:206});
});
it("does not confirm an HTTP202 asynchronous mutation receipt",async()=>{
 const f=fixture();const request:typeof fetch=(url,init)=>init?.method==='PATCH'?Promise.resolve(Response.json({...detail(),name:'New',row_version:2},{status:202})):f.request(url,init);
 await expect(mutateProject(context,{kind:'update',id,expectedVersion:1,changes:{name:'New'}},'x'.repeat(40),undefined,request)).rejects.toMatchObject({uncertain:true});
});
it("creates only the selected unit and validates the exact creation receipt",async()=>{
 const input={code:base.code,name:base.name,journey_key:'initial' as const,scope_summary:base.scope_summary,coordinator_user_id:userId,target_date:base.target_date};
 const f=fixture({mutation:detail()});expect(await mutateProject(context,{kind:'create',input},'x'.repeat(40),undefined,f.request)).toEqual(detail());
 const call=f.calls.find(c=>c.init?.method==='POST')!;expect(call.path).toBe('/qms-projects');expect(JSON.parse(call.init!.body as string)).toEqual({...input,unit_id:unitId});
});
it("matches a step receipt to both parent and step versions and requested content",async()=>{
 const d=detail();d.row_version=2;d.steps[0]={...d.steps[0],row_version:2,status:'reported',notes:'Work performed; independent evidence review remains pending.'};
 const f=fixture({mutation:d});expect(await mutateProject(context,{kind:'step',id,stepId:d.steps[0].id,expectedVersion:1,expectedStepVersion:1,changes:{status:'reported',notes:d.steps[0].notes}},'x'.repeat(40),undefined,f.request)).toEqual(d);
 const bad=fixture({mutation:{...d,row_version:3}});await expect(mutateProject(context,{kind:'step',id,stepId:d.steps[0].id,expectedVersion:1,expectedStepVersion:1,changes:{status:'reported',notes:d.steps[0].notes}},'x'.repeat(40),undefined,bad.request)).rejects.toMatchObject({uncertain:true});
});
it("only confirms the requested archive or restoration status",async()=>{
 const f=fixture({mutation:{...detail(),row_version:2,status:'archived'}});expect(await mutateProject(context,{kind:'status',id,expectedVersion:1,targetStatus:'archived',reason:'Planning paused'},'x'.repeat(40),undefined,f.request)).toMatchObject({status:'archived',row_version:2});
 const bad=fixture();await expect(mutateProject(context,{kind:'status',id,expectedVersion:1,targetStatus:'archived',reason:'Planning paused'},'x'.repeat(40),undefined,bad.request)).rejects.toMatchObject({uncertain:true});
});
it("flags identity loss after a write separately from a rejected concurrency conflict",async()=>{
 const f=fixture({mutation:{...detail(),row_version:2,name:'New'},after:{id:other,current_tenant_id:tenantId}});
 await expect(mutateProject(context,{kind:'update',id,expectedVersion:1,changes:{name:'New'}},'x'.repeat(40),undefined,f.request)).rejects.toMatchObject({uncertain:true,contextLost:true});
});

it.each([500,502,504])('treats HTTP%s mutation failure as uncertain and prevents blind retry',async status=>{
 const f=fixture({status,target:'/qms-projects'});
 await expect(mutateProject(context,{kind:'update',id,expectedVersion:1,changes:{name:'New'}},'x'.repeat(40),undefined,f.request)).rejects.toMatchObject({status,uncertain:true});
});

it('identifies a catalog upgrade separately from revoked authority',()=>{
 try{parseProjectDetail({...detail(),catalog_version:'guided-qms-v2'},context);throw new Error('accepted unsupported version');}
 catch(error){expect(error).toMatchObject({catalogMismatch:true,contextLost:false});}
});
