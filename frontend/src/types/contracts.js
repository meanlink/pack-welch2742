/** @typedef {{id:number,name:string,source:string,rows:number,active_records:number,quarantine_count:number,checksum:string,excluded_runs?:string[]}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,input_runs:string[],invalidated_reason:string,recalc_group_id:?number,supersedes_job_id:?number}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean,hold_reason:string,recalc_group_id:?number}} ReportSchedule */
/** @typedef {{id:number,dataset_id:number,run:string,reason:string,status:string,restored_at:?number,restore_reason:?string}} Quarantine */
/** @typedef {{id:number,dataset_id:number,reason:string,status:string,quarantine_runs:string[],jobs:AnalysisJob[]}} RecalcGroup */
/** @typedef {{id:number,report_id:number,filename:string,destination:string,invalid:boolean,invalid_reason:string}} Delivery */
export {};
