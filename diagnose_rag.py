#!/usr/bin/env python3
"""Simple diagnostic to check RAG usage without Flask dependencies."""

import sys
import json
from pathlib import Path
sys.path.insert(0, '.')

from backend.app.db.session import get_session
from backend.app.db.models import Audit, Chunk, AuditChunkResult, Flag
from sqlalchemy import desc

session = get_session()

# Get latest audit
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()

if not audit:
    print("No audits found.")
    sys.exit(0)

print(f"=== Audit Diagnostic ===")
print(f"Audit ID: {audit.external_id}")
print(f"Status: {audit.status}")
print(f"Chunks: {audit.chunk_completed}/{audit.chunk_total}")
print()

# Flags summary
flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
red = len([f for f in flags if f.flag_type == "RED"])
yellow = len([f for f in flags if f.flag_type == "YELLOW"])
green = len([f for f in flags if f.flag_type == "GREEN"])

print(f"=== Flags ===")
print(f"RED: {red}")
print(f"YELLOW: {yellow}")
print(f"GREEN: {green}")
print(f"Total: {len(flags)}")
print()

# Check context usage in results
results = session.query(AuditChunkResult).filter(
    AuditChunkResult.audit_id == audit.id
).order_by(AuditChunkResult.chunk_index.asc()).limit(20).all()

print(f"=== Context Analysis (first 20 chunks) ===")
chunks_with_context = 0
chunks_with_reg_refs = 0
chunks_with_reg_citations = 0
total_context_tokens = 0
refinement_count = 0

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
        chunks_with_reg_citations += 1
    
    if analysis.get("needs_additional_context") or analysis.get("refined"):
        refinement_count += 1

print(f"Chunks with context tokens: {chunks_with_context}/{len(results)}")
print(f"Average context tokens: {total_context_tokens / len(results) if results else 0:.0f}")
print(f"Chunks with regulation references: {chunks_with_reg_refs}")
print(f"Chunks with regulation citations: {chunks_with_reg_citations}")
print(f"Chunks needing refinement: {refinement_count}")
print()

# Check vector collections
print("=== Vector Database Collections ===")
try:
    import chromadb
    from backend.app.config.settings import AppConfig
    
    config = AppConfig()
    chroma_path = Path(config.data_root) / "chroma"
    
    if not chroma_path.exists():
        print(f"⚠️  ChromaDB path does not exist: {chroma_path}")
    else:
        client = chromadb.PersistentClient(path=str(chroma_path))
        
        collections = ["manual_chunks", "regulation_chunks", "amc_chunks", "gm_chunks", "evidence_chunks"]
        for coll_name in collections:
            try:
                coll = client.get_collection(name=coll_name)
                count = coll.count()
                print(f"{coll_name}: {count} chunks")
                if count == 0:
                    print(f"  ⚠️  EMPTY - RAG will not work for this collection!")
            except Exception as e:
                print(f"{coll_name}: NOT FOUND ({str(e)[:60]})")
                print(f"  ⚠️  Collection missing - RAG will not work!")
except Exception as e:
    print(f"Error checking vector DB: {e}")
    import traceback
    traceback.print_exc()

print()

# Sample analysis details
print("=== Sample Analysis Details ===")
for i, result in enumerate(results[:5], 1):
    analysis = result.analysis or {}
    print(f"\nChunk {result.chunk_index}:")
    print(f"  Flag: {analysis.get('flag', 'N/A')}")
    print(f"  Context tokens: {result.context_token_count or 0}")
    print(f"  Reg refs: {len(analysis.get('regulation_references', []))}")
    print(f"  Reg citations: {len(analysis.get('citations', {}).get('regulation_sections', []))}")
    if analysis.get('needs_additional_context'):
        print(f"  ⚠️  Requested more context: {analysis.get('context_query', 'N/A')[:60]}")

print()
print("=== Issues Found ===")
issues = []

if red + yellow < 5 and audit.chunk_total > 100:
    issues.append("⚠️  Very few flags (RED+YELLOW) for large document - may indicate:")
    issues.append("   - RAG collections empty or not populated")
    issues.append("   - LLM too conservative (check prompt)")
    issues.append("   - Context not reaching LLM properly")

if chunks_with_context == 0:
    issues.append("⚠️  CRITICAL: No chunks have context tokens - RAG not working!")

if chunks_with_reg_refs == 0 and chunks_with_reg_citations == 0:
    issues.append("⚠️  WARNING: No regulation references found - LLM may not be using context!")

if not issues:
    print("✓ No obvious issues found")
else:
    for issue in issues:
        print(issue)

