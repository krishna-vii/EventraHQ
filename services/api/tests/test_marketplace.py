import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException

from app.main import create_app
from app.settings import Settings
from app.auth import SupabaseAuth
from app.inference import HostedAI, InvalidModelAnswer
from app.media import image_extension
from app.payments import Razorpay, verify_webhook, captured_payment
from app.security import RateLimit
from app.catalogue import FIXTURES


@pytest.fixture
def anyio_backend(): return "asyncio"


def client(app): return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000")


def configured(**values):
    return Settings(database_url="postgresql://eventra_app:dummy@127.0.0.1:54322/postgres", supabase_url="http://127.0.0.1:54321", supabase_key="test-publishable", **values)


class DatabaseDouble:
    def __init__(self): self.calls = []
    async def call(self, action, payload=None, actor=None):
        self.calls.append((action,payload,actor))
        if action == "profile": return {"roles": ["organizer"], "profile": {"id":actor}}
        if action == "authorize": return {"authorized":True}
        return {"items":[]}


@pytest.mark.anyio
async def test_unconfigured_accounts_fail_closed_and_never_create_fake_sessions():
    async with client(create_app()) as c:
        assert (await c.get('/api/v1/session')).json() == {'user':None,'configured':False}
        r=await c.post('/api/v1/auth/login',json={'email':'test@example.com','password':'long-enough-password'})
        assert r.status_code==503 and 'set-cookie' not in r.headers
        assert (await c.post('/api/v1/auth/register',json={'display_name':'Test','email':'test@example.com','password':'long-enough-password','role':'admin'})).status_code==422
        for path in ['me','events','saved','artist/me','inquiries','bookings','notifications','admin']:
            assert (await c.get('/api/v1/'+path)).status_code==401


@pytest.mark.anyio
async def test_identity_is_obtained_from_auth_service_not_client_role_headers():
    user_id=str(uuid4());app=create_app(configured());db=DatabaseDouble();app.state.database=db
    async def handler(request):
        assert request.headers['authorization']=='Bearer signed-by-test-provider'
        assert request.url.path=='/auth/v1/user'
        return httpx.Response(200,json={'id':user_id,'email':'member@example.com','user_metadata':{'role':'admin'}})
    app.state.auth.transport=httpx.MockTransport(handler)
    async with client(app) as c:
        r=await c.get('/api/v1/session',headers={'Authorization':'Bearer signed-by-test-provider','X-User-ID':str(uuid4()),'X-Role':'admin'})
        assert r.status_code==200
        assert r.json()['roles']==['organizer']
        assert r.json()['user']['id']==user_id
        assert all(call[2]==user_id for call in db.calls)


@pytest.mark.anyio
async def test_registration_does_not_forward_role_metadata_and_cookies_are_httponly():
    app=create_app(configured());sent=[]
    async def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'access_token':'test-access','refresh_token':'test-refresh','expires_in':3600})
    app.state.auth.transport=httpx.MockTransport(handler)
    async with client(app) as c:
        r=await c.post('/api/v1/auth/register',json={'email':'member@example.com','password':'long-enough-password','display_name':'Member'})
        assert r.json()['authenticated']
        assert sent[0]['data']=={'display_name':'Member'}
        cookies=r.headers.get_list('set-cookie')
        assert len(cookies)==2 and all('HttpOnly' in v and 'SameSite=strict' in v for v in cookies)
        assert all('Path=/api/v1' in v for v in cookies)


@pytest.mark.anyio
async def test_cookie_authenticated_writes_require_same_origin():
    app=create_app();
    async with client(app) as c:
        for method,path in [('POST','/api/v1/events'),('PUT','/api/v1/artist/portfolio')]:
            r=await c.request(method,path,headers={'Cookie':'eventra_access=test','Content-Type':'application/json'},content='{}')
            assert r.status_code==403
        assert (await c.post('/api/v1/auth/refresh',json={},headers={'Origin':'https://evil.invalid'})).status_code==403


@pytest.mark.anyio
async def test_event_validation_rejects_unzoned_past_and_negative_budgets():
    app=create_app();future=datetime.now(timezone.utc)+timedelta(days=2)
    data={'title':'Wedding','city':'Pune','event_type':'Wedding','starts_at':future.isoformat(),'ends_at':(future+timedelta(hours=3)).isoformat(),'budget_paise':100000,'guest_count':50,'notes':''}
    async with client(app) as c:
        for fields in [{'starts_at':'2020-01-01T12:00:00Z','ends_at':'2020-01-01T14:00:00Z'},{'starts_at':'2030-01-01T12:00:00'},{'budget_paise':-100},{'organizer_id':str(uuid4())}]:
            assert (await c.post('/api/v1/events',json={**data,**fields})).status_code==422


@pytest.mark.anyio
async def test_discovery_pagination_sort_genre_dates_and_honest_reviews():
    async with client(create_app()) as c:
        r=(await c.get('/api/v1/artists',params={'sort':'price_low','page_size':2,'page':2})).json()
        assert r['total']==8 and len(r['items'])==2
        assert r['items'][0]['name']=='Tara Noor'
        assert all(a['review_count']==0 and a['rating']==0 for a in r['items'])
        assert (await c.get('/api/v1/artists',params={'genre':'Saxophone'})).json()['total']==1
        assert (await c.get('/api/v1/artists',params={'event_date':'2030-01-01'})).json()['total']==0
        assert (await c.get('/api/v1/artists/by-slug/dj-aarya')).json()['name']=='DJ Aarya'
        assert (await c.get('/api/v1/artists',params={'sort':'DROP TABLE'})).status_code==422
        assert (await c.get('/api/v1/artists',params={'page_size':201})).status_code==422


