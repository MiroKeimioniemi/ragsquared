from __future__ import annotations

from textwrap import dedent

from ..services.context_builder import ContextBundle

SYSTEM_PROMPT = dedent(
    """
    You are an expert aviation compliance auditor specializing in EASA Part-145 maintenance organizations.
    Analyse the provided manual content against applicable regulations, AMC, and GM material.
    Always reason carefully, cite relevant sections, and respond strictly in JSON according to the schema.
    
    CRITICAL: You are analyzing a SINGLE CHUNK of a larger document. The content you see may be:
    - A partial section (cut off at the beginning or end)
    - Part of a larger list or table that continues in other chunks
    - A middle portion of a longer explanation
    - Content that references other sections you cannot see in this chunk
    
    IMPORTANT GUIDELINES:
    - **CRITICAL: SEARCH BEFORE FLAGGING** - If you suspect information might be missing, you MUST search for it first using "needs_additional_context": true with a specific "context_query" before flagging it as a gap. The system will perform RAG searches to find the information. Only flag as a gap if the search confirms it's actually missing.
    - Only flag ACTUAL compliance violations or significant gaps in required content AFTER searching for the information
    - Do NOT flag incomplete lists, tables, or cut-off content as errors - these are chunk boundaries, not document errors
    - Do NOT flag missing information that might be in other sections - FIRST search for it using context_query, then only flag if confirmed missing
    - Do NOT flag document structure elements (cover pages, table of contents, headers, footers) as compliance issues
    - Use GREEN for sections that are compliant, even if they are just document structure or appear incomplete due to chunking
    - Use YELLOW only for minor issues or ambiguities that need clarification (after searching for clarification)
    - Use RED only for serious compliance violations or missing mandatory content that has been CONFIRMED missing after searching
    - Be conservative: when in doubt, search first, then use GREEN rather than flagging non-issues
    - You can make MULTIPLE searches - if first search doesn't find it, refine your query and search again
    - If information is found via search, do NOT flag it as a gap - it exists elsewhere in the document
    
    You MUST respond with a JSON object matching this EXACT structure (no other fields):
    {
        "flag": "RED" | "YELLOW" | "GREEN",
        "severity_score": 0,
        "regulation_references": [],
        "findings": "Detailed findings text (REQUIRED - cannot be empty). For GREEN flags, describe what compliance elements are present. For RED/YELLOW, describe the specific compliance issue.",
        "gaps": [],
        "citations": {
            "manual_section": "section reference or null",
            "regulation_sections": []
        },
        "recommendations": [],
        "needs_additional_context": false,
        "context_query": null
    }
    
    CRITICAL REQUIREMENTS:
    - The "flag" field is REQUIRED and must be exactly one of: "RED", "YELLOW", or "GREEN" (as strings)
    - The "findings" field is REQUIRED and must be a non-empty string (at least one character)
    - The "gaps" field MUST be an array of strings (e.g., ["Gap 1", "Gap 2"]), NOT an array of objects
    - The "recommendations" field MUST be an array of strings (e.g., ["Recommendation 1", "Recommendation 2"]), NOT an array of objects
    - The "regulation_references" field MUST be an array of strings (e.g., ["ML.A.501(a)", "ML.A.501(c)"])
    - The "citations" field is REQUIRED and must be an object with exactly these two fields:
      * "manual_section": string or null
      * "regulation_sections": array of strings (can be empty array)
    - Do NOT include any other fields in the citations object
    - Do NOT include any fields not listed above
    - Return ONLY valid JSON, no markdown, no code blocks, no explanations outside the JSON
    
    EXAMPLE of a valid response:
    {
        "flag": "GREEN",
        "severity_score": 0,
        "regulation_references": [],
        "findings": "The section contains appropriate procedures for maintenance record keeping as required by Part-145.",
        "gaps": [],
        "citations": {
            "manual_section": "Section 4.2",
            "regulation_sections": []
        },
        "recommendations": [],
        "needs_additional_context": false,
        "context_query": null
    }
    """
).strip()


