"""样本片段溯源：隔离口径、任务实际使用片段、影响面追溯。"""
from sqlalchemy import select
from src.models import Dataset, Job, Quarantine, Report


def active_quarantines(db, dataset_id):
    return list(db.scalars(
        select(Quarantine).where(Quarantine.dataset_id == dataset_id,
                                 Quarantine.status == 'active').order_by(Quarantine.id)))


def excluded_runs(db, dataset_id):
    return {q.run for q in active_quarantines(db, dataset_id)}


def effective_records(db, dataset):
    """当前有效样本：原始记录剔除处于隔离态的片段。批次原始记录不可变。"""
    excluded = excluded_runs(db, dataset.id)
    if not excluded:
        return list(dataset.records)
    return [r for r in dataset.records if str(r.get('run')) not in excluded]


def runs_for(records, params):
    """按任务参数口径（班次过滤）推导实际参与计算的片段号。"""
    shift = str((params or {}).get('shift', '全部'))
    runs = []
    for r in records:
        if shift == '全部' or r.get('shift') == shift:
            runs.append(str(r.get('run')))
    return runs


def job_input_runs(db, job):
    """任务实际使用片段：优先取计算时快照，旧任务按参数口径回溯。"""
    if job.input_runs:
        return set(job.input_runs)
    dataset = db.get(Dataset, job.dataset_id)
    if not dataset:
        return set()
    return set(runs_for(dataset.records, job.params))


def jobs_using_runs(db, dataset_id, runs):
    """追溯实际用到给定片段的全部任务（含历史失效任务）。"""
    targets = set(runs)
    hits = []
    for j in db.scalars(select(Job).where(Job.dataset_id == dataset_id)):
        if job_input_runs(db, j) & targets:
            hits.append(j)
    return hits


def root_job(db, job):
    """沿替代链找到最初的旧分析。"""
    seen = set()
    cur = job
    while cur.supersedes_job_id and cur.id not in seen:
        seen.add(cur.id)
        parent = db.get(Job, cur.supersedes_job_id)
        if not parent:
            break
        cur = parent
    return cur


def chain_jobs(db, root):
    """同一替代链上的全部任务（根在前）。"""
    out = [root]
    seen = {root.id}
    for child in db.scalars(select(Job).where(Job.supersedes_job_id == root.id)):
        if child.id in seen:
            continue
        seen.add(child.id)
        out.extend(chain_jobs(db, child))
    return out


def reports_for_root(db, root_id):
    """绑定到某条替代链（任一任务）的分发计划。"""
    linked = []
    for r in db.scalars(select(Report)):
        if root_job(db, db.get(Job, r.job_id)).id == root_id:
            linked.append(r)
    return linked
