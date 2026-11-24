from sqlalchemy.orm import Session

from app.models import AuditLog


def audit(db: Session, action: str, *, user_id: int | None, org_id: int | None = None,
          entity: str = "", entity_id: object = "", **data) -> None:
    db.add(AuditLog(org_id=org_id, user_id=user_id, action=action, entity=entity,
                    entity_id=str(entity_id), data=data))
