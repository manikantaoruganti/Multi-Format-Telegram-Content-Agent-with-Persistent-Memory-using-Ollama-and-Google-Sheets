import pytest
from app.llm.prompts import SYSTEM_PROMPT_TEMPLATE, USER_PROMPT_TEMPLATE, CORRECTION_PROMPT_TEMPLATE, X_SHORTEN_PROMPT_TEMPLATE, LINKEDIN_REGEN_PROMPT_TEMPLATE
from app.models.content import LLMContent

def test_system_prompt_template_structure():
    assert "expert content strategist" in SYSTEM_PROMPT_TEMPLATE
    assert "Output Format: Always respond with a single JSON object." in SYSTEM_PROMPT_TEMPLATE
    assert "X Post Constraints" in SYSTEM_PROMPT_TEMPLATE
    assert "LinkedIn Post Constraints" in SYSTEM_PROMPT_TEMPLATE
    assert "Your output MUST conform to this JSON schema" in SYSTEM_PROMPT_TEMPLATE
    assert '"title": "string"' in SYSTEM_PROMPT_TEMPLATE
    assert '"x_post": "string"' in SYSTEM_PROMPT_TEMPLATE
    assert '"linkedin_post": "string"' in SYSTEM_PROMPT_TEMPLATE

def test_user_prompt_template_formatting():
    content_type = "URL"
    source_content = "This is an article about AI."
    user_style = "witty and informal"

    formatted_prompt = USER_PROMPT_TEMPLATE.format(
        content_type=content_type,
        source_content=source_content,
        user_style=user_style
    )

    assert f"Content Type: {content_type}" in formatted_prompt
    assert f"Source Content:\n---\n{source_content}\n---" in formatted_prompt
    assert f'User\'s Preferred Style: "{user_style}"' in formatted_prompt
    assert "Generate the JSON output as described in the system prompt." in formatted_prompt

def test_correction_prompt_template_formatting():
    invalid_response = "```json\n{invalid json}\n```"
    formatted_prompt = CORRECTION_PROMPT_TEMPLATE.format(invalid_response=invalid_response)

    assert "Your previous response was invalid JSON." in formatted_prompt
    assert "Return ONLY a valid JSON object matching this schema" in formatted_prompt
    assert "Previous invalid response (for your reference, do not repeat errors):" in formatted_prompt
    assert invalid_response in formatted_prompt
    assert '"title": "string"' in formatted_prompt # Schema should be included

def test_x_shorten_prompt_template_formatting():
    original_x_post = "This is a very long X post that definitely exceeds the 280 character limit and needs to be shortened significantly to fit the platform's constraints. It contains important information that must be preserved in a more concise format."
    original_length = len(original_x_post)
    user_style = "direct and punchy"

    formatted_prompt = X_SHORTEN_PROMPT_TEMPLATE.format(
        original_x_post=original_x_post,
        original_length=original_length,
        user_style=user_style
    )

    assert "exceeds the 280-character limit." in formatted_prompt
    assert f"Original X Post (length: {original_length} chars):" in formatted_prompt
    assert original_x_post in formatted_prompt
    assert f'User\'s Preferred Style: "{user_style}"' in formatted_prompt
    assert "New X Post (<= 280 chars):" in formatted_prompt

def test_linkedin_regen_prompt_template_formatting():
    x_post = "Short X post."
    linkedin_post = "Short X post." # Identical
    user_style = "professional and expansive"

    formatted_prompt = LINKEDIN_REGEN_PROMPT_TEMPLATE.format(
        x_post=x_post,
        linkedin_post=linkedin_post,
        user_style=user_style
    )

    assert "LinkedIn post is identical to the X post." in formatted_prompt
    assert "Please rewrite the LinkedIn post to be distinct, more professional, and generally longer" in formatted_prompt
    assert f"Original X Post:\n---\n{x_post}\n---" in formatted_prompt
    assert f"Original LinkedIn Post (identical to X post):\n---\n{linkedin_post}\n---" in formatted_prompt
    assert f'User\'s Preferred Style: "{user_style}"' in formatted_prompt
    assert "New LinkedIn Post (distinct from X post, professional, generally longer):" in formatted_prompt
