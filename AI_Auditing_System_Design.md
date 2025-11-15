# AI-Assisted End-to-End Auditing Workflow System Design
## EASA Part-145 Maintenance Organizations

### Executive Summary

This document outlines the design for an AI-assisted auditing system that automates compliance checking for aviation maintenance organizations against EASA Part-145 regulations. The system processes large volumes of organizational manuals and evidence documents, cross-references them against EU regulations (EASA Easy Access Rules), and generates comprehensive audit reports with flagging and recommendations.

---

## 1. System Overview

### 1.1 Core Objectives
- **Cost Reduction**: Reduce auditing costs by 50-70%
- **Time Efficiency**: Accelerate processes from weeks to days
- **Consistency**: Eliminate human fatigue and subjectivity
- **Accuracy**: Detect minor anomalies and non-conformities
- **Scalability**: Handle large document volumes efficiently

### 1.2 Target Use Cases
1. **Primary**: EASA Part-145 maintenance organization audits
2. **Secondary**: Pre-submission manual compatibility testing (Test Bench)
3. **Future**: Maritime, rail, and communications sector adaptation

### 1.3 Hackathon Scope & Constraints
- **Backend Only Focus**: Frontend deferred; all effort goes into API + agent layer.
- **Stack Simplification**: Use Flask, SQLite, and local storage to minimize setup time.
- **Agent Priority**: Deliver the custom agentic workflow with OpenRouter-powered LLM access.
- **Pragmatic Choices**: Prefer off-the-shelf libraries (LangChain/LlamaIndex, embeddings SDKs) over bespoke infrastructure.
- **Out-of-Scope**: Elastic scaling, distributed queues, cloud object storage, and long-term ops tooling.

---

## 2. System Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Ingestion Layer                  │
│  (Manuals, Evidence Sets, EASA Regulations, AMC, GM)        │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  Document Processing Pipeline                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Chunking   │→ │   Embedding  │→ │   Indexing   │      │
│  │   Engine     │  │   Generator  │  │   (Vector    │      │
│  │              │  │              │  │    Store)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                   AI Agent Orchestration                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │   Single-Agent Compliance Runner (Sequential)       │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │   │
│  │  │ Context Prep │  │ LLM Analysis │  │ Flagging │  │   │
│  │  └──────────────┘  └──────────────┘  └──────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                    Flagging & Reporting                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Flag       │→ │   Report     │→ │   Question   │      │
│  │   Generator  │  │   Compiler   │  │   Generator  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 Component Breakdown

#### 2.2.1 Document Ingestion Layer
- **Input Sources**:
  - Organizational manuals (PDF, DOCX, HTML)
  - Evidence sets (compliance documents, procedures, records)
  - EASA Easy Access Rules (Part-145, AMC, GM)
  - Historical regulatory versions (for comparison)
- **Format Support**: PDF, DOCX, HTML, Markdown, TXT
- **Preprocessing**: OCR for scanned documents, text extraction, metadata extraction

#### 2.2.2 Document Processing Pipeline
- **Chunking Strategy**:
  - Semantic chunking (preserve context)
  - Overlap windows (50-100 tokens) to maintain continuity
  - Section-aware chunking (respect document structure)
  - Chunk size: 500-1000 tokens (configurable)
- **Embedding Generation**:
  - Model: Multi-lingual embedding model (e.g., `text-embedding-3-large` or `sentence-transformers/all-mpnet-base-v2`)
  - Separate embeddings for:
    - Manual chunks
    - Regulation chunks
    - Evidence chunks
- **Vector Store**:
  - Primary: ChromaDB or Pinecone (for scalability)
  - Collections:
    - `manual_chunks`: Organization's manual sections
    - `regulation_chunks`: EASA Part-145 regulations
    - `amc_chunks`: Acceptable Means of Compliance
    - `gm_chunks`: Guidance Material
    - `evidence_chunks`: Supporting evidence documents

#### 2.2.3 AI Agent Orchestration (Single-Agent Hackathon Edition)

**ComplianceRunner Workflow (sequential)**:

```
For each chunk from manual:
  1. Initial Context Loading
     - Load chunk content
     - Retrieve top-k similar chunks from same document (document context)
     - Retrieve top-k relevant regulation chunks (regulation context)
     - Retrieve top-k relevant AMC/GM chunks (guidance context)
  
  2. Contextual Analysis
     - Agent analyzes chunk with loaded context
     - Identifies potential regulatory references
     - Detects missing information or ambiguities
  
  3. Adaptive Context Retrieval
     - If subsection is unspecified → search vector store
     - If regulation reference unclear → retrieve specific regulation section
     - If evidence needed → search evidence chunks
     - Iterative refinement (max 2-3 iterations)
  
  4. Compliance Assessment
     - Compare chunk against relevant regulations
     - Identify gaps and non-conformities
     - Assess severity and risk level
  
  5. Flag Generation
     - RED: Critical non-conformity (must fix)
     - YELLOW: Potential issue or gap (review required)
     - GREEN: Compliant or acceptable
```

This hackathon release keeps everything inside a single `ComplianceRunner` so we can ship quickly without coordinating multiple agents or parallel context hops. Section 4.5 documents how this runner should expose clean hooks (planning hints, retrieval adapters, output schema) so that future agents can plug in without rewriting the MVP.

**Agent Capabilities**:
- **LLM Model**: GPT-4 or Claude 3.5 Sonnet (for complex reasoning)
- **Context Window**: 128K tokens (to handle large context)
- **Reasoning**: Chain-of-thought, structured output (JSON)
- **Tool Use**: Vector search, regulation lookup, citation extraction

#### 2.2.4 Flagging System

**Flag Criteria**:

| Flag | Severity | Criteria | Action Required |
|------|----------|----------|-----------------|
| 🔴 RED | Critical | Direct violation of mandatory requirement, missing mandatory element, safety-critical gap | Must address before approval |
| 🟡 YELLOW | Warning | Ambiguous language, potential non-compliance, missing recommended element, unclear reference | Review and clarify |
| 🟢 GREEN | Compliant | Meets requirements, properly documented, clear and unambiguous | No action needed |

