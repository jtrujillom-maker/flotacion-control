"""Verify a running app: python smoke_http.py http://127.0.0.1:8000."""
import json
from pathlib import Path
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main():
    base=(sys.argv[1] if len(sys.argv)>1 else 'http://127.0.0.1:8000').rstrip('/')
    checks=[]
    def get(path):
        with urlopen(base+path,timeout=60) as r:
            assert r.status==200
            return r.read()
    assert json.loads(get('/health'))['engine']=='python'
    checks.append('GET /health: motor Python disponible')
    for path,marker in [('/',b'FLOTACI'),('/style.css',b'.sidebar'),('/dashboard.js',b'/api/compare')]:
        assert marker in get(path)
        checks.append('GET '+path+': contenido correcto')
    def post(path,data):
        req=Request(base+path,data=json.dumps(data).encode(),headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=60) as r:
            return json.load(r)
    comparison=post('/api/compare',{'duration':600})
    assert len(comparison)==3
    for result in comparison.values():
        assert result['status']=='completed'
        assert len(result['records'])==601
    checks.append('POST /api/compare: tres estrategias, 601 muestras por estrategia')
    assert post('/api/tune',{'k_prime':-0.001018,'delay_s':7})['ti_s']==56
    checks.append('POST /api/tune: SIMC correcto')
    try:
        post('/api/compare',{'dt':0})
        raise AssertionError('invalid dt accepted')
    except HTTPError as e:
        assert e.code==400
    checks.append('POST inválido: respuesta HTTP 400')
    report={'url':base,'passed':True,'checks':checks}
    (Path(__file__).resolve().parent/'http_test_results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))


if __name__=='__main__':
    main()
