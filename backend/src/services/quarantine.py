"""故障片段隔离、恢复与影响追溯。

影响判定不看批次整体是否变化，而是比对每个任务实际使用样本的指纹：
任务快照 = 批次当前有效片段（剔除全部生效隔离）再按任务班次参数筛选。
因此只隔离某个晚班片段时，使用早班口径的分析不会被误判失效。
"""
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Dataset, Job, Report, Delivery, SegmentExclusion
from src.services.audit import record
from src.utils.serialization import checksum

INVALID_PREFIX = '输入片段已隔离：'


def active_exclusions(db, dataset_id):
    return list(db.scalars(select(SegmentExclusion)
                           .where(SegmentExclusion.dataset_id == dataset_id,
                                  SegmentExclusion.active == True)
                           .order_by(SegmentExclusion.id)))


def excluded_runs(db, dataset_id):
    return {e.run for e in active_exclusions(db, dataset_id)}


def active_records(db, dataset):
    """剔除当前生效隔离片段后的批次记录，保持原始顺序。"""
    blocked = excluded_runs(db, dataset.id)
    if not blocked:
        return list(dataset.records)
    return [r for r in dataset.records if str(r.get('run')) not in blocked]


def used_records(records, params):
    """任务实际参与计算的片段（与 analyze 的班次口径一致）。"""
    shift = str((params or {}).get('shift', '全部'))
    if shift == '全部':
        return list(records)
    return [r for r in records if str(r.get('shift')) == shift]


def job_input_checksum(db, job, dataset=None):
    d = dataset or db.get(Dataset, job.dataset_id)
    return checksum(used_records(active_records(db, d), job.params))


def _reason_text(dataset, runs, reason):
    text = f'批次「{dataset.name}」片段 {", ".join(runs)} 已隔离：{reason}'
    return text[:500]


def invalidate_job(db, job, reason):
    """旧结论标失效并暂停其分发；排队/运行中的旧计算不允许再变成可用结果。"""
    if job.invalid:
        return False
    job.invalid = True
    job.invalid_reason = reason
    if job.status in ('queued', 'running'):
        job.status = 'failed'
        job.error = (INVALID_PREFIX + reason)[:990]
        job.finished_at = time.time()
    for r in db.scalars(select(Report).where(Report.job_id == job.id)):
        r.suspended = True
        r.suspended_reason = reason
        for d in db.scalars(select(Delivery).where(Delivery.report_id == r.id, Delivery.invalid == False)):
            d.invalid = True
            d.invalid_reason = reason
    return True


def recover_job(db, job):
    """片段恢复后，若任务快照与当前有效样本重新一致，则恢复有效并解除暂停。"""
    if not job.invalid:
        return False
    if job.input_checksum != job_input_checksum(db, job):
        return False
    job.invalid = False
    job.invalid_reason = ''
    if job.status == 'failed' and job.error.startswith(INVALID_PREFIX):
        job.status = 'queued'
        job.error = ''
        job.finished_at = None
    for r in db.scalars(select(Report).where(Report.job_id == job.id)):
        r.suspended = False
        r.suspended_reason = ''
        # 已发出的文件即使在片段恢复后也保留失效标记，不做回滚
    return True


def revalidate_dataset(db, dataset, reason):
    """隔离/恢复后逐任务重判：回填旧任务指纹，失效受影响者，恢复重新匹配者。"""
    jobs = list(db.scalars(select(Job).where(Job.dataset_id == dataset.id)))
    affected, recovered = [], []
    for j in jobs:
        if not j.input_checksum:  # 特性上线前的旧任务：原始快照即完整批次
            j.input_checksum = checksum(used_records(dataset.records, j.params))
        current = job_input_checksum(db, j, dataset)
        if j.input_checksum != current:
            if invalidate_job(db, j, reason):
                affected.append(j.id)
        elif recover_job(db, j):
            recovered.append(j.id)
    return affected, recovered


def quarantine(db, dataset_id, runs, reason, user):
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    wanted, seen = [], set()
    for run in runs:
        run = str(run).strip()
        if run and run not in seen:
            seen.add(run)
            wanted.append(run)
    known = {str(r.get('run')) for r in dataset.records}
    missing = [r for r in wanted if r not in known]
    if missing:
        raise HTTPException(422, '片段不存在于该批次：' + ', '.join(missing))
    blocked = excluded_runs(db, dataset_id)
    duplicated = [r for r in wanted if r in blocked]
    if duplicated:
        raise HTTPException(409, '片段已处于隔离状态：' + ', '.join(duplicated))
    now = time.time()
    for run in wanted:
        db.add(SegmentExclusion(dataset_id=dataset_id, run=run, reason=reason,
                                active=True, created_by=user.id, created_at=now))
    db.flush()
    text = _reason_text(dataset, wanted, reason)
    affected, recovered = revalidate_dataset(db, dataset, text)
    record(db, user.email, 'segment.quarantine',
           {'dataset': dataset_id, 'runs': wanted, 'affected_jobs': affected})
    db.commit()
    return {'excluded': wanted, 'affected_job_ids': affected, 'recovered_job_ids': recovered,
            'reason': text}


def restore(db, exclusion_id, user):
    e = db.get(SegmentExclusion, exclusion_id)
    if not e:
        raise HTTPException(404, '隔离记录不存在')
    if not e.active:
        raise HTTPException(409, '该片段此前已恢复，无需重复操作')
    dataset = db.get(Dataset, e.dataset_id)
    e.active = False
    e.restored_at = time.time()
    e.restored_by = user.id
    db.flush()
    reason = f'片段 {e.run} 已恢复，样本回到隔离前口径'[:500]
    affected, recovered = revalidate_dataset(db, dataset, reason)
    record(db, user.email, 'segment.restore',
           {'dataset': e.dataset_id, 'run': e.run, 'recovered_jobs': recovered,
            'still_affected_jobs': affected})
    db.commit()
    return {'exclusion_id': e.id, 'run': e.run, 'recovered_job_ids': recovered,
            'still_affected_job_ids': affected}
