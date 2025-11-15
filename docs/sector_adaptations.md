# Sector Adaptation Guide

This document outlines the configuration changes and adaptations required to extend the AI Auditing System beyond aviation (EASA Part-145) to other sectors such as maritime and rail compliance.

## Overview

The AI Auditing System is designed with modularity in mind, allowing adaptation to different regulatory sectors. The core architecture remains the same, but several components require sector-specific configuration.

## Key Differences Between Sectors

### Aviation (EASA Part-145)
- **Regulatory Framework**: EU Regulation 1321/2014, Part-145
- **Document Types**: Maintenance Organization Exposition (MOE), Continuing Airworthiness
- **Key Requirements**: Personnel qualifications, maintenance procedures, quality systems, record keeping
- **Authority**: EASA (European Union Aviation Safety Agency)

### Maritime (IMO)
- **Regulatory Framework**: SOLAS, MARPOL, STCW, ISM Code
- **Document Types**: Safety Management System (SMS) Manual, Ship Security Plan
- **Key Requirements**: Safety management, environmental protection, crew certification, port state control
- **Authority**: IMO (International Maritime Organization), Flag States

### Rail (EU Railway)
- **Regulatory Framework**: EU Directive 2016/797, CSM-RA, TSIs
- **Document Types**: Safety Management System, Maintenance Plans
- **Key Requirements**: Safety management, interoperability, maintenance procedures, certification
- **Authority**: ERA (European Union Agency for Railways), National Safety Authorities

## Configuration Changes Required

### 1. Regulation Corpora

**Current State**: System uses EASA Part-145 regulations stored in `hackathon_resources/`

**Adaptation Required**:
- Replace regulation documents with sector-specific regulations
- Update document `source_type` values if needed
- Ensure regulation documents are properly structured (XML, PDF, etc.)

**Configuration**:
```python
# In document ingestion
source_type = "regulation"  # Keep same
organization = "IMO" or "ERA"  # Change based on sector
```

**Files to Modify**:
- `backend/app/services/documents.py` - Document ingestion
- `hackathon_resources/` - Replace with sector-specific regulations
- `backend/app/services/context_builder.py` - Regulation retrieval logic (if sector-specific)

### 2. Chunking Heuristics

**Current State**: Semantic chunking optimized for aviation MOE structure

**Adaptation Required**:
- Adjust chunk size based on document structure
- Update section path extraction for sector-specific document formats
- Modify parent heading detection for different heading styles

**Configuration**:
```python
# In backend/app/services/chunking.py
CHUNK_SIZE = 1000  # Adjust based on sector document structure
CHUNK_OVERLAP = 200  # May need adjustment
```

**Files to Modify**:
- `backend/app/services/chunking.py` - Chunking parameters
- `backend/app/config/settings.py` - Add sector-specific chunking config

### 3. Prompt Templates

**Current State**: Prompts reference "EASA Part-145" and aviation-specific terminology

**Adaptation Required**:
- Update system prompts to reference sector-specific regulations
- Modify user prompts to use sector terminology
- Adjust flag categorization if sector uses different severity levels

**Configuration**:
```python
# In backend/app/prompts/compliance.py
SYSTEM_PROMPT = """
You are an AI assistant analyzing {sector} compliance documents...
Reference: {regulation_framework}
"""
```

**Files to Modify**:
- `backend/app/prompts/compliance.py` - Main compliance prompt
- `backend/app/prompts/questions.py` - Question generation prompt
- `backend/app/config/settings.py` - Add sector configuration

### 4. Scoring Thresholds

**Current State**: Scoring uses aviation-specific weights (RED: -10, YELLOW: -3, GREEN: +1)

**Adaptation Required**:
- Adjust penalty/bonus weights based on sector risk profiles
- Modify severity score ranges if sector uses different scales
- Update compliance score calculation formula

**Configuration**:
```python
# In backend/app/services/compliance_score.py
RED_PENALTY = 10  # Adjust based on sector
YELLOW_PENALTY = 3  # Adjust based on sector
GREEN_BONUS = 1  # Adjust based on sector
```

**Files to Modify**:
- `backend/app/services/compliance_score.py` - Score calculation
- `backend/app/config/settings.py` - Add scoring configuration

### 5. Citation Types

**Current State**: Citations reference "regulation", "manual_section", etc.

**Adaptation Required**:
- Ensure citation types match sector document structure
- Update citation extraction logic if sector uses different reference formats
- Modify citation display in reports/UI

**Files to Modify**:
- `backend/app/services/flagging.py` - Citation creation
- `backend/app/db/models.py` - Citation model (if new types needed)
- `backend/app/templates/review.html` - Citation display

## Decision Matrix

| Component | Aviation | Maritime | Rail | Change Type |
|-----------|----------|----------|------|-------------|
| Regulation Documents | EASA Part-145 | IMO SOLAS/MARPOL | EU Directive 2016/797 | Data Swap |
| Document Structure | MOE | SMS Manual | Safety Management System | Data Swap |
| Chunking Strategy | Semantic (1000 tokens) | Semantic (may vary) | Semantic (may vary) | Config Tweak |
| Prompt Templates | EASA-specific | IMO-specific | ERA-specific | Rewire |
| Scoring Weights | -10/-3/+1 | May differ | May differ | Config Tweak |
| Citation Formats | Part-145.A.30 | SOLAS Ch.II-2 | TSI Reference | Data Swap |
| Flag Categories | RED/YELLOW/GREEN | Same | Same | No Change |
| Database Schema | Current | Same | Same | No Change |
| API Endpoints | Current | Same | Same | No Change |
| CLI Commands | Current | Same | Same | No Change |

