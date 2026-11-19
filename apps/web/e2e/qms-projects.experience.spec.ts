import AxeBuilder from '@axe-core/playwright';
import { expect,test,type Page } from '@playwright/test';
import { journeys } from '../src/lib/guided-journeys';
import type { ProjectDetail } from '../src/lib/qms-projects';

const tenant='10000000-0000-4000-8000-000000000001',actor='20000000-0000-4000-8000-000000000007',unit='30000000-0000-4000-8000-000000000001',id='40000000-0000-4000-8000-000000000001';
const now='2026-11-18T12:00:00Z';
function sample():ProjectDetail{return {id,tenant_id:tenant,unit_id:unit,code:'QMS-001',name:'Synthetic saved project',journey_key:'initial',catalog_version:'guided-qms-v1',scope_summary:'Synthetic laboratory scope',coordinator_user_id:actor,target_date:null,status:'open',row_version:1,created_by_user_id:actor,created_at:now,updated_at:now,steps:journeys[0].steps.map((s,i)=>({id:`50000000-0000-4000-8000-${String(i+1).padStart(12,'0')}`,tenant_id:tenant,unit_id:unit,project_id:id,step_key:s.id,position:i+1,status:s.productGap?'feature_pending':'not_started',notes:'',assignee_user_id:null,target_date:null,row_version:1,updated_by_user_id:actor,updated_at:now}))};}
async function fixture(page:Page,readOnly=false){
 const state={project:sample(),exists:true,writeStatus:200,readStatus:200,writeCount:0,commitThenFail:false,catalogMismatch:false};
 const caps=['projects.read',...readOnly?[]:['projects.manage'],'processes.read'];
 await page.route('**/api/identity/**',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname.replace('/api/identity','');
  const ok=(json:unknown,headers?:Record<string,string>)=>route.fulfill({json,headers});
  if(path==='/auth/me')return ok({id:actor,current_tenant_id:tenant,display_name:'Synthetic project coordinator',email:null},{'Set-Cookie':'pm_csrf='+('x'.repeat(40))+'; Path=/; SameSite=Lax'});
  if(path==='/auth/tenants')return ok([{id:tenant,name:'DEMO Project Company',slug:'demo-project',role:'owner'}]);
  if(path==='/qms-access/active-capabilities')return ok({capabilities:caps});
  if(path==='/qms-access/effective')return ok({unit_id:unit,capabilities:caps});
  if(path==='/organization/units')return ok([{id:unit,tenant_id:tenant,code:'LAB',name:'Synthetic laboratory',unit_type:'site',status:'active'}],{'X-Tenant-ID':tenant});
  if(path.startsWith('/organization/units/'))return ok({id:unit,tenant_id:tenant,status:'active',code:'LAB',name:'Synthetic laboratory',unit_type:'site'});
  if(path==='/organization/members')return ok([{id:actor,display_name:'Synthetic coordinator',role:'owner'}],{'X-Tenant-ID':tenant});
  if(path==='/action-center')return ok({scope:'mine',generated_at:now,summary:{total:0,overdue:0,due_soon:0,unassigned:0,by_source:{}},items:[]});
  if(path==='/processes')return ok([]);
  if(!path.startsWith('/qms-projects'))return route.fulfill({status:404,json:{}});
  if(req.method()==='GET'){
   if(state.readStatus!==200)return route.fulfill({status:state.readStatus,json:{}});
   return ok(path==='/qms-projects'?state.exists?[state.project]:[]:{...state.project,catalog_version:state.catalogMismatch?'future-catalog':state.project.catalog_version});
  }
  state.writeCount++;
  if(state.writeStatus!==200&&!state.commitThenFail)return route.fulfill({status:state.writeStatus,json:{detail:'Synthetic rejected write'}});
  const b=req.postDataJSON() as Record<string,unknown>;
  if(path==='/qms-projects'){state.exists=true;state.project={...sample(),...b} as ProjectDetail;}
  else if(path.endsWith('/status')){state.project={...state.project,status:b.target_status as 'open'|'archived',row_version:state.project.row_version+1};}
  else if(path.includes('/steps/')){state.project={...state.project,row_version:state.project.row_version+1,steps:state.project.steps.map(s=>s.id===path.split('/').at(-1)?{...s,...b,row_version:s.row_version+1}:s)} as ProjectDetail;}
  else state.project={...state.project,...b,row_version:state.project.row_version+1} as ProjectDetail;
  if(state.commitThenFail)return route.fulfill({status:state.writeStatus,json:{}});
  return route.fulfill({status:path==='/qms-projects'?201:200,json:state.project});
 });return state;
}
async function open(page:Page){await page.goto('/#implementation-guide-heading');await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('combobox',{name:'Saved project',exact:true}).selectOption(id);await expect(page.getByRole('heading',{name:'Synthetic saved project',exact:true})).toBeVisible();}

