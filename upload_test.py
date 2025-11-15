import requests

files = {'file': open('hackathon_resources/AI anonyymi MOE.docx', 'rb')}
data = {'source_type': 'manual', 'organization': 'Test Organization', 'description': 'Final test upload'}

r = requests.post('http://localhost:5000/api/documents', files=files, data=data)
print(f'Status: {r.status_code}')
import json
resp = r.json()
print(f"Audit ID: {resp['audit']['id']}, Status: {resp['audit']['status']}, External ID: {resp['audit']['external_id']}")

