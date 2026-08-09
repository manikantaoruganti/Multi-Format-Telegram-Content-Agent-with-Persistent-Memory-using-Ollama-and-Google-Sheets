import json
import logging
import re
from pydantic import ValidationError
from app.models.content import LLMContent
from app.llm.ollama_client import OllamaClient, LLMClientError
from app.llm.prompts import CORRECTION_PROMPT_TEMPLATE, X_SHORTEN_PROMPT_TEMPLATE, LINKEDIN_REGEN_PROMPT_TEMPLATE
from app.utils.validation import is_x_post_valid

logger = logging.getLogger(__name__)

class LLMValidationException(Exception):
    """Custom exception for LLM output validation failures."""
    pass

class LLMValidator:
    """
    Validates and corrects LLM generated JSON output.
    Handles malformed JSON, schema validation, and specific content constraints.
    """
    def __init__(self, ollama_client: OllamaClient):
        self.ollama_client = ollama_client

    def _extract_json_from_response(self, response_text: str) -> dict:
        """
        Attempts to extract a JSON object from a string that might contain
        markdown fences or additional text.
        """
        # Try to find JSON within markdown fences
        match = re.search(r"```json\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if match:
            json_str = match.group(1)
            logger.debug("Extracted JSON from markdown fences.")
            return json.loads(json_str)

        # If no fences, try to parse the whole string as JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            # As a last resort, try to find the first and last curly braces
            # and parse the substring in between. This is less robust but can
            # handle cases where LLM adds text before/after JSON.
            first_brace = response_text.find('{')
            last_brace = response_text.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str_candidate = response_text[first_brace : last_brace + 1]
                try:
                    logger.debug("Attempting to extract JSON by brace matching.")
                    return json.loads(json_str_candidate)
                except json.JSONDecodeError:
                    pass # Fall through to error
            raise LLMValidationException("Could not extract valid JSON from LLM response.")

    async def _validate_and_correct_x_post(self, llm_output: LLMContent, user_style: str) -> LLMContent:
        """
        Validates the X post character limit and attempts to correct it if exceeded.
        """
        x_post = llm_output.variants.x_post
        if not is_x_post_valid(x_post):
            logger.warning(f"X post exceeds 280 characters (length: {len(x_post)}). Requesting shorter version.")
            try:
                shorten_prompt = X_SHORTEN_PROMPT_TEMPLATE.format(
                    original_x_post=x_post,
                    original_length=len(x_post),
                    user_style=user_style
                )
                # Request plain text output for this specific prompt
                new_x_post = await self.ollama_client.generate_content(
                    system_prompt="You are a concise copywriter.",
                    user_prompt=shorten_prompt,
                    format_json=False
                )
                new_x_post = new_x_post.strip()
                if not is_x_post_valid(new_x_post):
                    logger.error(f"LLM failed to shorten X post to <= 280 chars after retry. Final length: {len(new_x_post)}")
                    # As a final safety, truncate if LLM fails to shorten
                    llm_output.variants.x_post = new_x_post[:280]
                else:
                    llm_output.variants.x_post = new_x_post
                logger.info(f"X post successfully shortened to {len(llm_output.variants.x_post)} characters.")
            except LLMClientError as e:
                logger.error(f"Failed to get shortened X post from LLM: {e}")
                # Fallback: truncate if LLM fails to shorten
                llm_output.variants.x_post = x_post[:280]
        return llm_output

    async def _validate_and_correct_linkedin_post(self, llm_output: LLMContent, user_style: str) -> LLMContent:
        """
        Validates that LinkedIn post is distinct from X post and attempts to regenerate if identical.
        """
        if llm_output.variants.x_post == llm_output.variants.linkedin_post:
            logger.warning("LinkedIn post is identical to X post. Requesting regeneration.")
            try:
                regen_prompt = LINKEDIN_REGEN_PROMPT_TEMPLATE.format(
                    x_post=llm_output.variants.x_post,
                    linkedin_post=llm_output.variants.linkedin_post,
                    user_style=user_style
                )
                # Request plain text output for this specific prompt
                new_linkedin_post = await self.ollama_client.generate_content(
                    system_prompt="You are a professional content strategist.",
                    user_prompt=regen_prompt,
                    format_json=False
                )
                new_linkedin_post = new_linkedin_post.strip()
                if new_linkedin_post == llm_output.variants.x_post or not new_linkedin_post:
                    logger.error("LLM failed to generate a distinct LinkedIn post after retry or returned empty.")
                    # Fallback: append a generic differentiator if LLM fails
                    llm_output.variants.linkedin_post += " (Expanded for LinkedIn)"
                else:
                    llm_output.variants.linkedin_post = new_linkedin_post
                logger.info("LinkedIn post successfully regenerated to be distinct.")
            except LLMClientError as e:
                logger.error(f"Failed to get distinct LinkedIn post from LLM: {e}")
                # Fallback: append a generic differentiator if LLM fails
                llm_output.variants.linkedin_post += " (Expanded for LinkedIn)"
        return llm_output

    async def validate_and_correct(self, raw_llm_response: str, system_prompt: str, user_prompt: str, user_style: str, max_retries: int = 3) -> LLMContent:
        """
        Validates the raw LLM response against the Pydantic schema and applies corrections.
        Retries with a correction prompt if initial parsing or validation fails.
        """
        attempts = 0
        current_response = raw_llm_response

        while attempts <= max_retries:
            try:
                # 1. Extract JSON from potentially malformed response
                json_data = self._extract_json_from_response(current_response)

                # 2. Validate against Pydantic model
                llm_output = LLMContent(**json_data)

                # 3. Validate all fields are non-empty strings
                if not all(
                    isinstance(getattr(llm_output, field), str) and getattr(llm_output, field).strip()
                    for field in ['title', 'rationale', 'category']
                ):
                    raise LLMValidationException("One or more top-level fields are empty or not strings.")
                if not all(
                    isinstance(getattr(llm_output.variants, field), str) and getattr(llm_output.variants, field).strip()
                    for field in ['x_post', 'linkedin_post']
                ):
                    raise LLMValidationException("One or more variant fields are empty or not strings.")

                # 4. Apply specific content validations and corrections
                llm_output = await self._validate_and_correct_x_post(llm_output, user_style)
                llm_output = await self._validate_and_correct_linkedin_post(llm_output, user_style)

                logger.info(f"LLM output validated successfully after {attempts} attempts.")
                return llm_output

            except (json.JSONDecodeError, ValidationError, LLMValidationException) as e:
                attempts += 1
                logger.warning(f"LLM output validation failed (attempt {attempts}/{max_retries+1}): {e}")
                if attempts > max_retries:
                    logger.error(f"Max retries ({max_retries}) reached for LLM output validation. Final error: {e}")
                    raise LLMValidationException(f"Failed to get valid LLM output after multiple retries: {e}") from e

                logger.info(f"Retrying LLM with correction prompt. Original invalid response: {current_response[:200]}...")
                correction_user_prompt = CORRECTION_PROMPT_TEMPLATE.format(invalid_response=current_response)
                try:
                    # Use the original system prompt for the correction, but a specific user prompt
                    current_response = await self.ollama_client.generate_content(
                        system_prompt=system_prompt, # Use original system prompt
                        user_prompt=correction_user_prompt,
                        format_json=True
                    )
                except LLMClientError as llm_e:
                    logger.error(f"Failed to get LLM response for correction prompt: {llm_e}")
                    raise LLMValidationException(f"LLM failed to respond to correction prompt: {llm_e}") from llm_e
            except Exception as e:
                logger.error(f"An unexpected error occurred during LLM validation: {e}", exc_info=True)
                raise LLMValidationException(f"Unexpected error during validation: {e}") from e
