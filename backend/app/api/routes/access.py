from fastapi import APIRouter

from app.api.deps import CurrentUser, PremiumUser

router = APIRouter(prefix="/access", tags=["access control"])


@router.get("/ats-score")
def ats_score_access(current_user: CurrentUser):
    """Authorization guard for the forthcoming ATS scoring module (FREE and PREMIUM)."""
    return {"allowed": True, "feature": "ats-score", "plan": current_user.plan}


@router.get("/premium")
def premium_feature_access(current_user: PremiumUser):
    """Reusable guard for future resume, interview, and job-search modules."""
    return {"allowed": True, "feature": "premium", "plan": current_user.plan}