**Flag Attributes**:
- Flag type (RED/YELLOW/GREEN)
- Severity score (0-100)
- Affected regulation reference (Part-145.X.Y)
- Gap description
- Recommendation
- Citations (manual section, regulation section)
- Evidence references

#### 2.2.5 Report Generation

**Report Structure**:

1. **Executive Summary**
   - Overall compliance score
   - Flag distribution (RED/YELLOW/GREEN counts)
   - Critical issues summary
   - Approval recommendation

2. **Detailed Findings**
   - Organized by manual section
   - Each finding includes:
     - Chunk identifier
     - Flag type and severity
     - Regulation reference
     - Gap/non-conformity description
     - Evidence/citations
     - Recommendations
     - Comparison with regulation text

3. **Regulatory Comparison**
   - Side-by-side comparison of manual vs. regulation
   - Version differences (if applicable)
   - Missing elements
   - Additional elements (beyond requirements)

4. **Auditor Questions**
   - Comprehensive list of questions for manual review
   - Organized by regulation section
   - Includes context and reasoning

5. **Appendices**
   - Full chunk analysis logs
   - Vector search results
   - Regulation excerpts
   - Evidence document references

---

## 3. Detailed Workflow

### 3.1 Phase 1: Document Ingestion & Indexing

```
1. Upload Documents
   ├── Manual documents (organization)
   ├── EASA Part-145 regulations
   ├── AMC (Acceptable Means of Compliance)
   ├── GM (Guidance Material)
   └── Evidence sets (optional)

2. Document Processing
   ├── Extract text (OCR if needed)
   ├── Parse structure (sections, subsections)
   ├── Extract metadata (version, date, organization)
   └── Normalize format

3. Chunking
   ├── Manual → semantic chunks (preserve structure)
   ├── Regulations → section-based chunks
   ├── AMC/GM → guidance chunks
   └── Evidence → evidence chunks

4. Embedding & Indexing
   ├── Generate embeddings for all chunks
   ├── Store in vector database
   ├── Create metadata index (section numbers, references)
   └── Build cross-reference map
```

### 3.2 Phase 2: Chunk-by-Chunk Processing

```
For each chunk in manual:
  
  Step 1: Initial Context Loading
  ├── Retrieve chunk content
  ├── Vector search: top-5 similar chunks from same manual
  ├── Vector search: top-10 relevant regulation chunks
  ├── Vector search: top-5 relevant AMC/GM chunks
  └── Load section metadata (parent sections, references)
  
  Step 2: Agent Analysis
  ├── Input: chunk + loaded context
  ├── Agent analyzes compliance
  ├── Identifies regulatory references
  └── Detects ambiguities/gaps
  
  Step 3: Adaptive Context Retrieval (if needed)
  ├── If subsection unspecified → search vector store
  ├── If regulation unclear → retrieve specific section
  ├── If evidence needed → search evidence chunks
  └── Refine analysis with additional context
  
  Step 4: Compliance Assessment
  ├── Compare against regulations
  ├── Identify gaps/non-conformities
  ├── Assess severity
  └── Generate flag
  
  Step 5: Output
  ├── Flag (RED/YELLOW/GREEN)
  ├── Severity score
  ├── Findings description
  ├── Regulation references
  ├── Citations
  └── Recommendations
```

### 3.3 Phase 3: Report Compilation

```
1. Aggregate Results
   ├── Collect all chunk analyses
   ├── Group by manual section
   ├── Sort by severity (RED → YELLOW → GREEN)
   └── Calculate statistics

2. Generate Executive Summary
   ├── Overall compliance score
   ├── Flag distribution
   ├── Critical issues list
   └── Approval recommendation

3. Compile Detailed Findings
   ├── For each RED flag: detailed analysis
   ├── For each YELLOW flag: detailed analysis
   ├── Include citations and evidence
   └── Add recommendations

4. Regulatory Comparison
   ├── Extract regulation requirements
   ├── Compare with manual sections
   ├── Highlight differences
   └── Version comparison (if applicable)

5. Generate Auditor Questions
   ├── For each regulation section
   ├── Generate relevant questions
   ├── Include context
   └── Organize by priority

6. Format Report
   ├── Markdown/PDF export
   ├── Interactive HTML (optional)
   └── Include appendices
```

---

## 4. Technical Implementation

### 4.1 Technology Stack

**Core Framework**:
- **Language**: Python 3.11+
- **Web Framework**: Flask + Flask-RESTful (lightweight routing, request handling)
- **LLM Framework**: LangChain or LlamaIndex (use whichever accelerates prototyping)
- **LLM Access**: OpenRouter (configured with GPT-4o / Claude 3.5 via API key)
- **Embedding Model**: OpenAI `text-embedding-3-large` or `sentence-transformers/all-mpnet-base-v2`
- **Vector Database**: ChromaDB (embedded, file-backed for hackathon portability)
- **Document Processing**: PyPDF2, python-docx, BeautifulSoup4, pytesseract (optional OCR)
- **Chunking**: LangChain `RecursiveCharacterTextSplitter` with custom section-aware logic

**Infrastructure (Hackathon Edition)**:
- **Persistence**: SQLite via SQLAlchemy (single-file DB, zero setup)
- **Background Tasks**: Simple worker threads or `rq` (Redis optional) triggered from Flask; fallback to synchronous jobs for demos.
- **File Storage**: Local `./data/uploads` + `./data/processed` directories managed by app.
- **Secrets**: `.env` file + `python-dotenv` for OpenRouter keys and embedding credentials.
- **Frontend**: Deferred; CLI or Swagger UI for manual interaction.

### 4.2 Key Components

#### 4.2.1 Document Processor

```python
class DocumentProcessor:
    - extract_text(document_path)
    - parse_structure(document)
    - chunk_document(document, strategy="semantic")
    - generate_embeddings(chunks)
    - index_chunks(chunks, collection_name)
```

#### 4.2.2 Context Retriever

```python
class ContextRetriever:
    - retrieve_document_context(chunk, top_k=5)
    - retrieve_regulation_context(chunk, top_k=10)
    - retrieve_guidance_context(chunk, top_k=5)
    - retrieve_adaptive_context(query, collection, top_k)
    - combine_contexts(*contexts)
```

