# Demo Walkthrough Guide

This guide provides step-by-step instructions for running the AI Auditing System demo, including expected outputs and talking points for presenters.

## Prerequisites

- Python 3.11+ installed
- Virtual environment activated (`.venv`)
- Dependencies installed (`make dev-install`)
- Sample documents in `hackathon_resources/` directory

## Quick Start

Run the automated demo:
```bash
make demo
```

This will:
1. Reset demo state
2. Ingest sample documents
3. Process documents (chunking + embedding)
4. Create and run an audit
5. Generate compliance report
6. Output artifacts to `data/demo/output/`

## Manual Walkthrough

### Step 1: Setup

```bash
# Ensure environment is ready
make dev-install
make db-upgrade
```

**Talking Point**: "We've built a comprehensive AI-assisted auditing system that automates compliance checking for aviation maintenance organizations against EASA Part-145 regulations."

### Step 2: Ingest Documents

```bash
# Upload a manual (MOE)
curl -X POST http://localhost:5000/documents \
  -F "file=@hackathon_resources/AI anonyymi MOE.docx" \
  -F "source_type=manual" \
  -F "organization=Demo Organization"

# Upload regulation
curl -X POST http://localhost:5000/documents \
  -F "file=@hackathon_resources/Easy Access Rules for Continuing Airworthiness (Regulation (EU) No 13212014).xml" \
  -F "source_type=regulation" \
  -F "organization=EASA"
```

**Expected Output**: JSON response with document IDs and metadata.

**Talking Point**: "The system accepts various document formats - PDFs, Word documents, XML, HTML. Each document is stored with metadata including source type (manual, regulation, AMC/GM, evidence) and organization."

### Step 3: Process Documents

```bash
# Chunk the manual
python -m pipelines.chunk <extracted-json> --doc-id <manual-doc-id>

# Generate embeddings
python -m pipelines.embed --doc-id <manual-doc-id>
```

**Talking Point**: "Documents are broken down into semantic chunks that preserve context. Each chunk is embedded using state-of-the-art models and stored in a vector database for fast semantic search."

### Step 4: Create Audit

```bash
# Create a draft audit (faster for demo)
curl -X POST http://localhost:5000/audits \
  -H "Content-Type: application/json" \
  -d '{"document_id": <manual-doc-id>, "is_draft": true}'
```

**Expected Output**: Audit ID and status.

**Talking Point**: "Draft mode allows us to quickly test the system with limited processing. Full audits process all chunks and provide comprehensive compliance analysis."

### Step 5: Run Compliance Check

```bash
# Run the compliance runner
python -m backend.app.services.run_audit --audit-id <audit-id> --max-chunks 5
```

**Expected Output**: Progress updates showing chunks processed.

**Talking Point**: "The compliance runner processes each chunk sequentially, building context from the manual, regulations, AMC/GM guidance, and evidence. It uses advanced LLMs to analyze compliance and flag issues."

### Step 6: View Results

```bash
# Check audit status
python cli.py status <audit-id>

# List flags
python cli.py flags <audit-id>

# View scores
python cli.py scores --plot
```

**Expected Output**: 
- Status table showing progress
- Flags table with RED/YELLOW/GREEN findings
- Score trend visualization

**Talking Point**: "The system categorizes findings into RED (critical), YELLOW (warning), and GREEN (compliant) flags. Each flag includes specific regulation references, gaps identified, and recommendations."

### Step 7: Generate Report

```bash
# Generate markdown report
python cli.py report <audit-id> --output-dir data/demo/output

# Generate PDF report
python cli.py report <audit-id> --output-dir data/demo/output --pdf
```

**Expected Output**: Markdown and PDF reports in `data/demo/output/`.

**Talking Point**: "Reports include executive summaries, detailed findings with citations, and prioritized auditor questions. These can be exported for review and documentation."

### Step 8: Compare Audits

```bash
# Compare two audits
python cli.py compare <audit-a> <audit-b> --format markdown
```

**Talking Point**: "The system tracks compliance scores over time, allowing organizations to monitor improvements and compare different versions of their manuals."

## Demo Artifacts

After running the demo, check `data/demo/output/` for:
- `audit_<id>.md` - Markdown compliance report
- `audit_<id>.pdf` - PDF compliance report (if generated)
- Comparison reports (if comparing audits)

## Talking Points

### Key Features

1. **Automated Compliance Checking**: Reduces manual review time from days to hours
2. **Context-Aware Analysis**: Uses semantic search to find relevant regulations and guidance
3. **Structured Findings**: Categorizes issues by severity with specific recommendations
4. **Audit Trail**: Tracks all analysis with citations and evidence
5. **Score Tracking**: Monitors compliance improvements over time

### Technical Highlights

1. **Vector Search**: Uses ChromaDB for fast semantic retrieval
2. **LLM Integration**: Leverages GPT-4/Claude for complex reasoning
3. **Adaptive Context**: Automatically refines analysis when more context is needed
4. **Structured Logging**: Full observability with request correlation
5. **API-First Design**: RESTful APIs for integration with existing systems

### Use Cases

1. **Initial MOE Review**: Fast initial assessment of new maintenance organization manuals
2. **Periodic Audits**: Regular compliance checks to ensure ongoing adherence
3. **Change Impact Analysis**: Assess impact of manual updates on compliance
4. **Training**: Help organizations understand regulatory requirements
5. **Authority Review**: Assist regulatory authorities in MOE inspections

## Troubleshooting

### No Documents Found

If demo script can't find documents:
- Ensure `hackathon_resources/` directory exists
- Check that sample files are present
- Verify file permissions

### Database Errors

If you see database errors:
- Run `make db-upgrade` to apply migrations
- Check `DATABASE_URL` environment variable
- Ensure database file is writable

### LLM Errors

If LLM calls fail:
- Verify `OPENROUTER_API_KEY` is set
- Check API rate limits
- System will fall back to echo client (placeholder analysis)

### Slow Processing

For faster demos:
- Use draft mode (`is_draft: true`)
- Limit chunks (`--max-chunks 5`)
- Skip evidence retrieval

## Next Steps

After the demo:
1. Explore the API documentation
2. Review generated reports
3. Try different document types
4. Experiment with filtering and comparison features
5. Check the operations guide for monitoring and troubleshooting

## Support

For questions or issues:
- Check `docs/operations.md` for operational guidance
- Review `docs/testing.md` for testing information
- See `AI_Auditing_System_Design.md` for system architecture

