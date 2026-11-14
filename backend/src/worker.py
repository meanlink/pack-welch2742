import time, json, logging
from pathlib import Path
from sqlalchemy import select
from redis import Redis
from src.config.database import Session
from src.config.settings import REDIS_URL
from src.models import Job, Dataset, Report
from src.services.business import analyze
from src.services.reports import deliver
from src.services.quarantine import active_records, job_input_checksum, INVALID_PREFIX
from src.services.recompute import switch_all_ready
from src.services.audit import record
logging.basicConfig(level=logging.INFO)
def execute(job_id):
    with Session() as db:
        j=db.get(Job,job_id)
        if not j or j.status!='queued':return
        j.status='running'; db.commit()
        try:
            d=db.get(Dataset,j.dataset_id)
            # 计算只使用剔除隔离片段后的有效记录
            result=analyze(active_records(db,d),j.params)
            json.dumps(result,allow_nan=False)
            db.refresh(j)  # 读取计算期间可能发生的隔离变更
            current=job_input_checksum(db,j,d)
            if j.invalid or j.status!='running' or j.input_checksum!=current:
                # 输入在计算期间被隔离：结果不允许落为可用，保持/补齐失效态
                if not j.invalid:
                    reason=j.invalid_reason or '计算期间输入片段被隔离，旧样本结果作废'
                    j.invalid=True;j.invalid_reason=reason
                    j.status='failed';j.error=(INVALID_PREFIX+reason)[:990];j.finished_at=time.time()
                    for r in db.scalars(select(Report).where(Report.job_id==j.id)):
                        r.suspended=True;r.suspended_reason=reason
                record(db,'worker','job.discarded_stale',{'id':j.id})
                db.commit();return
            j.result=result;j.status='completed';j.finished_at=time.time()
            record(db,'worker','job.completed',{'id':j.id})
        except Exception as e:
            logging.exception('Analysis failed')
            j.status='failed';j.error=str(e)[:990];j.finished_at=time.time()
            record(db,'worker','job.failed',{'id':j.id,'error':j.error})
        db.commit()
def tick():
    with Session() as db:
        queued=list(db.scalars(select(Job.id).where(Job.status=='queued').limit(3)))
    for job_id in queued:execute(job_id)
    with Session() as db:
        # 重算全部完成并批准后自动切换简报；未齐则继续暂停分发
        switch_all_ready(db)
        for r in db.scalars(select(Report).where(Report.enabled==True,Report.next_run<=time.time())):
            d=deliver(db,r)
            if d:record(db,'worker','report.delivered',{'id':r.id,'delivery':d.id})
        db.commit()
def main():
    r=Redis.from_url(REDIS_URL,socket_timeout=3)
    # This Compose stack has a single worker. A crash must not strand its jobs.
    with Session() as db:
        for j in db.scalars(select(Job).where(Job.status=='running')):
            if j.invalid:
                j.status='failed'
                j.error=(j.error or (INVALID_PREFIX+(j.invalid_reason or '输入片段已隔离')))[:990]
                j.finished_at=time.time()
                record(db,'worker','job.invalid_stopped',{'id':j.id})
            else:
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
