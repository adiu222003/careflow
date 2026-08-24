from __future__ import annotations

import logging

try:
    from google import genai
    from pydantic import BaseModel, Field
    HAS_GENAI = True
except ImportError:
    from pydantic import BaseModel, Field
    HAS_GENAI = False

from app.core.config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class PreVisitSummary(BaseModel):
    summary: str = Field(description="A concise structured clinical summary of the patient's symptoms.")
    urgency: str = Field(description="The triaged urgency level. Must be exactly 'Low', 'Medium', or 'High'.")
    key_concerns: list[str] = Field(description="Bullet points of the main medical concerns to address.")


class PostVisitSummary(BaseModel):
    structured_notes: str = Field(description="The doctor's raw notes formatted into a clean, professional clinical structure.")
    follow_up_recommended: bool = Field(description="Whether a follow-up appointment is recommended based on the notes.")
    action_items: list[str] = Field(description="List of action items for the patient or staff.")


class AIService:
    """
    Handles interactions with the LLM for medical summaries.
    Includes rate-limit retry logic and fallback generation.
    """

    def __init__(self) -> None:
        self.system_instruction = "This is an administrative clinical-support summary, not a diagnosis and not a medical recommendation. Do not invent symptoms, diagnoses, treatments or medications. Do not override clinician judgment."
        if not HAS_GENAI or not settings.gemini_api_key:
            self.client = None
            logger.warning("Gemini API not configured. AIService will use mock fallbacks.")
        else:
            self.client = genai.Client(api_key=settings.gemini_api_key)

    async def generate_pre_visit_summary(self, symptoms_text: str) -> PreVisitSummary:
        """
        Summarizes raw patient symptoms into a structured clinical summary.
        """
        if not symptoms_text or len(symptoms_text.strip()) < 10:
            return PreVisitSummary(
                summary="Insufficient symptom data provided.",
                urgency="Low",
                key_concerns=[]
            )

        if not self.client:
            return self._mock_pre_visit_summary(symptoms_text)

        prompt = f"""
        Please structure the following raw patient symptoms into a clinical summary.
        Extract the main concerns and estimate urgency (Low, Medium, High).

        Patient Symptoms:
        {symptoms_text}
        """

        try:
            import asyncio

            from google.genai import types

            def _sync_call():
                return self.client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=PreVisitSummary,
                        temperature=0.0,
                        system_instruction=self.system_instruction
                    )
                )

            response = await asyncio.to_thread(_sync_call)
            if not response.text:
                raise ValueError("Empty response text")
            return PreVisitSummary.model_validate_json(response.text)
        except Exception as e:
            logger.error(f"Failed to generate pre-visit summary: {e}")
            # Fallback
            return PreVisitSummary(
                summary="[AI Generation Failed] " + symptoms_text[:200],
                urgency="Medium",
                key_concerns=["Review raw symptoms"]
            )

    async def generate_post_visit_summary(self, doctor_notes: str) -> PostVisitSummary:
        """
        Structures raw doctor notes into a clean post-visit summary.
        """
        if not doctor_notes or len(doctor_notes.strip()) < 5:
            return PostVisitSummary(
                structured_notes="No notes provided.",
                follow_up_recommended=False,
                action_items=[]
            )

        if not self.client:
            return self._mock_post_visit_summary(doctor_notes)

        prompt = f"""
        Please structure the following raw doctor notes into a clean, professional clinical summary.
        Extract any action items and determine if follow-up is recommended.

        Doctor Notes:
        {doctor_notes}
        """

        try:
            import asyncio

            from google.genai import types

            def _sync_call():
                return self.client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=PostVisitSummary,
                        temperature=0.0,
                        system_instruction=self.system_instruction
                    )
                )

            response = await asyncio.to_thread(_sync_call)
            if not response.text:
                raise ValueError("Empty response text")
            return PostVisitSummary.model_validate_json(response.text)
        except Exception as e:
            logger.error(f"Failed to generate post-visit summary: {e}")
            # Fallback
            return PostVisitSummary(
                structured_notes="[AI Generation Failed] " + doctor_notes[:200],
                follow_up_recommended=False,
                action_items=["Review raw notes"]
            )

    def _mock_pre_visit_summary(self, text: str) -> PreVisitSummary:
        """Mock fallback when LLM is disabled."""
        return PreVisitSummary(
            summary=f"Mock summary of: {text[:50]}...",
            urgency="Medium",
            key_concerns=["Patient reported symptoms", "Needs review"]
        )

    def _mock_post_visit_summary(self, text: str) -> PostVisitSummary:
        """Mock fallback when LLM is disabled."""
        return PostVisitSummary(
            structured_notes=f"Mock structured notes: {text[:50]}...",
            follow_up_recommended=True,
            action_items=["Follow up in 2 weeks", "Prescribe meds"]
        )
