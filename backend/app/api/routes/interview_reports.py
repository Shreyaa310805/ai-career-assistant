from uuid import UUID

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.api.deps import DbSession, PremiumUser
from app.api.routes.interviews import _owned_application, _owned_interview
from app.services.interview_reporting import application_report, session_report, report_pdf

router = APIRouter(tags=["interview reports"])


@router.get('/interviews/{interview_id}/report')
def get_session_report(interview_id: UUID, db: DbSession, current_user: PremiumUser):
    interview = _owned_interview(interview_id, current_user.id, db)
    if interview.status != 'completed':
        raise HTTPException(409, 'Complete this interview before viewing its report')
    report = session_report(interview, db)
    report.pop('skill_names')
    return {'success': True, 'data': report, 'error': None}


@router.get('/applications/{application_id}/interview-report')
def get_application_report(application_id: UUID, db: DbSession, current_user: PremiumUser):
    application = _owned_application(application_id, current_user.id, db)
    return {'success': True, 'data': application_report(application, db), 'error': None}


@router.get('/applications/{application_id}/interview-report/pdf')
def download_application_report(application_id: UUID, db: DbSession, current_user: PremiumUser):
    application = _owned_application(application_id, current_user.id, db)
    return Response(report_pdf(application_report(application, db)), media_type='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="SkillSync-interview-report-{application_id}.pdf"',
        'Cache-Control': 'no-store',
    })
