from datetime import datetime, timezone
from uuid import UUID

import fitz
import pytest

from app.db.session import SessionLocal
from app.models.interview import Interview, InterviewQuestion, InterviewAnswer, InterviewAnswerEvaluation, InterviewVisualFrame
from tests.test_auth import client
from tests.test_applications import premium_token_for, token_for
from tests.test_interviews import create_application


def seed(app_id, score=80, completed=True, source='typed', mode='text', evaluated=True, visual=False):
    with SessionLocal() as db:
        interview = Interview(application_id=UUID(app_id), personality='technical', difficulty='medium', mode=mode,
                              status='completed' if completed else 'in_progress', completed_at=datetime.now(timezone.utc) if completed else None)
        db.add(interview); db.flush()
        question = InterviewQuestion(interview_id=interview.id, question_number=1, question='Explain Python APIs.', topic='Python',
                                     question_type='technical', difficulty='medium', expected_skills=['Python', 'API Design'], reason='Tests role skills.')
        db.add(question); db.flush()
        answer = InterviewAnswer(interview_id=interview.id, question_id=question.id, answer_text='I use clear API boundaries.', source=source,
                                 audio_storage_key='private/path.webm' if source == 'voice' else None)
        db.add(answer); db.flush()
        if evaluated:
            db.add(InterviewAnswerEvaluation(answer_id=answer.id, overall_score=score, relevance_score=score, correctness_score=score,
                depth_score=score, clarity_score=score, evidence_score=score, confidence_score=70, confidence_rationale='Decisive phrasing.',
                strengths=['Clear example'], weaknesses=['More depth'], missing_points=[], feedback='Use a deeper example.'))
        if visual:
            db.add(InterviewVisualFrame(interview_id=interview.id, question_id=question.id, face_visible=True, multiple_people=False,
                looking_at_camera=True, engagement_score=80, attentiveness_score=80, composure_score=90, presentation_score=80,
                expression='neutral', observation='Face centered.'))
        db.commit()
        return str(interview.id)


@pytest.mark.parametrize('source,mode,visual', [('typed','text',False),('voice','audio',False),('voice','video',True),('voice','video',False)])
def test_single_session_and_modalities(source, mode, visual):
    headers = premium_token_for(f'report-{source}-{mode}-{visual}@example.com', 'Reporter')
    app_id = create_application(headers)
    interview_id = seed(app_id, source=source, mode=mode, visual=visual)
    report = client.get(f'/api/v1/applications/{app_id}/interview-report', headers=headers).json()['data']
    assert report['completed_session_count'] == 1
    assert report['metrics']['overall_score'] == 80
    assert report['demonstrated_skills'] == ['API Design', 'Python']
    assert report['verbal_confidence']['score'] == (70 if source == 'voice' else None)
    assert report['visual_confidence']['score'] == (90 if visual else None)
    assert 'private/path' not in str(report)
    session = client.get(f'/api/v1/interviews/{interview_id}/report', headers=headers)
    assert session.status_code == 200
    assert session.json()['data']['technical_score'] == 80


def test_multiple_incomplete_unevaluated_and_skill_semantics():
    headers = premium_token_for('report-multiple@example.com', 'Reporter')
    app_id = create_application(headers)
    seed(app_id, score=80)
    seed(app_id, score=40)
    incomplete = seed(app_id, score=0, completed=False)
    seed(app_id, evaluated=False)
    response = client.get(f'/api/v1/applications/{app_id}/interview-report', headers=headers)
    report = response.json()['data']
    assert report['completed_session_count'] == 3
    assert report['total_questions_attempted'] == 3
    assert report['total_questions_evaluated'] == 2
    assert all(v == 60 for k,v in report['metrics'].items() if k != 'confidence_score')
    assert report['skills_needing_improvement'] == ['API Design', 'Python']
    assert client.get(f'/api/v1/interviews/{incomplete}/report', headers=headers).status_code == 409
    pdf = client.get(f'/api/v1/applications/{app_id}/interview-report/pdf', headers=headers)
    assert pdf.status_code == 200 and pdf.headers['content-type'] == 'application/pdf'
    assert 'attachment' in pdf.headers['content-disposition']
    with fitz.open(stream=pdf.content, filetype='pdf') as doc:
        assert 'SkillSync' in doc[0].get_text()


