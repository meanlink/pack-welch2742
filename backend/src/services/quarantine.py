"""故障片段隔离/恢复与受影响分析的统一重算编排。"""
import time
from fastapi import HTTPException
from sqlalchemy import select
from src.models import Dataset, Job, Quarantine, RecalcGroup, Report, Delivery
from src.services.audit import record
from src.services import traceability as trace
from src.services.jobs import enqueue
from src.services.reports import mark_file_invalid

# 重算组终态：不再参与新的样本事件
_CLOSED_STATUSES = ('switched', 'cancelled')


def _validate_run(dataset, run):
    known = {str(r.get('run')) for r in dataset.records}
    if run not in known:
        raise HTTPException(422, f'片段 {run} 不在该数据批次中，请核对片段号')


def impact_preview(db, dataset_id, runs):
    """隔离/恢复前的影响面预览：仅按实际使用片段追溯。"""
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    jobs = trace.jobs_using_runs(db, dataset_id, runs)
    items, report_ids, delivery_ids = [], set(), set()
    for j in jobs:
        root = trace.root_job(db, j)
        for r in trace.reports_for_root(db, root.id):
            report_ids.add(r.id)
            for d in db.scalars(select(Delivery).where(Delivery.report_id == r.id)):
                delivery_ids.add(d.id)
        items.append({'job_id': j.id, 'name': j.name, 'status': j.status,
                      'approved': j.approved, 'supersedes_job_id': j.supersedes_job_id,
                      'recalc_group_id': j.recalc_group_id})
    return {'dataset_id': dataset_id, 'runs': sorted(set(runs)), 'jobs': items,
            'report_ids': sorted(report_ids), 'delivery_ids': sorted(delivery_ids)}


def _cancel_open_groups(db, dataset_id):
    """新样本事件接管前，把同批次未终结的重算组标记为被取代。"""
    cancelled = []
    for g in db.scalars(select(RecalcGroup).where(RecalcGroup.dataset_id == dataset_id)):
        if g.status not in _CLOSED_STATUSES:
            g.status = 'cancelled'
            cancelled.append(g)
    return cancelled


def _invalidate_pending_replacements(db, cancelled_groups):
    """被取代重算组里尚未产出可用结论的重算任务直接作废，避免重复计算。"""
    if not cancelled_groups:
        return []
    group_ids = [g.id for g in cancelled_groups]
    invalidated = []
    for j in db.scalars(select(Job).where(Job.recalc_group_id.in_(group_ids))):
        if j.status in ('queued', 'running', 'failed'):
            j.status = 'invalid'
            j.error = '样本口径再次变更，本次重算被新的重算组取代'
            j.invalidated_reason = j.error
            j.finished_at = time.time()
            invalidated.append(j)
    return invalidated


def _relink_held_reports(db, old_group_ids, new_group):
    """连续样本事件时，把仍在暂停的计划从旧重算组改挂到新组，
    保证最终切换不会漏掉计划。"""
    if not old_group_ids:
        return
    for r in db.scalars(select(Report).where(Report.recalc_group_id.in_(old_group_ids),
                                             Report.hold_reason != '')):
        r.recalc_group_id = new_group.id
        r.enabled = False
        r.hold_reason = f'样本口径再次变更，继续暂停分发，等待新重算组 #{new_group.id} 批准切换：{new_group.reason}'


def _replacement_name(db, root):
    base = root.name
    candidate = base + ' · 重算'
    suffix = 2
    existing = {j.name for j in db.scalars(select(Job).where(Job.dataset_id == root.dataset_id))}
    while candidate in existing:
        candidate = f'{base} · 重算 {suffix}'
        suffix += 1
    return candidate


def apply_sample_event(db, dataset_id, runs, reason, user, kind):
    """样本成员变更（隔离/恢复）的统一处理：失效旧结论、暂停分发、统一重算。

    kind='quarantine'：片段被隔离，runs 为新隔离片段；
    kind='restore'：片段恢复可用，runs 为恢复片段。
    """
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    runs = sorted(set(runs))
    for run in runs:
        _validate_run(dataset, run)

    affected = trace.jobs_using_runs(db, dataset_id, runs)
    # 根分析去重（同一替代链只重算一次，避免重复建分析）
    roots, seen_roots = [], set()
    for j in affected:
        root = trace.root_job(db, j)
        if root.id not in seen_roots:
            seen_roots.add(root.id)
            roots.append(root)

    cancelled_groups = _cancel_open_groups(db, dataset_id)
    dead = _invalidate_pending_replacements(db, cancelled_groups)

    group = RecalcGroup(dataset_id=dataset_id, reason=reason, status='running',
                        triggered_by=user.id, created_at=time.time(), quarantine_runs=runs)
    db.add(group)
    db.flush()
    _relink_held_reports(db, [g.id for g in cancelled_groups], group)

    now = time.time()
    event_label = '片段隔离' if kind == 'quarantine' else '片段恢复'
    replacement_ids = []
    for root in roots:
        chain = trace.chain_jobs(db, root)
        # 链上仍可能被当作可用结论的任务一律失效；排队/运行中的旧计算不能变成可用结果
        for j in chain:
            if j.status != 'invalid':
                j.status = 'invalid'
                j.approved = False
                j.invalidated_reason = f'{event_label}（{", ".join(runs)}）：{reason}'
                if j.finished_at is None:
                    j.finished_at = now
        # 暂停链上分发计划，并把已发文件标明失效（文件本身保留）
        for r in trace.reports_for_root(db, root.id):
            r.enabled = False
            r.hold_reason = f'{event_label}导致原结论失效，暂停分发，等待统一重算批准：{reason}'
            r.recalc_group_id = group.id
            for d in db.scalars(select(Delivery).where(Delivery.report_id == r.id,
                                                        Delivery.invalid == False)):  # noqa: E712
                d.invalid = True
                d.invalid_reason = f'依据片段已被{event_label[2:]}（{", ".join(runs)}），本归档结论失效，仅留档备查'
                db.flush()
                mark_file_invalid(d)
        # 每个受影响分析建立一个重算任务，沿用原参数与创建人，绝不重复建分析
        rep = Job(name=_replacement_name(db, root), dataset_id=dataset_id,
                  params=dict(root.params), status='queued', created_by=root.created_by,
                  created_at=now, recalc_group_id=group.id, supersedes_job_id=root.id,
                  invalidated_reason='')
        db.add(rep)
        db.flush()
        replacement_ids.append(rep.id)
        enqueue(rep.id)

    record(db, user.email,
           'quarantine.isolate' if kind == 'quarantine' else 'quarantine.restore',
           {'dataset_id': dataset_id, 'runs': runs, 'reason': reason,
            'recalc_group_id': group.id, 'affected_roots': [r.id for r in roots],
            'replacement_jobs': replacement_ids,
            'cancelled_groups': [g.id for g in cancelled_groups],
            'invalidated_jobs': [j.id for j in dead]})
    return group, roots, replacement_ids


