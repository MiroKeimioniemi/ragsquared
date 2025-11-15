# Recursive RAG Implementation

## Overview

The system now implements **recursive RAG** that provides comprehensive context by:

1. **Extracting references** from chunks (sections, subsections, chapters, parts)
2. **Recursively fetching** referenced sections via RAG
3. **Finding litigation** related to each chunk
4. **Recursively processing** litigation references
5. **Building comprehensive context** for analysis

## How It Works

### 1. Reference Extraction

The `ReferenceExtractor` class uses regex patterns to identify section references:
- "Section 4.2", "section 4.2", "Sect. 4.2"
- "4.2.1", "4.2"
- "Chapter 3", "chapter 3"
- "Part 145.A.30", "Part-145.A.30"
- "OSA 5", "OSA 5.2" (Finnish)
- "Kohdassa 3.4" (Finnish)

### 2. Recursive Processing Flow

```
Initial Chunk
  ↓
Extract References → RAG for each reference
  ↓
For each referenced section:
  - Extract its references → RAG recursively
  - Find litigation → RAG for litigation
  - For litigation: Extract references → RAG recursively
  ↓
Build comprehensive context bundle
```

### 3. Context Building

The `RecursiveContextBuilder`:
- Starts with base context (regulations, guidance, neighbors)
- Processes chunks in a queue (BFS traversal)
- Tracks processed chunks to avoid infinite loops
- Limits depth (default: 3 levels) to prevent excessive processing
- Limits references per chunk (default: 10) to manage token budgets

### 4. Litigation Retrieval

For each chunk processed:
- Searches `evidence_chunks` collection for related litigation
- Uses chunk content as query for semantic search
- Recursively processes references found in litigation

## Configuration

The recursive RAG is **enabled by default** in `ComplianceRunner`. To disable:

```python
runner = ComplianceRunner(session, config, use_recursive_rag=False)
```

### Parameters

- `max_depth`: Maximum recursion depth (default: 3)
- `max_references_per_chunk`: Max references to process per chunk (default: 10)

## Updated Prompt

The prompt now instructs the agent to:
1. **Identify references** in the focus chunk
2. **Use all context** including referenced sections and litigation
3. **Consider recursive references** when analyzing
4. **Use litigation context** for interpretation insights

## Benefits

1. **Full Context**: Agent sees all referenced sections, not just the focus chunk
2. **Comprehensive Analysis**: Can identify issues that span multiple sections
3. **Litigation Insights**: Understands how regulations have been interpreted
4. **Recursive Coverage**: References within references are also fetched

## Performance Considerations

- **Token Budget**: Recursive RAG can significantly increase context size
- **Processing Time**: More RAG calls = longer processing time
- **Rate Limits**: More API calls may hit rate limits faster
- **Depth Limits**: Max depth prevents infinite loops and excessive processing

## Example Flow

For a chunk mentioning "Section 4.2" and "Part-145.A.30":

1. **Initial RAG**: Get regulations, guidance, neighbors
2. **Extract References**: Find "Section 4.2" and "Part-145.A.30"
3. **RAG for Section 4.2**: Search manual_chunks for section 4.2
4. **RAG for Part-145.A.30**: Search regulation_chunks for Part-145.A.30
5. **Extract from Section 4.2**: If it references "Section 3.1", fetch that too
6. **Litigation for each**: Find litigation related to each chunk
7. **Final Analysis**: Agent analyzes with ALL context

## Logging

The system logs:
- Reference extraction: "Found X references in chunk..."
- Recursive processing: "Processing chunk X at depth Y"
- Litigation retrieval: "Found X litigation chunks"
- Final context: "Recursive context built: X manual, Y regulations, Z litigation..."

## Future Enhancements

- LLM-based reference extraction (more accurate than regex)
- Dedicated litigation collection
- Reference resolution using section_path metadata
- Smart caching of frequently referenced sections
- Configurable depth/limits per audit type

