import {api} from './client.js';
export const datasets={
 list:()=>api('/datasets'),
 get:id=>api('/datasets/'+id),
 create:data=>api('/datasets',{method:'POST',body:JSON.stringify(data)}),
 quarantines:id=>api('/datasets/'+id+'/quarantines'),
 impact:(id,run)=>api('/datasets/'+id+'/impact-preview',{method:'POST',body:JSON.stringify({run,reason:'影响面预览'})}),
 isolate:(id,payload)=>api('/datasets/'+id+'/quarantines',{method:'POST',body:JSON.stringify(payload)}),
 restore:(qid,reason)=>api('/datasets/quarantines/'+qid+'/restore',{method:'POST',body:JSON.stringify({reason})})
};
export const jobs={
 list:()=>api('/jobs'),
 get:id=>api('/jobs/'+id),
 create:data=>api('/jobs',{method:'POST',body:JSON.stringify(data)}),
 approve:id=>api('/jobs/'+id+'/approve',{method:'POST'}),
 recalcGroups:datasetId=>api('/jobs/recalc/groups'+(datasetId?('?dataset_id='+datasetId):'')),
 retryRecalc:groupId=>api('/jobs/recalc/'+groupId+'/retry',{method:'POST',body:JSON.stringify({})}),
 switchRecalc:groupId=>api('/jobs/recalc/'+groupId+'/switch',{method:'POST',body:JSON.stringify({})})
};
export const reports={list:()=>api('/reports'),create:data=>api('/reports',{method:'POST',body:JSON.stringify(data)}),toggle:id=>api('/reports/'+id+'/toggle',{method:'POST'}),deliveries:()=>api('/deliveries')};
