from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from src.config.database import get_db
from src.middlewares.auth import current_user
from src.models import Dataset, Job, Report, Audit, Quarantine
from src.services.business import metadata
from src.services import traceability as trace
router=APIRouter()
@router.get('/meta')
def meta():return metadata()
@router.get('/overview')
def overview(db=Depends(get_db),user=Depends(current_user)):
    datasets=list(db.scalars(select(Dataset)))
    records=sum(len(trace.effective_records(db,d)) for d in datasets)
    return {'datasets':len(datasets),
            'records':records,
            'jobs':db.scalar(select(func.count()).select_from(Job)),
            'approved':db.scalar(select(func.count()).select_from(Job).where(Job.approved==True)),
            'invalid_jobs':db.scalar(select(func.count()).select_from(Job).where(Job.status=='invalid')),
            'active_quarantines':db.scalar(select(func.count()).select_from(Quarantine).where(Quarantine.status=='active')),
            'held_reports':db.scalar(select(func.count()).select_from(Report).where(Report.hold_reason!='')),
            'reports':db.scalar(select(func.count()).select_from(Report))}
@router.get('/audits')
def audits(db=Depends(get_db),user=Depends(current_user)):
    return [{'id':a.id,'actor':a.actor,'action':a.action,'detail':a.detail,'at':a.at} for a in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(50))]
