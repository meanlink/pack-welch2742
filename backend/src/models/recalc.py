from sqlalchemy import String, Double, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base
class RecalcGroup(Base):
    __tablename__ = 'recalc_groups'
    id: Mapped[int] = mapped_column(primary_key=True)
    dataset_id: Mapped[int] = mapped_column(ForeignKey('datasets.id'), index=True)
    reason: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(30), default='running', index=True)
    triggered_by: Mapped[int] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[float] = mapped_column(Double)
    switched_at: Mapped[float | None] = mapped_column(Double, nullable=True)
    quarantine_runs: Mapped[list] = mapped_column(JSON, default=list)
