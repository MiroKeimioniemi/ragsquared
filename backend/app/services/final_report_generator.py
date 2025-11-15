"""Service for generating comprehensive final reports addressing all compliance issues."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config.settings import AppConfig
from ..db.models import Audit, AuditChunkResult, Citation, Flag
from .analysis import ComplianceLLMClient

logger = logging.getLogger(__name__)


@dataclass
class FinalReport:
    """Final comprehensive report addressing all compliance issues."""
    
    audit_id: int
    executive_summary: str
    critical_issues: list[dict[str, Any]]  # RED flags
    warnings: list[dict[str, Any]]  # YELLOW flags
    recommendations: list[str]
    overall_assessment: str
    raw_content: str  # Full LLM-generated report


class FinalReportGenerator:
    """Generates comprehensive final reports synthesizing all compliance issues."""
    
    def __init__(self, session: Session, config: AppConfig):
        self.session = session
        self.config = config
        try:
            self.llm_client = ComplianceLLMClient(config)
        except ValueError:
            # LLM not available - will use fallback
            logger.warning("LLM client not available, will use fallback report generation")
            self.llm_client = None
    
    def generate_report(self, audit_id: int) -> FinalReport:
        """Generate a comprehensive final report for an audit."""
        logger.info(f"Generating final report for audit {audit_id}")
        
        # Get audit
        audit = self.session.get(Audit, audit_id)
        if not audit:
            raise ValueError(f"Audit {audit_id} not found")
        
        # Get all RED and YELLOW flags
        flags = self.session.execute(
            select(Flag)
            .where(
                Flag.audit_id == audit.id,
                Flag.flag_type.in_(['RED', 'YELLOW'])
            )
            .order_by(Flag.severity_score.desc())
        ).scalars().all()
        
        if not flags:
            # No issues found - generate a positive report
            return self._generate_no_issues_report(audit)
        
        # Collect all context for each flag
        flag_data = []
        for flag in flags:
            flag_info = self._collect_flag_context(flag, audit.id)
            flag_data.append(flag_info)
        
        # Generate comprehensive report using LLM
        report_content = self._generate_report_content(audit, flag_data)
        
        # Parse the report into structured format
        structured_report = self._parse_report(report_content, flag_data)
        
        return FinalReport(
            audit_id=audit.id,
            executive_summary=structured_report.get("executive_summary", ""),
            critical_issues=structured_report.get("critical_issues", []),
            warnings=structured_report.get("warnings", []),
            recommendations=structured_report.get("recommendations", []),
            overall_assessment=structured_report.get("overall_assessment", ""),
            raw_content=report_content,
        )
    
    def _collect_flag_context(self, flag: Flag, audit_id: int) -> dict[str, Any]:
        """Collect all context information for a flag."""
        # Get citations
        citations = self.session.execute(
            select(Citation).where(Citation.flag_id == flag.id)
        ).scalars().all()
        
        # Get chunk result with context summary
        chunk_result = self.session.execute(
            select(AuditChunkResult).where(
                AuditChunkResult.audit_id == audit_id,
                AuditChunkResult.chunk_id == flag.chunk_id
            )
        ).scalar_one_or_none()
        
        context_summary = None
        if chunk_result and chunk_result.analysis:
            context_summary = chunk_result.analysis.get("context_summary")
        
        return {
            "flag_id": flag.id,
            "flag_type": flag.flag_type,
            "severity_score": flag.severity_score,
            "chunk_id": flag.chunk_id,
            "findings": flag.findings,
            "gaps": flag.gaps or [],
            "recommendations": flag.recommendations or [],
            "citations": [
                {
                    "type": cit.citation_type,
                    "reference": cit.reference,
                }
                for cit in citations
            ],
            "context": context_summary,
        }
    
    def _generate_report_content(self, audit: Audit, flag_data: list[dict[str, Any]]) -> str:
        """Generate comprehensive report content using LLM."""
        
        # Build prompt with all flag information
        red_flags = [f for f in flag_data if f["flag_type"] == "RED"]
        yellow_flags = [f for f in flag_data if f["flag_type"] == "YELLOW"]
        
        prompt = f"""You are an expert aviation compliance auditor. Generate a comprehensive final audit report addressing all compliance issues found in the audit.

AUDIT INFORMATION:
- Audit ID: {audit.external_id}
- Total Chunks Processed: {audit.chunk_total}
- Status: {audit.status}