#### 4.2.3 Compliance Agent

```python
class ComplianceAgent:
    - analyze_chunk(chunk, context)
    - identify_regulatory_references(chunk)
    - detect_gaps(chunk, regulations)
    - assess_compliance(chunk, regulations)
    - generate_flag(analysis_result)
    - generate_recommendations(flag, gap)
```

#### 4.2.4 Report Generator

```python
class ReportGenerator:
    - compile_findings(chunk_analyses)
    - generate_executive_summary(statistics)
    - generate_detailed_findings(flags)
    - generate_regulatory_comparison(manual, regulations)
    - generate_auditor_questions(regulations, findings)
    - export_report(format="markdown")
```

### 4.3 Agent Prompt Design

**Main Analysis Prompt**:

```
You are an expert aviation compliance auditor specializing in EASA Part-145 maintenance organizations.

Your task is to analyze a section of an organization's manual against EASA Part-145 regulations, AMC, and GM.

CONTEXT PROVIDED:
- Manual Section: {chunk}
- Document Context: {document_context}
- Relevant Regulations: {regulation_context}
- Guidance Material: {guidance_context}

ANALYSIS REQUIREMENTS:
1. Identify which EASA Part-145 requirements apply to this section
2. Compare the manual section against the requirements
3. Identify any gaps, ambiguities, or non-conformities
4. Assess severity:
   - RED: Critical non-conformity (mandatory requirement violated/missing)
   - YELLOW: Potential issue (ambiguous, unclear, missing recommended element)
   - GREEN: Compliant (meets requirements)

OUTPUT FORMAT (JSON):
{
  "flag": "RED|YELLOW|GREEN",
  "severity_score": 0-100,
  "regulation_references": ["Part-145.X.Y", ...],
  "findings": "Description of findings",
  "gaps": ["Gap 1", "Gap 2", ...],
  "citations": {
    "manual_section": "Section X.Y",
    "regulation_sections": ["Part-145.X.Y"]
  },
  "recommendations": ["Recommendation 1", ...],
  "needs_additional_context": true/false,
  "context_query": "Query for additional context if needed"
}
```

**Adaptive Context Retrieval Prompt**:

```
The previous analysis identified a gap or ambiguity: {gap_description}

Search for additional context to clarify:
- Regulation: {regulation_query}
- Evidence: {evidence_query}
- Related sections: {section_query}

Provide refined analysis with new context.
```

### 4.4 Data Flow

```
Document Upload
    ↓
Document Processing (parallel)
    ├── Manual Processing
    ├── Regulation Processing
    └── Evidence Processing
    ↓
Chunking & Embedding (parallel)
    ↓
Vector Store Indexing
    ↓
Chunk Processing (sequential with parallel context retrieval)
    ├── Context Retrieval (parallel)
    ├── Agent Analysis
    ├── Adaptive Retrieval (if needed)
    └── Flag Generation
    ↓
Result Aggregation
    ↓
Report Generation
    ↓
Export (Markdown/PDF)
```

### 4.5 Agent Execution Guidelines & Future Expansion

**Hackathon Reality: Single-Agent `ComplianceRunner`**
- One LangChain/LlamaIndex chain owns planning, retrieval, reasoning, and flag synthesis in sequence.
- The runner maintains a lightweight state object (`ChunkSession`) that carries manual chunk text, retrieval pointers, and prior decisions so retries stay deterministic.
- Each chunk follows the exact order: build context → call OpenRouter model → normalize JSON → persist/log.
- No parallel sub-agents are spawned; instead, planner/retriever logic lives as Python functions the runner can call synchronously.

**Hackathon Flow (per chunk)**
1. `prepare_context(session)`: deterministic retrieval fan-out (manual neighbors, regulations, AMC/GM, optional evidence) with capped token budgets.
2. `analyze_chunk(session)`: OpenRouter call (default `claude-3.5-sonnet` or `gpt-4o-mini` fallback) using the structured prompt from §4.3; always request JSON.
3. `score_and_flag(result)`: map severity, attach citations, and return a normalized payload ready for SQLite + report rendering.
4. `log_and_emit(session, result)`: persist raw prompt/response under `data/logs/compliance_runner/{timestamp}.json`, then stream summarized status to the CLI/API.

**Future Agent Big-Picture Principles**
- **Composable boundaries**: even if a single process owns everything today, keep `prepare_context`, `analyze_chunk`, and `score_and_flag` pure so future agents can take over individual steps without rewiring storage.
- **Deterministic contracts**: every step must read/write typed dataclasses (e.g., `ContextBundle`, `ComplianceResult`). Version fields allow later agents to negotiate schema upgrades.
- **Budget awareness**: expose knobs for context sizes, retry counts, and provider/model selection so a future “retrieval specialist” agent can tune them without touching business logic.
- **Observability first**: log prompts, token counts, and citations regardless of how many agents exist. Traces become the truth source when concurrent agents arrive.

**Future Agent Small-Picture Checklist**
- Define JSON schemas in `contracts/` before introducing a new agent; include sample payloads.
- Reuse the existing `.env` keys (`OPENROUTER_API_KEY`, `OPENROUTER_MODEL_COMPLIANCE`, etc.) to avoid per-agent secrets sprawl.
- Keep hand-offs file-based (paths/IDs) or DB-referenced—never raw blob strings—so agents can work on different machines or threads later.
- Guard every OpenRouter call with retry + circuit-breaker helpers to prevent cascading failures when orchestration becomes more complex.
- When experimenting with new agents, fork the runner via feature flags (`AGENT_MODE=single|hybrid`) instead of editing the core loop; this keeps the hackathon demo stable.

**OpenRouter Integration Notes**
- Store API keys + preferred model IDs inside `.env` and load with `python-dotenv`; even the single runner should support swapping models per stage.
- Use `httpx` directly (sync) for minimal dependencies; wrap it in `openrouter_client.py` so future agents share throttling + telemetry code.
- Continue logging prompts/responses to `./data/logs/{component}/{timestamp}.json`; when agents multiply, give each a folder but reuse the same metadata schema (chunk_id, doc_id, token counts).

---

