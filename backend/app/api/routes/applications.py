from uuid import UUID

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession, PremiumUser
from app.models.application import Application, ApplicationStatus
from app.schemas.application import ApplicationCreate, ApplicationResponse, ApplicationUpdate, DashboardSummary

# The application tracker is a PREMIUM feature. FREE accounts reach the ATS
# pipeline through /quick-scan instead, which needs no application of its own.
router = APIRouter(tags=["applications"])

# The FREE-tier scratch application is an implementation detail of /quick-scan.
# Excluding it here keeps it out of every list, count and lookup, including for
# a user who later upgrades.
TRACKED = Application.is_scratch.is_(False)


def owned_application(application_id: UUID, user_id: UUID, db: DbSession) -> Application:
    application = db.scalar(select(Application).where(Application.id == application_id, Application.user_id == user_id, TRACKED))
    if not application:
        # Do not disclose whether another user's application exists.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def clean_values(payload: ApplicationCreate | ApplicationUpdate, *, partial: bool = False) -> dict:
    values = payload.model_dump(exclude_unset=partial)
    for field in ("company", "role", "location", "job_description"):
        if field in values and isinstance(values[field], str):
            values[field] = values[field].strip() or None
    if "job_url" in values and values["job_url"] is not None:
        values["job_url"] = str(values["job_url"])
    return values


@router.get("/applications", response_model=list[ApplicationResponse])
def list_applications(db: DbSession, current_user: PremiumUser):
    return list(db.scalars(select(Application).where(Application.user_id == current_user.id, TRACKED).order_by(Application.updated_at.desc())).all())


@router.post("/applications", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(payload: ApplicationCreate, db: DbSession, current_user: PremiumUser):
    values = clean_values(payload)
    application = Application(user_id=current_user.id, **values)
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


@router.get("/applications/{application_id}", response_model=ApplicationResponse)
def get_application(application_id: UUID, db: DbSession, current_user: PremiumUser):
    return owned_application(application_id, current_user.id, db)


@router.patch("/applications/{application_id}", response_model=ApplicationResponse)
def update_application(application_id: UUID, payload: ApplicationUpdate, db: DbSession, current_user: PremiumUser):
    application = owned_application(application_id, current_user.id, db)
    for field, value in clean_values(payload, partial=True).items():
        setattr(application, field, value)
    db.commit()
    db.refresh(application)
    return application


@router.delete("/applications/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(application_id: UUID, db: DbSession, current_user: PremiumUser):
    application = owned_application(application_id, current_user.id, db)
    db.delete(application)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: DbSession, current_user: PremiumUser):
    counts = dict(db.execute(select(Application.status, func.count(Application.id)).where(Application.user_id == current_user.id, TRACKED).group_by(Application.status)).all())
    return DashboardSummary(
        total=sum(counts.values()),
        saved=counts.get(ApplicationStatus.SAVED, 0),
        applied=counts.get(ApplicationStatus.APPLIED, 0),
        interviewing=counts.get(ApplicationStatus.INTERVIEWING, 0),
        selected=counts.get(ApplicationStatus.SELECTED, 0),
        offer=counts.get(ApplicationStatus.OFFER, 0),
        offer_declined=counts.get(ApplicationStatus.OFFER_DECLINED, 0),
        rejected=counts.get(ApplicationStatus.REJECTED, 0),
        recent_applications=list(db.scalars(select(Application).where(Application.user_id == current_user.id, TRACKED).order_by(Application.updated_at.desc()).limit(5)).all()),
    )


@router.get("/applications/{application_id}/integrations/ats")
def ats_integration(application_id: UUID, db: DbSession, current_user: CurrentUser):
    owned_application(application_id, current_user.id, db)
    return {"application_id": application_id, "feature": "ats", "allowed": True}


@router.get("/applications/{application_id}/integrations/{feature}")
def premium_integration(application_id: UUID, feature: str, db: DbSession, current_user: PremiumUser):
    if feature not in {"interviews", "skill-gap", "learning", "roadmap", "what-if", "versions"}:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Integration not found")
    owned_application(application_id, current_user.id, db)
    return {"application_id": application_id, "feature": feature, "allowed": True}
