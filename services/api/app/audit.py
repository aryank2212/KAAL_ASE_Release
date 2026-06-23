from uuid import UUID

from sqlalchemy.orm import Session

from app.models import AuditEvent


def audit(
    db: Session,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    case_id: UUID | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(
        AuditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            case_id=case_id,
            metadata_json=metadata or {},
        )
    )

