"""Service for generating prioritized auditor questions from compliance findings."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field, conint, field_validator

import httpx

from ..config.settings import AppConfig
from ..db.models import Audit, AuditorQuestion, Flag
from ..db.session import get_session

logger = logging.getLogger(__name__)


class QuestionItem(BaseModel):
    """Schema for a single auditor question."""

    question_text: str = Field(min_length=10)
    priority: conint(ge=1, le=10) = 5  # type: ignore[assignment]
    rationale: str = Field(min_length=5)

    @field_validator("question_text", "rationale", mode="before")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else ""


class QuestionPlan(BaseModel):
    """Schema for LLM response containing multiple questions."""

    questions: list[QuestionItem] = Field(min_length=1, max_length=10)

    @field_validator("questions", mode="after")
    @classmethod
    def _validate_questions(cls, values: list[QuestionItem]) -> list[QuestionItem]:
        # Ensure at least one question
        if not values:
            raise ValueError("At least one question is required")
        return values


class QuestionGenerator:
    """Generates prioritized auditor questions from compliance flags."""

    def __init__(self, config: AppConfig | None = None, http_client: httpx.Client | None = None):
        self.config = config or AppConfig()
        self._http_client = http_client or httpx.Client(timeout=60.0)

    def _call_llm(self, system_prompt: str, user_prompt: str, json_mode: bool = True) -> str:
        """Call LLM API (OpenRouter, Featherless, or other OpenAI-compatible) for question generation."""
        api_key = self.config.llm_api_key or self.config.openrouter_api_key
        if not api_key:
            # Fallback: return empty JSON to trigger heuristic generation
            logger.warning("No LLM API key, will use heuristic questions")
            return '{"questions": []}'

        # Determine API base URL
        api_base_url = self.config.llm_api_base_url
        if api_key.startswith("rc_"):
            # Featherless API key detected
            api_base_url = "https://api.featherless.ai/v1"
            logger.debug("Using Featherless API for question generation")
        elif not api_base_url or api_base_url == "https://openrouter.ai/api/v1":
            api_base_url = "https://openrouter.ai/api/v1"

        api_url = f"{api_base_url.rstrip('/')}/chat/completions"
        model = self.config.llm_model_compliance or self.config.openrouter_model_compliance

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        payload = {
            "model": model,
            "messages": messages,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self._http_client.post(api_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "")
            raise ValueError("No choices in LLM API response")
        except Exception as e:
            logger.error(f"LLM call failed: {e}", exc_info=True)
            raise

    def generate_for_audit(self, audit_id: int, min_questions_per_section: int = 3) -> int:
        """
        Generate questions for all regulation sections with flags in the audit.
        Returns the number of questions created.
        """
        session = get_session()
        audit = session.get(Audit, audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found")

        # Group flags by regulation reference
        flags = session.query(Flag).filter(Flag.audit_id == audit_id).all()
        if not flags:
            logger.info(f"No flags found for audit {audit_id}, skipping question generation")
            return 0

        regulation_groups = self._group_flags_by_regulation(flags)
        total_questions = 0

        for regulation_ref, reg_flags in regulation_groups.items():
            # Generate questions for this regulation section
            questions = self._generate_questions_for_regulation(
                audit_id, regulation_ref, reg_flags, min_questions_per_section
            )
            total_questions += len(questions)

        logger.info(f"Generated {total_questions} questions for audit {audit_id}")
        return total_questions

    def _group_flags_by_regulation(self, flags: list[Flag]) -> dict[str, list[Flag]]:
        """Group flags by their primary regulation reference."""
        groups: dict[str, list[Flag]] = defaultdict(list)

        for flag in flags:
            # Extract regulation references from citations
            regulation_refs = [
                cit.reference
                for cit in flag.citations
                if cit.citation_type == "regulation"
            ]
            if regulation_refs:
                # Use the first regulation reference as the primary one
                primary_ref = regulation_refs[0]
                groups[primary_ref].append(flag)
            else:
                # Fallback: use regulation_references from flag metadata if available
                if flag.analysis_metadata and "regulation_references" in flag.analysis_metadata:
                    refs = flag.analysis_metadata["regulation_references"]
                    if refs:
                        groups[refs[0]].append(flag)
                    else:
                        # No regulation reference found, use a generic group
                        groups["UNKNOWN"].append(flag)
                else:
                    groups["UNKNOWN"].append(flag)

        return groups

    def _generate_questions_for_regulation(
        self,
        audit_id: int,
        regulation_ref: str,
        flags: list[Flag],
        min_questions: int,
    ) -> list[AuditorQuestion]:
        """Generate questions for a specific regulation section."""
        session = get_session()

        # Check if questions already exist for this regulation
        existing = (
            session.query(AuditorQuestion)
            .filter(
                AuditorQuestion.audit_id == audit_id,
                AuditorQuestion.regulation_reference == regulation_ref,
            )
            .all()
        )
        if existing:
            logger.debug(f"Questions already exist for {regulation_ref}, skipping")
            return existing

        # Prepare summary data
        flags_summary = self._build_flags_summary(flags)
        all_gaps = []
        all_findings = []
        flag_ids = []

        for flag in flags:
            flag_ids.append(flag.id)
            if flag.gaps:
                all_gaps.extend(flag.gaps)
            if flag.findings:
                all_findings.append(flag.findings)

        # Generate questions using LLM
        from ..prompts.questions import SYSTEM_PROMPT_QUESTIONS, build_question_prompt

        prompt = build_question_prompt(regulation_ref, flags_summary, all_gaps, all_findings)

        try:
            # Call LLM to generate questions
            response_text = self._call_llm(
                system_prompt=SYSTEM_PROMPT_QUESTIONS,
                user_prompt=prompt,
                json_mode=True,
            )

            # Parse and validate response
            import json

            response_data = json.loads(response_text)
            question_plan = QuestionPlan.model_validate(response_data)

            # Ensure minimum question count with heuristics
            questions = question_plan.questions
            if len(questions) < min_questions:
                questions.extend(self._generate_heuristic_questions(flags, min_questions - len(questions)))

            # Persist questions
            persisted_questions = []
            for q_item in questions:
                question = AuditorQuestion(
                    audit_id=audit_id,
                    regulation_reference=regulation_ref,
                    question_text=q_item.question_text,
                    priority=q_item.priority,
                    rationale=q_item.rationale,
                    related_flag_ids=flag_ids,
                    question_metadata={"generated_by": "llm", "flag_count": len(flags)},
                )
                session.add(question)
                persisted_questions.append(question)

            session.commit()
            logger.info(f"Generated {len(persisted_questions)} questions for {regulation_ref}")
            return persisted_questions

        except Exception as e:
            logger.error(f"Error generating questions for {regulation_ref}: {e}", exc_info=True)
            session.rollback()
            # Fallback to heuristic questions
            questions = self._generate_heuristic_questions(flags, min_questions)
            persisted_questions = []
            for q_item in questions:
                question = AuditorQuestion(
                    audit_id=audit_id,
                    regulation_reference=regulation_ref,
                    question_text=q_item.question_text,
                    priority=q_item.priority,
                    rationale=q_item.rationale,
                    related_flag_ids=flag_ids,
                    question_metadata={"generated_by": "heuristic", "flag_count": len(flags)},
                )
                session.add(question)
                persisted_questions.append(question)
            session.commit()
            return persisted_questions

    def _build_flags_summary(self, flags: list[Flag]) -> str:
        """Build a summary of flags for the prompt."""
        red_count = sum(1 for f in flags if f.flag_type == "RED")
        yellow_count = sum(1 for f in flags if f.flag_type == "YELLOW")
        green_count = sum(1 for f in flags if f.flag_type == "GREEN")

        summary = f"Found {len(flags)} flags: {red_count} RED, {yellow_count} YELLOW, {green_count} GREEN"
        if red_count > 0:
            summary += "\n\nCritical issues (RED flags):"
            for flag in flags:
                if flag.flag_type == "RED":
                    summary += f"\n- {flag.findings[:200]}"
        return summary

    def _generate_heuristic_questions(
        self, flags: list[Flag], count: int
    ) -> list[QuestionItem]:
        """Generate heuristic questions when LLM fails or as baseline coverage."""
        questions = []
        red_flags = [f for f in flags if f.flag_type == "RED"]
        yellow_flags = [f for f in flags if f.flag_type == "YELLOW"]

        # Priority 1-3: Questions for RED flags
        for i, flag in enumerate(red_flags[:count]):
            questions.append(
                QuestionItem(
                    question_text=f"Can you provide evidence or clarification for: {flag.findings[:150]}?",
                    priority=min(3, i + 1),
                    rationale=f"Critical compliance issue identified: {flag.findings[:100]}",
                )
            )

        # Priority 4-6: Questions for YELLOW flags
        remaining = count - len(questions)
        for i, flag in enumerate(yellow_flags[:remaining]):
            questions.append(
                QuestionItem(
                    question_text=f"Please clarify or provide additional documentation for: {flag.findings[:150]}?",
                    priority=min(6, 4 + i),
                    rationale=f"Potential compliance concern: {flag.findings[:100]}",
                )
            )

        # Priority 7-10: Generic questions
        remaining = count - len(questions)
        generic_questions = [
            "Are all required procedures documented and accessible to personnel?",
            "Is there evidence of regular review and updates to the manual?",
            "Are personnel qualifications and training records maintained?",
        ]
        for i, q_text in enumerate(generic_questions[:remaining]):
            questions.append(
                QuestionItem(
                    question_text=q_text,
                    priority=min(10, 7 + i),
                    rationale="General compliance verification question",
                )
            )

        return questions[:count]

