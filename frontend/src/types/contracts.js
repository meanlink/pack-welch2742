/** @typedef {{id:number,name:string,source:string,rows:number,checksum:string,exclusions?:Array,records?:Array}} Dataset */
/** @typedef {{id:number,name:string,dataset_id:number,status:string,result:Object,approved:boolean,invalid:boolean,invalid_reason:string,recompute_key:?string,source_job_id:?number}} AnalysisJob */
/** @typedef {{id:number,name:string,job_id:number,destination:string,next_run:number,enabled:boolean,suspended:boolean,suspended_reason:string,recompute_key:?string}} ReportSchedule */
/** @typedef {{id:number,run:string,reason:string,active:boolean,created_at:number,restored_at:?number}} SegmentExclusion */
export {};