def isolate(db, data, dataset_id, user):
    run = data.run.strip()
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    _validate_run(dataset, run)
    exists = db.scalar(select(Quarantine).where(Quarantine.dataset_id == dataset_id,
                                                Quarantine.run == run,
                                                Quarantine.status == 'active'))
    if exists:
        raise HTTPException(409, f'片段 {run} 已处于隔离状态，请勿重复隔离')
    q = Quarantine(dataset_id=dataset_id, run=run, reason=data.reason.strip(),
                   status='active', created_by=user.id, created_at=time.time())
    db.add(q)
    db.flush()
    group, roots, replacement_ids = apply_sample_event(
        db, dataset_id, [run], data.reason.strip(), user, 'quarantine')
    q.recalc_group_id = group.id
    return q, group, roots, replacement_ids


def restore(db, data, qid, user):
    q = db.get(Quarantine, qid)
    if not q:
        raise HTTPException(404, '隔离记录不存在')
    if q.status != 'active':
        raise HTTPException(409, '该片段已恢复，无需重复操作')
    q.status = 'restored'
    q.restored_at = time.time()
    q.restored_by = user.id
    q.restore_reason = data.reason.strip()
    group, roots, replacement_ids = apply_sample_event(
        db, q.dataset_id, [q.run], f'恢复片段 {q.run}：{data.reason.strip()}', user, 'restore')
    return q, group, roots, replacement_ids


def list_quarantines(db, dataset_id):
    return list(db.scalars(select(Quarantine)
                           .where(Quarantine.dataset_id == dataset_id)
                           .order_by(Quarantine.id.desc())))


def retry_group(db, group_id, user):
    """失败后接着完成：只重试失败的重算任务，已完成/排队的不重复提交。"""
    group = db.get(RecalcGroup, group_id)
    if not group:
        raise HTTPException(404, '重算组不存在')
    if group.status in _CLOSED_STATUSES:
        raise HTTPException(409, '该重算组已终结，不能再重试')
    retried = []
    for j in db.scalars(select(Job).where(Job.recalc_group_id == group.id)):
        if j.status == 'failed':
            j.status = 'queued'
            j.error = ''
            j.finished_at = None
            db.flush()
            enqueue(j.id)
            retried.append(j.id)
    record(db, user.email, 'recalc.retry', {'group_id': group.id, 'jobs': retried,
                                            'note': '重试失败的重算任务'})
    return group, retried


def evaluate_group(db, group):
    """重算组状态机评估，由 worker 在任务完成后调用。"""
    if group.status in _CLOSED_STATUSES:
        return group
    jobs = list(db.scalars(select(Job).where(Job.recalc_group_id == group.id)))
    if any(j.status == 'failed' for j in jobs):
        return group  # 中途失败：保持运行态，暂停分发，等待重试接着完成
    if any(j.status in ('queued', 'running') for j in jobs):
        return group
    if jobs and all(j.status == 'completed' and j.approved for j in jobs):
        group.status = 'waiting_approval'
    return group


def approve_and_switch(db, group_id, user):
    """全部算完并获批准后，才把简报统一切换到新结果。"""
    group = db.get(RecalcGroup, group_id)
    if not group:
        raise HTTPException(404, '重算组不存在')
    if group.status in _CLOSED_STATUSES:
        raise HTTPException(409, '该重算组已终结')
    jobs = list(db.scalars(select(Job).where(Job.recalc_group_id == group.id)))
    if not jobs:
        raise HTTPException(409, '重算组内没有分析任务')
    pending = [j.id for j in jobs if not (j.status == 'completed' and j.approved)]
    if pending:
        raise HTTPException(409, f'仍有重算结果未完成或未获批准：{pending}；中途失败请先重试')
    now = time.time()
    group.status = 'switched'
    group.switched_at = now
    switched = []
    # 重算组关联的暂停计划全部改绑新任务并恢复分发
    for r in db.scalars(select(Report).where(Report.recalc_group_id == group.id)):
        rep = next((j for j in jobs if trace.root_job(db, j).id
                    == trace.root_job(db, db.get(Job, r.job_id)).id), None)
        if rep is None:
            continue
        r.job_id = rep.id
        r.enabled = True
        r.hold_reason = ''
        # 保持原节奏：若暂停期间已到期，恢复后尽快补发一次
        if r.next_run < now:
            r.next_run = now
        switched.append(r.id)
    record(db, user.email, 'recalc.switch', {'group_id': group.id, 'reports': switched})
    return group, switched