CRITICAL ISSUES (RED FLAGS) - {len(red_flags)} found:
"""
        
        for idx, flag in enumerate(red_flags, 1):
            prompt += f"""
{idx}. {flag['findings']}
   - Severity Score: {flag['severity_score']}
   - Chunk ID: {flag['chunk_id']}
   - Gaps Identified: {', '.join(flag['gaps']) if flag['gaps'] else 'None'}
   - Recommendations: {', '.join(flag['recommendations']) if flag['recommendations'] else 'None'}
   - Citations: {', '.join([c['reference'] for c in flag['citations']]) if flag['citations'] else 'None'}
"""
            if flag.get('context'):
                ctx = flag['context']
                prompt += f"""
   - Context Used:
     * Manual chunks: {ctx.get('manual_neighbors_count', 0)}
     * Regulations: {ctx.get('regulation_slices_count', 0)}
     * Guidance: {ctx.get('guidance_slices_count', 0)}
     * Evidence: {ctx.get('evidence_slices_count', 0)}
"""
        
        prompt += f"""

WARNINGS (YELLOW FLAGS) - {len(yellow_flags)} found:
"""
        
        for idx, flag in enumerate(yellow_flags, 1):
            prompt += f"""
{idx}. {flag['findings']}
   - Severity Score: {flag['severity_score']}
   - Chunk ID: {flag['chunk_id']}
   - Gaps Identified: {', '.join(flag['gaps']) if flag['gaps'] else 'None'}
   - Recommendations: {', '.join(flag['recommendations']) if flag['recommendations'] else 'None'}
   - Citations: {', '.join([c['reference'] for c in flag['citations']]) if flag['citations'] else 'None'}
"""
            if flag.get('context'):
                ctx = flag['context']
                prompt += f"""
   - Context Used:
     * Manual chunks: {ctx.get('manual_neighbors_count', 0)}
     * Regulations: {ctx.get('regulation_slices_count', 0)}
     * Guidance: {ctx.get('guidance_slices_count', 0)}
     * Evidence: {ctx.get('evidence_slices_count', 0)}
"""
        
        prompt += """

TASK: Generate a comprehensive final audit report that:
1. Provides an executive summary of the overall compliance status
2. Addresses all critical issues (RED flags) with detailed analysis
3. Addresses all warnings (YELLOW flags) with recommendations
4. Provides prioritized recommendations for remediation
5. Gives an overall assessment of the organization's compliance posture

The report should be professional, comprehensive, and actionable. Use the context information provided to understand the full scope of each issue.

Format your response as a JSON object with the following structure:
{
    "executive_summary": "Comprehensive summary of the audit findings and overall compliance status (2-3 paragraphs)",
    "critical_issues": [
        {
            "title": "Issue title",
            "description": "Detailed description of the issue",
            "severity": "HIGH",
            "affected_sections": ["section references"],
            "regulatory_basis": ["regulation references"],
            "recommendations": ["specific recommendation 1", "specific recommendation 2"]
        }
    ],
    "warnings": [
        {
            "title": "Warning title",
            "description": "Description of the warning",
            "affected_sections": ["section references"],
            "recommendations": ["recommendation"]
        }
    ],
    "recommendations": [
        "Prioritized list of overall recommendations (ordered by priority)"
    ],
    "overall_assessment": "Final assessment paragraph summarizing the organization's compliance posture and next steps"
}