test('a saved project resumes reported work without marking it verified',async({page})=>{
 const s=await fixture(page);s.exists=false;
 await page.goto('/#implementation-guide-heading');await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('button',{name:'New project',exact:true}).click();
 const form=page.getByRole('form',{name:'New project',exact:true});await form.getByLabel('Code',{exact:true}).fill('QMS-001');await form.getByLabel('Name',{exact:true}).fill('Synthetic saved project');await form.getByLabel('Scope and boundaries').fill('Scope prepared for independent review');await form.getByRole('button',{name:'Create project',exact:true}).click();
 await page.getByRole('button',{name:'Update step follow-up',exact:true}).click();const step=page.getByRole('form',{name:'Step follow-up',exact:true});await step.getByLabel('Work status').selectOption('reported');await step.getByLabel('Follow-up notes').fill('Work reported, evidence acceptance pending');await step.getByRole('button',{name:'Save step follow-up',exact:true}).click();
 await expect(page.getByText('Work reported · pending verification',{exact:true})).toBeVisible();await page.reload();await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('combobox',{name:'Saved project',exact:true}).selectOption(id);await expect(page.getByText('Work reported, evidence acceptance pending',{exact:true})).toBeVisible();
});
test('step conflict and failed reconciliation preserve the mounted draft',async({page})=>{
 const s=await fixture(page);await open(page);await page.getByRole('button',{name:'Update step follow-up',exact:true}).click();const form=page.getByRole('form',{name:'Step follow-up',exact:true});await form.getByLabel('Follow-up notes').fill('Keep this draft after a failed reload');s.writeStatus=409;await form.getByRole('button',{name:'Save step follow-up',exact:true}).click();await expect(form.getByRole('button',{name:'Save step follow-up',exact:true})).toBeDisabled();
 s.readStatus=500;await form.getByRole('button',{name:'Reload step, keep draft',exact:true}).click();await expect(form.getByLabel('Follow-up notes')).toHaveValue('Keep this draft after a failed reload');await expect(page.getByRole('status').filter({hasText:'could not be verified'})).toBeVisible();
 s.readStatus=200;await form.getByRole('button',{name:'Reload step, keep draft',exact:true}).click();await form.getByRole('button',{name:'Use current versions for this draft',exact:true}).click();s.writeStatus=200;await form.getByRole('button',{name:'Save step follow-up',exact:true}).click();await expect(page.getByText('Keep this draft after a failed reload',{exact:true})).toBeVisible();
});
test('ambiguous 502 commit requires reconciliation before a retry',async({page})=>{
 const s=await fixture(page);await open(page);await page.getByRole('button',{name:'Edit project',exact:true}).click();const form=page.getByRole('form',{name:'Edit project',exact:true});await form.getByLabel('Name',{exact:true}).fill('Saved before proxy failed');s.writeStatus=502;s.commitThenFail=true;await form.getByRole('button',{name:'Save project changes',exact:true}).click();await expect(form.getByRole('button',{name:'Save project changes',exact:true})).toBeDisabled();await expect(page.getByRole('alert').filter({hasText:'may have reached the server'})).toBeVisible();expect(s.writeCount).toBe(1);await expect(form.getByLabel('Name',{exact:true})).toHaveValue('Saved before proxy failed');
});
test('metadata and step drafts lock inline, sidebar and scope navigation',async({page})=>{
 await fixture(page);await open(page);
 for(const kind of ['metadata','step']){
  await page.getByRole('button',{name:kind==='metadata'?'Edit project':'Update step follow-up',exact:true}).click();
  await expect(page.getByRole('combobox',{name:'Current organization',exact:true})).toBeDisabled();await expect(page.getByRole('combobox',{name:'Organizational unit',exact:true})).toBeDisabled();await expect(page.getByRole('button',{name:'Open Processes',exact:true})).toBeDisabled();await expect(page.getByRole('link',{name:'Processes',exact:true})).toHaveAttribute('aria-disabled','true');
  await page.getByRole('link',{name:'Processes',exact:true}).click({force:true});await expect(page.getByRole('form',{name:kind==='metadata'?'Edit project':'Step follow-up',exact:true})).toBeVisible();
  await page.getByRole('button',{name:kind==='metadata'?'Cancel editing':'Cancel step editing',exact:true}).click();
 }
});
test('catalog incompatibility is explained without claiming lost permissions',async({page})=>{const s=await fixture(page);s.catalogMismatch=true;await page.goto('/#implementation-guide-heading');await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('combobox',{name:'Saved project',exact:true}).selectOption(id);await expect(page.getByRole('alert').filter({hasText:'incompatible guide catalog'})).toBeVisible();await expect(page.getByRole('combobox',{name:'Organizational unit',exact:true})).toHaveValue(unit);await expect(page.getByRole('button',{name:'Update step follow-up',exact:true})).toHaveCount(0);});
for(const status of [401,403])test(`project HTTP${status} clears project and unit observations`,async({page})=>{const s=await fixture(page);await open(page);await page.getByRole('button',{name:'Edit project',exact:true}).click();s.writeStatus=status;await page.getByRole('form',{name:'Edit project',exact:true}).getByRole('button',{name:'Save project changes',exact:true}).click();await expect(page.getByRole('heading',{name:'Synthetic saved project',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Open Processes',exact:true})).toHaveCount(0);await expect(page.getByText(status===401?'Your session has expired':'Access required',{exact:true}).first()).toBeVisible();});
test('read-only planning never offers mutations and gaps cannot be reported',async({page})=>{await fixture(page,true);await open(page);await expect(page.getByRole('button',{name:'New project',exact:true})).toHaveCount(0);await expect(page.getByRole('button',{name:'Update step follow-up',exact:true})).toHaveCount(0);await page.getByRole('button',{name:'Confirm the standard, edition and applicability Feature pending',exact:true}).click();await expect(page.getByRole('region',{name:'Saved project follow-up',exact:true}).getByText('Product feature pending',{exact:true})).toBeVisible();});
for(const width of [375,1280])test(`project planning responsive and accessibility ${width}`,async({page},info)=>{await fixture(page);await page.setViewportSize({width,height:900});await open(page);expect(await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth)).toBeLessThanOrEqual(1);const a=await new AxeBuilder({page}).include('.qms-project-planner').include('.project-step-plan').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();expect(a.violations).toEqual([]);await info.attach('saved-project',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});});

test('archiving and restoring keep project steps and their notes',async({page})=>{
 const s=await fixture(page);s.project.steps[0].notes='Retain this planning history';await open(page);
 await page.getByRole('button',{name:'Archive project',exact:true}).click();await page.getByRole('textbox',{name:'Reason for archiving',exact:true}).fill('Pause planning for scope review');await page.getByRole('button',{name:'Save status decision',exact:true}).click();await expect(page.getByRole('button',{name:'Update step follow-up',exact:true})).toHaveCount(0);await expect(page.getByText('Retain this planning history',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Restore project',exact:true}).click();await page.getByRole('textbox',{name:'Reason for restoring',exact:true}).fill('Resume after scope review');await page.getByRole('button',{name:'Save status decision',exact:true}).click();await expect(page.getByRole('button',{name:'Update step follow-up',exact:true})).toBeVisible();await expect(page.getByText('Retain this planning history',{exact:true})).toBeVisible();
});
test('a product gap can carry planning notes but cannot be reported implemented',async({page})=>{
 await fixture(page);await open(page);await page.getByRole('button',{name:'Confirm the standard, edition and applicability Feature pending',exact:true}).click();await page.getByRole('button',{name:'Update step follow-up',exact:true}).click();const form=page.getByRole('form',{name:'Step follow-up',exact:true});await expect(form.getByRole('combobox',{name:'Work status',exact:true})).toBeDisabled();await expect(form.getByRole('combobox',{name:'Work status',exact:true})).toHaveValue('feature_pending');await form.getByLabel('Follow-up notes').fill('Prepare applicability rationale with the quality professional');await form.getByRole('button',{name:'Save step follow-up',exact:true}).click();await expect(form).toHaveCount(0);await expect(page.getByRole('region',{name:'Saved project follow-up',exact:true}).getByText('Product feature pending',{exact:true})).toBeVisible();
});

test('a definite creation conflict permits correcting values without losing the draft',async({page})=>{
 const s=await fixture(page);await page.goto('/#implementation-guide-heading');await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('button',{name:'New project',exact:true}).click();const form=page.getByRole('form',{name:'New project',exact:true});await form.getByLabel('Code',{exact:true}).fill('QMS-001');await form.getByLabel('Name',{exact:true}).fill('Keep this new project draft');s.writeStatus=409;await form.getByRole('button',{name:'Create project',exact:true}).click();await expect(form.getByLabel('Name',{exact:true})).toHaveValue('Keep this new project draft');await expect(form.getByRole('button',{name:'Create project',exact:true})).toBeEnabled();await form.getByLabel('Code',{exact:true}).fill('QMS-002');s.writeStatus=200;await form.getByRole('button',{name:'Create project',exact:true}).click();await expect(page.getByRole('heading',{name:'Keep this new project draft',exact:true})).toBeVisible();
});

test('Unicode API-sized text remains readable and editable with character limits',async({page})=>{
 await page.setViewportSize({width:375,height:812});
 const s=await fixture(page),name='\u{1F9EA}'.repeat(160),notes='\u{1F4CB}'.repeat(2000);
 s.project.name=name;s.project.scope_summary='\u{1F30D}'.repeat(4000);s.project.row_version=2;s.project.steps[0]={...s.project.steps[0],row_version:2,status:'reported',notes};
 await page.goto('/#implementation-guide-heading');await page.getByRole('combobox',{name:'Organizational unit',exact:true}).selectOption(unit);await page.getByRole('combobox',{name:'Saved project',exact:true}).selectOption(id);
 await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();await expect(page.getByText(notes,{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Edit project',exact:true}).click();const metadata=page.getByRole('form',{name:'Edit project',exact:true});
 await metadata.getByLabel('Name',{exact:true}).fill('x'.repeat(161));await metadata.getByRole('button',{name:'Save project changes',exact:true}).click();await expect(metadata.getByLabel('Name',{exact:true})).toHaveAttribute('aria-invalid','true');await expect(page.getByRole('status').filter({hasText:'Use up to 40 characters'})).toBeVisible();expect(s.writeCount).toBe(0);
 await metadata.getByLabel('Name',{exact:true}).fill(name);await metadata.getByRole('button',{name:'Save project changes',exact:true}).click();await expect(metadata).toHaveCount(0);await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();expect(s.writeCount).toBe(1);
 await page.getByRole('button',{name:'Update step follow-up',exact:true}).click();const step=page.getByRole('form',{name:'Step follow-up',exact:true});await step.getByLabel('Follow-up notes').fill('x'.repeat(2001));await step.getByRole('button',{name:'Save step follow-up',exact:true}).click();await expect(step.getByLabel('Follow-up notes')).toHaveAttribute('aria-invalid','true');await expect(page.getByRole('status').filter({hasText:'Enter follow-up notes'})).toBeVisible();expect(s.writeCount).toBe(1);
 await step.getByLabel('Follow-up notes').fill(notes);await step.getByRole('button',{name:'Save step follow-up',exact:true}).click();await expect(step).toHaveCount(0);await expect(page.getByText(notes,{exact:true})).toBeVisible();expect(s.writeCount).toBe(2);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
});
