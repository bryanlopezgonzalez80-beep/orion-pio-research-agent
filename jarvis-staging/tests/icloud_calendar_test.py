"""Run with PYTHONPATH=jarvis-staging python -m unittest discover -s jarvis-staging/tests -p icloud_calendar_test.py."""
import unittest
from unittest.mock import patch
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
import icloud_calendar as cal


def status(properties):
    return '<d:response><d:href>/calendar</d:href><d:propstat><d:status>HTTP/1.1 200 OK</d:status><d:prop>'+properties+'</d:prop></d:propstat></d:response>'


def response(body):
    return httpx.Response(207, text='<d:multistatus xmlns:d="DAV:" xmlns:c="urn:ietf:params:xml:ns:caldav">'+body+'</d:multistatus>')


class ICloudTest(unittest.TestCase):
    def test_discovery_and_event(self):
        replies = iter([
            status('<d:current-user-principal><d:href>/principal</d:href></d:current-user-principal>'),
            status('<c:calendar-home-set><d:href>/home</d:href></c:calendar-home-set>'),
            status('<d:resourcetype><c:calendar/></d:resourcetype><d:displayname>Casa</d:displayname>'),
            status('<c:calendar-data>BEGIN:VCALENDAR\nBEGIN:VEVENT\nDTSTART:20261118T140000Z\nSUMMARY:Prueba\nEND:VEVENT\nEND:VCALENDAR</c:calendar-data>')
        ])
        def handler(req):
            self.assertEqual(req.url.host, 'caldav.icloud.com')
            return response(next(replies))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            (name,url), = cal.discover(client).values()
            self.assertEqual(name,'Casa')
            result = cal.read_today(client,url)
            self.assertEqual(result['events'],[{'start':'2026-11-18T10:00:00-04:00','title':'Prueba'}])

    def test_partial_report_fails(self):
        with httpx.Client(transport=httpx.MockTransport(lambda _:response('<d:response/>'))) as client:
            with self.assertRaises(ValueError):
                cal.read_today(client,cal.BASE)

    def test_auth_rejection_and_foreign_redirect(self):
        for reply,error in [(httpx.Response(401),cal.HTTPException),(httpx.Response(302, headers={'location':'https://example.com/'}),ValueError)]:
            with httpx.Client(transport=httpx.MockTransport(lambda _:reply)) as client:
                with self.assertRaises(error):
                    cal.discover(client)

    def test_account_isolation_and_disconnect(self):
        app = FastAPI()
        identity = {'id':'first'}
        cal.register(app,lambda:identity)
        api = TestClient(app)
        url = '/v1/calendar/icloud/'
        with patch.object(cal,'remote',return_value={'one':('Casa',cal.BASE)}):
            r = api.post(url+'connect',json={'email':'a@example.test','password':'aaaa-bbbb-cccc-dddd'})
        self.assertEqual(r.status_code,200)
        selection = {'connection':r.json()['connection'],'calendar':'one'}
        identity['id']='second'
        self.assertEqual(api.post(url+'today',json=selection).status_code,410)
        identity['id']='first'
        self.assertEqual(api.post(url+'disconnect',json=selection).status_code,200)
        self.assertEqual(api.post(url+'today',json=selection).status_code,410)
