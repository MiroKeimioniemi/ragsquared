"""Check specific audit."""
import sys
sys.path.insert(0, '.')

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit

app = create_app()
with app.app_context():
    session = get_session()
    audit = session.query(Audit).filter(Audit.external_id == 'c892210df1f64ba88066a2d6669429ad').first()
    if audit:
        print(f'Audit found: ID={audit.id}, Status={audit.status}, Document={audit.document.original_filename if audit.document else "N/A"}, Created={audit.created_at}')
        print(f'Chunk progress: {audit.chunk_completed}/{audit.chunk_total}')
    else:
        print('Audit not found')

