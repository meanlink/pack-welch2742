from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Job
from src.schemas.job import JobInput, RecomputeInput
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs
from src.services import recompute as rservice
from src.services.recompute import switch_group_if_ready
from src.services.audit import record
from src.utils.serialization import job_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [job_dict(j) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(200))]
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),u=Depends(can_write)):
    j=jobs.create(db,data,u); record(db,u.email,'job.create',{'id':j.id,'params':j.params})
    db.commit(); jobs.enqueue(j.id); return job_dict(j)
@router.get('/{id}')
def detail(id:int,db=Depends(get_db),u=Depends(current_user)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    return job_dict(j)
@router.post('/{id}/approve')
def approve(id:int,db=Depends(get_db),u=Depends(admin_only)):
    j=db.get(Job,id)
    if not j: raise HTTPException(404,'分析任务不存在')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    if j.invalid:raise HTTPException(409,'该分析依据的片段已隔离，结论已失效；请批准隔离后的重算结果')
    j.approved=True; record(db,u.email,'job.approve',{'id':id}); db.commit()
    # 若它属于某个重算批次，尝试统一切换；未全部批准时保持暂停分发
    if j.recompute_key: switch_group_if_ready(db,j.recompute_key)
    return job_dict(j)
@router.post('/recompute/datasets/{dataset_id}')
def recompute(dataset_id:int,data:RecomputeInput,db=Depends(get_db),u=Depends(can_write)):
    return rservice.recompute_affected(db,dataset_id,u,data.reason)
@router.get('/recompute/groups')
def recompute_groups(db=Depends(get_db),u=Depends(current_user)):
    return rservice.groups(db)
@router.post('/recompute/{key}/retry')
def recompute_retry(key:str,db=Depends(get_db),u=Depends(can_write)):
    return rservice.retry_group(db,key,u)
