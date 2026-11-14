from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from src.config.database import get_db
from src.models import Job, RecalcGroup
from src.schemas.job import JobInput
from src.schemas.recalc import RecalcRetry, RecalcApprove
from src.middlewares.auth import current_user, can_write, admin_only
from src.services import jobs, quarantine
from src.services.quarantine import evaluate_group
from src.services.audit import record
from src.utils.serialization import job_dict, recalc_dict
router=APIRouter(prefix='/jobs')
@router.get('')
def listing(db=Depends(get_db),u=Depends(current_user)):
    return [job_dict(j) for j in db.scalars(select(Job).order_by(Job.id.desc()).limit(100))]
# 固定路径必须声明在 /{id} 之前，否则会被详情路由吞掉
@router.get('/recalc/groups')
def recalc_groups(dataset_id:int|None=None,db=Depends(get_db),u=Depends(current_user)):
    stmt=select(RecalcGroup).order_by(RecalcGroup.id.desc())
    if dataset_id is not None:
        stmt=stmt.where(RecalcGroup.dataset_id==dataset_id)
    groups=list(db.scalars(stmt.limit(100)))
    out=[]
    for g in groups:
        members=[job_dict(j) for j in db.scalars(select(Job).where(Job.recalc_group_id==g.id))]
        item=recalc_dict(g); item['jobs']=members
        out.append(item)
    return out
@router.post('/recalc/{group_id}/retry')
def recalc_retry(group_id:int,data:RecalcRetry,db=Depends(get_db),u=Depends(can_write)):
    group,retried=quarantine.retry_group(db,group_id,u)
    db.commit()
    return {'group':recalc_dict(group),'retried_job_ids':retried}
@router.post('/recalc/{group_id}/switch')
def recalc_switch(group_id:int,data:RecalcApprove,db=Depends(get_db),u=Depends(admin_only)):
    group,switched=quarantine.approve_and_switch(db,group_id,u)
    db.commit()
    return {'group':recalc_dict(group),'switched_report_ids':switched}
@router.post('',status_code=201)
def create(data:JobInput,db=Depends(get_db),u=Depends(can_write)):
    j=jobs.create(db,data,u); record(db,u.email,'job.create',{'id':j.id,'params':j.params,'input_runs':j.input_runs})
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
    if j.status=='invalid': raise HTTPException(409,'该结论已因片段隔离失效，不能批准；请批准重算后的新结论')
    if j.status!='completed':raise HTTPException(409,'仅已完成结果可以批准')
    j.approved=True; record(db,u.email,'job.approve',{'id':id})
    # 若属于重算组，批准后评估组状态（全部完成并批准才进入待切换）
    if j.recalc_group_id is not None:
        group=db.get(RecalcGroup,j.recalc_group_id)
        if group: evaluate_group(db,group)
    db.commit()
    return job_dict(j)