## 5. Test Bench Feature (Bonus)

### 5.1 Test Bench Workflow

Organizations can upload draft manuals before official submission to test compatibility:

```
1. Upload Draft Manual
   └── Mark as "draft" / "test"

2. Run Compatibility Check
   ├── Same processing pipeline
   ├── Generate report
   └── Provide feedback

3. Iterative Improvement
   ├── Organization fixes issues
   ├── Re-upload
   └── Re-check

4. Final Report
   └── Export for official submission
```

### 5.2 Test Bench Features

- **Pre-submission validation**: Check before official submission
- **Iterative feedback**: Multiple rounds of checking
- **Comparison mode**: Compare draft versions
- **Compliance score tracking**: Monitor improvement over iterations
- **Quick feedback**: Faster processing (no full audit depth)

---

## 6. Scalability & Performance

### 6.1 Performance Targets

- **Document Processing**: < 5 minutes for 500-page manual
- **Chunk Processing**: < 30 seconds per chunk (with context)
- **Full Audit**: < 2 hours for typical manual (100-200 chunks)
- **Test Bench**: < 30 minutes for quick check

### 6.2 Throughput Hacks (Good Enough for Demo)

- **Lightweight Parallelism**: 
  - Use `concurrent.futures.ThreadPoolExecutor` for OCR/text extraction fan-out.
  - Keep chunk processing sequential to preserve context; only context retrieval calls run concurrently.
  - Optional: drop-in `rq` worker if Redis is available; otherwise stick with synchronous Flask endpoints + background threads.
- **Aggressive Caching**:
  - Cache embeddings and regulation contexts on disk (`./cache/embeddings.pkl`).
  - Store previously retrieved regulation snippets (JSON) to avoid repeated OpenRouter calls.
- **Vector Store Hygiene**:
  - Batch insert chunks to Chroma to reduce metadata writes.
  - Periodically compact the local Chroma store (or delete + rebuild) if corruption occurs.

### 6.3 Cost Optimization

- **Embedding Caching**: Reuse embeddings for same documents
- **Batch Processing**: Process multiple chunks in single LLM call when possible
- **Model Selection**: Use cheaper models for simple tasks, expensive for complex
- **Context Management**: Limit context size to necessary tokens

---

## 7. Multi-Sector Adaptation

### 7.1 Adaptation Strategy

The system is designed to be sector-agnostic:

1. **Regulation Source**: Replace EASA Part-145 with sector-specific regulations
2. **Chunking Strategy**: Adapt to sector-specific document structures
3. **Flag Criteria**: Adjust severity thresholds per sector
4. **Agent Prompts**: Update with sector-specific expertise

### 7.2 Sector-Specific Configurations

| Sector | Regulation Source | Key Differences |
|--------|------------------|-----------------|
| Aviation | EASA Easy Access Rules | Part-145, Part-M, Part-66 |
| Maritime | IMO Conventions, EU Directives | SOLAS, MARPOL, STCW |
| Rail | EU Railway Package, TSI | Safety, interoperability |
| Communications | EU Directives, National Regulations | Cybersecurity, data protection |

---

## 8. Implementation Phases

### Phase 1: MVP (Weeks 1-2)
- Basic document ingestion
- Simple chunking
- Vector store setup
- Single-agent analysis
- Basic flagging (RED/YELLOW/GREEN)
- Simple report generation

### Phase 2: Enhanced Agent (Weeks 3-4)
- Multi-context retrieval
- Adaptive context search
- Improved flagging logic
- Detailed report with citations
- Regulatory comparison

### Phase 3: Test Bench (Week 5)
- Draft manual support
- Iterative checking
- Comparison features
- Quick feedback mode

### Phase 4: Optimization (Week 6)
- Performance tuning
- Cost optimization
- UI/UX improvements
- Documentation

---

## 9. Success Metrics

- **Accuracy**: > 90% flag accuracy (validated by human auditors)
- **Cost Reduction**: 50-70% reduction in audit costs
- **Time Reduction**: From weeks to days
- **Coverage**: 100% of manual sections analyzed
- **User Satisfaction**: Positive feedback from auditors

---

## 10. Risk Mitigation

### 10.1 Technical Risks

- **LLM Hallucination**: 
  - Mitigation: Require citations, validate against source
  - Use structured output, fact-checking
- **Context Window Limits**:
  - Mitigation: Smart context selection, summarization
- **Vector Search Quality**:
  - Mitigation: Hybrid search (semantic + keyword), reranking

### 10.2 Compliance Risks

- **False Positives/Negatives**:
  - Mitigation: Human auditor review, confidence scores
  - Continuous learning from feedback
- **Regulatory Changes**:
  - Mitigation: Version tracking, update notifications

---

## 11. Future Enhancements

1. **Multi-language Support**: Process documents in multiple languages
2. **Visual Audits**: Image/document analysis for visual compliance
3. **Real-time Collaboration**: Multiple auditors working simultaneously
4. **Learning System**: Improve from auditor feedback
5. **Integration**: API for integration with existing audit systems
6. **Advanced Analytics**: Trend analysis, predictive compliance

---

## 12. Conclusion

This AI-assisted auditing system provides a scalable, cost-efficient solution for compliance checking in aviation and other regulated sectors. By combining semantic search, multi-context retrieval, and intelligent agent analysis, the system can process large volumes of documents, identify non-conformities, and generate comprehensive audit reports that support human auditors' decision-making.

The modular design allows for easy adaptation across sectors, and the test bench feature enables organizations to proactively ensure compliance before official submission.

---

## Appendix A: Example Output

### Flag Example

```json
{
  "chunk_id": "manual_section_4.2.3",
  "flag": "RED",
  "severity_score": 85,
  "regulation_references": ["Part-145.A.30(c)", "AMC 145.A.30(c)"],
  "findings": "The manual section 4.2.3 does not specify the minimum qualifications for certifying staff as required by Part-145.A.30(c). The section mentions 'qualified personnel' but does not define the specific requirements.",
  "gaps": [
    "Missing definition of minimum qualifications for certifying staff",
    "No reference to Part-66 license requirements",
    "No mention of type rating requirements"
  ],
  "citations": {
    "manual_section": "4.2.3 Personnel Qualifications",
    "regulation_sections": ["Part-145.A.30(c)", "AMC 145.A.30(c)"]
  },
  "recommendations": [
    "Add explicit reference to Part-66 license requirements",
    "Specify minimum experience requirements",
    "Include type rating requirements for specific aircraft"
  ]
}
```

