import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records), 'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved','created_at','finished_at','input_checksum','invalid','invalid_reason','recompute_key','source_job_id']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run','enabled','suspended','suspended_reason','recompute_key']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination','invalid','invalid_reason']}
def exclusion_dict(e):
    return {'id':e.id,'dataset_id':e.dataset_id,'run':e.run,'reason':e.reason,'active':e.active,'created_at':e.created_at,'restored_at':e.restored_at}
