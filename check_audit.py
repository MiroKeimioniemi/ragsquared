import requests
import json
import time

# Check list of audits
r = requests.get('http://localhost:5000/api/audits')
print(f'Status: {r.status_code}')
audits = r.json().get('audits', [])
print(f'\nFound {len(audits)} audits\n')

# Show the most recent 5
for audit in audits[-5:]:
    print(f"ID: {audit.get('id')}, Status: {audit.get('status')}, External ID: {audit.get('external_id')}")
    print(f"  Document ID: {audit.get('document_id')}, Created: {audit.get('created_at')}")
    if audit.get('started_at'):
        print(f"  Started: {audit.get('started_at')}")
    if audit.get('completed_at'):
        print(f"  Completed: {audit.get('completed_at')}")
    if audit.get('failed_at'):
        print(f"  Failed: {audit.get('failed_at')}, Reason: {audit.get('failure_reason', 'N/A')}")
    print()

