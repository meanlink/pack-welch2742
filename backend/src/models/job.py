from sqlalchemy import String, JSON, Double, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str] = mapped_column(String(1000), default='')
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    finished_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    # 样本溯源：本任务实际参与计算的片段号快照
    input_runs: Mapped[list] = mapped_column(JSON, default=list)
    # 失效链路：invalid 任务由哪次片段隔离触发；重算任务归属哪个重算组、替代哪个旧任务
    invalidated_reason: Mapped[str] = mapped_column(String(500), default='')
    recalc_group_id: Mapped[int | None] = mapped_column(ForeignKey('recalc_groups.id'), nullable=True, index=True)
    supersedes_job_id: Mapped[int | None] = mapped_column(ForeignKey('jobs.id'), nullable=True)
