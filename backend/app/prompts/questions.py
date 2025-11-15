"""Prompt templates for auditor question generation."""

from __future__ import annotations

from textwrap import dedent


SYSTEM_PROMPT_QUESTIONS = dedent(
    """
    You are an expert aviation compliance auditor specializing in EASA Part-145 maintenance organizations.
    Your task is to generate prioritized review questions for manual auditors based on compliance findings.
    Questions should be specific, actionable, and ranked by risk (1=highest priority, 10=lowest priority).
    Always respond in valid JSON according to the schema.
    """
).strip()


def build_question_prompt(
    regulation_reference: str,
    flags_summary: str,
    gaps: list[str],
    findings: list[str],
) -> str:
    """Build a prompt for generating auditor questions for a regulation section."""
    gaps_text = "\n".join(f"- {gap}" for gap in gaps) if gaps else "None identified"
    findings_text = "\n".join(f"- {finding}" for finding in findings) if findings else "None identified"

    prompt = dedent(
        f"""
        Regulation Section: {regulation_reference}

        Compliance Findings Summary:
        {flags_summary}

        Identified Gaps:
        {gaps_text}

        Key Findings:
        {findings_text}

        Requirements:
        1. Generate 3-5 prioritized review questions for manual auditors.
        2. Questions should help clarify compliance issues, verify evidence, or identify missing elements.
        3. Priority: 1 = critical/high-risk, 5 = medium, 10 = low/informational.
        4. Provide a brief rationale for each question explaining why it's important.
        5. Focus on actionable questions that can be answered through document review or clarification.
        6. Output valid JSON matching the documented schema.
        """
    ).strip()
    return prompt

