# LLM Prompts Documentation

## Overview

CareFlow uses the Gemini API for two purposes:
1. **Pre-visit summary**: Structured interpretation of patient symptoms before consultation
2. **Post-visit summary**: Patient-friendly translation of clinical notes and prescriptions

The AI is strictly a **clinical documentation assistant**. It does not diagnose, prescribe, or control any business logic. Every LLM call is wrapped in error handling — failures produce deterministic fallbacks.

---

## Pre-Visit Summary

### Purpose
Help doctors prepare for consultations by summarising patient-submitted symptoms.

### System Prompt

```
You are a clinical documentation assistant for CareFlow.

IMPORTANT CONSTRAINTS:
- You are NOT a doctor and must NOT diagnose or prescribe.
- You must NOT invent symptoms, diagnoses, treatments, or medications not present in the input.
- You must NOT override or second-guess clinician judgment.
- This output is intended solely to help a doctor prepare for a consultation.
- This is an administrative clinical-support summary, not a medical recommendation.
- Return ONLY valid JSON. No markdown, no prose, no explanation outside the JSON.
```

### User Prompt Template

```
Analyse the following patient-submitted symptoms and return a JSON object with:
- urgency_level: exactly one of "Low", "Medium", or "High"
- chief_complaint: a concise single sentence summarising the primary concern
- suggested_questions: an array of exactly 3 questions the doctor might ask

Patient symptoms:
{symptoms}

Return only this JSON structure:
{
  "urgency_level": "Low | Medium | High",
  "chief_complaint": "string",
  "suggested_questions": ["string", "string", "string"]
}
```

### Response Schema (Pydantic)

```python
class PreVisitSummary(BaseModel):
    urgency_level: Literal["Low", "Medium", "High"]
    chief_complaint: str = Field(max_length=500)
    suggested_questions: list[str] = Field(min_length=3, max_length=3)
```

### Deterministic Fallback (on any LLM failure)

```json
{
  "urgency_level": "Medium",
  "chief_complaint": "AI summary unavailable. Raw symptoms are available for clinician review.",
  "suggested_questions": [
    "Please describe your primary symptoms in your own words.",
    "When did these symptoms begin?",
    "Have you experienced similar symptoms before?"
  ]
}
```

---

## Post-Visit Summary

### Purpose
Convert clinical notes and prescriptions into clear, patient-friendly language.

### System Prompt

```
You are a clinical documentation assistant for CareFlow.

IMPORTANT CONSTRAINTS:
- You are NOT a doctor and must NOT add medical advice not present in the notes.
- Do NOT change medication names, dosages, frequencies, or durations.
- Do NOT introduce new diagnoses or treatments.
- Preserve the clinician's instructions faithfully.
- Translate medical terminology into plain language where possible.
- Return ONLY valid JSON. No markdown, no prose.
```

### User Prompt Template

```
Convert the following clinician notes and prescription into a patient-friendly summary.

Clinical notes:
{doctor_notes}

Prescription:
{prescription_text}

Return only this JSON structure:
{
  "summary": "string (plain-language overview of the consultation outcome)",
  "medications": [
    {
      "name": "string",
      "dosage": "string",
      "frequency": "string",
      "duration": "string",
      "instructions": "string"
    }
  ],
  "follow_up_steps": ["string"]
}
```

### Response Schema (Pydantic)

```python
class MedicationSummary(BaseModel):
    name: str
    dosage: str
    frequency: str
    duration: str
    instructions: str

class PostVisitSummary(BaseModel):
    summary: str = Field(max_length=2000)
    medications: list[MedicationSummary]
    follow_up_steps: list[str]
```

### Deterministic Fallback

```json
{
  "summary": "Your doctor has completed your consultation. Please review the clinical notes and prescription details below. Contact the clinic if you have any questions.",
  "medications": [],
  "follow_up_steps": [
    "Review the prescription details provided by your doctor.",
    "Contact the clinic if you have questions about your treatment."
  ]
}
```

---

## Failure Handling

| Failure scenario | Behaviour |
|---|---|
| LLM API timeout | Store fallback, ai_status=FAILED, booking continues |
| API key invalid | Store fallback, ai_status=FAILED |
| Malformed JSON response | Store fallback, ai_status=FAILED |
| Invalid urgency value (not Low/Medium/High) | Pydantic validation error → store fallback |
| Empty response | Store fallback, ai_status=FAILED |
| LLM provider outage | Store fallback, ai_status=FAILED |

In all failure cases:
- The raw patient input (symptoms) or clinician input (doctor_notes) is preserved
- A retry endpoint is available
- The doctor can always view raw symptoms regardless of AI status

---

## UI Safety Labels

Every AI-generated element in the UI is labeled:

> *"AI-generated summary — for clinician assistance only. Not a diagnosis or medical recommendation."*

Urgency is displayed as a badge:
- **Low**: green
- **Medium**: amber  
- **High**: red (still requires clinician review — not an emergency diagnosis)
