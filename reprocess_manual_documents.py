#!/usr/bin/env python3
"""Re-process manual documents with section-aware chunking."""

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
from backend.app.services.embeddings import EmbeddingService
from backend.app.processing.extraction import DocumentExtractor
from backend.app.services.chunking import SemanticChunker, SectionText
from sqlalchemy import select

def main():
    config = AppConfig()
    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)
    
    session = get_session()
    
    try:
        # Step 1: Find all manual documents
        print("Step 1: Finding manual documents...")
        
        stmt = select(Document).where(Document.source_type == "manual")
        documents = session.execute(stmt).scalars().all()
        
        if not documents:
            print("No manual documents found.")
            return 0
        
        print(f"Found {len(documents)} manual document(s):")
        for doc in documents:
            print(f"  - {doc.external_id}: {doc.original_filename}")
        
        # Process each document
        for doc_idx, document in enumerate(documents, 1):
            print(f"\n{'='*60}")
            print(f"Processing document {doc_idx}/{len(documents)}: {document.original_filename}")
            print(f"{'='*60}")
            
            try:
                # Step 2: Extract text if not already extracted
                print("\nStep 2: Extracting text from document...")
                extraction_file = Path(config.data_root) / "processed" / f"{document.external_id}.json"
                
                if extraction_file.exists():
                    print(f"Loading existing extraction from: {extraction_file}")
                    import json
                    extraction_data = json.loads(extraction_file.read_text(encoding="utf-8"))
                else:
                    # Make storage path absolute
                    storage_path = Path(config.data_root) / document.storage_path
                    if not storage_path.exists():
                        print(f"ERROR: Storage path does not exist: {storage_path}")
                        continue
                    
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
                
                # Step 3: Delete existing chunks and regenerate with section-aware chunking
                print("\nStep 3: Regenerating chunks with section-aware chunking...")
                existing_chunks = session.query(Chunk).filter(Chunk.document_id == document.id).all()
                if existing_chunks:
                    print(f"Deleting {len(existing_chunks)} existing chunks...")
                    session.query(Chunk).filter(Chunk.document_id == document.id).delete(synchronize_session=False)
                    session.flush()
                
                # Chunk the document with section-aware chunking
                if not sections:
                    print("ERROR: No sections found in extraction result!")
                    continue
                
                chunker = SemanticChunker(config.chunking)
                # Use section-aware chunking (one chunk per section)
                payloads = chunker.chunk_sections(document.external_id, sections, section_aware=True)
                
                print(f"Generated {len(payloads)} chunks (was {len(existing_chunks)} before)")
                
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
                
                # Determine collection name based on source type
                collection_name = "manual_chunks"
                
                # Process in batches
                batch_size = 32
                total_processed = 0
                total_failed = 0
                
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    batch_num = (i // batch_size) + 1
                    total_batches = (len(chunks) + batch_size - 1) // batch_size
                    
                    print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
                    
                    result = embedding_service.process_chunks(batch, collection_name=collection_name)
                    
                    total_processed += result["processed"]
                    total_failed += result["failed"]
                    
                    print(f"  Processed: {result['processed']}, Failed: {result['failed']}")
                
                print(f"\n=== SUMMARY for {document.original_filename} ===")
                print(f"Total chunks processed: {total_processed}")
                print(f"Total chunks failed: {total_failed}")
                print(f"Document ID: {document.id}")
                print(f"Document External ID: {document.external_id}")
                print(f"Collection: {collection_name}")
                print(f"Chunk count: {len(existing_chunks)} -> {len(payloads)}")
                
            except Exception as e:
                session.rollback()
                print(f"ERROR processing document {document.external_id}: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        print(f"\n{'='*60}")
        print(f"Completed processing {len(documents)} document(s)")
        print(f"{'='*60}")
        
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

