// Reuse unchanged business assertions with an explicitly synthetic identity adapter.
// No OIDC credentials, real application sessions or backend writes are used.
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, writeFile, symlink } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { spawn } from 'node:child_process';
const root=process.cwd();
const out=resolve(process.env.FLOW_FIXTURE_OUTPUT??'artifacts/complete-flow-audit-20261114/fixture-regressions');
await mkdir(out,{recursive:true});
const temporary=await mkdtemp(join(tmpdir(),'pmqms-flow-fixtures-'));
await symlink(resolve('apps/web/node_modules'),join(temporary,'node_modules'));
const sourceFiles=['documents.experience.spec.ts','capa-origin.experience.spec.ts','internal-audits.experience.spec.ts'];
const manifest={mode:'All identity and business API responses are browser-memory fixtures; not real OIDC or SQL authorization.',backendRequestsForwarded:0,temporary,sourceFiles:[],baseURL:process.env.FLOW_WEB_URL??'http://127.0.0.1:3103'};
for(const file of sourceFiles){
 const source=await readFile(resolve('apps/web/e2e',file),'utf8');
 manifest.sourceFiles.push({path:'apps/web/e2e/'+file,sha256:createHash('sha256').update(source).digest('hex'),adaptation:'Only import ./support/auth replaced with ./auth-fixture; assertions unchanged.'});
 let adapted=source.replaceAll('"./support/auth"','"./auth-fixture"');
 if(file==='capa-origin.experience.spec.ts'){
  adapted+=String.raw`
 test('isolated Action Center opens the exact CAPA follow-up without backend writes',async({page},testInfo)=>{
  const {state}=await fixture(page,'ncr');
  await page.route('**/api/identity/action-center?**',route=>route.fulfill({json:{scope:'mine',generated_at:new Date().toISOString(),summary:{total:1,overdue:0,due_soon:1,unassigned:0,by_source:{capa:1}},items:[{id:'flow-capa-action',source:'capa',source_id:capaId,unit_id:unitA,title:'Follow up RELATED-CAPA',context:'Synthetic linked corrective action',state:'draft',urgency:'due_soon',due_date:'2026-12-01',overdue:false,assigned_to_user_id:'66666666-6666-4666-8666-666666666666',assignee_name:'In-memory reviewer',target_workspace:'capa',target_record_id:capaId,target_subrecord_id:null,target_process_id:processId,updated_at:new Date().toISOString()}]}}));
  await page.setViewportSize({width:375,height:812});
  await page.goto('/#action-center-heading',{waitUntil:'networkidle'});
  const button=page.getByRole('button',{name:'Open Follow up RELATED-CAPA',exact:true});await expect(button).toBeVisible();
  await testInfo.attach('synthetic-follow-up-mobile',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
  const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();expect(axe.violations).toEqual([]);
  await button.click();await expect(page.locator('section[aria-labelledby="capa-heading"] .ncr-detail')).toContainText('RELATED-CAPA');
  const url=new URL(page.url());expect(url.searchParams.get('pm_record')).toBe(capaId);expect(url.searchParams.get('pm_unit')).toBe(unitA);expect(url.searchParams.get('pm_process')).toBe(processId);expect(state.posts).toEqual([]);
  await testInfo.attach('synthetic-follow-up-CAPA-detail',{body:await page.screenshot({fullPage:true}),contentType:'image/png'});
 });`;
  manifest.sourceFiles.at(-1).adaptation+=' One additional isolated Action Center to CAPA navigation assertion appended.';
 }
 await writeFile(join(temporary,file),adapted);
}
await writeFile(join(temporary,'auth-fixture.ts'),String.raw`
import {expect,test,type Page} from '@playwright/test';
const states=new WeakMap<Page,{blocked:string[]}>();
test.afterEach(async({page},testInfo)=>{const state=states.get(page);if(state){await testInfo.attach('isolated-network-guard',{body:Buffer.from(JSON.stringify({mode:'identity/business in-memory only',backendRequestsForwarded:0,blocked:state.blocked})),contentType:'application/json'});expect(state.blocked,'Unexpected API request was blocked, never forwarded').toEqual([])}});
export async function authenticateWithKeycloak(page:Page,options:Record<string,string>){
 const state={blocked:[] as string[]};states.set(page,state);
 await page.route('**/api/identity/**',route=>{
  const path=new URL(route.request().url()).pathname.replace('/api/identity','');
  if(route.request().method()!=='GET'){state.blocked.push(route.request().method()+' '+path);return route.abort('blockedbyclient')}
  if(path==='/auth/me')return route.fulfill({json:{id:'66666666-6666-4666-8666-666666666666',display_name:'In-memory flow reviewer',email:null,current_tenant_id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'}});
  if(path==='/auth/tenants')return route.fulfill({json:[{id:'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa',name:'Synthetic flow company',slug:'synthetic-flow-company',role:'member'}]});
  if(path==='/qms-access/active-capabilities')return route.fulfill({json:{capabilities:['processes.read','processes.manage','documents.read','documents.author','documents.review','documents.approve','documents.release','documents.obsolete','controls.read','controls.manage','control_instances.read','control_instances.manage','evidence.read','evidence.create','evidence.review','risks.read','risks.manage','risks.review','ncr.read','ncr.manage','ncr.review','capa.read','capa.manage','capa.review','audits.read','audits.manage','audits.review','audits.execute']}});
  if(path==='/action-center')return route.fulfill({json:{scope:'mine',generated_at:new Date().toISOString(),summary:{total:0,overdue:0,due_soon:0,unassigned:0,by_source:{}},items:[]}});
  // Individual spec fixtures installed later answer business routes first.
  // Unknown routes fail closed instead of falling through to the real backend.
  return route.fulfill({status:403,json:{detail:'Not supplied by isolated flow fixture'}});
 });
 await page.goto(options.destination??'/',{waitUntil:'networkidle'});
 await expect(page.getByRole('heading',{name:'Work with clarity.'})).toBeVisible();
}
`);
await writeFile(join(temporary,'playwright.config.ts'),`import {defineConfig} from '@playwright/test'; export default defineConfig({testDir:'.',testMatch:'*.spec.ts',outputDir:${JSON.stringify(join(out,'results'))},workers:1,retries:0,timeout:30000,reporter:[['line'],['json',{outputFile:${JSON.stringify(join(out,'results.json'))}}]],use:{baseURL:${JSON.stringify(manifest.baseURL)},headless:true,reducedMotion:'reduce',screenshot:'only-on-failure',trace:'off',video:'off'}});`);
await writeFile(join(out,'source-manifest.json'),JSON.stringify(manifest,null,2)+'\n');
const executable=resolve('apps/web/node_modules/@playwright/test/cli.js');
const grep=process.env.FLOW_FIXTURE_GREP?['--grep',process.env.FLOW_FIXTURE_GREP]:[];
const child=spawn(process.execPath,[executable,'test','--config',join(temporary,'playwright.config.ts'),'--grep-invert','live ',...grep],{cwd:root,env:{...process.env,KEYCLOAK_USER_A_PASSWORD:'in-memory-only-not-a-credential',KEYCLOAK_MULTI_USER_PASSWORD:'in-memory-only-not-a-credential',KEYCLOAK_OWNER_PASSWORD:'in-memory-only-not-a-credential'},stdio:['ignore','pipe','pipe']});
let log='';for(const stream of [child.stdout,child.stderr])stream.on('data',chunk=>{log+=chunk;process.stdout.write(chunk)});
const status=await new Promise(resolveExit=>child.on('exit',resolveExit));
await writeFile(join(out,'run.log'),log);manifest.exitCode=status;await writeFile(join(out,'source-manifest.json'),JSON.stringify(manifest,null,2)+'\n');process.exitCode=status??1;
