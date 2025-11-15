#!/usr/bin/env python3
"""Diagnostic script to check RAG usage and context retrieval for audits."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit, Chunk, AuditChunkResult, Flag
from sqlalchemy import desc, func
import json

app = create_app()
with app.app_context():
    session = get_session()
    
    # Get latest audit
    latest_audit = session.query(Audit).order_by(Audit.created_at.desc()).first()
    
    if not latest_audit:
        print("No audits found in database.")
        sys.exit(0)
    
    print(f"=== Audit RAG Diagnostic ===")
    print(f"Audit ID: {latest_audit.external_id}")
    print(f"Status: {latest_audit.status}")
    print(f"Chunks: {latest_audit.chunk_completed}/{latest_audit.chunk_total}")
    print()
    
    # Get flags summary
    flags = session.query(Flag).filter(Flag.audit_id == latest_audit.id).all()
    red_flags = [f for f in flags if f.flag_type == "RED"]
    yellow_flags = [f for f in flags if f.flag_type == "YELLOW"]
    green_flags = [f for f in flags if f.flag_type == "GREEN"]
    
    print(f"=== Flags Summary ===")
    print(f"Total flags: {len(flags)}")
    print(f"RED: {len(red_flags)}")
    print(f"YELLOW: {len(yellow_flags)}")
    print(f"GREEN: {len(green_flags)}")
    print()
    
    # Check audit chunk results to see context usage
    results = session.query(AuditChunkResult).filter(
        AuditChunkResult.audit_id == latest_audit.id
    ).order_by(AuditChunkResult.chunk_index.asc()).limit(10).all()
    
    print(f"=== Context Usage Analysis (first 10 chunks) ===")
    total_context_tokens = 0
    chunks_with_context = 0
    chunks_with_regulations = 0
    chunks_with_guidance = 0
    chunks_needing_refinement = 0
    
    for result in results:
        context_tokens = result.context_token_count or 0
        total_context_tokens += context_tokens
        
        if context_tokens > 0:
            chunks_with_context += 1
        
        # Parse analysis to check context usage
        analysis = result.analysis or {}
        
        # Check if regulations were referenced
        reg_refs = analysis.get("regulation_references", [])
        if reg_refs:
            chunks_with_regulations += 1
        
        # Check if refinement was needed
        if analysis.get("needs_additional_context") or analysis.get("refined"):
            chunks_needing_refinement += 1
        
        # Check citations
        citations = analysis.get("citations", {})
        reg_citations = citations.get("regulation_sections", [])
        if reg_citations:
            chunks_with_regulations += 1
        
        print(f"Chunk {result.chunk_index}: {context_tokens} tokens, "
              f"flag={analysis.get('flag', 'N/A')}, "
              f"reg_refs={len(reg_refs)}, "
              f"needs_context={analysis.get('needs_additional_context', False)}")
    
    print()
    print(f"Average context tokens: {total_context_tokens / len(results) if results else 0:.0f}")
    print(f"Chunks with context: {chunks_with_context}/{len(results)}")
    print(f"Chunks referencing regulations: {chunks_with_regulations}")
    print(f"Chunks needing refinement: {chunks_needing_refinement}")
    print()
    
    # Check vector database collections
    print("=== Vector Database Check ===")
    try:
        from backend.app.services.context_builder import ChromaVectorClient
        from backend.app.config.settings import AppConfig
        
        config = AppConfig()
        chroma_path = Path(config.data_root) / "chroma"
        vector_client = ChromaVectorClient(chroma_path, app_config=config)
        
        collections_to_check = [
            "manual_chunks",
            "regulation_chunks",
            "amc_chunks",
            "gm_chunks",
            "evidence_chunks"
        ]
        
        for collection_name in collections_to_check:
            try:
                collection = vector_client._client.get_collection(name=collection_name)
                count = collection.count()
                print(f"{collection_name}: {count} chunks")
            except Exception as e:
                print(f"{collection_name}: NOT FOUND or ERROR ({str(e)[:50]})")
        
        vector_client.close()
    except Exception as e:
        print(f"Error checking vector database: {e}")
    
    print()
    
    # Sample a few chunk results to see actual context
    print("=== Sample Chunk Analysis Details ===")
    sample_results = results[:3] if len(results) >= 3 else results
    
    for result in sample_results:
        print(f"\n--- Chunk {result.chunk_index} ---")
        analysis = result.analysis or {}
        print(f"Flag: {analysis.get('flag', 'N/A')}")
        print(f"Severity: {analysis.get('severity_score', 0)}")
        print(f"Context tokens: {result.context_token_count or 0}")
        print(f"Regulation references: {len(analysis.get('regulation_references', []))}")
        print(f"Findings (first 200 chars): {analysis.get('findings', '')[:200]}")
        
        # Check if needs_additional_context was set
        if analysis.get('needs_additional_context'):
            print(f"⚠️  Requested additional context: {analysis.get('context_query', 'N/A')}")
        
        # Check citations
        citations = analysis.get('citations', {})
        if citations.get('regulation_sections'):
            print(f"Regulation citations: {citations['regulation_sections']}")
        else:
            print("⚠️  No regulation citations found")
    
    print()
    print("=== Recommendations ===")
    if len(red_flags) + len(yellow_flags) < 10 and latest_audit.chunk_total > 100:
        print("⚠️  WARNING: Very few flags found for a large document.")
        print("   This might indicate:")
        print("   1. RAG collections may be empty or not populated")
        print("   2. Context may not be reaching the LLM properly")
        print("   3. LLM may be too conservative in flagging issues")
        print("   4. Prompt may need adjustment to be more sensitive")
    
    if chunks_with_context == 0:
        print("⚠️  WARNING: No chunks have context tokens - RAG may not be working!")
    
    if chunks_with_regulations == 0:
        print("⚠️  WARNING: No chunks reference regulations - LLM may not be using context!")

