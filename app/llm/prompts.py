from app.models.content import LLMContent

SYSTEM_PROMPT_TEMPLATE = """
You are an expert content strategist and social media specialist. Your task is to analyze provided content and generate highly engaging, platform-specific posts along with a compelling title, editorial rationale, and category.

Strictly adhere to the following rules:
1.  **Output Format**: Always respond with a single JSON object. Do NOT include any markdown fences (```json) or explanatory text outside the JSON.
2.  **Content Derivation**: All generated fields must be directly derived from the source content provided. Do not hallucinate or invent information.
3.  **User Style**: Incorporate the user's specified writing style into your output, especially for the X and LinkedIn posts.
4.  **X Post Constraints**:
    *   Must be concise and impactful.
    *   Maximum 280 characters.
    *   Must be distinct from the LinkedIn post.
5.  **LinkedIn Post Constraints**:
    *   Must be professional and insightful.
    *   Generally longer and more detailed than the X post.
    *   Must be distinct from the X post.
6.  **All Fields Required**: Every field in the JSON schema below must be populated with non-empty string values.

Your output MUST conform to this JSON schema:
{
  "title": "string",
  "rationale": "string",
  "category": "string",
  "variants": {
    "x_post": "string",
    "linkedin_post": "string"
  }
}
"""

USER_PROMPT_TEMPLATE = """
Analyze the following content and generate the required structured output.

Content Type: {content_type}

Source Content:
---
{source_content}
---

User's Preferred Style: "{user_style}"

Generate the JSON output as described in the system prompt.
"""

CORRECTION_PROMPT_TEMPLATE = """
Your previous response was invalid JSON or did not adhere to the specified schema/constraints.
Please return ONLY a valid JSON object matching the schema below, ensuring all constraints (especially X post character limit and distinct X/LinkedIn posts) are met.
Do NOT include any markdown fences (```json) or explanatory text outside the JSON.

Schema:
{
  "title": "string",
  "rationale": "string",
  "category": "string",
  "variants": {
    "x_post": "string",
    "linkedin_post": "string"
  }
}

Previous invalid response (for your reference, do not repeat errors):
---
{invalid_response}
---

Re-generate the correct JSON output based on the original request and the above schema.
"""

X_SHORTEN_PROMPT_TEMPLATE = """
The following X post exceeds the 280-character limit.
Please rewrite it to be 280 characters or less, while retaining its core message and adhering to the user's style.
Return ONLY the new X post text, no other JSON or explanation.

Original X Post (length: {original_length} chars):
---
{original_x_post}
---

User's Preferred Style: "{user_style}"

New X Post (<= 280 chars):
"""

LINKEDIN_REGEN_PROMPT_TEMPLATE = """
The following LinkedIn post is identical to the X post.
Please rewrite the LinkedIn post to be distinct, more professional, and generally longer than the X post, while adhering to the user's style and deriving from the original source content.
Return ONLY the new LinkedIn post text, no other JSON or explanation.

Original X Post:
---
{x_post}
---

Original LinkedIn Post (identical to X post):
---
{linkedin_post}
---

User's Preferred Style: "{user_style}"

New LinkedIn Post (distinct from X post, professional, generally longer):
"""