### Report Section Example

```markdown
## Section 4.2.3: Personnel Qualifications

**Flag**: 🔴 RED  
**Severity**: 85/100  
**Regulation**: Part-145.A.30(c), AMC 145.A.30(c)

### Findings
The manual section does not meet the requirements of Part-145.A.30(c) regarding minimum qualifications for certifying staff. The section uses vague language ("qualified personnel") without specifying the exact requirements.

### Gaps Identified
1. Missing definition of minimum qualifications
2. No reference to Part-66 license requirements
3. No mention of type rating requirements

### Recommendations
1. Add explicit reference to Part-66 license requirements
2. Specify minimum experience requirements (e.g., 3 years)
3. Include type rating requirements for specific aircraft types

### Citations
- Manual: Section 4.2.3
- Regulation: Part-145.A.30(c) - "The organisation shall ensure that certifying staff meet the requirements of Part-66."
- AMC: AMC 145.A.30(c) - Provides detailed guidance on qualification requirements.
```

---

## Appendix B: Technology Alternatives

| Component | Option 1 (Recommended) | Option 2 | Option 3 |
|-----------|----------------------|----------|----------|
| LLM Access | OpenRouter (GPT-4o mini) | OpenRouter (Claude 3.5) | Local Llama 3 70B |
| Embeddings | OpenAI text-embedding-3-large | sentence-transformers | Cohere |
| Vector DB | ChromaDB (local) | SQLite FTS fallback | Weaviate (later) |
| Framework | Flask + LangChain | Flask + LlamaIndex | FastAPI (post-hack) |
| Worker Model | ThreadPoolExecutor | RQ (Redis optional) | APScheduler background jobs |

---

*Document Version: 1.0*  
*Last Updated: [Date]*

---

## 13. Hackathon Build Plan (Backend-First)

Use this as the authoritative to-do list during the sprint. Each task calls out the deliverable, dependencies, and a lightweight verification step.

**Status Summary (Updated 2025-11-15):** ✅ **ALL SECTIONS COMPLETE** - The entire hackathon build plan has been successfully implemented. All 7 major sections (Setup, Document Ingestion, Audit Engine, APIs & Reporting, Test Bench Mode, Dev Experience, and Stretch Goals) are complete with full test coverage, documentation, and working implementations.

### Legend
- [ ] = Not started
- [~] = In progress
- [x] = Complete

### 13.1 Hackathon Setup
1. - [x] **Repo + tooling bootstrap**
   - Deliverable: `backend/` Flask project with `pyproject.toml`, `Makefile`, `.env.example`, `README`.
   - Blocking: None.
   - Verification: `make dev-up` creates venv, installs deps, runs `flask run` hello-world.
2. - [x] **Environment & secrets wiring**
   - Deliverable: `.env` loader (python-dotenv) providing OpenRouter key, embedding key, chunk params.
   - Blocking: 13.1.1.
   - Verification: `python scripts/check_env.py` confirms required vars exist.
3. - [x] **Local storage scaffolding**
   - Deliverable: `./data/uploads`, `./data/processed`, `./data/logs`, `./data/chroma` directories with helper module ensuring existence.
   - Blocking: 13.1.1.
   - Verification: `python scripts/ensure_dirs.py` creates folders and passes idempotency test.
> Section 13.1 status: ✅ Completed on 2025-11-14.

> Section 13.2 (Document Ingestion & Processing) status: ✅ Completed.

### 13.2 Document Ingestion & Processing
1. - [x] **Document upload API**
   - Deliverable: Flask blueprint (`/documents`) accepting PDF/DOCX/Markdown, storing files locally, recording metadata in SQLite.
   - Blocking: 13.1.*
   - Verification: `pytest tests/api/test_upload.py` uploads fixture and asserts DB row created (implemented via `backend/app/api/documents.py` + `DocumentService`).
2. - [x] **Text extraction worker**
   - Deliverable: Module using PyPDF2, python-docx, BeautifulSoup, and optional Tesseract; runnable via CLI or background thread.
   - Blocking: 13.2.1.
   - Verification: `python -m workers.extract path/to/fixture.pdf` outputs normalized JSON with sections (backed by `DocumentExtractor` + Typer CLI).
3. - [x] **Semantic chunker**
   - Deliverable: Section-aware chunker (500-1000 tokens, 80-token overlap) leveraging LangChain splitter with custom callbacks.
   - Blocking: 13.2.2.
   - Verification: `pytest tests/services/test_chunking.py tests/pipelines/test_chunk_cli.py`.
   - Implementation Notes:
     - `ChunkingConfig` now lives in `backend/app/config/settings.py`, pulling `CHUNK_SIZE`, `CHUNK_OVERLAP`, `CHUNK_TOKENIZER`, and `CHUNK_MAX_SECTION_TOKENS` from the environment (`AppConfig.chunking` helper).
     - `backend/app/services/chunking.py` ships the `SemanticChunker`, `SectionText`, and `ChunkPayload` classes. It uses a tokenizer-aware splitter (tiktoken-backed with char fallback) to mimic LangChain's behavior, enforces deterministic chunk IDs (`{doc_id}_{section_index}_{chunk_index}`), computes token spans, and threads prev/next references directly into chunk metadata.
     - `ChunkPayload` preserves `section_path`, `parent_heading`, `token_start`, `token_end`, `prev_chunk_id`, and `next_chunk_id` in a single metadata blob so future stages can walk neighbors without additional SQL.
     - `python -m pipelines.chunk --doc-id <doc>` consumes extraction JSON, invokes the chunker, and bulk-inserts rows into SQLite (with `--dry-run` and `--replace` safety nets).
     - Contract coverage lives in `tests/services/test_chunking.py` (chunk boundaries/metadata) and `tests/pipelines/test_chunk_cli.py` (end-to-end CLI ↔ DB round trip).
