import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report, RecalcGroup
from src.services.business import analyze
from src.services import traceability as trace
from src.services.quarantine import evaluate_group
from src.services.reports import deliver
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        j.status='running'; db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            # 重算任务按当前有效样本（剔除隔离片段）计算；普通任务沿用其入队时的片段快照口径
            if j.recalc_group_id is not None:
                records=trace.effective_records(db,d)
            else:
                excluded=trace.excluded_runs(db,d.id)
                records=[r for r in d.records if str(r.get('run')) not in excluded]
            result=analyze(records,j.params)
            json.dumps(result,allow_nan=False)
            # 写入结果前再确认一次：排队/运行中的旧计算不能重新变成可用结果
            j=db.get(Job,job_id)
            if j.status=='invalid':
                record(db,'worker','job.discard_stale',{'id':j.id})
                db.commit();return
            j.result=result;j.status='completed';j.finished_at=time.time()
            j.input_runs=trace.runs_for(records,j.params)
            record(db,'worker','job.completed',{'id':j.id})
            if j.recalc_group_id is not None:
                group=db.get(RecalcGroup,j.recalc_group_id)
                if group: evaluate_group(db,group)
        except Exception as e:
            logging.exception('Analysis failed')
            j=db.get(Job,job_id)
            if j.status=='invalid':
                db.commit();return
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def tick():
    with Session() as db:
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    with Session() as db:
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            j.status='queued';record(db,'worker','job.recovered',{'id':j.id})
        db.commit()
    while True:
        Path('/tmp/heartbeat').touch()
        try:
            item=r.blpop('analysis:queue',timeout=1)
            if item:execute(int(item[1]))
            tick()
        except Exception:
            logging.exception('Worker retry');time.sleep(2)
if __name__=='__main__':main()
