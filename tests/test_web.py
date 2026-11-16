import io
import json
import unittest
from app import application


def request(path, method='GET', data=None):
    body=json.dumps(data).encode() if data is not None else b''
    env={'PATH_INFO':path,'REQUEST_METHOD':method,'CONTENT_LENGTH':str(len(body)),'wsgi.input':io.BytesIO(body)}
    response={}
    def start(status,headers):
        response['status']=int(status.split()[0]);response['headers']=dict(headers)
    response['body']=b''.join(application(env,start))
    return response


class WebTests(unittest.TestCase):
    def test_static_assets(self):
        for path,marker in [('/',b'FLOTACI'),('/style.css',b'.sidebar'),('/dashboard.js',b'/api/compare')]:
            r=request(path)
            self.assertEqual(r['status'],200)
            self.assertIn(marker,r['body'])
            self.assertEqual(int(r['headers']['Content-Length']),len(r['body']))

    def test_api_comparison(self):
        r=request('/api/compare','POST',{'duration':600})
        self.assertEqual(r['status'],200)
        results=json.loads(r['body'])
        self.assertTrue(all(v['status']=='completed' for v in results.values()))
        for v in results.values():
            self.assertEqual(len(v['records']),601)

    def test_simc_endpoint(self):
        r=request('/api/tune','POST',{'k_prime':-0.001018,'delay_s':7})
        self.assertEqual(r['status'],200)
        self.assertEqual(json.loads(r['body'])['ti_s'],56)

    def test_request_boundaries(self):
        for data in ({'duration':7200,'dt':0.25},{'duration':600,'dt':0},{'setpoint_events':[[0,1.2,30]]}):
            self.assertEqual(request('/api/compare','POST',data)['status'],400)

    def test_no_filesystem_traversal(self):
        self.assertEqual(request('/../model.py')['status'],404)

    def test_error_response(self):
        self.assertEqual(request('/api/compare','POST',[])['status'],400)
