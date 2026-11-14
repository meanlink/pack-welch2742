"""受影响分析的统一重算。

一次操作给每个受影响（失效）分析按原参数、原批次建立重算任务，归入同一
recompute_key 批次：不重复建分析、不漏掉计划。全部重算完成且逐一获批准后，
关联的分发计划才统一切换到新结果；中途失败只暂停分发，重试在同一批次内补齐。
"""
import time, uuid
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Dataset, Job, Report
from src.services.quarantine import job_input_checksum
from src.services.audit import record


def _recompute_key():
    return 'rc-' + uuid.uuid4().hex[:24]


def recompute_affected(db, dataset_id, user, reason):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    sources = list(db.scalars(select(Job).where(Job.dataset_id == dataset_id, Job.invalid == True)))
    if not sources:
        raise HTTPException(409, '该批次当前没有受隔离影响而失效的分析，无需重算')
    key = _recompute_key()
    created, skipped = [], []
    for src in sources:
        # 同一来源任务已存在重算结果时不重复建分析（失败可在原批次内重试）
        existing = db.scalar(select(Job).where(Job.source_job_id == src.id,
                                               Job.recompute_key != None))
        if existing:
            skipped.append(src.id)
            continue
        checksum_value = job_input_checksum(db, Job(dataset_id=dataset.id, params=src.params), dataset)
        j = Job(name=src.name + ' · 隔离后重算', dataset_id=src.dataset_id, params=dict(src.params),
                created_by=user.id, created_at=time.time(), status='queued',
                input_checksum=checksum_value, recompute_key=key, source_job_id=src.id)
        db.add(j); db.flush()
        created.append(j.id)
    record(db, user.email, 'job.recompute',
           {'dataset': dataset_id, 'key': key, 'created': created, 'skipped': skipped, 'reason': reason})
    db.commit()
    # 提交后再入 Redis 队列；SQL queued 状态本身是持久兜底
    from src.services.jobs import enqueue
    for jid in created:
        enqueue(jid)
    return {'recompute_key': key, 'created_job_ids': created, 'skipped_source_ids': skipped}


def groups(db):
    rows = list(db.scalars(select(Job).where(Job.recompute_key != None).order_by(Job.id.desc())))
    out = {}
    for j in rows:
        g = out.setdefault(j.recompute_key, {'recompute_key': j.recompute_key, 'total': 0,
                                             'completed': 0, 'failed': 0, 'pending': 0,
                                             'approved': 0, 'switched': False, 'jobs': []})
        g['total'] += 1
        if j.status == 'completed':
            g['completed'] += 1
            if j.approved:
                g['approved'] += 1
        elif j.status == 'failed':
            g['failed'] += 1
        else:
            g['pending'] += 1
        g['jobs'].append({'id': j.id, 'name': j.name, 'status': j.status,
                          'approved': j.approved, 'invalid': j.invalid,
                          'source_job_id': j.source_job_id})
        if j.invalid:
            g['switched'] = False
    for g in out.values():
        # 关联计划已全部指向本批次，即切换完成
        key = g['recompute_key']
        g['switched'] = g['total'] > 0 and g['total'] == g['approved'] and g['failed'] == 0 and g['pending'] == 0 \
            and db.scalar(select(Report).where(Report.recompute_key == key)) is not None
        g['ready_to_switch'] = g['total'] == g['approved'] and g['failed'] == 0 and g['pending'] == 0
    return sorted(out.values(), key=lambda g: g['recompute_key'], reverse=True)


def retry_group(db, key, user):
    jobs = list(db.scalars(select(Job).where(Job.recompute_key == key)))
    if not jobs:
        raise HTTPException(404, '重算批次不存在')
    retried = []
    for j in jobs:
        if j.status == 'failed' and not j.invalid:
            j.status = 'queued'
            j.error = ''
            j.finished_at = None
            retried.append(j.id)
    db.flush()
    if not retried:
        raise HTTPException(409, '该批次没有可重试的失败任务')
    record(db, user.email, 'job.recompute.retry', {'key': key, 'retried': retried})
    db.commit()
    from src.services.jobs import enqueue
    for jid in retried:
        enqueue(jid)
    return {'recompute_key': key, 'retried_job_ids': retried}


def switch_all_ready(db):
    """兜底：把所有已全部完成并批准的批次切到新结果（worker 周期调用）。"""
    keys = [g['recompute_key'] for g in groups(db) if g.get('ready_to_switch') and not g.get('switched')]
    return [k for k in keys if switch_group_if_ready(db, k)]


def switch_group_if_ready(db, key):
    """全部重算完成并批准后，把关联分发计划统一切到新结果。"""
    jobs = list(db.scalars(select(Job).where(Job.recompute_key == key)))
    if not jobs:
        return False
    if any(j.status != 'completed' or not j.approved or j.invalid for j in jobs):
        return False
    by_source = {j.source_job_id: j.id for j in jobs}
    switched = []
    for source_id, new_id in by_source.items():
        for r in db.scalars(select(Report).where(Report.job_id == source_id)):
            r.job_id = new_id
            r.recompute_key = key
            r.suspended = False
            r.suspended_reason = ''
            r.next_run = min(r.next_run, time.time())
            switched.append(r.id)
    if switched:
        record(db, 'system', 'report.switched', {'key': key, 'reports': switched})
        db.commit()
    return bool(switched)
