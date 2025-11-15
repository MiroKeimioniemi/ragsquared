#!/usr/bin/env python3
"""Clear all embeddings and recreate legislation/regulation embeddings."""

import sys
import shutil
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
from sqlalchemy import select

def clear_chromadb_collections(config: AppConfig) -> None:
    """Clear all ChromaDB collections."""
    try:
        import chromadb
    except ImportError:
        print("WARNING: chromadb not installed, skipping ChromaDB cleanup")
        return
    
    chroma_path = Path(config.data_root) / "chroma"
    if not chroma_path.exists():
        print("No ChromaDB directory found, skipping...")
        return
    
    print("Clearing ChromaDB collections...")
    client = chromadb.PersistentClient(path=str(chroma_path))
    
    # List all collections
    collections = client.list_collections()
    collection_names = [coll.name for coll in collections]
    
    if not collection_names:
        print("  No collections found")
        return
    
    print(f"  Found {len(collection_names)} collections: {', '.join(collection_names)}")
    
    for coll_name in collection_names:
        try:
            client.delete_collection(name=coll_name)
            print(f"  [OK] Deleted collection: {coll_name}")
        except Exception as e:
            print(f"  [ERROR] Failed to delete collection {coll_name}: {e}")

def clear_embedding_cache(config: AppConfig) -> None:
    """Clear the embedding cache directory."""
    cache_dir = Path(config.data_root) / "cache" / "embeddings"
    
    if not cache_dir.exists():
        print("No embedding cache directory found, skipping...")
        return
    
    print("Clearing embedding cache...")
    try:
        # Count files before deletion
        cache_files = list(cache_dir.glob("*.npy"))
        file_count = len(cache_files)
        
        if file_count > 0:
            shutil.rmtree(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            print(f"  [OK] Deleted {file_count} cached embedding files")
        else:
            print("  No cached files found")
    except Exception as e:
        print(f"  [ERROR] Failed to clear cache: {e}")

def reset_chunk_embedding_status(session, source_type: str = "regulation") -> int:
    """Reset embedding status for chunks of a specific source type."""
    print(f"Resetting embedding status for {source_type} chunks...")
    
    # Find all documents of the specified source type
    stmt = select(Document).where(Document.source_type == source_type)
    documents = session.execute(stmt).scalars().all()
    
    if not documents:
        print(f"  No {source_type} documents found")
        return 0
    
    print(f"  Found {len(documents)} {source_type} document(s)")
    
    total_chunks = 0
    for doc in documents:
        # Reset all chunks for this document to pending
        chunks = session.query(Chunk).filter(Chunk.document_id == doc.id).all()
        if chunks:
            for chunk in chunks:
                chunk.embedding_status = "pending"
            total_chunks += len(chunks)
            print(f"  [OK] Reset {len(chunks)} chunks for document: {doc.original_filename}")
    
    session.commit()
    print(f"  Total chunks reset: {total_chunks}")
    return total_chunks

def regenerate_regulation_embeddings(session, config: AppConfig, embedding_service: EmbeddingService) -> int:
    """Regenerate embeddings for all regulation documents."""
    print("\nRegenerating regulation embeddings...")
    
    # Find all regulation documents
    stmt = select(Document).where(Document.source_type == "regulation")
    documents = session.execute(stmt).scalars().all()
    
    if not documents:
        print("  No regulation documents found")
        return 0
    
    print(f"  Found {len(documents)} regulation document(s)")
    
    total_processed = 0
    total_failed = 0
    
    for doc in documents:
        print(f"\n  Processing document: {doc.original_filename}")
        
        # Get all pending chunks for this document
        chunks = (
            session.query(Chunk)
            .filter(Chunk.document_id == doc.id)
            .filter(Chunk.embedding_status == "pending")
            .all()
        )
        
        if not chunks:
            print(f"    No pending chunks found")
            continue
        
        print(f"    Found {len(chunks)} chunks to embed")
        
        # Process in batches
        batch_size = 32
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(chunks) + batch_size - 1) // batch_size
            
            print(f"    Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
            
            try:
                result = embedding_service.process_chunks(batch, collection_name="regulation_chunks")
                total_processed += result["processed"]
                total_failed += result.get("failed", 0)
                print(f"      [OK] Processed: {result['processed']}, Failed: {result.get('failed', 0)}")
            except Exception as e:
                print(f"      [ERROR] Error processing batch: {e}")
                total_failed += len(batch)
    
    print(f"\n  === REGULATION EMBEDDING SUMMARY ===")
    print(f"  Total chunks processed: {total_processed}")
    print(f"  Total chunks failed: {total_failed}")
    
    return total_processed

def main():
    """Main function to clear and regenerate embeddings."""
    print("=" * 60)
    print("CLEAR AND REGENERATE EMBEDDINGS")
    print("=" * 60)
    
    config = AppConfig()
    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)
    
    session = get_session()
    
    try:
        # Step 1: Clear ChromaDB collections
        print("\n[Step 1] Clearing ChromaDB collections...")
        clear_chromadb_collections(config)
        
        # Step 2: Clear embedding cache
        print("\n[Step 2] Clearing embedding cache...")
        clear_embedding_cache(config)
        
        # Step 3: Reset chunk embedding status for regulations
        print("\n[Step 3] Resetting chunk embedding status...")
        reset_chunk_embedding_status(session, source_type="regulation")
        
        # Step 4: Regenerate regulation embeddings
        print("\n[Step 4] Regenerating regulation embeddings...")
        embedding_service = EmbeddingService(session, config)
        try:
            total_processed = regenerate_regulation_embeddings(session, config, embedding_service)
        finally:
            embedding_service.close()
        
        print("\n" + "=" * 60)
        print("COMPLETE")
        print("=" * 60)
        print(f"Total regulation chunks processed: {total_processed}")
        print("\nNote: Other document types (manual, amc, gm, evidence) were not regenerated.")
        print("To regenerate them, run this script with appropriate modifications.")
        
        return 0
        
    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    sys.exit(main())

