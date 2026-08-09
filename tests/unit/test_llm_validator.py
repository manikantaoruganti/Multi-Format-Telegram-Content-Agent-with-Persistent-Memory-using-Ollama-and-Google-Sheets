import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError
from app.llm.validator import LLMValidator, LLMValidationException
from app.llm.ollama_client import OllamaClient, LLMClientError
from app.models.content import LLMContent, ContentVariants
from app.llm.prompts import SYSTEM_PROMPT_TEMPLATE, CORRECTION_PROMPT_TEMPLATE, X_SHORTEN_PROMPT_TEMPLATE, LINKEDIN_REGEN_PROMPT_TEMPLATE

@pytest.fixture
def mock_ollama_client():
    client = MagicMock(spec=OllamaClient)
    client.generate_content = AsyncMock()
    return client

@pytest.fixture
def llm_validator(mock_ollama_client):
    return LLMValidator(mock_ollama_client)

@pytest.fixture
def valid_llm_response_json():
    return {
        "title": "The Future of AI in Content Creation",
        "rationale": "This article explores how AI is revolutionizing content generation, offering insights into efficiency and creativity.",
        "category": "Technology",
        "variants": {
            "x_post": "AI is transforming content creation! 🤖 Discover how it boosts efficiency & sparks creativity. #AI #ContentMarketing",
            "linkedin_post": "The integration of AI into content creation workflows is no longer a futuristic concept but a present reality. This deep dive explores the multifaceted impact on efficiency, scalability, and the very nature of creative work. A must-read for marketers and strategists."
        }
    }

@pytest.fixture
def valid_llm_response_str(valid_llm_response_json):
    return json.dumps(valid_llm_response_json)

@pytest.fixture
def user_style():
    return "witty and informal"

@pytest.mark.asyncio
async def test_validator_valid_json(llm_validator, mock_ollama_client, valid_llm_response_str, valid_llm_response_json, user_style):
    mock_ollama_client.generate_content.return_value = valid_llm_response_str # Not called in this path

    result = await llm_validator.validate_and_correct(
        valid_llm_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style
    )
    assert isinstance(result, LLMContent)
    assert result.title == valid_llm_response_json["title"]
    assert result.variants.x_post == valid_llm_response_json["variants"]["x_post"]
    assert result.variants.linkedin_post == valid_llm_response_json["variants"]["linkedin_post"]
    mock_ollama_client.generate_content.assert_not_called() # Should not call LLM for correction

@pytest.mark.asyncio
async def test_validator_malformed_json_with_retry(llm_validator, mock_ollama_client, valid_llm_response_str, user_style):
    malformed_response = "```json\n" + valid_llm_response_str + "```\nSome extra text."
    
    # First call to LLM (initial generation)
    # Second call to LLM (correction prompt)
    mock_ollama_client.generate_content.side_effect = [
        malformed_response, # Initial malformed response
        valid_llm_response_str # Corrected response after retry
    ]

    result = await llm_validator.validate_and_correct(
        malformed_response,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1
    )
    assert isinstance(result, LLMContent)
    assert result.title == "The Future of AI in Content Creation"
    assert mock_ollama_client.generate_content.call_count == 2
    # Check the correction prompt was sent
    args, _ = mock_ollama_client.generate_content.call_args_list[1]
    assert args[0] == SYSTEM_PROMPT_TEMPLATE
    assert "Your previous response was invalid JSON." in args[1]
    assert "Some extra text." in args[1] # Original invalid response included

@pytest.mark.asyncio
async def test_validator_malformed_json_max_retries_exceeded(llm_validator, mock_ollama_client, user_style):
    malformed_response = "This is not JSON."
    mock_ollama_client.generate_content.side_effect = [
        malformed_response, # Initial malformed response
        malformed_response, # First retry
        malformed_response, # Second retry
        malformed_response, # Third retry (max_retries=3)
    ]

    with pytest.raises(LLMValidationException, match="Failed to get valid LLM output after multiple retries"):
        await llm_validator.validate_and_correct(
            malformed_response,
            SYSTEM_PROMPT_TEMPLATE,
            "user prompt",
            user_style,
            max_retries=3
        )
    assert mock_ollama_client.generate_content.call_count == 4 # Initial + 3 retries

@pytest.mark.asyncio
async def test_validator_missing_field(llm_validator, mock_ollama_client, user_style):
    invalid_json = {"title": "Title", "rationale": "Rationale", "category": "Category", "variants": {"x_post": "X", "linkedin_post": ""}} # Missing linkedin_post content
    invalid_response_str = json.dumps(invalid_json)
    valid_response_str = json.dumps({**invalid_json, "variants": {"x_post": "X", "linkedin_post": "LinkedIn"}})

    mock_ollama_client.generate_content.side_effect = [
        invalid_response_str, # Initial invalid response
        valid_response_str # Corrected response after retry
    ]

    result = await llm_validator.validate_and_correct(
        invalid_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1
    )
    assert isinstance(result, LLMContent)
    assert result.variants.linkedin_post == "LinkedIn"
    assert mock_ollama_client.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_validator_x_post_too_long(llm_validator, mock_ollama_client, valid_llm_response_json, user_style):
    long_x_post = "a" * 281
    initial_response_json = {**valid_llm_response_json, "variants": {**valid_llm_response_json["variants"], "x_post": long_x_post}}
    initial_response_str = json.dumps(initial_response_json)

    shortened_x_post = "a" * 200
    
    # First call to LLM (initial generation)
    # Second call to LLM (shorten X post)
    mock_ollama_client.generate_content.side_effect = [
        initial_response_str, # Initial response with long X post
        shortened_x_post # LLM returns shortened X post
    ]

    result = await llm_validator.validate_and_correct(
        initial_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1 # Max retries for JSON validation, not X post shortening
    )
    assert isinstance(result, LLMContent)
    assert result.variants.x_post == shortened_x_post
    assert len(result.variants.x_post) <= 280
    assert mock_ollama_client.generate_content.call_count == 2
    # Check the X shorten prompt was sent
    args, _ = mock_ollama_client.generate_content.call_args_list[1]
    assert "exceeds the 280-character limit" in args[1]
    assert args[0] == "You are a concise copywriter." # Specific system prompt for shortening

