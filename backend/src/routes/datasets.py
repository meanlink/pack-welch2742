from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Dataset, Quarantine
from src.schemas.dataset import DatasetInput
from src.schemas.quarantine import QuarantineInput, RestoreInput
from src.middlewares.auth import current_user, can_write
from src.services import datasets, quarantine
from src.services import traceability as trace
from src.services.audit import record
from src.utils.serialization import dataset_dict, quarantine_dict
router=APIRouter(prefix='/datasets')
def _active_counts(db):
    counts={}
    for q in db.scalars(select(Quarantine).where(Quarantine.status=='active')):
        counts[q.dataset_id]=counts.get(q.dataset_id,0)+1
    return counts
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    counts=_active_counts(db)
    return [dataset_dict(d,counts.get(d.id,0)) for d in db.scalars(select(Dataset).order_by(Dataset.id.desc()))]
@router.post('',status_code=201)
def create(data:DatasetInput,db=Depends(get_db),u=Depends(can_write)):
    d=datasets.create(db,data); record(db,u.email,'dataset.create',{'id':d.id,'rows':len(d.records)})
    db.commit(); return dataset_dict(d)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    d=db.get(Dataset,id)
    if not d:raise HTTPException(404,'数据批次不存在')
    excluded=trace.excluded_runs(db,id)
    return {**dataset_dict(d,len(excluded)),'records':d.records,'excluded_runs':sorted(excluded)}
@router.get('/{id}/quarantines')
def quarantines(id:int,db=Depends(get_db),u=Depends(current_user)):
    if not db.get(Dataset,id):raise HTTPException(404,'数据批次不存在')
    return [quarantine_dict(q) for q in quarantine.list_quarantines(db,id)]
@router.post('/{id}/quarantines',status_code=201)
def isolate(id:int,data:QuarantineInput,db=Depends(get_db),u=Depends(can_write)):
    q,group,roots,replacement_ids=quarantine.isolate(db,data,id,u)
    db.commit()
    return {'quarantine':quarantine_dict(q),'recalc_group_id':group.id,
            'affected_job_ids':[r.id for r in roots],'replacement_job_ids':replacement_ids}
@router.post('/quarantines/{qid}/restore')
def restore(qid:int,data:RestoreInput,db=Depends(get_db),u=Depends(can_write)):
    q,group,roots,replacement_ids=quarantine.restore(db,data,qid,u)
    db.commit()
    return {'quarantine':quarantine_dict(q),'recalc_group_id':group.id,
            'affected_job_ids':[r.id for r in roots],'replacement_job_ids':replacement_ids}
@router.post('/{id}/impact-preview')
def impact(id:int,payload:QuarantineInput,db=Depends(get_db),u=Depends(current_user)):
    return quarantine.impact_preview(db,id,[payload.run.strip()])
