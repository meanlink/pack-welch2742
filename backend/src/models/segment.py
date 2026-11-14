from sqlalchemy import String, Double, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class SegmentExclusion(Base):
    """秒表故障片段的隔离记录；同一批次同一 run 同时只允许一条生效记录。"""
    __tablename__ = 'segment_exclusions'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'))
    run: Mapped[str] = mapped_column(String(160))
    reason: Mapped[str] = mapped_column(String(500))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    restored_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    restored_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
