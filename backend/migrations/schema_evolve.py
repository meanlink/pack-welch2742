"""片段隔离与统一重算所需的增量结构。

项目使用 Base.metadata.create_all 建表（新表自动创建）；对已存在的旧表，
这里用可重入的 ALTER TABLE 补齐新列，支持 MySQL 与 SQLite，默认值保证旧行可用。
"""
from sqlalchemy import inspect, text
from sqlalchemy.types import String, Double, Boolean, Integer

# (表, 列, 类型, 非空, SQL 字面量默认值；可空列为 None)
SPECS = [
    ('jobs', 'input_checksum', String(64), False, "''"),
    ('jobs', 'invalid', Boolean(), False, '0'),
    ('jobs', 'invalid_reason', String(500), False, "''"),
    ('jobs', 'recompute_key', String(40), True, None),
    ('jobs', 'source_job_id', Integer(), True, None),
    ('reports', 'suspended', Boolean(), False, '0'),
    ('reports', 'suspended_reason', String(500), False, "''"),
    ('reports', 'recompute_key', String(40), True, None),
    ('deliveries', 'invalid', Boolean(), False, '0'),
    ('deliveries', 'invalid_reason', String(500), False, "''"),
]


def evolve(engine):
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    table_columns = {}
    with engine.begin() as conn:
        for table, column, col_type, nullable, default_literal in SPECS:
            if table not in existing_tables:
                continue  # 新表由 create_all 按最新模型创建
            if table not in table_columns:
                table_columns[table] = {c['name'] for c in inspector.get_columns(table)}
            if column in table_columns[table]:
                continue
            type_sql = col_type.compile(dialect=engine.dialect)
            ddl = f'ALTER TABLE {table} ADD COLUMN {column} {type_sql}'
            if not nullable:
                ddl += f' NOT NULL DEFAULT {default_literal}'
            conn.execute(text(ddl))
