import pytest
from unittest.mock import patch, MagicMock

from app.services.ai_service import AIService, PreVisitSummary, PostVisitSummary

@pytest.mark.asyncio
async def test_pre_visit_summary_empty():
    service = AIService()
    result = await service.generate_pre_visit_summary("")
    assert result.summary == "Insufficient symptom data provided."
    assert result.urgency == "Low"
    assert result.key_concerns == []

@pytest.mark.asyncio
async def test_post_visit_summary_empty():
    service = AIService()
    result = await service.generate_post_visit_summary("    ")
    assert result.structured_notes == "No notes provided."
    assert result.follow_up_recommended is False
    assert result.action_items == []

@pytest.mark.asyncio
@patch("app.services.ai_service.HAS_GENAI", False)
async def test_pre_visit_summary_mock_fallback():
    service = AIService()
    # When HAS_GENAI is False, model is None
    service.model = None
    result = await service.generate_pre_visit_summary("Patient has severe headache.")
    assert "Mock summary" in result.summary
    assert result.urgency == "Medium"

@pytest.mark.asyncio
@patch("app.services.ai_service.HAS_GENAI", False)
async def test_post_visit_summary_mock_fallback():
    service = AIService()
    service.model = None
    result = await service.generate_post_visit_summary("Prescribed ibuprofen.")
    assert "Mock structured notes" in result.structured_notes
    assert result.follow_up_recommended is True

@pytest.mark.asyncio
async def test_pre_visit_summary_llm_success():
    service = AIService()
    mock_client = MagicMock()
    service.client = mock_client
    
    mock_response = MagicMock()
    mock_response.text = '{"summary": "Bad headache.", "urgency": "High", "key_concerns": ["Headache"]}'
    
    # We need to mock asyncio.to_thread because it calls generate_content
    with patch("asyncio.to_thread", return_value=mock_response):
        result = await service.generate_pre_visit_summary("Severe headache")
        
    assert result.summary == "Bad headache."
    assert result.urgency == "High"
    assert result.key_concerns == ["Headache"]

@pytest.mark.asyncio
async def test_post_visit_summary_llm_failure():
    service = AIService()
    mock_client = MagicMock()
    service.client = mock_client
    
    # Simulate an exception in to_thread
    with patch("asyncio.to_thread", side_effect=Exception("API Error")):
        result = await service.generate_post_visit_summary("Some notes")
        
    assert "AI Generation Failed" in result.structured_notes
    assert result.action_items == ["Review raw notes"]
