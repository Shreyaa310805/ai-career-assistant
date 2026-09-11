"""Exercise the running app against Razorpay TEST without printing auth or provider keys.

Creates a disposable local smoke account and an unpaid TEST subscription, then cancels it.
Run from backend: python scripts/check_billing_app.py
"""
import secrets
import uuid
import httpx


def main():
    with httpx.Client(base_url='http://localhost:8000/api/v1', timeout=30) as client:
        registration = client.post('/auth/register', json={'name': 'Billing Smoke Test',
            'email': f'billing-smoke-{uuid.uuid4().hex}@example.com', 'password': secrets.token_urlsafe(24)})
        assert registration.status_code == 201, f'Registration status: {registration.status_code}'
        client.headers['Authorization'] = 'Bearer ' + registration.json()['access_token']
        catalog = client.get('/billing/catalog')
        assert catalog.status_code == 200, f'Catalog status: {catalog.status_code}'
        assert catalog.json()['plans'][0]['available']
        trial_headers = {'Idempotency-Key': str(uuid.uuid4())}
        trial = client.post('/practice/interviews', json={}, headers=trial_headers)
        assert trial.status_code == 200, f'Trial status: {trial.status_code}'
        replay = client.post('/practice/interviews', json={}, headers=trial_headers)
        assert replay.json()['data']['interview_id'] == trial.json()['data']['interview_id']
        assert client.get('/interviews/' + trial.json()['data']['interview_id'] + '/report').status_code == 403
        checkout = client.post('/billing/checkout', json={'interval': 'monthly'})
        assert checkout.status_code == 201, f'Checkout status: {checkout.status_code}'
        try:
            replay = client.post('/billing/checkout', json={'interval': 'monthly'})
            assert replay.json()['subscription_id'] == checkout.json()['subscription_id']
            assert client.get('/billing/plan').json()['plan'] == 'FREE'
            print('Running app: signup, catalog, idempotent trial, report gate, TEST checkout creation and reuse passed.')
        finally:
            cancelled = client.post('/billing/cancel')
            assert cancelled.status_code == 200, f'Cancellation status: {cancelled.status_code}'
            assert cancelled.json()['subscription_id'] is None
            print('Unpaid TEST subscription cancelled through the application API.')
        client.post('/auth/logout')


if __name__ == '__main__':
    main()
