"""Check queued audits."""
import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit, Document

app = create_app()
with app.app_context():
    session = get_session()
    queued = session.query(Audit).filter(Audit.status == 'queued').order_by(Audit.created_at.desc()).all()
    print(f'Queued audits: {len(queued)}')
    for a in queued:
        doc_name = a.document.original_filename if a.document else "N/A"
        print(f'  {a.external_id}: Document={doc_name}, Created={a.created_at}')

