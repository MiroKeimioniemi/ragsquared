#!/usr/bin/env python3
"""Regenerate embeddings for the regulation document."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from backend.app.config.settings import AppConfig
from backend.app.db.models import Base, Document, Chunk
from backend.app.db.session import get_session, init_engine
from backend.app.services.documents import DocumentService
from backend.app.services.embeddings import EmbeddingService
from backend.app.processing.extraction import DocumentExtractor
from backend.app.services.chunking import SemanticChunker, SectionText
from sqlalchemy import select

REGULATION_FILE = project_root / "hackathon_resources" / "Easy Access Rules for Continuing Airworthiness (Regulation (EU) No 13212014).xml"

def main():
    config = AppConfig()
    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)
    
    session = get_session()
    
    try:
        # Step 1: Find or create the regulation document
        print("Step 1: Finding or creating regulation document...")
        
        # Look for existing regulation document
        stmt = select(Document).where(
            Document.source_type == "regulation",
            Document.original_filename.like("%1321%")
        )
        document = session.execute(stmt).scalar_one_or_none()
        
        if document:
            print(f"Found existing document: {document.original_filename} (ID: {document.id}, External ID: {document.external_id})")
        else:
            print("Document not found, uploading...")
            # Upload the file
            from werkzeug.datastructures import FileStorage
            
            with open(REGULATION_FILE, 'rb') as f:
                file_storage = FileStorage(
                    stream=f,
                    filename=REGULATION_FILE.name,
                    content_type="application/xml"
                )
                
                doc_service = DocumentService(Path(config.data_root), session)
                document = doc_service.create_from_upload(
                    file_storage,
                    source_type="regulation",
                    organization="EASA",
                    description="EU Regulation 1321/2014 - Continuing Airworthiness"
                )
                session.commit()
                print(f"Uploaded document: {document.original_filename} (ID: {document.id}, External ID: {document.external_id})")
        
        # Step 2: Force re-extraction with improved XML extraction logic
        print("\nStep 2: Re-extracting text from document (using improved extraction)...")
        extraction_file = Path(config.data_root) / "processed" / f"{document.external_id}.json"
        
        # Force re-extraction by deleting existing extraction file
        if extraction_file.exists():
            print(f"Deleting existing extraction file to force re-extraction: {extraction_file}")
            extraction_file.unlink()
        
        # Make storage path absolute
        storage_path = Path(config.data_root) / document.storage_path
        if not storage_path.exists():
            print(f"ERROR: Storage path does not exist: {storage_path}")
            return 1
        
        print(f"Extracting text from: {storage_path}")
        extractor = DocumentExtractor()
        extracted_doc = extractor.extract(storage_path)
        extraction_data = extracted_doc.to_dict()
        
        # Save extraction result
        processed_dir = Path(config.data_root) / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        extraction_file = processed_dir / f"{document.external_id}.json"
        import json
        extraction_file.write_text(json.dumps(extraction_data, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved extraction to: {extraction_file}")
        print(f"Extracted {len(extraction_data.get('sections', []))} sections")
        
        # Convert to SectionText objects for chunking
        sections = []
        for idx, section_data in enumerate(extraction_data.get("sections", [])):
            section_path = section_data.get("metadata", {}).get("section_path")
            if isinstance(section_path, str):
                section_path = [section_path]
            elif not isinstance(section_path, list):
                section_path = None
            
            sections.append(
                SectionText(
                    index=section_data.get("index", idx),
                    title=section_data.get("title"),
                    content=section_data.get("content", ""),
                    section_path=[str(p) for p in section_path] if section_path else None,
                    metadata=section_data.get("metadata", {}),
                )
            )
        
        # Step 3: Delete existing chunks and regenerate
        print("\nStep 3: Regenerating chunks...")
        existing_chunks = session.query(Chunk).filter(Chunk.document_id == document.id).all()
        if existing_chunks:
            print(f"Deleting {len(existing_chunks)} existing chunks...")
            # Retry logic for database lock
            import time
            max_retries = 5
            for retry in range(max_retries):
                try:
                    session.query(Chunk).filter(Chunk.document_id == document.id).delete(synchronize_session=False)
                    session.flush()
                    break
                except Exception as e:
                    if "locked" in str(e).lower() and retry < max_retries - 1:
                        wait_time = 2 ** retry  # Exponential backoff
                        print(f"Database locked, waiting {wait_time} seconds before retry {retry + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        session.rollback()
                    else:
                        raise
        
        # Chunk the document
        if not sections:
            print("ERROR: No sections found in extraction result!")
            return 1
        
        chunker = SemanticChunker(config.chunking)
        # Use section-aware chunking for regulations (one chunk per section)
        payloads = chunker.chunk_sections(document.external_id, sections, section_aware=True)
        
        print(f"Generated {len(payloads)} chunks")
        
        # Save chunks to database
        for idx, payload in enumerate(payloads):
            metadata = {
                **payload.metadata,
                "chunk_id": payload.chunk_id,
                "section_path": payload.section_path,
                "parent_heading": payload.parent_heading,
            }
            section_path = " > ".join(payload.section_path).strip() or None
            chunk_row = Chunk(
                document_id=document.id,
                chunk_id=payload.chunk_id,
                chunk_index=idx,
                section_path=section_path,
                parent_heading=payload.parent_heading,
                content=payload.text,
                token_count=payload.token_count,
                chunk_metadata=metadata,
                embedding_status="pending",  # Mark as pending for embedding
            )
            session.add(chunk_row)
        
        session.commit()
        print(f"Saved {len(payloads)} chunks to database")
        
        # Step 4: Generate embeddings
        print("\nStep 4: Generating embeddings...")
        embedding_service = EmbeddingService(session, config)
        
        # Get all chunks for this document
        chunks = session.query(Chunk).filter(Chunk.document_id == document.id).all()
        print(f"Found {len(chunks)} chunks to embed")
        
        # Process in batches (larger batches for faster processing)
        batch_size = 1024  # Increased to 1024 to speed up processing
        total_processed = 0
        total_failed = 0
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
            
            result = embedding_service.process_chunks(batch, collection_name="regulation_chunks")
            
            total_processed += result["processed"]
            total_failed += result["failed"]
            
            print(f"  Processed: {result['processed']}, Failed: {result['failed']}")
        
        print(f"\n=== SUMMARY ===")
        print(f"Total chunks processed: {total_processed}")
        print(f"Total chunks failed: {total_failed}")
        print(f"Document ID: {document.id}")
        print(f"Document External ID: {document.external_id}")
        print(f"Collection: regulation_chunks")
        
        return 0
        
    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    sys.exit(main())

