#!/usr/bin/env python3
"""Exercise the real running API against its SQLite database using synthetic data.
Mutates the demo record, leaves Earth link connected with zero-second delay.
"""
import json
import os
import sys
import urllib.request
import uuid

BASE = sys.argv[1].rstrip('/') if len(sys.argv)>1 else 'http://127.0.0.1:8000'

def call(path, token=None, method='GET', body=None):
    request=urllib.request.Request(BASE+'/api'+path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={'Content-Type':'application/json',**({'Authorization':'Bearer '+token} if token else {})})
    with urllib.request.urlopen(request,timeout=15) as response:
        return json.load(response)


def main():
    password=os.getenv('DEMO_PASSWORD','demo-orbit-2026')
    astronaut=call('/auth/login',method='POST',body={'username':'astronaut','password':password})['token']
    doctor=call('/auth/login',method='POST',body={'username':'doctor','password':password})['token']
    try:
        call('/mission/context',astronaut,'PATCH',{'online':False,'delay_seconds':0})
        findings=call('/assessments',astronaut,'POST',{})
        assert len(findings)==6
        report=call('/symptoms',astronaut,'POST',{'description':'Synthetic API walkthrough: dizziness after an exercise session','severity':4})
        alert_id=report['alert']['id']
        assert call('/sync',astronaut,'POST')['status']=='offline'
        ground=next(r for r in call('/doctors/crew',doctor) if r['user_id']=='astro-01')
        assert alert_id not in {a['id'] for a in ground['snapshot']['alerts']}
        print('PASS: local analysis and symptom reporting work while Earth is offline.')
        call('/mission/context',astronaut,'PATCH',{'online':True})
        call('/sync',astronaut,'POST')
        ground=next(r for r in call('/doctors/crew',doctor) if r['user_id']=='astro-01')
        assert alert_id in {a['id'] for a in ground['snapshot']['alerts']}
        print('PASS: the ground snapshot receives the queued symptom report.')
        review=call('/doctor-reviews',doctor,'POST',{'id':str(uuid.uuid4()),'user_id':'astro-01','alert_id':alert_id,
                    'assessment':'Demo physician review completed','feedback':'Please record the context and collection times of follow-up measurements.'})
        onboard=call('/astronauts/astro-01/health',astronaut)
        assert review['id'] not in {r['id'] for r in onboard['reviews']}
        call('/sync',doctor,'POST')
        onboard=call('/astronauts/astro-01/health',astronaut)
        assert review['id'] in {r['id'] for r in onboard['reviews']}
        call('/doctor-reviews/'+review['id']+'/acknowledge',astronaut,'POST')
        # An undelivered acknowledgment must not leak through the doctor endpoint.
        assert not next(r for r in call('/doctors/reviews',doctor) if r['id']==review['id'])['acknowledged_at']
        call('/sync',astronaut,'POST')
        ground=next(r for r in call('/doctors/crew',doctor) if r['user_id']=='astro-01')
        assert next(r for r in ground['snapshot']['reviews'] if r['id']==review['id'])['acknowledged_at']
        print('PASS: doctor feedback is delivered, acknowledged, and synchronized back to Earth.')
    finally:
        call('/auth/logout',astronaut,'POST')
        call('/auth/logout',doctor,'POST')

if __name__=='__main__':
    main()