4. - [x] **Embedding pipeline**
   - Deliverable: CLI `python -m pipelines.embed --doc-id <id>` that batches chunks, caches embeddings, and writes to Chroma.
   - Blocking: 13.2.3.
   - Verification: Command populates `manual_chunks` collection; `scripts/vectortest.py` retrieves top-3 neighbors.
   - Implementation Notes:
     - `EmbeddingService` in `backend/app/services/embeddings.py` provides batch processing (`get_pending_chunks`, `process_chunks`) with automatic status tracking (`pending` → `in_progress` → `completed`/`failed`).
     - `EmbeddingClient` abstraction supports OpenAI-compatible APIs and sentence-transformers with pluggable providers determined by model name prefix.
     - Embeddings are cached on disk (`./data/cache/embeddings/<sha256>.npy`) keyed by SHA256 of chunk text, enabling instant re-runs for unchanged content.
     - ChromaDB persistence via `_store_in_chroma` method writes to named collections (`manual_chunks`, `regulation_chunks`, etc.) with full metadata preservation.
     - `pipelines/embed.py` CLI accepts `--doc-id`, `--collection`, `--batch-size`, `--dry-run`, and `--verbose` flags for flexible execution.
     - `scripts/vectortest.py` provides semantic search testing with `--query`, `--collection`, and `--top-k` parameters, displaying results in rich tables.
     - Test coverage in `tests/services/test_embeddings.py` (service logic) and `tests/pipelines/test_embed_cli.py` (CLI integration with mocked embedding generation).
5. - [x] **Metadata persistence**
   - Deliverable: SQLite tables (`documents`, `chunks`, `embeddings_jobs`) with Alembic migration or SQL script.
   - Blocking: 13.2.1-13.2.4.
   - Verification: `pytest tests/db/test_models.py` passes.
   - Implementation Notes:
     - Alembic migrations implemented: `20251114_chunks_embeddings.py`, `20251115_audits_runner.py`, `20251115_flags.py`, `20251115_auditor_questions.py`, `20251115_compliance_scores.py`.
     - SQLAlchemy models in `backend/app/db/models.py` with typed relationships: `Document`, `Chunk`, `EmbeddingJob`, `Audit`, `AuditChunkResult`, `Flag`, `Citation`, `AuditorQuestion`, `ComplianceScore`.
     - Indexes on high-frequency queries (`idx_chunks_doc_status`, `idx_embeddings_jobs_status`, `idx_audits_status`).
     - Database unit tests in `tests/db/test_models.py` cover cascading deletes, JSON metadata serialization, and unique constraints.

> Section 13.3 (Single-Agent Audit Engine) status: ✅ Completed.

### 13.3 Single-Agent Audit Engine
1. - [x] **Context builder utilities**
   - Deliverable: `context_builder.py` that deterministically retrieves manual neighbors, regulation snippets, AMC/GM guidance, and optional evidence for a chunk.
   - Blocking: 13.2.5.
   - Verification: Contract test feeds synthetic embeddings and asserts token budgets + ordering are respected.
   - Implementation Notes:
     - `ContextBuilder` in `backend/app/services/context_builder.py` with `ContextBuilderConfig` in `settings.py`.
     - Retrieval helpers wrap SQLite + Chroma queries, normalize outputs into `ContextSlice` objects with token estimates.
     - `build_context(chunk_id, *, include_evidence=False)` orders slices manual → regulations → AMC/GM → evidence, trimming to configured token ceiling.
     - In-memory query caching to avoid redundant vector queries.
     - Test coverage in `tests/services/test_context_builder.py`.
2. - [x] **Compliance runner loop**
   - Deliverable: `compliance_runner.py` orchestrating the sequential flow (context → LLM call → normalization) for every chunk in an audit job.
   - Blocking: 13.3.1.
   - Verification: Fixture audit executes `python -m backend.app.services.run_audit --audit-id <id>` and produces deterministic stdout/log events.
   - Implementation Notes:
     - `ComplianceRunner` class in `backend/app/services/compliance_runner.py` acquires pending audit jobs and advances them chunk by chunk.
     - Persists checkpoints (`last_chunk_id`) for resume safety, respects embedding completion, skips already analyzed chunks, honors draft-mode throttles.
     - CLI entrypoint: `python -m backend.app.services.run_audit --audit-id ... --max-chunks ...`.
     - Integration tests in `tests/services/test_compliance_runner.py`.
3. - [x] **LLM prompt + schema enforcement**
   - Deliverable: Prompt templates + pydantic validators that keep OpenRouter responses in the JSON format described in §4.3.
   - Blocking: 13.3.2.
   - Verification: Replay test loads recorded responses and validates parsing + coercion.
   - Implementation Notes:
     - Prompt templates in `backend/app/prompts/` (compliance.py, questions.py).
     - `ComplianceLLMClient` in `backend/app/services/analysis.py` wraps OpenRouter with JSON schema hints, retry/backoff.
     - Pydantic models for structured output validation.
     - Test coverage in `tests/services/test_analysis.py`.
4. - [x] **Retry & refinement hooks**
   - Deliverable: Optional single-agent "reflection" pass that reuses the same runner to request additional context when `needs_additional_context` is true (max 1 retry).
   - Blocking: 13.3.3.
   - Verification: Simulation script forces a retry scenario and confirms the loop exits cleanly when budget exhausted.
   - Implementation Notes:
     - Refinement logic in `ComplianceRunner._analyze_with_optional_refinement()`.
     - Expands context window (widen neighbor span, pull extra regulation chunks, include evidence) before re-running prompt.
     - Configurable max retry count via `REFINEMENT_MAX_ATTEMPTS`.
     - Refinement attempts recorded in analysis metadata.
5. - [x] **Flag synthesizer & persistence**
   - Deliverable: Deterministic module mapping runner output to RED/YELLOW/GREEN, persisting rows in SQLite `flags` + `citations`.
   - Blocking: 13.3.4.
   - Verification: Unit test covers severity mapping edge cases.
   - Implementation Notes:
     - `FlagSynthesizer` in `backend/app/services/flagging.py` maps runner output to RED/YELLOW/GREEN flags.
     - Alembic migration `20251115_flags.py` creates `flags` and `citations` tables with indexes.
     - Severity thresholds encoded (score ≥80 ⇒ RED), idempotent upserts keyed by `(audit_id, chunk_id)`.
     - Test coverage in `tests/services/test_flagging.py`.

