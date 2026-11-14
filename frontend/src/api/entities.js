import {api} from './client.js';
export const datasets={
 list:()=>api('/datasets'),
 get:id=>api('/datasets/'+id),
 create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)}),
 impact:(id,runs)=>api('/datasets/'+id+'/impact?runs='+encodeURIComponent(runs.join(','))),
 quarantine:(id,payload)=>api('/datasets/'+id+'/exclusions',{method:'POST',body:JSON.stringify(payload)}),
 quarantineBatch:(id,payload)=>api('/datasets/'+id+'/exclusions/batch',{method:'POST',body:JSON.stringify(payload)}),
 restore:exclusionId=>api('/datasets/exclusions/'+exclusionId+'/restore',{method:'POST'})
};
export const jobs={
 list:()=>api('/jobs'),
 get:id=>api('/jobs/'+id),
 create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),
 approve:id=>api('/jobs/'+id+'/approve',{method:'POST'}),
 recompute:(datasetId,reason)=>api('/jobs/recompute/datasets/'+datasetId,{method:'POST',body:JSON.stringify({reason})}),
 recomputeGroups:()=>api('/jobs/recompute/groups'),
 retryGroup:key=>api('/jobs/recompute/'+key+'/retry',{method:'POST'})
};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
