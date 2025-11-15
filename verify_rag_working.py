#!/usr/bin/env python3
"""
Script to verify RAG is working correctly.
Run this after uploading a document and running an audit.
"""

import sys
from pathlib import Path
sys.path.insert(0, '.')

try:
    from backend.app.db.session import get_session
    from backend.app.db.models import Audit, Flag, AuditChunkResult, Chunk
    from sqlalchemy import desc
    import json
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Make sure you're in the project root and dependencies are installed.")
    sys.exit(1)

def check_vector_collections():
    """Check if vector collections are populated."""
    print("\n=== Vector Database Collections ===")
    try:
        import chromadb
        from backend.app.config.settings import AppConfig
        
        config = AppConfig()
        chroma_path = Path(config.data_root) / "chroma"
        
        if not chroma_path.exists():
            print(f"❌ ChromaDB path does not exist: {chroma_path}")
            return False
        
        client = chromadb.PersistentClient(path=str(chroma_path))
        
        collections = {
            "manual_chunks": "Manual document chunks",
            "regulation_chunks": "Regulation chunks (CRITICAL for compliance)",
            "amc_chunks": "AMC guidance chunks",
            "gm_chunks": "GM guidance chunks",
            "evidence_chunks": "Evidence chunks"
        }
        
        all_ok = True
        for coll_name, description in collections.items():
            try:
                coll = client.get_collection(name=coll_name)
                count = coll.count()
                status = "✅" if count > 0 else "❌"
                print(f"{status} {coll_name}: {count} chunks - {description}")
                if count == 0 and coll_name in ["regulation_chunks", "amc_chunks", "gm_chunks"]:
                    print(f"   ⚠️  WARNING: {coll_name} is EMPTY - RAG will not work for regulations/guidance!")
                    all_ok = False
            except Exception as e:
                print(f"❌ {coll_name}: NOT FOUND - {str(e)[:60]}")
                if coll_name in ["regulation_chunks", "amc_chunks", "gm_chunks"]:
                    print(f"   ⚠️  WARNING: {coll_name} missing - RAG will not work!")
                    all_ok = False
        
        return all_ok
    except Exception as e:
        print(f"❌ Error checking vector database: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_audit_results():
    """Check audit results for RAG usage."""
    print("\n=== Latest Audit Results ===")
    session = get_session()
    
    audit = session.query(Audit).order_by(desc(Audit.created_at)).first()
    
    if not audit:
        print("❌ No audits found in database")
        return False
    
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    red = len([f for f in flags if f.flag_type == 'RED'])
    yellow = len([f for f in flags if f.flag_type == 'YELLOW'])
    green = len([f for f in flags if f.flag_type == 'GREEN'])
    
    print(f"Audit ID: {audit.external_id}")
    print(f"Status: {audit.status}")
    print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
    print(f"Flags: RED={red}, YELLOW={yellow}, GREEN={green}, Total={len(flags)}")
    
    if audit.chunk_total > 100 and (red + yellow) < 10:
        print(f"\n⚠️  WARNING: Only {red + yellow} flags (RED+YELLOW) for {audit.chunk_total} chunks!")
        print("   This suggests RAG may not be working or LLM is too conservative.")
    
    # Check context usage
    results = session.query(AuditChunkResult).filter(
        AuditChunkResult.audit_id == audit.id
    ).order_by(AuditChunkResult.chunk_index.asc()).limit(20).all()
    
    if not results:
        print("\n❌ No audit chunk results found")
        return False
    
    print(f"\n=== Context Usage Analysis (first 20 chunks) ===")
    chunks_with_context = 0
    chunks_with_reg_refs = 0
    chunks_with_reg_cites = 0
    total_context_tokens = 0
    chunks_with_zero_regs = 0
    
    for result in results:
        analysis = result.analysis or {}
        context_tokens = result.context_token_count or 0
        total_context_tokens += context_tokens
        
        if context_tokens > 0:
            chunks_with_context += 1
        
        reg_refs = analysis.get("regulation_references", [])
        if reg_refs:
            chunks_with_reg_refs += 1
        
        citations = analysis.get("citations", {})
        reg_cites = citations.get("regulation_sections", [])
        if reg_cites:
            chunks_with_reg_cites += 1
        
        if context_tokens > 0 and len(reg_refs) == 0 and len(reg_cites) == 0:
            chunks_with_zero_regs += 1
    
    avg_tokens = total_context_tokens / len(results) if results else 0
    
    print(f"Chunks with context tokens: {chunks_with_context}/{len(results)}")
    print(f"Average context tokens: {avg_tokens:.0f}")
    print(f"Chunks with regulation references: {chunks_with_reg_refs}")
    print(f"Chunks with regulation citations: {chunks_with_reg_cites}")
    print(f"Chunks with context but NO regulation refs/cites: {chunks_with_zero_regs}")
    
    # Sample details
    print(f"\n=== Sample Chunk Details ===")
    for i, result in enumerate(results[:5], 1):
        analysis = result.analysis or {}
        print(f"\nChunk {result.chunk_index}:")
        print(f"  Flag: {analysis.get('flag', 'N/A')}")
        print(f"  Context tokens: {result.context_token_count or 0}")
        print(f"  Reg refs: {len(analysis.get('regulation_references', []))}")
        print(f"  Reg citations: {len(analysis.get('citations', {}).get('regulation_sections', []))}")
        if analysis.get('needs_additional_context'):
            print(f"  ⚠️  Requested more context: {analysis.get('context_query', 'N/A')[:60]}")
    
    # Issues
    print(f"\n=== Issues Found ===")
    issues = []
    
    if chunks_with_context == 0:
        issues.append("❌ CRITICAL: No chunks have context tokens - RAG not working!")
    
    if avg_tokens < 100:
        issues.append(f"⚠️  WARNING: Very low average context tokens ({avg_tokens:.0f}) - may indicate empty collections")
    
    if chunks_with_reg_refs == 0 and chunks_with_reg_cites == 0:
        issues.append("⚠️  WARNING: No regulation references found - LLM may not be using context!")
    
    if chunks_with_zero_regs > len(results) * 0.5:
        issues.append(f"⚠️  WARNING: {chunks_with_zero_regs}/{len(results)} chunks have context but no regulation refs - LLM may be ignoring context")
    
    if not issues:
        print("✅ No obvious issues found")
    else:
        for issue in issues:
            print(issue)
    
    return len(issues) == 0

if __name__ == "__main__":
    print("=" * 60)
    print("RAG Verification Script")
    print("=" * 60)
    
    collections_ok = check_vector_collections()
    results_ok = check_audit_results()
    
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    
    if collections_ok and results_ok:
        print("✅ RAG appears to be working correctly")
    else:
        print("❌ Issues found - check the warnings above")
        if not collections_ok:
            print("\nTo fix empty collections:")
            print("1. Load regulation documents")
            print("2. Run embedding pipeline for regulations")
            print("3. Check if regulation documents were processed")

