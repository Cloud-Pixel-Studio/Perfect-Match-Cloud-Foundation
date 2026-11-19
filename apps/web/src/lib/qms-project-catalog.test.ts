import { readFileSync } from 'node:fs';
import { expect,it } from 'vitest';
import { journeys } from './guided-journeys';
it('keeps the immutable server step identities, sequence and product gaps equal to the guided UI',()=>{
 const expected={version:'guided-qms-v1',journeys:journeys.map(j=>({key:j.id,steps:j.steps.map((s,i)=>({key:s.id,position:i+1,feature_pending:!!s.productGap}))}))};
 const read=(path:string)=>JSON.parse(readFileSync(new URL(path,import.meta.url),'utf8'));
 expect(read('../../../../docs/product/QMS_PROJECT_CATALOG_V1.json')).toEqual(expected);
 expect(read('../../../api/src/pmc_api/qms_project_catalog.json')).toEqual(expected);
});
