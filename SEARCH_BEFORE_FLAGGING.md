# Search Before Flagging - Implementation Guide

## Problem

The agent was flagging information as "missing" or "gaps" when it might actually exist elsewhere in the document. For example:
- "Critical part definition is missing" - but it might be defined in another section
- "PMA part acceptance process not detailed" - but it might be in a referenced section

## Solution

The agent now **MUST search before flagging gaps**. The workflow is:

1. **Identify potential gap**: Agent notices something seems missing
2. **Search first**: Set `needs_additional_context: true` with a specific `context_query`
3. **System searches**: RAG searches document and regulations for the information
4. **Evaluate results**: 
   - If found → Do NOT flag as gap (it exists elsewhere)
   - If not found → Can flag as gap (confirmed missing)

## Implementation Changes

### 1. Updated Prompt (`compliance.py`)

**Key Instructions Added:**
- **CRITICAL: SEARCH BEFORE FLAGGING** - Must search first before flagging gaps
- Only flag gaps AFTER searching and confirming missing
- Can make MULTIPLE searches with different queries
- If information found via search, do NOT flag as gap

**Example Workflow in Prompt:**
```
If you notice "critical part definition" seems missing:
1. Set needs_additional_context: true
2. context_query: "definition of critical part"
3. System searches → if found, don't flag
4. If not found after search, then can flag as gap
```

### 2. Enhanced Refinement System (`compliance_runner.py`)

**Changes:**
- Increased refinement attempts for recursive RAG (up to 5 searches)
- Better logging of search queries
- Stops if query unchanged (avoid infinite loops)
- Allows multiple targeted searches

**Flow:**
```
Initial Analysis → needs_additional_context: true
  ↓
Search 1: "critical part definition"
  ↓
Still needs context? → Search 2: "PMA part acceptance process"
  ↓
Still needs context? → Search 3: "evaluation criteria for PMA parts"
  ↓
After searches → Final analysis with full context
```

### 3. Recursive Context Builder (`recursive_context_builder.py`)

**New Features:**
- `context_query` parameter for targeted searches
- `_search_for_concept()` method for concept-based searches (not just section references)
- Searches both manual chunks AND regulations for concepts
- Recursively processes found chunks

**Search Types:**
1. **Section References**: "Section 4.2", "OSA 5" → Finds referenced sections
2. **Concepts**: "critical part definition", "PMA acceptance process" → Semantic search
3. **Regulations**: "Part-145.A.30", "AMC guidance" → Finds regulation sections

## Example: PMA Parts Issue

**Before (Incorrect):**
```
Gaps: 
- "Critical part definition missing"
- "PMA part acceptance process not detailed"
Flag: YELLOW
```

**After (Correct):**
```
Step 1: Initial analysis → needs_additional_context: true
        context_query: "definition of critical part"

Step 2: System searches → Finds definition in Section 3.4
        → Do NOT flag as gap

Step 3: Still analyzing → needs_additional_context: true
        context_query: "PMA part acceptance procedures"

Step 4: System searches → Finds process in Section 5.2
        → Do NOT flag as gap

Final: Only flag if searches confirm information is missing
```

## Benefits

1. **Accurate Gap Identification**: Only flags gaps that are actually missing
2. **Comprehensive Context**: Agent sees all relevant information before deciding
3. **Reduced False Positives**: Won't flag things that exist elsewhere
4. **Better Analysis**: Agent has full picture before making recommendations

## Configuration

- `REFINEMENT_MAX_ATTEMPTS`: Default 1, increased to 5 for recursive RAG
- Can be adjusted via environment variable
- System automatically stops if queries don't change (avoid loops)

## Logging

You'll see:
```
INFO: Refinement attempt 1/5: Searching for: definition of critical part...
INFO: Processing context_query: definition of critical part...
INFO: Concept search: definition of critical part... (match 1)
INFO: Found definition in Section 3.4 - not flagging as gap
```

## Best Practices for Agent

1. **Be specific in queries**: "definition of critical part" not just "critical part"
2. **Try multiple queries**: If first search doesn't find it, refine the query
3. **Search regulations too**: Use queries that will search both manual and regulations
4. **Only flag after searching**: Never flag something as missing without searching first

