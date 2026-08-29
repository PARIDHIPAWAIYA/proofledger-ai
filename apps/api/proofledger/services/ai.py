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
