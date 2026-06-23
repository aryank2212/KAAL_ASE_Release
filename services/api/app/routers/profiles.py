from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.audit import audit
from app.database import get_db
from app.models import Case, Profile, ProfileVersion
from app.schemas import ProfileCreate, ProfilePatch, ProfileRead


router = APIRouter()


def profile_snapshot(profile: Profile) -> dict:
    return {
        "profile_id": str(profile.profile_id),
        "case_id": str(profile.case_id),
        "name": profile.name,
        "aliases": profile.aliases,
        "known_locations": profile.known_locations,
        "social_profiles": profile.social_profiles,
        "images": profile.images,
        "documents": profile.documents,
        "timeline": profile.timeline,
        "relationships": profile.relationships,
        "confidence_score": float(profile.confidence_score),
        "risk_score": float(profile.risk_score),
        "source_references": profile.source_references,
        "review_status": profile.review_status,
        "version": profile.version,
    }


@router.post("/cases/{case_id}/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
def create_profile(case_id: UUID, payload: ProfileCreate, db: Session = Depends(get_db)) -> Profile:
    if not db.get(Case, case_id):
        raise HTTPException(status_code=404, detail="Case not found")

    profile = Profile(case_id=case_id, **payload.model_dump())
    db.add(profile)
    db.flush()
    db.add(ProfileVersion(profile_id=profile.profile_id, version=profile.version, profile_snapshot=profile_snapshot(profile)))
    audit(db, action="profile.create", resource_type="profile", resource_id=str(profile.profile_id), case_id=case_id)
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profiles/{profile_id}", response_model=ProfileRead)
def get_profile(profile_id: UUID, db: Session = Depends(get_db)) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.patch("/profiles/{profile_id}", response_model=ProfileRead)
def update_profile(profile_id: UUID, patch: ProfilePatch, db: Session = Depends(get_db)) -> Profile:
    profile = db.get(Profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    updates = patch.model_dump(exclude_unset=True)
    change_reason = updates.pop("change_reason", None)
    for key, value in updates.items():
        setattr(profile, key, value)
    profile.version += 1

    db.flush()
    db.add(
        ProfileVersion(
            profile_id=profile.profile_id,
            version=profile.version,
            profile_snapshot=profile_snapshot(profile),
            change_reason=change_reason,
        )
    )
    audit(
        db,
        action="profile.update",
        resource_type="profile",
        resource_id=str(profile.profile_id),
        case_id=profile.case_id,
        metadata={"updated_fields": sorted(updates.keys()), "change_reason": change_reason},
    )
    db.commit()
    db.refresh(profile)
    return profile