Return ONLY valid JSON, no markdown, no code blocks.
"""
        
        if not self.llm_client:
            # LLM not available, use fallback
            logger.info("LLM not available, using fallback report generation")
            return self._generate_fallback_report(red_flags, yellow_flags)
        
        try:
            # Use the LLM to generate the report
            import httpx
            
            system_prompt = "You are an expert aviation compliance auditor generating comprehensive audit reports. Your reports must be professional, actionable, and based on the provided audit findings."
            
            # Use the LLM client's config to make the API call
            api_url = self.llm_client.config.api_url
            headers = {
                "Authorization": f"Bearer {self.llm_client.config.api_key}",
                "Content-Type": "application/json",
            }
            
            payload = {
                "model": self.llm_client.config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,  # Lower temperature for more consistent reports
                "max_tokens": 4000,  # Allow for comprehensive reports
            }
            
            with httpx.Client(timeout=self.llm_client.config.timeout) as client:
                response = client.post(api_url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()
                
                content = result["choices"][0]["message"]["content"].strip()
                
                # Extract JSON from response (handle markdown code blocks if present)
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()
                
                return content
                
        except Exception as e:
            logger.error(f"Error generating report with LLM: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # Fallback to structured report
            return self._generate_fallback_report(red_flags, yellow_flags)
    
    def _parse_report(self, report_content: str, flag_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Parse the LLM-generated report into structured format."""
        try:
            parsed = json.loads(report_content)
            return parsed
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse report JSON: {e}, using fallback")
            # Fallback parsing
            red_flags = [f for f in flag_data if f["flag_type"] == "RED"]
            yellow_flags = [f for f in flag_data if f["flag_type"] == "YELLOW"]
            return self._generate_fallback_report(red_flags, yellow_flags, as_dict=True)
    
    def _generate_fallback_report(
        self, 
        red_flags: list[dict[str, Any]], 
        yellow_flags: list[dict[str, Any]],
        as_dict: bool = False
    ) -> str | dict[str, Any]:
        """Generate a fallback report if LLM fails."""
        executive_summary = f"""
This audit identified {len(red_flags)} critical compliance issues and {len(yellow_flags)} warnings that require attention.

The organization's maintenance organization exposition (MOE) has been reviewed against EASA Part-145 requirements. While many areas demonstrate compliance, several issues have been identified that need to be addressed to ensure full regulatory compliance.
"""
        
        critical_issues = []
        for flag in red_flags:
            critical_issues.append({
                "title": flag['findings'][:100] + "..." if len(flag['findings']) > 100 else flag['findings'],
                "description": flag['findings'],
                "severity": "HIGH",
                "affected_sections": [flag['chunk_id']],
                "regulatory_basis": [c['reference'] for c in flag['citations'] if c['type'] == 'regulation'],
                "recommendations": flag['recommendations'] or ["Review and update the relevant section to address the identified gap."]
            })
        
        warnings = []
        for flag in yellow_flags:
            warnings.append({
                "title": flag['findings'][:100] + "..." if len(flag['findings']) > 100 else flag['findings'],
                "description": flag['findings'],
                "affected_sections": [flag['chunk_id']],
                "recommendations": flag['recommendations'] or ["Clarify or enhance the relevant section."]
            })
        
        recommendations = []
        for flag in red_flags + yellow_flags:
            recommendations.extend(flag['recommendations'] or [])
        # Deduplicate while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)
        
        overall_assessment = f"""
The organization should prioritize addressing the {len(red_flags)} critical issues identified in this audit. These issues represent potential non-compliance with EASA Part-145 requirements and should be remediated before the next regulatory inspection.

The {len(yellow_flags)} warnings identified should also be addressed to improve the overall quality and clarity of the MOE. While these may not represent immediate compliance risks, addressing them will strengthen the organization's compliance posture.
"""
        
        if as_dict:
            return {
                "executive_summary": executive_summary.strip(),
                "critical_issues": critical_issues,
                "warnings": warnings,
                "recommendations": unique_recommendations[:10],  # Top 10
                "overall_assessment": overall_assessment.strip(),
            }
        else:
            return json.dumps({
                "executive_summary": executive_summary.strip(),
                "critical_issues": critical_issues,
                "warnings": warnings,
                "recommendations": unique_recommendations[:10],
                "overall_assessment": overall_assessment.strip(),
            }, indent=2)
    
    def _generate_no_issues_report(self, audit: Audit) -> FinalReport:
        """Generate a report when no issues are found."""
        return FinalReport(
            audit_id=audit.id,
            executive_summary=f"""
This audit of the maintenance organization exposition (MOE) found no critical compliance issues or warnings.

The document has been reviewed against EASA Part-145 requirements across {audit.chunk_total} sections. All reviewed sections demonstrate compliance with applicable regulations, and no gaps or ambiguities requiring immediate attention were identified.
""",
            critical_issues=[],
            warnings=[],
            recommendations=[
                "Continue to maintain compliance with EASA Part-145 requirements.",
                "Regularly review and update the MOE to reflect organizational changes.",
                "Ensure all personnel are familiar with the current MOE content."
            ],
            overall_assessment="""
The organization's MOE demonstrates strong compliance with EASA Part-145 requirements. No immediate action is required, but the organization should continue to maintain and update the MOE as needed.
""",
            raw_content="",
        )

