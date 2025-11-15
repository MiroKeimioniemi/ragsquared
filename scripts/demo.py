"""Demo script for AI Auditing System walkthrough."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

from backend.app import create_app
from backend.app.config.settings import AppConfig
from backend.app.db.models import Audit, Document
from backend.app.db.session import get_session
from backend.app.services.compliance_runner import ComplianceRunner
from backend.app.services.documents import DocumentService
from backend.app.services.question_generator import QuestionGenerator
from backend.app.reports.generator import ReportGenerator
from backend.app.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


def reset_demo_state(data_root: Path) -> None:
    """Reset demo state by clearing demo output directory."""
    demo_output = data_root / "demo" / "output"
    if demo_output.exists():
        shutil.rmtree(demo_output)
    demo_output.mkdir(parents=True, exist_ok=True)
    logger.info("Reset demo output directory", path=str(demo_output))


def ingest_sample_documents(data_root: Path, session: Any) -> dict[str, int]:
    """Ingest sample documents from hackathon_resources."""
    demo_dir = data_root / "demo"
    demo_dir.mkdir(parents=True, exist_ok=True)
    
    resources_dir = Path("hackathon_resources")
    doc_service = DocumentService(data_root, session)
    
    documents = {}
    
    # Ingest manual (MOE)
    moe_path = resources_dir / "AI anonyymi MOE.docx"
    if moe_path.exists():
        logger.info("Ingesting MOE manual", path=str(moe_path))
        with open(moe_path, "rb") as f:
            doc = doc_service.create_from_upload(
                f,
                source_type="manual",
                organization="Demo Organization",
                description="Sample Maintenance Organization Exposition (MOE)",
            )
            documents["manual"] = doc.id
            logger.info("MOE ingested", document_id=doc.id, external_id=doc.external_id)
    
    # Ingest regulation
    reg_path = resources_dir / "Easy Access Rules for Continuing Airworthiness (Regulation (EU) No 13212014).xml"
    if reg_path.exists():
        logger.info("Ingesting regulation", path=str(reg_path))
        with open(reg_path, "rb") as f:
            doc = doc_service.create_from_upload(
                f,
                source_type="regulation",
                organization="EASA",
                description="EASA Part-145 Regulation (EU) No 1321/2014",
            )
            documents["regulation"] = doc.id
            logger.info("Regulation ingested", document_id=doc.id, external_id=doc.external_id)
    
    return documents


def run_demo() -> None:
    """Run the complete demo workflow."""
    print("\n" + "=" * 70)
    print("AI Auditing System - Demo Walkthrough")
    print("=" * 70 + "\n")
    
    # Configure logging
    configure_logging(log_level="INFO", json_output=False)
    
    # Initialize app
    app = create_app()
    with app.app_context():
        config = AppConfig()
        data_root = Path(config.data_root)
        session = get_session()
        
        # Step 1: Reset state
        print("Step 1: Resetting demo state...")
        reset_demo_state(data_root)
        print("✓ Demo state reset\n")
        
        # Step 2: Ingest documents
        print("Step 2: Ingesting sample documents...")
        documents = ingest_sample_documents(data_root, session)
        if not documents:
            print("⚠ No sample documents found in hackathon_resources/")
            print("  Please ensure sample files are available.\n")
            return
        
        print(f"✓ Ingested {len(documents)} documents\n")
        
        # Step 3: Process manual document (chunking + embedding)
        if "manual" not in documents:
            print("⚠ Manual document not found, skipping processing steps\n")
            return
        
        manual_id = documents["manual"]
        print(f"Step 3: Processing manual document (ID: {manual_id})...")
        print("  Note: Chunking and embedding would be done here")
        print("  For demo, we'll create a draft audit with minimal processing\n")
        
        # Step 4: Create audit
        print("Step 4: Creating audit...")
        audit = Audit(
            document_id=manual_id,
            status="queued",
            is_draft=True,  # Use draft mode for faster demo
        )
        session.add(audit)
        session.commit()
        print(f"✓ Audit created: {audit.external_id}\n")
        
        # Step 5: Run compliance check (if chunks exist)
        print("Step 5: Running compliance check...")
        runner = ComplianceRunner(session, config)
        try:
            result = runner.run(audit.external_id, max_chunks=5)  # Limit to 5 chunks for demo
            print(f"✓ Processed {result.processed} chunks, {result.remaining} remaining")
            print(f"  Status: {result.status}\n")
        except Exception as e:
            print(f"⚠ Compliance check skipped: {e}\n")
            print("  (This is expected if no chunks exist yet)\n")
        
        # Step 6: Generate questions
        print("Step 6: Generating auditor questions...")
        try:
            question_gen = QuestionGenerator(session, config)
            question_gen.generate_for_audit(audit.id)
            print("✓ Auditor questions generated\n")
        except Exception as e:
            print(f"⚠ Question generation skipped: {e}\n")
        
        # Step 7: Generate report
        print("Step 7: Generating compliance report...")
        try:
            report_dir = data_root / "demo" / "output"
            generator = ReportGenerator(report_dir)
            request = ReportRequest(audit_id=audit.id, include_appendix=True)
            md_path = generator.render_markdown(request)
            print(f"✓ Report generated: {md_path}\n")
        except Exception as e:
            print(f"⚠ Report generation skipped: {e}\n")
        
        # Step 8: Summary
        print("=" * 70)
        print("Demo Summary")
        print("=" * 70)
        print(f"Audit ID: {audit.external_id}")
        print(f"Document ID: {manual_id}")
        print(f"Status: {audit.status}")
        print(f"\nNext steps:")
        print(f"  1. View report: {data_root / 'demo' / 'output'}")
        print(f"  2. Check flags: python cli.py flags {audit.external_id}")
        print(f"  3. View status: python cli.py status {audit.external_id}")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    run_demo()