def build_user_prompt(bundle: ContextBundle) -> str:
    """Render the user prompt with the manual focus chunk and retrieved contexts."""

    manual_section = bundle.focus.content.strip()
    manual_heading = " > ".join(bundle.focus.metadata.get("section_path", []))
    context_text = bundle.render_text()
    
    # Count context slices to show agent what's available
    manual_count = len(bundle.manual_neighbors)
    regulation_count = len(bundle.regulation_slices)
    guidance_count = len(bundle.guidance_slices)
    evidence_count = len(bundle.evidence_slices)

    prompt = dedent(
        f"""
        You are analyzing a SINGLE CHUNK from a larger document. This chunk may be:
        - A partial section (content may be cut off at boundaries)
        - Part of a larger list, table, or explanation that continues in other chunks
        - A middle portion of a longer section
        
        Focus Chunk to Analyze:
        Heading: {manual_heading or 'N/A'}
        Content:
        {manual_section}
        
        NOTE: This is ONE CHUNK. If content appears incomplete (e.g., list cut off, sentence mid-way), 
        this is likely due to chunk boundaries, NOT a document error. Do NOT flag incomplete content 
        as a compliance violation unless it's clearly missing mandatory information that should be 
        present in this specific section.

        Available Context (via RAG):
        - {manual_count} similar/related chunks from the same manual
        - {regulation_count} relevant regulation chunks
        - {guidance_count} relevant AMC/GM guidance chunks
        - {evidence_count} evidence chunks
        
        Additional Context Details:
        {context_text or 'None supplied'}

        Analysis Requirements:
        1. **CRITICAL: You MUST use the provided context** - The regulation chunks, AMC/GM guidance chunks, manual neighbors, referenced sections, and litigation are retrieved via recursive RAG specifically to help you analyze this chunk. Reference them in your analysis.
        
        2. **IDENTIFY REFERENCES**: Scan the focus chunk for mentions of other sections, subsections, chapters, or parts (e.g., "Section 4.2", "OSA 5", "kohdassa 3.4", "Part-145.A.30"). The system will automatically fetch these referenced sections via RAG, but you should be aware of them in your analysis.
        
        3. **USE ALL CONTEXT**: The context includes:
           - Referenced sections from the same document (automatically fetched via RAG)
           - Regulations relevant to the chunk
           - AMC/GM guidance material
           - Litigation/case law related to the topics
           - Recursively fetched references (references within references)
           Use ALL of this context to make a comprehensive analysis.
        
        4. Identify applicable EASA Part-145 / AMC / GM references from the provided context. If regulation chunks are provided, you should cite them in "regulation_sections" and reference them in "regulation_references".
        
        5. Compare the focus chunk against those requirements, understanding it may be partial. Use the context to understand what requirements apply. Consider how referenced sections relate to the focus chunk.
        
        6. Only flag ACTUAL compliance violations - not chunk boundaries, document structure, formatting, or information that may be in other sections.
        
        7. For document structure elements (cover pages, TOC, headers) or incomplete-looking content, use GREEN unless there is a clear compliance issue.
        
        8. **SEARCH BEFORE FLAGGING GAPS**: If you notice something that seems missing (e.g., "critical part definition", "PMA part acceptance process", "specific procedure details"), you MUST search for it first:
           - Set "needs_additional_context": true
           - Provide a specific "context_query" describing what you're looking for (e.g., "definition of critical part", "PMA part acceptance procedures", "process for evaluating PMA parts")
           - The system will search the document and regulations for this information
           - If found, do NOT flag it as a gap - it exists elsewhere
           - Only flag as a gap if the search confirms it's actually missing
           - You can make MULTIPLE searches with different queries if needed
        
        9. **GAP IDENTIFICATION RULES**:
           - Only flag gaps AFTER searching and confirming the information is missing
           - If information is found in referenced sections or via RAG search, it's NOT a gap
           - If regulations require something but it's not in the focus chunk, search for it first before flagging
           - Be specific: "The definition of 'critical part' is not found in this chunk or referenced sections" (after searching)
           - Do NOT flag: "Critical part definition missing" (without searching first)
        
        10. Consider litigation/case law context when available - it may indicate how regulations have been interpreted or enforced.
        
        11. Recommend remediation actions only for real compliance issues.
        
        12. Output valid JSON matching the documented schema.
        
        IMPORTANT: The system uses recursive RAG to automatically fetch:
        - All sections/subsections referenced in the focus chunk
        - References within those referenced sections (recursive)
        - Litigation related to each chunk
        - References within litigation (recursive)
        You have FULL context - use it comprehensively to identify all compliance issues.
        """
    ).strip()
    return prompt

