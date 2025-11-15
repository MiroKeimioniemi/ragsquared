"""Check available audits."""
import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit

app = create_app()
with app.app_context():
    session = get_session()
    audits = session.query(Audit).order_by(Audit.created_at.desc()).limit(5).all()
    print('Recent audits:')
    if audits:
        for a in audits:
            doc_name = a.document.original_filename if a.document else "N/A"
            print(f'  - ID: {a.id}, External ID: {a.external_id}, Status: {a.status}, Document: {doc_name}')
            print(f'    Review URL: http://localhost:5000/review/{a.external_id}')
    else:
        print('  No audits found')

