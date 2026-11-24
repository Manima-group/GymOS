from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Organization


def next_seq(db: Session, org_id: int, field: str) -> int:
    """Atomic per-tenant counter (invoice/member numbers). Row-locks until the transaction commits."""
    col = getattr(Organization, field)
    return db.execute(update(Organization).where(Organization.id == org_id)
                      .values({field: col + 1}).returning(col)).scalar_one()