> Section 13.4 (APIs & Reporting) status: ✅ Completed.

### 13.4 APIs & Reporting
1. - [x] **Findings API**
   - Deliverable: Flask endpoints `/audits/<id>/flags` with filtering (severity, regulation) and pagination.
   - Blocking: 13.3.5.
   - Verification: `pytest tests/api/test_findings.py` ensures correct sorting + filtering.
   - Implementation Notes:
     - Flask blueprint in `backend/app/api/findings.py` with `/audits/<audit_id>/flags` endpoint.
     - Query parameters: `severity`, `regulation`, `page`, `page_size`, `include_questions`.
     - SQLAlchemy query builder joins `flags`, `citations`, and `chunks` tables with filtering and pagination.
     - Normalized JSON output ready for UI/CLI consumption.
     - Test coverage in `tests/api/test_findings.py`.
2. - [x] **Report generator**
   - Deliverable: Markdown renderer combining executive summary, findings, appendix; exports to `.md` + optional PDF via `md-to-pdf`.
   - Blocking: 13.4.1.
   - Verification: Snapshot test asserts stable Markdown for fixture audit.
   - Implementation Notes:
     - `ReportGenerator` in `backend/app/reports/generator.py` queries audits, aggregated flag stats, and citations.
     - Markdown templates with executive summary, per-section findings, and appendices.
     - CLI entrypoint: `python -m backend.app.reports.build --audit-id ... --output-dir ... --pdf --html`.
     - Generated files cached in `./data/reports/<audit_id>/`.
     - Test coverage in `tests/reports/test_report_generator.py`.
3. - [x] **Auditor question generator**
   - Deliverable: Lightweight agent/prompt generating prioritized review questions per regulation section.
   - Blocking: 13.3.5.
   - Verification: Contract test ensures minimum question count and metadata.
   - Implementation Notes:
     - `QuestionGenerator` in `backend/app/services/question_generator.py` with `QuestionPlan` Pydantic schema.
     - Prompt templates in `backend/app/prompts/questions.py`.
     - Heuristics guarantee baseline coverage (at least one question per RED flag).
     - Questions surfaced through Findings API (`include_questions=1`) and report generator's appendix.
     - Test coverage in `tests/services/test_question_generator.py`.
4. - [x] **Developer CLI (frontend placeholder)**
   - Deliverable: `python cli.py status <audit_id>` showing progress + download links to reports.
   - Blocking: 13.4.1.
   - Verification: Manual run demonstrates upload → process → report within dev console.
   - Implementation Notes:
     - Typer CLI in `cli.py` with `status`, `flags`, `report`, `compare`, and `scores` subcommands.
     - Polling loop with `--poll` option, `--json` output for scripting, ANSI-colored summaries.
     - Documented in `README.md`.
     - Test coverage in `tests/cli/test_cli.py` and `tests/cli/test_cli_compare.py`.

> Section 13.5 (Test Bench Mode) status: ✅ Completed.

### 13.5 Test Bench Mode
1. - [x] **Draft job flag**
   - Deliverable: `audits` table column `is_draft` plus API parameter to trigger lighter processing (reduced chunks/context).
   - Blocking: 13.2.5, 13.3.5.
   - Verification: API test confirms draft audits skip heavy steps but still emit summary.
   - Implementation Notes:
     - Alembic migration `20251115_audits_runner.py` adds `audits.is_draft BOOLEAN DEFAULT 0`.
     - Exposed through upload/create-audit endpoints (`POST /api/documents`, `POST /audits`) and CLI flags.
     - Runner branches on `is_draft`: limits to first 5 chunks, reduces context budgets (50%), disables evidence, skips refinement.
     - Report generation labels draft status clearly.
     - Test coverage in `tests/services/test_draft_mode.py` and `tests/api/test_audits.py`.
2. - [x] **Comparison CLI**
   - Deliverable: `python cli.py compare <audit_a> <audit_b>` highlighting delta in flags + compliance score.
   - Blocking: 13.5.1.
   - Verification: CLI output matches expected diff fixture.
   - Implementation Notes:
     - `compare` subcommand in `cli.py` reuses Findings API to fetch flags/metrics for both audits.
     - Diff logic highlights added/removed/changed flags, severity shifts, and score deltas.
     - Output modes: text (default), `--json` for machine-readable output.
     - Test coverage in `tests/cli/test_cli_compare.py`.
3. - [x] **Score tracker**
   - Deliverable: SQLite table `compliance_scores` + helper plotting ASCII trend.
   - Blocking: 13.5.2.
   - Verification: Unit test computes score changes correctly.
   - Implementation Notes:
     - Alembic migration `20251115_compliance_scores.py` creates `compliance_scores` table.
     - `ScoreTracker` service in `backend/app/services/score_tracker.py` calculates aggregate metrics after each audit completes.
     - CLI `scores` subcommand renders ASCII trend tables with `--plot` option.
     - API endpoint `/api/scores` surfaces score history.
     - Test coverage in `tests/services/test_compliance_score.py`.

> Section 13.6 (Dev Experience & Demo Polish) status: ✅ Completed.

### 13.6 Dev Experience & Demo Polish
1. - [x] **Testing harness**
   - Deliverable: Pytest suite covering API, DB models, agents (with recorded fixtures).
   - Blocking: 13.2.*, 13.3.*.
   - Verification: `make test` green locally + in CI (GitHub Actions matrix: py3.11, Windows/Linux).
   - Implementation Notes:
     - Tests organized by domain: `tests/api`, `tests/services`, `tests/pipelines`, `tests/cli`, `tests/db`.
     - Shared factories in `tests/conftest.py` for documents/chunks/audits.
     - `make test` runs pytest with coverage, `make test-fast` without coverage.
     - GitHub Actions workflow (`.github/workflows/tests.yml`) runs matrix builds (py3.11, Windows/Linux).
     - Documentation in `docs/testing.md`.
