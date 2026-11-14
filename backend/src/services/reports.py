import time, os, csv, io, hashlib, json
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Job, Report, Delivery
from src.config.settings import ARTIFACT_DIR
def create(db, data):
    j=db.get(Job,data.job_id)
    if not j or j.status!='completed' or not j.approved:
        raise HTTPException(409,'请先选择已完成且获批准的分析结果')
    r=Report(name=data.name, job_id=j.id, destination=data.destination, interval_seconds=data.interval_seconds, next_run=time.time()+data.delay_seconds, enabled=True)
    db.add(r); db.flush()
    return r
def deliver(db, report):
    # 暂停（含片段隔离导致的失效暂停）的计划不产生新归档
    if not report.enabled or report.hold_reason:
        return
    j=db.get(Job,report.job_id)
    # 失效或未批准的旧结论不能再分发
    if not j or not j.approved or j.status!='completed': return
    out=io.StringIO()
    out.write('\ufeff')
    table=j.result.get('table',{})
    cols=table.get('columns',[])
    writer=csv.writer(out)
    def safe(v):
        if isinstance(v,(int,float)) and not isinstance(v,bool): return v
        text=str(v)
        return "'"+text if text.startswith(('=','+','-','@','\t','\r')) else text
    writer.writerow([safe(c['label']) for c in cols])
    for row in table.get('rows',[]): writer.writerow([safe(row.get(c['key'],'')) for c in cols])
    data=out.getvalue().encode('utf-8')
    delivery=Delivery(report_id=report.id, created_at=time.time(), checksum=hashlib.sha256(data).hexdigest(), filename='', destination=report.destination)
    db.add(delivery); db.flush()
    delivery.filename=f'report-{report.id}-delivery-{delivery.id}.csv'
    os.makedirs(ARTIFACT_DIR,exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR,delivery.filename),'wb') as f:f.write(data)
    with open(os.path.join(ARTIFACT_DIR,delivery.filename+'.json'),'w') as f: json.dump({'job':j.name,'params':j.params,'result':j.result,'checksum':delivery.checksum,'invalid':False},f,ensure_ascii=False,allow_nan=False)
    report.next_run=time.time()+report.interval_seconds
    return delivery
def mark_file_invalid(delivery):
    """已发文件保留在磁盘，仅在 JSON 侧车标明失效（CSV 内容不可变、由校验指纹保护）。"""
    path=os.path.join(ARTIFACT_DIR,delivery.filename+'.json')
    if not os.path.exists(path):
        return
    with open(path) as f:
        payload=json.load(f)
    payload['invalid']=True
    payload['invalid_reason']=delivery.invalid_reason
    with open(path,'w') as f:
        json.dump(payload,f,ensure_ascii=False,allow_nan=False)
