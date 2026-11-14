from sqlalchemy import String, Double, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class Quarantine(Base):
    __tablename__ = 'quarantines'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    run: Mapped[str] = mapped_column(String(160), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), default='active', index=True)
    created_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    restored_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    restored_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'), nullable=True)
    restore_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recalc_group_id: Mapped[int | None] = mapped_column(ForeignKey('recalc_groups.id'), nullable=True)
