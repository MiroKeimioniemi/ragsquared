# RAG Diagnostic Guide

## Issue: Only 1 RED and 3 YELLOW flags from 150 chunks

This guide helps diagnose why the system is finding so few compliance issues.

## What to Check

### 1. Check Logs for RAG Usage

With the improved logging, you should now see at INFO level:

- `RAG query: Searching 'regulation_chunks' collection (top_k=10)...` - Shows RAG is being called
- `RAG query: Found X/10 similar chunks in 'regulation_chunks' collection` - Shows results
- `RAG query: No results from 'regulation_chunks' collection...` - **WARNING**: Collection is empty!
- `Context built for chunk X: Y manual neighbors, Z regulations, W guidance...` - Summary of context
- `⚠️  No regulation context retrieved...` - **WARNING**: No regulations found

**What to look for:**
- Are RAG queries being executed? (Should see "RAG query: Searching..." for each collection)
- Are collections returning results? (Should see "Found X/Y similar chunks")
- Are warnings about empty collections? (This means RAG won't work)

### 2. Check Vector Database Collections

Run this to check if collections are populated:

```python
import chromadb
from pathlib import Path

chroma_path = Path("./data/chroma")
client = chromadb.PersistentClient(path=str(chroma_path))

collections = ["manual_chunks", "regulation_chunks", "amc_chunks", "gm_chunks"]
for coll_name in collections:
    try:
        coll = client.get_collection(name=coll_name)
        print(f"{coll_name}: {coll.count()} chunks")
    except:
        print(f"{coll_name}: NOT FOUND")
```

**Expected:**
- `regulation_chunks`: Should have thousands of chunks (regulation documents)
- `amc_chunks`: Should have chunks (AMC guidance)
- `gm_chunks`: Should have chunks (GM guidance)
- `manual_chunks`: Should have chunks from uploaded documents

**If collections are empty:**
- Regulations need to be processed and embedded
- Check if regulation documents were loaded into the system
- Run embedding pipeline for regulations

### 3. Check Context in Audit Results

Check the database to see what context was actually retrieved:

```python
from backend.app.db.session import get_session
from backend.app.db.models import AuditChunkResult
from sqlalchemy import desc

session = get_session()
audit = session.query(Audit).order_by(desc(Audit.created_at)).first()
results = session.query(AuditChunkResult).filter(
    AuditChunkResult.audit_id == audit.id
).limit(10).all()

for result in results:
    print(f"Chunk {result.chunk_index}: {result.context_token_count} tokens")
    analysis = result.analysis or {}
    print(f"  Regulations: {len(analysis.get('regulation_references', []))}")
    print(f"  Citations: {len(analysis.get('citations', {}).get('regulation_sections', []))}")
```

**What to look for:**
- `context_token_count` should be > 0 (ideally > 1000)
- `regulation_references` should have entries if regulations were provided
- `regulation_sections` in citations should have entries

### 4. Check LLM Responses

The LLM should be:
- Referencing regulations from context
- Citing regulation sections
- Using context to identify compliance gaps

**If LLM is not using context:**
- Check if context is actually in the prompt (should see regulation chunks in logs)
- Prompt may need to be more explicit (already improved)
- LLM might be too conservative (system prompt says "be conservative")

### 5. Common Issues

#### Issue: Collections are Empty
**Symptom:** Logs show "No results from 'regulation_chunks' collection"
**Solution:** 
- Load regulation documents
- Run embedding pipeline: `python -m pipelines.embed --doc-id <regulation_doc_id> --collection regulation_chunks`
- Check if regulations were processed

#### Issue: RAG Not Being Called
**Symptom:** No "RAG query: Searching..." messages in logs
**Solution:**
- Check if `build_context` is being called
- Check if vector client is initialized
- Check for errors in context_builder

#### Issue: Context Not Reaching LLM
**Symptom:** Context tokens > 0 but no regulation references in analysis
**Solution:**
- Check prompt - context should be in user message
- Verify context_text is not empty in bundle.render_text()
- LLM might be ignoring context (prompt improved to be more explicit)

#### Issue: LLM Too Conservative
**Symptom:** Many GREEN flags, few RED/YELLOW
**Solution:**
- System prompt says "be conservative" - this may be too lenient
- Consider adjusting severity thresholds
- Check if LLM is actually comparing against regulations

## Next Steps

1. **Run the audit again** with improved logging to see:
   - Are RAG queries happening?
   - Are collections populated?
   - Is context being built?
   - Is context reaching the LLM?

2. **Check the logs** for:
   - RAG query messages
   - Context summary messages
   - Warnings about empty collections
   - Warnings about missing context

3. **Verify collections** are populated:
   - Check ChromaDB collections
   - Verify regulation documents were processed
   - Check embedding status

4. **Review sample analyses**:
   - Check if regulations are being referenced
   - Check if context is being used
   - Verify LLM is comparing against regulations

## Improvements Made

1. **Enhanced Logging:**
   - RAG queries now log at INFO level (was DEBUG)
   - Empty collections now log as WARNING (was DEBUG)
   - Context summary logs at INFO level
   - Warnings when critical context is missing

2. **Improved Prompt:**
   - More explicit instruction to use context
   - Emphasizes that context was retrieved via RAG
   - Tells agent to cite regulations from context
   - Warns not to ignore provided context

3. **Better Visibility:**
   - Each RAG query is logged
   - Context bundle summary for each chunk
   - Warnings when context is missing

## Testing

After these changes, when you run an audit, you should see in the logs:

```
INFO: RAG query: Searching 'regulation_chunks' collection (top_k=10)...
INFO: RAG query: Found 10/10 similar chunks in 'regulation_chunks' collection
INFO: RAG query: Searching 'amc_chunks' collection (top_k=5)...
INFO: RAG query: Found 5/5 similar chunks in 'amc_chunks' collection
INFO: Context built for chunk abc123: 5 manual neighbors, 10 regulations, 10 guidance, 0 evidence, total tokens: 4500
INFO: RAG context ready: 10 regulations, 10 guidance, 5 manual neighbors
```

If you see warnings instead:
```
WARNING: RAG query: No results from 'regulation_chunks' collection (collection may be empty or not exist) - RAG will not work for this collection!
WARNING: ⚠️  No regulation context retrieved for chunk abc123 - LLM will not have regulation references to compare against!
```

This indicates the collections are empty and need to be populated.

