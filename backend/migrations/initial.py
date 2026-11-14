from sqlalchemy import inspect, text, select
from src.config.database import Base, engine
from src import models

# 旧库增量列：列名 -> 建列 DDL 片段（MySQL 与 SQLite 均兼容的通用类型写法）
_ADDED_COLUMNS = {
    'jobs': [
        ('input_runs', 'JSON NULL'),
        ('invalidated_reason', "VARCHAR(500) NOT NULL DEFAULT ''"),
        ('recalc_group_id', 'INT NULL'),
        ('supersedes_job_id', 'INT NULL'),
    ],
    'reports': [
        ('hold_reason', "VARCHAR(500) NOT NULL DEFAULT ''"),
        ('recalc_group_id', 'INT NULL'),
    ],
    'deliveries': [
        ('invalid', "BOOLEAN NOT NULL DEFAULT 0"),
        ('invalid_reason', "VARCHAR(500) NOT NULL DEFAULT ''"),
    ],
}

def _add_missing_columns():
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, columns in _ADDED_COLUMNS.items():
            if table not in existing_tables:
                continue
            present = {col['name'] for col in inspector.get_columns(table)}
            for name, ddl in columns:
                if name not in present:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {ddl}'))

def _backfill_input_runs():
    """旧任务没有 input_runs 快照：按其参数口径从批次原始记录回溯实际使用片段，
    保证故障片段影响面追溯对历史分析同样有效。"""
    from src.config.database import Session
    from src.models import Dataset, Job
    from src.services.traceability import runs_for
    with Session() as db:
        datasets = {d.id: d for d in db.scalars(select(Dataset))}
        changed = False
        for j in db.scalars(select(Job).where(Job.input_runs == None)):  # noqa: E711
            d = datasets.get(j.dataset_id)
            if d is None:
                continue
            j.input_runs = runs_for(d.records, j.params)
            changed = True
        if changed:
            db.commit()

def migrate():
    Base.metadata.create_all(engine)
    _add_missing_columns()
    _backfill_input_runs()

if __name__ == '__main__':
    migrate()