**Change Types**:
- **Data Swap**: Replace data files, no code changes
- **Config Tweak**: Modify configuration values, minimal code changes
- **Rewire**: Requires code modifications to templates/logic
- **No Change**: Component works as-is across sectors

## Implementation Steps

### Step 1: Prepare Sector-Specific Data

1. Collect regulation documents for target sector
2. Organize documents in `hackathon_resources/` or create sector-specific directory
3. Ensure documents are in supported formats (PDF, DOCX, XML, HTML, TXT)

### Step 2: Update Configuration

1. Create sector configuration file or environment variables:
   ```bash
   SECTOR=maritime
   REGULATION_FRAMEWORK=IMO_SOLAS
   SCORING_RED_PENALTY=10
   SCORING_YELLOW_PENALTY=3
   ```

2. Update `backend/app/config/settings.py` to read sector config

### Step 3: Modify Prompts

1. Update `backend/app/prompts/compliance.py`:
   - Replace "EASA Part-145" with sector-specific framework
   - Update regulation reference examples
   - Adjust terminology (e.g., "maintenance organization" → "ship operator")

2. Update `backend/app/prompts/questions.py`:
   - Modify question generation prompts for sector context
   - Update regulation reference patterns

### Step 4: Adjust Scoring (if needed)

1. Review sector risk profiles
2. Update penalty/bonus weights in `backend/app/services/compliance_score.py`
3. Test scoring with sample data

### Step 5: Test and Validate

1. Ingest sector-specific regulation documents
2. Process sample compliance documents
3. Verify flag categorization and scoring
4. Review generated reports for sector-appropriate language

## Example: Maritime Adaptation

### Configuration Changes

```python
# backend/app/config/settings.py
@dataclass
class SectorConfig:
    name: str = "maritime"
    regulation_framework: str = "IMO_SOLAS"
    authority: str = "IMO"
    document_types: list[str] = field(default_factory=lambda: ["sms_manual", "regulation"])
```

### Prompt Updates

```python
# backend/app/prompts/compliance.py
SYSTEM_PROMPT = """
You are an AI assistant analyzing maritime safety management system (SMS) compliance 
against IMO SOLAS, MARPOL, and ISM Code requirements.

Analyze the provided manual section against relevant IMO regulations...
"""
```

### Scoring Adjustments

```python
# backend/app/services/compliance_score.py
# Maritime may have different risk profiles
RED_PENALTY = 15  # Higher penalty for safety-critical maritime issues
YELLOW_PENALTY = 5
GREEN_BONUS = 1
```

## Feature Flags

Consider implementing feature flags for multi-sector support:

```python
# backend/app/config/settings.py
sector: str = field(default_factory=lambda: os.getenv("SECTOR", "aviation"))
enable_multi_sector: bool = field(default_factory=lambda: os.getenv("ENABLE_MULTI_SECTOR", "0") == "1")
```

## Backlog Items

### High Priority
1. **Sector Configuration System**: Centralized configuration for sector-specific settings
2. **Prompt Template System**: Dynamic prompt loading based on sector
3. **Regulation Corpus Management**: Support for multiple regulation sets
4. **Sector-Specific Scoring**: Configurable scoring weights per sector

### Medium Priority
5. **Multi-Sector Database**: Support for audits across multiple sectors
6. **Sector-Specific UI**: Customizable UI elements per sector
7. **Regulation Versioning**: Track regulation changes over time
8. **Cross-Sector Comparison**: Compare compliance across sectors

### Low Priority
9. **Sector Templates**: Pre-configured templates for common sectors
10. **Sector Migration Tools**: Utilities to migrate between sectors
11. **Sector Analytics**: Sector-specific compliance analytics
12. **Regulation Mapping**: Map requirements across sectors

## Testing Strategy

### Unit Tests
- Test scoring with sector-specific weights
- Test prompt generation with different sectors
- Test citation extraction with sector-specific formats

### Integration Tests
- Test end-to-end audit with sector-specific regulations
- Test report generation with sector terminology
- Test API endpoints with sector-specific data

### Validation
- Review with sector Subject Matter Experts (SMEs)
- Validate flag categorization against sector standards
- Verify report accuracy with sector experts

## Notes

- **Database Schema**: Current schema is sector-agnostic and requires no changes
- **API Endpoints**: All endpoints work across sectors without modification
- **CLI Commands**: CLI commands are sector-agnostic
- **Vector Store**: ChromaDB works with any document type, no changes needed
- **LLM Integration**: LLM prompts are the primary adaptation point

## Support

For questions about sector adaptation:
- Review this document
- Check `AI_Auditing_System_Design.md` for architecture details
- Consult with sector SMEs for domain-specific requirements
- Test thoroughly with sector-specific data before production use

