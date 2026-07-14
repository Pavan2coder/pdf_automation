"""
services/ai_service.py
──────────────────────
Sends extracted document text to Gemini (or OpenAI) and receives a
structured list of ProjectData objects back as validated JSON.

Design choices
──────────────
• One AI call per session (all source files concatenated) – cheaper and gives
  the model full context to separate multiple projects automatically.
• Strict JSON schema in the prompt + Pydantic validation on the way back.
• Automatic retry with exponential back-off (tenacity).
• Falls back to OpenAI if Gemini key is absent / call fails.
"""

from __future__ import annotations

import json
import re
from typing import Any

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.logging import get_logger
from app.models.schemas import ProjectData, TeamMember

log = get_logger(__name__)

# ── Optional AI SDK imports ────────────────────────────────────────────────────
try:
    import google.generativeai as genai  # type: ignore
    _HAVE_GEMINI = True
except ImportError:
    _HAVE_GEMINI = False

try:
    from openai import AsyncOpenAI  # type: ignore
    _HAVE_OPENAI = True
except ImportError:
    _HAVE_OPENAI = False


# ──────────────────────────────────────────────────────────────────────────────
# Prompt template
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an expert academic project analyst and technical writer.
Your job is to extract structured information from raw project document text
and return ONLY a valid JSON array – nothing else, no markdown, no explanation.
""".strip()

_USER_PROMPT_TEMPLATE = """
Below is the combined text of one or more project documents (reports, abstracts,
PPTs, proposals, etc.). There may be multiple SEPARATE projects in this text.

YOUR TASK:
1. Identify each distinct project.
2. For each project, extract ALL available information and fill the JSON schema.
3. Rewrite every field professionally: fix grammar, improve clarity, keep meaning.
4. If a field has no information, use null – never invent content.
5. Return a JSON ARRAY where each element is one project object.

JSON SCHEMA FOR EACH PROJECT OBJECT:
{{
  "project_name":        "short name / title used to name output files",
  "project_title":       "full formal title",
  "theme":               "theme / domain (e.g. Education, Healthcare, IoT)",
  "problem_statement":   "clear problem description",
  "idea_description":    "what the project does, how it works",
  "objectives":          "bullet-point or paragraph list of objectives",
  "purpose":             "why this project matters",
  "motivation":          "what motivated this project",
  "methodology":         "technical approach and methods used",
  "technology_stack":    "languages, frameworks, APIs, hardware used",
  "components":          "hardware or software components",
  "working_principle":   "how the system works step by step",
  "architecture":        "system architecture description",
  "features":            "key features of the system",
  "uniqueness":          "what makes it unique / innovative",
  "advantages":          "advantages over existing solutions",
  "applications":        "potential real-world applications",
  "customer_segment":    "target users or customer segments",
  "customer_survey":     "survey questions and outcomes if available",
  "market_analysis":     "market size, growth, opportunity",
  "competitor_analysis": "comparison with existing competitors",
  "business_model":      "business model canvas summary",
  "revenue_streams":     "how it will make money",
  "cost_estimation":     "prototype or development cost breakdown",
  "prototype_details":   "prototype description and demo results",
  "implementation_plan": "step-by-step implementation plan",
  "roadmap":             "project timeline and milestones",
  "future_scope":        "planned future enhancements",
  "expected_outcomes":   "expected results and impact",
  "conclusion":          "project conclusion summary",
  "team_members": [
    {{
      "name":        "Full Name",
      "roll_number": "roll number if present else null",
      "phone":       "phone if present else null",
      "email":       "email if present else null"
    }}
  ],
  "guide_name":        "faculty guide full name",
  "guide_designation": "guide designation (e.g. Assistant Professor)",
  "guide_department":  "guide department",
  "institution":       "institution / university name",
  "references":        "references list as a single string"
}}

IMPORTANT RULES:
- Return ONLY the JSON array. No preamble, no code fences, no explanation.
- If there is exactly one project, return an array with one object.
- project_name must be a SHORT identifier (2-4 words, no special chars except spaces).
- Every string value must be professional, grammatically correct English.
- Do NOT truncate or shorten important technical content.

