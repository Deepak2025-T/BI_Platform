from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..deps import require_manager
from ..models import AIModel, DataConnection, Report, ReportCategory, ReportTemplate, User

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_manager)])


@router.get("/usage")
def usage(db: Session = Depends(get_db)):
    return {
        "users": db.scalar(select(func.count(User.id))),
        "active_users": db.scalar(select(func.count(User.id)).where(User.is_active.is_(True))),
        "reports": db.scalar(select(func.count(Report.id))),
        "published": db.scalar(select(func.count(Report.id)).where(Report.status == "published")),
        "templates": db.scalar(select(func.count(ReportTemplate.id))),
        "categories": db.scalar(select(func.count(ReportCategory.id))),
        "connections": db.scalar(select(func.count(DataConnection.id))),
        "connections_ok": db.scalar(select(func.count(DataConnection.id)).where(DataConnection.status == "ok")),
        "warnings": settings.setup_warnings(),
        "ai_models": db.scalar(select(func.count(AIModel.id))),
        "ai_models_active": db.scalar(select(func.count(AIModel.id)).where(AIModel.is_active.is_(True))),
    }
