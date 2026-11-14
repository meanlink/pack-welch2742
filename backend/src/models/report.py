from sqlalchemy import String, Double, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Report(Base):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    job_id: Mapped[int] = mapped_column(ForeignKey('jobs.id'))
    destination: Mapped[str] = mapped_column(String(120))
    interval_seconds: Mapped[int]
    next_run: Mapped[float] = mapped_column(Double)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 分发暂停原因（片段隔离导致的失效暂停）；空字符串表示计划本身正常
    hold_reason: Mapped[str] = mapped_column(String(500), default='')
    # 重算切换后绑定的重算组
    recalc_group_id: Mapped[int | None] = mapped_column(ForeignKey('recalc_groups.id'), nullable=True, index=True)
class Delivery(Base):
    __tablename__ = 'deliveries'
    id: Mapped[int] = mapped_column(primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey('reports.id'))
    created_at: Mapped[float] = mapped_column(Double)
    checksum: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(160))
    destination: Mapped[str] = mapped_column(String(120))
    invalid: Mapped[bool] = mapped_column(Boolean, default=False)
    invalid_reason: Mapped[str] = mapped_column(String(500), default='')
