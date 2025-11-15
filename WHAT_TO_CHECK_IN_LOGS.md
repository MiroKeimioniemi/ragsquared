# What to Check in Logs After Improvements

After the improvements I made, when you run an audit, you should see these log messages that will help diagnose RAG usage.

## Expected Log Messages (INFO Level)

### 1. RAG Query Messages

For each chunk, you should see RAG queries being executed:

```
INFO: RAG query: Searching 'regulation_chunks' collection (top_k=10) with query (first 50 chars): [chunk content]...
INFO: RAG query: Found 10/10 similar chunks in 'regulation_chunks' collection
```

**OR if collections are empty:**

```
WARNING: RAG query: No results from 'regulation_chunks' collection (collection may be empty or not exist) - RAG will not work for this collection!
```

### 2. Context Building Messages

For each chunk, you should see:

```
INFO: Building RAG context for chunk abc123... (draft=False, evidence=True)
INFO: RAG retrieval: Found 5 matches from collection 'manual_chunks' for chunk abc123...
INFO: RAG retrieval: Found 10 matches from collection 'regulation_chunks' for chunk abc123...
INFO: RAG retrieval: Found 5 matches from collection 'amc_chunks' for chunk abc123...
INFO: RAG retrieval: Found 5 matches from collection 'gm_chunks' for chunk abc123...
INFO: Context built for chunk abc123: 5 manual neighbors (including RAG), 10 regulations, 10 guidance, 0 evidence, total tokens: 4500
INFO: RAG context ready: 10 regulations, 10 guidance, 5 manual neighbors
```

**OR if context is missing:**

```
WARNING: ⚠️  No regulation context retrieved for chunk abc123 - LLM will not have regulation references to compare against!
WARNING: ⚠️  No guidance (AMC/GM) context retrieved for chunk abc123 - LLM will not have guidance material!
```

### 3. Processing Messages

```
INFO: Processing chunk
INFO: Starting chunk processing
INFO: Analysis completed
```

## What Each Message Tells You

### ✅ RAG is Working If You See:

1. **"RAG query: Searching..."** messages for each collection (regulation_chunks, amc_chunks, gm_chunks, manual_chunks)
2. **"RAG query: Found X/Y similar chunks"** messages showing results
3. **"Context built for chunk X: Y regulations, Z guidance..."** with non-zero counts
4. **"RAG context ready: X regulations, Y guidance..."** with non-zero counts

### ❌ RAG is NOT Working If You See:

1. **"RAG query: No results from 'regulation_chunks' collection..."** - Collection is empty
2. **"⚠️  No regulation context retrieved..."** - No regulations found
3. **"⚠️  No guidance (AMC/GM) context retrieved..."** - No guidance found
4. **"Context built for chunk X: 0 regulations, 0 guidance..."** - No context retrieved

## How to Check Logs

### Option 1: Flask Console Output

If running Flask with `flask run` or `make dev-up`, logs appear in the console.

### Option 2: Check Log Files

Logs may be written to files. Check:
- `data/logs/` directory
- Or check where Flask is outputting logs

### Option 3: Run Verification Script

Run the verification script I created:

```bash
python verify_rag_working.py
```

This will:
- Check if vector collections are populated
- Analyze audit results for context usage
- Show sample chunk details
- Identify issues

## Common Issues and Solutions

### Issue: "No results from 'regulation_chunks' collection"

**Problem:** The regulation_chunks collection is empty.

**Solution:**
1. Check if regulation documents were loaded
2. Run embedding pipeline for regulations:
   ```bash
   python -m pipelines.embed --doc-id <regulation_doc_id> --collection regulation_chunks
   ```
3. Verify ChromaDB collections using the verification script

### Issue: "Context built for chunk X: 0 regulations, 0 guidance"

**Problem:** RAG queries are running but returning no results.

**Solution:**
1. Check if collections exist and are populated
2. Verify embeddings were generated correctly
3. Check if query embeddings match stored embeddings (dimension mismatch)

### Issue: "Chunks have context but no regulation references"

**Problem:** Context is being retrieved but LLM is not using it.

**Solution:**
1. Check if context is actually in the prompt (should see regulation chunks in context_text)
2. The prompt was improved to be more explicit - verify it's being used
3. LLM might be too conservative - check system prompt

## Next Steps

1. **Run an audit** and watch the console/logs
2. **Look for the log messages** listed above
3. **Run the verification script** to get a summary
4. **Check vector collections** to ensure they're populated
5. **Review sample analyses** to see if regulations are being referenced

The improved logging should make it immediately clear:
- ✅ Is RAG being called? (Look for "RAG query: Searching...")
- ✅ Are collections populated? (Look for "Found X/Y similar chunks" vs "No results")
- ✅ Is context being built? (Look for "Context built for chunk...")
- ✅ Is context reaching the LLM? (Check audit results for regulation references)