def test_not_assessed_empty_and_authorization():
    owner = premium_token_for('report-owner@example.com', 'Owner')
    other = premium_token_for('report-other@example.com', 'Other')
    free = token_for('report-free@example.com', 'Free')
    app_id = create_application(owner)
    empty = client.get(f'/api/v1/applications/{app_id}/interview-report', headers=owner).json()['data']
    assert empty['metrics']['overall_score'] is None
    assert empty['readiness'] == 'Not assessed'
    interview_id = seed(app_id, evaluated=False)
    report = client.get(f'/api/v1/applications/{app_id}/interview-report', headers=owner).json()['data']
    assert all(s['status'] == 'not_assessed' and s['score'] is None for s in report['skill_evidence'])
    assert report['assessed_skills'] == []
    for suffix in ('interview-report', 'interview-report/pdf'):
        path = f'/api/v1/applications/{app_id}/{suffix}'
        assert client.get(path, headers=other).status_code == 404
        assert client.get(path, headers=free).status_code == 403
        assert client.get(path).status_code == 401
        assert client.get(f'/api/v1/applications/00000000-0000-0000-0000-000000000001/{suffix}', headers=owner).status_code == 404
    assert client.get(f'/api/v1/interviews/{interview_id}/report', headers=other).status_code == 404


def test_long_pdf_wraps_and_paginates():
    from app.services.interview_reporting import report_pdf
    headers = premium_token_for('report-long@example.com', 'Reporter')
    app_id = create_application(headers)
    seed(app_id)
    report = client.get(f'/api/v1/applications/{app_id}/interview-report', headers=headers).json()['data']
    report['generated_at'] = datetime.now(timezone.utc)
    report['per_question_analysis'][0]['feedback'] = 'Long feedback requiring wrapping. ' * 1000
    with fitz.open(stream=report_pdf(report), filetype='pdf') as doc:
        assert len(doc) > 2
        assert 'Long feedback' in ''.join(p.get_text() for p in doc)


def test_completion_preserves_legacy_and_adds_report_fields(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr('app.api.routes.interviews.summarize_interview_for_application', lambda **kwargs: SimpleNamespace(
        summary='A completed interview with a clear example.', recommendation=SimpleNamespace(value='hire')))
    headers = premium_token_for('report-complete@example.com', 'Reporter')
    app_id = create_application(headers)
    interview_id = seed(app_id, completed=False)
    response = client.post(f'/api/v1/interviews/{interview_id}/complete', headers=headers)
    assert response.status_code == 200
    data = response.json()['data']
    assert data['status'] == 'completed' and data['average_score'] == 80
    assert data['overall_score'] == 80 and data['questions_attempted'] == 1
    assert data['application_id'] == app_id and data['report_id'] == interview_id
    assert data['visual_confidence']['status'] == 'not_assessed'
    assert len(data['per_question_analysis']) == 1
    report = client.get(f'/api/v1/interviews/{interview_id}/report', headers=headers).json()['data']
    assert report['overall_score'] == data['overall_score']
    assert report['summary'] == data['summary']
    assert client.get(f'/api/v1/applications/{app_id}/interview-report', headers=headers).json()['data']['completed_session_count'] == 1


def test_answer_weighting_dynamic_sessions_and_default_confidence():
    headers = premium_token_for('report-weighted@example.com', 'Reporter')
    app_id = create_application(headers)
    interview_id = seed(app_id, score=90)
    with SessionLocal() as db:
        q = InterviewQuestion(interview_id=UUID(interview_id), question_number=2, question='Explain database boundaries.', topic='Databases',
                             question_type='technical', difficulty='medium', expected_skills=['SQL'], reason='Tests SQL.')
        db.add(q); db.flush()
        a = InterviewAnswer(interview_id=UUID(interview_id), question_id=q.id, source='typed', answer_text='An example.')
        db.add(a); db.flush()
        db.add(InterviewAnswerEvaluation(answer_id=a.id, overall_score=30, relevance_score=30, correctness_score=30, depth_score=30,
            clarity_score=30, evidence_score=30, confidence_score=50, confidence_rationale='', strengths=[], weaknesses=[], missing_points=[], feedback='More detail required.'))
        db.commit()
    path = f'/api/v1/applications/{app_id}/interview-report'
    before = client.get(path, headers=headers).json()['data']
    assert before['metrics']['overall_score'] == 60
    assert before['metric_observation_counts']['confidence_score'] == 1
    seed(app_id, score=0)
    after = client.get(path, headers=headers).json()['data']
    assert after['metrics']['overall_score'] == 40
    assert after['completed_session_count'] == 2
    assert after['metric_observation_counts']['overall_score'] == 3
