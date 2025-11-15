# RAG Implementation - Design Spec Compliance

## Summary

The RAG (Retrieval Augmented Generation) implementation has been updated to match the requirements specified in `AI_Auditing_System_Design.md` Section 3.2 (Phase 2: Chunk-by-Chunk Processing).

## Spec Requirements (Section 3.2)

**Step 1: Initial Context Loading**
- Vector search: **top-5 similar chunks from same manual**
- Vector search: **top-10 relevant regulation chunks**
- Vector search: **top-5 relevant AMC/GM chunks**

## Implementation Changes

### 1. Configuration Updates (`backend/app/config/settings.py`)

**Before:**
- `CONTEXT_REGULATION_TOP_K` default: 5
- `CONTEXT_GUIDANCE_TOP_K` default: 3

**After:**
- `CONTEXT_REGULATION_TOP_K` default: **10** ✅ (matches spec)
- `CONTEXT_GUIDANCE_TOP_K` default: **5** ✅ (matches spec)

### 2. Context Builder Updates (`backend/app/services/context_builder.py`)

**Manual RAG Search:**
- Added explicit RAG search within `manual_chunks` collection
- Uses **top-5** similar chunks via vector search (hardcoded per spec)
- Combines with sequential neighbors (window-based) to avoid duplicates
- Comment added: "Per spec (Section 3.2): Vector search: top-5 similar chunks from same manual"

**Regulation RAG Search:**
- Uses `regulation_top_k` (now defaults to **10**)
- Comment added: "Per spec (Section 3.2): Vector search: top-10 relevant regulation chunks"

**Guidance RAG Search:**
- AMC: Uses `guidance_top_k` (now defaults to **5**)
- GM: Uses `guidance_top_k` (now defaults to **5**)
- Comment added: "Per spec (Section 3.2): Vector search: top-5 relevant AMC/GM chunks"
- Note: We interpret this as top-5 from AMC and top-5 from GM (separate collections), giving up to 10 total guidance chunks

### 3. Enhanced Logging

Added comprehensive logging to track RAG usage:
- Logs when vector queries are executed
- Logs number of matches found per collection
- Logs context summary (manual neighbors, regulations, guidance, evidence counts)
- Helps debug when collections are empty or queries fail

## Verification

Run `python verify_rag_spec.py` to confirm all settings match the spec.

## Current Status

✅ **All RAG settings match the design spec!**

- Manual RAG: top-5 similar chunks (via vector search)
- Regulation RAG: top-10 relevant chunks
- Guidance RAG: top-5 AMC + top-5 GM chunks
- Evidence RAG: top-2 (optional, not in spec)

## Next Steps

1. **Generate Embeddings**: The `manual_chunks` collection needs to be populated with embeddings for RAG to work. Run `regenerate_embeddings.py` (when database is not locked).

2. **Load Regulation Data**: For regulation RAG to work, regulation documents need to be processed and stored in the `regulation_chunks` collection.

3. **Load AMC/GM Data**: For guidance RAG to work, AMC and GM documents need to be processed and stored in `amc_chunks` and `gm_chunks` collections.

## Notes

- The RAG implementation uses ChromaDB for vector storage
- Collections are created automatically when embeddings are stored
- If a collection doesn't exist, the query gracefully returns empty results (logged as debug)
- Sequential neighbors (window-based) are still included alongside RAG results for comprehensive context