@pytest.mark.asyncio
async def test_validator_x_post_too_long_llm_fails_to_shorten(llm_validator, mock_ollama_client, valid_llm_response_json, user_style):
    long_x_post = "a" * 281
    initial_response_json = {**valid_llm_response_json, "variants": {**valid_llm_response_json["variants"], "x_post": long_x_post}}
    initial_response_str = json.dumps(initial_response_json)

    still_long_x_post = "b" * 285 # LLM fails to shorten enough
    
    mock_ollama_client.generate_content.side_effect = [
        initial_response_str,
        still_long_x_post
    ]

    result = await llm_validator.validate_and_correct(
        initial_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1
    )
    assert isinstance(result, LLMContent)
    assert result.variants.x_post == still_long_x_post[:280] # Should be truncated as a fallback
    assert len(result.variants.x_post) == 280
    assert mock_ollama_client.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_validator_x_and_linkedin_identical(llm_validator, mock_ollama_client, valid_llm_response_json, user_style):
    identical_post = "This is an identical post."
    initial_response_json = {**valid_llm_response_json, "variants": {"x_post": identical_post, "linkedin_post": identical_post}}
    initial_response_str = json.dumps(initial_response_json)

    distinct_linkedin_post = "This is a distinct LinkedIn post, more professional."
    
    mock_ollama_client.generate_content.side_effect = [
        initial_response_str, # Initial response with identical posts
        distinct_linkedin_post # LLM returns distinct LinkedIn post
    ]

    result = await llm_validator.validate_and_correct(
        initial_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1
    )
    assert isinstance(result, LLMContent)
    assert result.variants.x_post == identical_post
    assert result.variants.linkedin_post == distinct_linkedin_post
    assert result.variants.x_post != result.variants.linkedin_post
    assert mock_ollama_client.generate_content.call_count == 2
    # Check the LinkedIn regen prompt was sent
    args, _ = mock_ollama_client.generate_content.call_args_list[1]
    assert "LinkedIn post is identical to the X post" in args[1]
    assert args[0] == "You are a professional content strategist." # Specific system prompt for LinkedIn regen

@pytest.mark.asyncio
async def test_validator_x_and_linkedin_identical_llm_fails_to_distinguish(llm_validator, mock_ollama_client, valid_llm_response_json, user_style):
    identical_post = "This is an identical post."
    initial_response_json = {**valid_llm_response_json, "variants": {"x_post": identical_post, "linkedin_post": identical_post}}
    initial_response_str = json.dumps(initial_response_json)

    still_identical_post = "This is an identical post." # LLM fails to make it distinct
    
    mock_ollama_client.generate_content.side_effect = [
        initial_response_str,
        still_identical_post
    ]

    result = await llm_validator.validate_and_correct(
        initial_response_str,
        SYSTEM_PROMPT_TEMPLATE,
        "user prompt",
        user_style,
        max_retries=1
    )
    assert isinstance(result, LLMContent)
    assert result.variants.x_post == identical_post
    assert result.variants.linkedin_post == still_identical_post + " (Expanded for LinkedIn)" # Fallback
    assert result.variants.x_post != result.variants.linkedin_post
    assert mock_ollama_client.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_validator_llm_client_error_during_correction(llm_validator, mock_ollama_client, user_style):
    malformed_response = "This is not JSON."
    mock_ollama_client.generate_content.side_effect = [
        malformed_response, # Initial malformed response
        LLMClientError("Ollama is down") # LLM fails during correction
    ]

    with pytest.raises(LLMValidationException, match="LLM failed to respond to correction prompt"):
        await llm_validator.validate_and_correct(
            malformed_response,
            SYSTEM_PROMPT_TEMPLATE,
            "user prompt",
            user_style,
            max_retries=1
        )
    assert mock_ollama_client.generate_content.call_count == 2

@pytest.mark.asyncio
async def test_validator_empty_fields_after_correction_retry(llm_validator, mock_ollama_client, user_style):
    initial_invalid_json = {"title": "Title", "rationale": "", "category": "Category", "variants": {"x_post": "X", "linkedin_post": "LinkedIn"}}
    initial_invalid_response_str = json.dumps(initial_invalid_json)

    # LLM returns JSON but with an empty field even after correction prompt
    still_invalid_json = {"title": "Title", "rationale": "", "category": "Category", "variants": {"x_post": "X", "linkedin_post": "LinkedIn"}}
    still_invalid_response_str = json.dumps(still_invalid_json)

    mock_ollama_client.generate_content.side_effect = [
        initial_invalid_response_str,
        still_invalid_response_str, # First retry still has empty rationale
        still_invalid_response_str, # Second retry still has empty rationale
        still_invalid_response_str, # Third retry still has empty rationale
    ]

    with pytest.raises(LLMValidationException, match="Failed to get valid LLM output after multiple retries"):
        await llm_validator.validate_and_correct(
            initial_invalid_response_str,
            SYSTEM_PROMPT_TEMPLATE,
            "user prompt",
            user_style,
            max_retries=3
        )
    assert mock_ollama_client.generate_content.call_count == 4
