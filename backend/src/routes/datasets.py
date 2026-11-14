from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset, Job
from src.schemas.dataset import DatasetInput, ExclusionInput, ExclusionBatchInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import datasets
from src.services import quarantine as qservice
from src.services.quarantine import active_records, used_records
from src.services.audit import record
from src.utils.serialization import dataset_dict, exclusion_dict
router=APIRouter(prefix='/datasets')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [dataset_dict(d) for d in db.scalars(select(Dataset).order_by(Dataset.id.desc()))]
@router.post('',status_code=201)
def create(data:DatasetInput,db=Depends(get_db),u=Depends(can_write)):
    d=datasets.create(db,data); record(db,u.email,'dataset.create',{'id':d.id,'rows':len(d.records)})
    db.commit(); return dataset_dict(d)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    d=db.get(Dataset,id)
    if not d:raise HTTPException(404,'数据批次不存在')
    blocked={e.run:e for e in qservice.active_exclusions(db,id)}
    records=[]
    for row in d.records:
        marked=dict(row)
        marked['excluded']=str(row.get('run')) in blocked
        records.append(marked)
    return {**dataset_dict(d),'records':records,
            'exclusions':[exclusion_dict(e) for e in
                          db.scalars(select(qservice.SegmentExclusion)
                                     .where(qservice.SegmentExclusion.dataset_id==id)
                                     .order_by(qservice.SegmentExclusion.id.desc()))]}
@router.get('/{id}/impact')
def impact(id:int, runs:str, db=Depends(get_db),u=Depends(current_user)):
    """隔离前预览：按任务实际使用片段追溯受影响分析，不做任何变更。"""
    d=db.get(Dataset,id)
    if not d:raise HTTPException(404,'数据批次不存在')
    wanted={r.strip() for r in runs.split(',') if r.strip()}
    known={str(r.get('run')) for r in d.records}
    missing=sorted(wanted-known)
    if missing:raise HTTPException(422,'片段不存在于该批次：'+', '.join(missing))
    jobs=list(db.scalars(select(Job).where(Job.dataset_id==id)))
    affected=[]
    for j in jobs:
        used={str(r.get('run')) for r in used_records(active_records(db,d),j.params)}
        if wanted & used:
            affected.append({'id':j.id,'name':j.name,'status':j.status,'approved':j.approved,
                             'invalid':j.invalid,'shift':j.params.get('shift','全部')})
    return {'runs':sorted(wanted),'affected_jobs':affected}
@router.post('/{id}/exclusions',status_code=201)
def quarantine(id:int,data:ExclusionInput,db=Depends(get_db),u=Depends(admin_only)):
    result=qservice.quarantine(db,id,[data.run],data.reason,u)
    return result
@router.post('/{id}/exclusions/batch',status_code=201)
def quarantine_batch(id:int,data:ExclusionBatchInput,db=Depends(get_db),u=Depends(admin_only)):
    result=qservice.quarantine(db,id,data.runs,data.reason,u)
    return result
@router.post('/exclusions/{exclusion_id}/restore')
def restore(exclusion_id:int,db=Depends(get_db),u=Depends(admin_only)):
    return qservice.restore(db,exclusion_id,u)
