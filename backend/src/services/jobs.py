import time
from fastapi import HTTPException
from redis import Redis
from sqlalchemy import select
from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata
from src.services import traceability as trace
def create(db, data, user):
    dataset=db.get(Dataset,data.dataset_id)
    if not dataset: raise HTTPException(404,'数据批次不存在')
    allowed={p['key']:p for p in metadata().get('parameters',[])}
    if set(data.params)-set(allowed): raise HTTPException(422,'包含未知分析参数')
    params={k:p['default'] for k,p in allowed.items()}
    params.update(data.params)
    for key,p in allowed.items():
        v=params[key]
        if p['type']=='number':
            try:
                v=float(v)
                if not (p.get('min',-1e9)<=v<=p.get('max',1e9)): raise ValueError()
                params[key]=v
            except (ValueError,TypeError): raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options',[])]:
            raise HTTPException(422,f'{p["label"]} 不是有效选项')
    # 新分析始终基于当前有效样本（已剔除隔离片段）；样本不足由算法校验返回可恢复错误
    records=trace.effective_records(db,dataset)
    input_runs=trace.runs_for(records,params)
    j=Job(name=data.name, dataset_id=dataset.id, params=params, created_by=user.id,
          created_at=time.time(), status='queued', input_runs=input_runs)
    db.add(j); db.flush()
    return j
def enqueue(job_id):
    try:
        r=Redis.from_url(REDIS_URL); r.rpush('analysis:queue',job_id); r.close()
    except Exception:
        pass # SQL queued status is the durable fallback
