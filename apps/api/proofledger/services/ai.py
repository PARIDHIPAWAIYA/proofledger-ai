from __future__ import annotations

from pydantic import BaseModel, Field

from proofledger.config import Settings
from proofledger.domain.models import ControlResult


class AIExplanation(BaseModel):
    summary: str
    likely_causes: list[str] = Field(max_length=3)
    next_question: str
    generated_by: str
    warning: str = "AI explanation is advisory and cannot approve a financial close."


class SchemaMappingResponse(BaseModel):
    mapping: dict[str, str | None]
    generated_by: str
    warning: str = (
        "Header-only suggestion. A controller must confirm every mapping before import."
    )


class BoundedExceptionExplainer:
    """Use Gemini only for grounded language; controls remain deterministic."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def explain(self, result: ControlResult) -> AIExplanation:
        if not self.settings.gemini_api_key:
            return self._deterministic_fallback(result)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.settings.gemini_api_key)
            prompt = (
                "You are a finance-operations copilot. Explain only the supplied "
                "deterministic control result. Do not invent records, assert approval, "
                "or provide legal/tax advice. Return a concise structured response.\n\n"
                f"CONTROL_RESULT={result.model_dump_json()}"
            )
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=AIExplanation,
                ),
            )
            explanation = AIExplanation.model_validate_json(response.text or "{}")
            return explanation.model_copy(update={"generated_by": self.settings.gemini_model})
        except Exception:
            return self._deterministic_fallback(result)

    @staticmethod
    def _deterministic_fallback(result: ControlResult) -> AIExplanation:
        causes = [result.explanation]
        if result.difference_paise:
            causes.append(f"Observed difference is {result.difference_paise} paise.")
        if result.remediation:
            causes.append(result.remediation)
        return AIExplanation(
            summary=f"{result.name}: {result.status.value}.",
            likely_causes=causes[:3],
            next_question=(
                result.remediation
                or "Which source document can independently confirm this result?"
            ),
            generated_by="deterministic-fallback",
        )


class BoundedSchemaMapper:
    """Suggest mappings from column names only; never receive or approve row data."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def suggest(
        self,
        *,
        source_type: str,
        headers: list[str],
        target_fields: list[str],
        deterministic_mapping: dict[str, str | None],
    ) -> SchemaMappingResponse:
        fallback = SchemaMappingResponse(
            mapping=deterministic_mapping,
            generated_by="deterministic-fallback",
        )
        if not self.settings.gemini_api_key:
            return fallback

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.settings.gemini_api_key)
            request = {
                "source_type": source_type,
                "source_column_names": headers,
                "target_fields": target_fields,
                "deterministic_suggestion": deterministic_mapping,
            }
            prompt = (
                "Map only the supplied source column names to the supplied canonical "
                "finance fields. A source column may be used at most once. Use null "
                "when uncertain. Never invent columns. This is advisory and requires "
                "human confirmation. No transaction values are included.\n\n"
                f"MAPPING_REQUEST={request}"
            )
            response = client.models.generate_content(
                model=self.settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=SchemaMappingResponse,
                ),
            )
            proposed = SchemaMappingResponse.model_validate_json(response.text or "{}")
            allowed_targets = set(target_fields)
            allowed_headers = set(headers)
            clean = dict(deterministic_mapping)
            used: set[str] = set()
            for target, source in proposed.mapping.items():
                if target not in allowed_targets or source not in allowed_headers:
                    continue
                if source in used:
                    continue
                clean[target] = source
                used.add(source)
            return SchemaMappingResponse(
                mapping=clean,
                generated_by=self.settings.gemini_model,
            )
        except Exception:
            return fallback
