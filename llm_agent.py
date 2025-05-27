import os
import json
import base64
import re
from dotenv import load_dotenv
from openai import OpenAI # Import OpenAI client

load_dotenv()
# The OpenAI client will automatically look for the OPENAI_API_KEY environment variable
# We will pass the client instance to the functions that need it.

# MODEL_NAME = "gpt-4o" # Or another suitable OpenAI model
# MAX_CHARS_SINGLE = 15000 # Keep this if needed for context splitting, but OpenAI handles larger contexts

def sanitize_actions(actions):
    valid = []
    for a in actions:
        # Keep the contains check as it's a general selector issue, not specific to Gemini
        if ":contains" in a.get("selector", ""):
            print(f"[Sanitizer] Skipping invalid selector: {a['selector']}")
            continue
        valid.append(a)
    return valid

# Modified to accept OpenAI client instance
def generate_playbook(client: OpenAI, sections, screenshot_path=None, model="gpt-4o"):
    combined = "\n\n".join(sections)

    messages = [
        {
            "role": "system",
            "content": "You are a reliable form automation agent. Analyze the structure of job application pages and generate JSON actions using proper CSS selectors (NO :contains()). Avoid duplicate actions."
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Here is the form content:\n" + combined + "\n\nRespond with a JSON array of actions to fill the form and click next."}
            ]
        }
    ]

    if screenshot_path:
        try:
            with open(screenshot_path, "rb") as img_file:
                b64_image = base64.b64encode(img_file.read()).decode("utf-8")
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_image}"
                }
            })
        except FileNotFoundError:
            print(f"[Warning] Screenshot not found at {screenshot_path}. Proceeding without image.")
        except Exception as e:
            print(f"[Error] Could not process screenshot {screenshot_path}: {e}")

    try:
        # Use OpenAI API call structure
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"} # Request JSON object output
        )

        # Access content via .message.content
        content = response.choices[0].message.content
        print(f"Raw LLM output (generate_playbook): '{content}'") # Debug print
        plan = _parse_json(content) # Use the existing JSON parsing helper

    except Exception as e:
        print(f"[LLM ERROR in generate_playbook] {e}")
        plan = None # Ensure plan is None on error

    if plan and "actions" in plan:
        plan["actions"] = sanitize_actions(plan["actions"])
        print(f"[LLM] Plan sanitized to {len(plan['actions'])} actions.")
    elif plan is None:
         print("[LLM] generate_playbook failed, returning empty plan.")
         plan = {"actions": []} # Return empty plan on failure


    return plan

# These functions are no longer directly used by generate_playbook in the new structure
# def _build_full_prompt(sections):
#     return [
#         {
#             "role": "system",
#             "content": (
#                 "You are a reliable form automation agent. Analyze the structure of job application pages and "
#                 "generate JSON actions using proper CSS selectors (NO :contains()). Avoid duplicate actions."
#             )
#         },
#         {
#             "role": "user",
#             "content": (
#                 "Here is the form content:\n" + "\n\n".join(sections) +
#                 "\n\nRespond with a JSON array of actions to fill the form and click next."
#             )
#         }
#     ]

# def _build_section_prompt(section_text, index):
#     return _build_full_prompt([f"Section {index}:\n{section_text}"])

def _parse_json(text):
    if not text: # Handle None or empty string input
        return None
    try:
        # Attempt to find JSON object within the text
        # OpenAI with response_format="json_object" should return pure JSON,
        # but keeping the regex for robustness against unexpected formatting.
        match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
        if match:
            json_string = match.group()
            # Clean up potential markdown code block
            if json_string.strip().startswith("```json"):
                 json_string = json_string.strip()[len("```json"):].rstrip("```")
            return json.loads(json_string)
        else:
            print("[ParseError] No JSON object found in LLM output.")
            return None
    except json.JSONDecodeError as e:
        print(f"[ParseError] JSON decoding failed: {e}. Input text: {text[:200]}...") # Add input text snippet for debugging
        return None
    except Exception as e:
        # print(f"Faulty JSON string: {json_string}") # json_string might not be defined here if match is None
        print(f"[ParseError] An unexpected error occurred during JSON parsing: {e}")
        return None


# Modified to accept OpenAI client instance
def analyze_page_with_context(client: OpenAI, sections, model="gpt-4o"):
    if not isinstance(client, OpenAI):
        print(f"[LLM ERROR in analyze_page_with_context] Invalid client type: Expected OpenAI, got {type(client)}")
        return {"summary": "Internal error: Invalid LLM client.", "suggested_action": None}

    try:
        combined_sections = "\n\n".join(sections)
        messages = [
            {
                "role": "system",
                "content": "You are an automation agent reviewing a job application step."
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": """
🧾 You have the extracted sections of the current page.

Your tasks:
1. Describe in plain English what’s happening.
2. Say if resume or cover letter appears to be uploaded.
3. Suggest the next UI action (click, wait, upload).

Always respond with JSON like:
{
  "summary": "Resume uploaded. Waiting for Next.",
  "suggested_action": {
    "action": "click",
    "selector": "button[type='submit']",
    "field": "Next"
  }
}
""" + "\n\nPage Sections:\n" + combined_sections[:40000]} # Truncate combined sections if very long
                ]
            }
        ]

        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1000, # Use max_tokens for OpenAI
                response_format={"type": "json_object"} # Request JSON object output
            )

            content = response.choices[0].message.content # Access content via .message.content
            print(f"Raw LLM output (analyze_page_with_context): '{content}'") # Debug print
            # Use the existing JSON parsing helper
            parsed_response = _parse_json(content)

            if parsed_response:
                return parsed_response
            else:
                 print("[ParseError] JSON parsing failed for analyze_page_with_context output.")
                 # Fallback: return raw content in summary if JSON parsing fails
                 return {"summary": "LLM returned invalid output.", "suggested_action": None} # Return specific default error response

        except Exception as e:
            print(f"[LLM ERROR in analyze_page_with_context] {e}")
            return {"summary": f"Error from LLM: {e}", "suggested_action": None}

    except Exception as e:
        print(f"[LLM ERROR in analyze_page_with_context] {e}")
        return {"summary": f"Error from LLM: {e}", "suggested_action": None}