2. - [x] **Logging & monitoring lite**
   - Deliverable: Structlog-based logging with request IDs, plus simple `/healthz` endpoint.
   - Blocking: 13.1.*, 13.3.4.
   - Verification: Tail logs during sample run to confirm agent step traces.
   - Implementation Notes:
     - `logging_config.py` configures structured logging with request IDs, audit_id, chunk_id context.
     - Flask middleware injects request/trace IDs and propagates through workers + runner threads.
     - `/healthz` endpoint in `backend/app/api/routes.py` reports DB connectivity and system status.
     - Key metrics emitted to stdout (chunks_per_minute, retry_count, token_usage).
     - Runbooks in `docs/operations.md`.
3. - [x] **Demo script + sample dataset**
   - Deliverable: Step-by-step script + sanitized sample manual/regulation subset for live demo.
   - Blocking: 13.4.*, 13.5.*
   - Verification: Dry run takes < 15 minutes end-to-end.
   - Implementation Notes:
     - Sample dataset in `hackathon_resources/` (manual excerpts, regulation references, AMC/GM guidance).
     - `scripts/demo_walkthrough.md` describes each terminal command, expected output, and talking points.
     - Automation via `make demo` (resets local state, ingests sample docs, runs embedding + audit + report).
     - `scripts/demo.py` provides automated demo execution.
     - Artifacts output to `data/demo/output/`.

> Section 13.7 (Stretch / Backlog) status: ✅ Completed.

### 13.7 Stretch / Backlog
1. - [x] **Minimal reviewer UI**
   - Deliverable: Generate static HTML (Jinja) summarizing flags; host via Flask route.
   - Blocking: 13.4.1.
   - Verification: Manual browser check.
   - Implementation Notes:
     - Flask blueprint `/review/<audit_id>` in `backend/app/api/review.py` queries Findings API and renders via Jinja.
     - Templates in `backend/app/templates/` (review.html, dashboard.html, upload.html) with CSS styling.
     - Client-side filters (severity, regulation) via query parameters.
     - Static HTML generation via `--html` flag in report builder.
     - Accessible and print-friendly styling.
2. - [x] **Sector adaptation notes**
   - Deliverable: Document listing delta for maritime/rail plus configuration knobs required.
   - Blocking: 13.3.5.
   - Verification: Notes reviewed with stakeholders.
   - Implementation Notes:
     - Comprehensive guide in `docs/sector_adaptations.md` outlining deltas between aviation, maritime, and rail compliance regimes.
     - Configuration changes documented (regulation corpora, chunking heuristics, prompt tweaks, scoring thresholds).
     - Decision matrix showing which modules need rewiring vs. simple data swaps for each sector.

> Keep this checklist version-controlled; update statuses, owners, and verification notes as work progresses.

---

## 14. Agent Build Guidelines

Future AI agents (or parallel teammate streams) will extend the sequential MVP. This section gives them both the big-picture direction and the small-picture guardrails they need to deliver upgrades without destabilizing the hackathon core.

### Shared Context Package
- Directory conventions: `backend/app`, `backend/workers`, `backend/scripts`, `data/`, `tests/`.
- Database schema contract: `documents`, `chunks`, `embeddings_jobs`, `audits`, `flags`, `citations`, `compliance_scores` (see Section 13.2.5).
- Runner contract: `prepare_context` → `analyze_chunk` → `score_and_flag` (Section 4.5).
- API contract: `/documents`, `/audits`, `/audits/<id>/flags`, `/reports/<id>` (Section 13.4).
- CLI contract: `python -m cli upload/process/status/compare` (Sections 13.4 & 13.5).

### 14.1 Big-Picture Guardrails
- **Protect the MVP loop**: New agents should plug into the runner through feature flags or adapters, never by rewriting its control flow.
- **Own a boundary, not the world**: Each agent focuses on a single concern (ingestion, context, reasoning, reporting, demo polish) and speaks via the shared contracts.
- **Version everything**: When changing payloads or prompts, bump schema versions and add migration notes so other agents can adapt in lockstep.
- **Ship observability with features**: Every enhancement must emit logs/metrics at the same granularity as the runner so regression triage stays simple.
- **Keep it demo-friendly**: Default settings must continue to run on a laptop with limited tokens/time; heavier flows should opt in via config.

### 14.2 Small-Picture Playbooks

1. **Bootstrap & Infrastructure Track**
   - Big picture: Provide stable foundations (Flask app factory, DB migrations, config loaders).
   - Small picture: Maintain `scripts/check_env.py`, directory bootstrapping, and helper utilities (`get_db()`, logging setup) used by the runner and future agents.

2. **Document Pipeline Track**
   - Big picture: Guarantee high-quality text + embeddings for the runner.
   - Small picture: Own upload endpoints, extraction workers, chunking, and embedding pipelines; ensure metadata needed by `context_builder` is persisted.

3. **Audit Engine Track**
   - Big picture: Enhance the `ComplianceRunner` without breaking sequential guarantees.
   - Small picture: Experiment with smarter planning heuristics, hybrid retrieval strategies, or alternative prompts, but surface them as toggles (`--strategy`, config flags).

4. **Flagging & Reporting Track**
   - Big picture: Turn runner output into auditor-ready artifacts.
   - Small picture: Maintain the flag synthesizer, reporting APIs, Markdown/PDF formatting, and CLI UX; add new report sections via template partials.

5. **Test Bench & Demo Track**
   - Big picture: Keep draft-mode, comparison tools, and live-demo storytelling sharp.
   - Small picture: Manage quick-run settings, score tracking, `/healthz`, structured logging, and scripted demo datasets.

### Coordination Tips
- Maintain the `contracts/` folder with JSON schema snapshots and wireframe prompts so every track codes against the same expectations.
- Reference artifacts (file paths, DB IDs) instead of passing raw blobs between agents; this keeps hand-offs light even if jobs run on separate machines.
- Before shipping, run `make demo` end-to-end (upload → extract → embed → audit → report → compare) to prove cross-track compatibility.
- Timestamp and namespace every log (`component`, `chunk_id`, `audit_id`) so multi-agent debugging stays tractable once concurrency returns.

