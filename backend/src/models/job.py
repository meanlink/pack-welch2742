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
    # 任务实际使用的输入快照指纹（已剔除当时隔离片段）
    input_checksum: Mapped[str] = mapped_column(String(64), default='')
    # 输入片段被隔离后，旧结论整体失效；恢复片段且指纹重新匹配后可回到有效
    invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid_reason: Mapped[str] = mapped_column(String(500), default='')
    # 统一重算批次键与来源任务；普通任务为空
    recompute_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_job_id: Mapped[int | None] = mapped_column(ForeignKey('jobs.id'), nullable=True)
