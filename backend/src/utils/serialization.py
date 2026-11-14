import hashlib, json
def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def dataset_dict(d, active_quarantine_count=0):
    return {'id':d.id, 'name':d.name, 'source':d.source, 'rows':len(d.records),
            'active_records':len(d.records)-active_quarantine_count,
            'quarantine_count':active_quarantine_count,
            'checksum':d.checksum, 'created_at':d.created_at}
def job_dict(j):
    return {k:getattr(j,k) for k in ['id','name','dataset_id','params','status','result','error','approved',
                                     'created_at','finished_at','input_runs','invalidated_reason',
                                     'recalc_group_id','supersedes_job_id']}
def report_dict(r):
    return {k:getattr(r,k) for k in ['id','name','job_id','destination','interval_seconds','next_run',
                                     'enabled','hold_reason','recalc_group_id']}
def delivery_dict(d):
    return {k:getattr(d,k) for k in ['id','report_id','created_at','checksum','filename','destination',
                                     'invalid','invalid_reason']}
def quarantine_dict(q):
    return {k:getattr(q,k) for k in ['id','dataset_id','run','reason','status','created_by','created_at',
                                     'restored_at','restored_by','restore_reason','recalc_group_id']}
def recalc_dict(g):
    return {k:getattr(g,k) for k in ['id','dataset_id','reason','status','triggered_by','created_at',
                                     'switched_at','quarantine_runs']}