@pytest.mark.anyio
async def test_ai_empty_eligibility_does_not_call_model_or_invent_matches():
    def provider(request): pytest.fail('AI must not run with no eligible artists')
    async with client(create_app(Settings(),httpx.MockTransport(provider))) as c:
        r=await c.post('/api/v1/assistant/runs',json={'brief':'An intimate evening','city':'Mumbai','max_price_paise':1})
        assert r.status_code==200 and 'No published artists match' in r.text
        assert '"artist_ids": []' in r.text


def test_signature_uses_exact_raw_body_and_constant_time_hex_verification():
    body=b'{"event":"payment.captured"}'
    sig=hmac.new(b'webhook-test',body,hashlib.sha256).hexdigest()
    assert verify_webhook(body,sig,'webhook-test')
    assert not verify_webhook(body+b' ',sig,'webhook-test')
    assert not verify_webhook(body,sig,'wrong-secret')
    assert not verify_webhook(body,'','webhook-test')


@pytest.mark.parametrize('change',[{'status':'authorized'},{'currency':'USD'},{'amount':True},{'amount':-1},{'id':'madeup'},{'order_id':'madeup'}])
def test_only_valid_captured_payment_entities_are_admitted(change):
    entity={'status':'captured','currency':'INR','amount':10000,'id':'pay_Test','order_id':'order_Test',**change}
    with pytest.raises(HTTPException): captured_payment({'event':'payment.captured','payload':{'payment':{'entity':entity}}})


@pytest.mark.anyio
async def test_webhook_verification_precedes_database_and_passes_verified_fields_only():
    settings=Settings(razorpay_key_id='rzp_test_example',razorpay_key_secret='test-secret',razorpay_webhook_secret='hook-secret')
    app=create_app(settings);db=DatabaseDouble();app.state.database=db
    body=json.dumps({'event':'payment.captured','payload':{'payment':{'entity':{'id':'pay_Test','order_id':'order_Test','amount':10000,'currency':'INR','status':'captured'}}}}).encode()
    async with client(app) as c:
        headers={'Content-Type':'application/json','X-Razorpay-Event-Id':'evt_Test'}
        assert (await c.post('/api/v1/payments/webhook',content=body,headers=headers)).status_code==401
        assert db.calls==[]
        headers['X-Razorpay-Signature']=hmac.new(b'hook-secret',body,hashlib.sha256).hexdigest()
        assert (await c.post('/api/v1/payments/webhook',content=body,headers=headers)).status_code==200
        assert db.calls[-1][0]=='payment_capture' and db.calls[-1][2] is None
        assert db.calls[-1][1]['body_sha256']==hashlib.sha256(body).hexdigest()


@pytest.mark.anyio
async def test_razorpay_order_is_server_priced_and_mismatched_provider_response_fails():
    settings=Settings(razorpay_key_id='rzp_test_example',razorpay_key_secret='test-secret',razorpay_webhook_secret='hook-secret')
    async def provider(request):
        payload=json.loads(request.content);assert payload=={'amount':111000,'currency':'INR','receipt':'server-receipt','partial_payment':False}
        return httpx.Response(200,json={'id':'order_Test','amount':1,'currency':'INR','receipt':'server-receipt'})
    with pytest.raises(HTTPException) as e:
        await Razorpay(settings,httpx.MockTransport(provider)).order(111000,'server-receipt')
    assert e.value.status_code==503


def test_production_configuration_rejects_live_keys_and_insecure_services():
    for kwargs in [{'app_env':'production'},{'razorpay_key_id':'rzp_live_do-not-use'},{'supabase_url':'https://untrusted.example'},{'inference_provider':'hosted'}]:
        with pytest.raises(ValueError): Settings(**kwargs)
    with pytest.raises(ValueError): Settings(allow_managed_services=True,database_url='postgresql://eventra_app:dummy@db.project.supabase.co:5432/postgres?sslmode=require')


@pytest.mark.anyio
async def test_hosted_provider_uses_server_credentials_and_discards_unknown_ids():
    settings=Settings(inference_provider='hosted',allow_managed_services=True,hosted_ai_url='https://provider.example/v1/chat/completions',hosted_ai_key='server-only',hosted_ai_model='test-model')
    async def provider(request):
        assert request.headers['authorization']=='Bearer server-only'
        payload=json.loads(request.content);assert 'tools' not in payload
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'message':'Untrusted answer','artist_ids':[str(uuid4())]})}}]})
    with pytest.raises(InvalidModelAnswer): await HostedAI(settings,httpx.MockTransport(provider)).recommend('Acoustic wedding',[FIXTURES[0]])


def test_file_type_checks_reject_svg_and_mismatched_image_content():
    assert image_extension(b'\xff\xd8\xfftest','image/jpeg')=='jpg'
    for body,mime in [(b'<svg onload="alert(1)"/>','image/svg+xml'),(b'<html>','image/jpeg')]:
        with pytest.raises(HTTPException): image_extension(body,mime)


def test_account_rate_limiter_bounds_attempts():
    limiter=RateLimit()
    assert all(limiter.allow('actor',3) for _ in range(3))
    assert not limiter.allow('actor',3)