DOCUMENT TEXT:
─────────────────────────────────────────────────────────────────────────
{combined_text}
─────────────────────────────────────────────────────────────────────────
"""


# ──────────────────────────────────────────────────────────────────────────────
# AI Service
# ──────────────────────────────────────────────────────────────────────────────

class AIService:
    """
    Wraps Gemini (primary) and OpenAI (fallback) behind a unified interface.
    Call `await ai.extract_projects(raw_texts)` to get list[ProjectData].
    """

    def __init__(self) -> None:
        self._provider = settings.AI_PROVIDER

        if self._provider == "gemini" and _HAVE_GEMINI and settings.GEMINI_API_KEY:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            self._gemini_model = genai.GenerativeModel(
                model_name=settings.GEMINI_MODEL,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=8192,
                ),
                system_instruction=_SYSTEM_PROMPT,
            )
            log.info("AI: Gemini configured (%s)", settings.GEMINI_MODEL)
        else:
            self._gemini_model = None

        if _HAVE_OPENAI and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            log.info("AI: OpenAI configured (%s)", settings.OPENAI_MODEL)
        else:
            self._openai_client = None

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────

    async def extract_projects(
        self, raw_texts: dict[str, str]
    ) -> list[ProjectData]:
        """
        Parameters
        ----------
        raw_texts : dict[filename → extracted_text]
            All source documents for this session.

        Returns
        -------
        list[ProjectData]
            One ProjectData per detected project.
        """
        combined = self._combine_texts(raw_texts)
        prompt   = _USER_PROMPT_TEMPLATE.format(combined_text=combined)

        # Try primary provider, fall back to secondary
        raw_json: str = ""
        last_error: Exception | None = None

        if self._provider == "gemini" and self._gemini_model:
            try:
                raw_json = await self._call_gemini(prompt)
            except Exception as exc:
                log.warning("Gemini failed (%s), trying OpenAI…", exc)
                last_error = exc

        if not raw_json and self._openai_client:
            try:
                raw_json = await self._call_openai(prompt)
            except Exception as exc:
                log.error("OpenAI also failed: %s", exc)
                last_error = exc

        if not raw_json:
            raise RuntimeError(
                f"All AI providers failed. Last error: {last_error}"
            )

        return self._parse_response(raw_json)

    # ──────────────────────────────────────────────────────────────────────────
    # Provider calls
    # ──────────────────────────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call_gemini(self, prompt: str) -> str:
        log.debug("Sending prompt to Gemini (%d chars)", len(prompt))
        response = await self._gemini_model.generate_content_async(prompt)
        text = response.text.strip()
        log.debug("Gemini response: %d chars", len(text))
        return text

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    async def _call_openai(self, prompt: str) -> str:
        log.debug("Sending prompt to OpenAI (%d chars)", len(prompt))
        response = await self._openai_client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.2,
            max_tokens=8192,
            response_format={"type": "json_object"},
        )
        text = response.choices[0].message.content or ""
        log.debug("OpenAI response: %d chars", len(text))
        return text

    # ──────────────────────────────────────────────────────────────────────────
    # Response parsing
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_response(self, raw: str) -> list[ProjectData]:
        """
        Parse AI JSON response → list[ProjectData].
        Handles both array and single-object responses.
        Strips markdown code fences if present.
        """
        # Strip markdown fences  ```json … ```
        raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r"\s*```$", "", raw.strip(), flags=re.MULTILINE)
        raw = raw.strip()

        try:
            data: Any = json.loads(raw)
        except json.JSONDecodeError as exc:
            # Try to salvage: find first [ … ] block
            match = re.search(r"\[.*\]", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    raise ValueError(f"Could not parse AI response as JSON: {exc}\n\nRaw:\n{raw[:500]}")
            else:
                raise ValueError(f"AI response is not valid JSON: {exc}\n\nRaw:\n{raw[:500]}")

        # Normalise to list
        if isinstance(data, dict):
            # OpenAI json_object mode may wrap array in a key
            for key in ("projects", "data", "result", "results"):
                if key in data and isinstance(data[key], list):
                    data = data[key]
                    break
            else:
                data = [data]

        if not isinstance(data, list):
            raise ValueError(f"Expected JSON array, got {type(data)}")

        projects: list[ProjectData] = []
        for raw_proj in data:
            try:
                proj = self._dict_to_project(raw_proj)
                projects.append(proj)
                log.info("Parsed project: %s", proj.project_name)
            except Exception as exc:
                log.warning("Skipping malformed project entry: %s", exc)

        return projects

    def _dict_to_project(self, d: dict[str, Any]) -> ProjectData:
        """Convert raw AI dict → validated ProjectData."""
        # Parse team_members separately (list of dicts)
        raw_members = d.pop("team_members", []) or []
        members: list[TeamMember] = []
        for m in raw_members:
            if isinstance(m, dict):
                members.append(TeamMember(
                    name        = m.get("name", ""),
                    roll_number = m.get("roll_number"),
                    phone       = m.get("phone"),
                    email       = m.get("email"),
                ))

        return ProjectData(**{**d, "team_members": members})

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _combine_texts(self, raw_texts: dict[str, str]) -> str:
        """
        Combine all source document texts with clear file-name separators so
        the model can distinguish between different documents.
        Priority: sort by document type heuristic (report > proposal > abstract > ppt).
        """
        priority = {"report": 0, "proposal": 1, "synopsis": 2,
                    "abstract": 3, "ppt": 4, "pptx": 4}

        def _rank(name: str) -> int:
            n = name.lower()
            for kw, rank in priority.items():
                if kw in n:
                    return rank
            return 99

        sorted_items = sorted(raw_texts.items(), key=lambda kv: _rank(kv[0]))

        parts: list[str] = []
        for fname, text in sorted_items:
            if text.strip():
                parts.append(
                    f"{'='*60}\n"
                    f"DOCUMENT: {fname}\n"
                    f"{'='*60}\n"
                    f"{text}"
                )

        return "\n\n".join(parts)
