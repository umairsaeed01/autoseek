import os
import json
import base64
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

MODEL_NAME = "gpt-4o"
MAX_CHARS_SINGLE = 15000

def sanitize_actions(actions):
    valid = []
    for a in actions:
        if ":contains" in a.get("selector", ""):
            print(f"[Sanitizer] Skipping invalid selector: {a['selector']}")
            continue
        valid.append(a)
    return valid

def generate_playbook(sections, model=MODEL_NAME):
    combined = "\n\n".join(sections)
    if len(combined) <= MAX_CHARS_SINGLE:
        prompt = _build_full_prompt(sections)
        response = client.chat.completions.create(
            model=model,
            messages=prompt,
            temperature=0
        )
        content = response.choices[0].message.content
        plan = _parse_json(content)
    else:
        plan = {"actions": []}
        for idx, section in enumerate(sections):
            prompt = _build_section_prompt(section, idx + 1)
            response = client.chat.completions.create(
                model=model,
                messages=prompt,
                temperature=0
            )
            content = response.choices[0].message.content
            part = _parse_json(content)
            if part:
                plan["actions"].extend(part if isinstance(part, list) else part.get("actions", []))
    if "actions" in plan:
        plan["actions"] = sanitize_actions(plan["actions"])
        print(f"[LLM] Plan sanitized to {len(plan['actions'])} actions.")
    return plan

def _build_full_prompt(sections):
    return [
        {
            "role": "system",
            "content": (
                "You are a reliable form automation agent. Analyze the structure of job application pages and "
                "generate JSON actions using proper CSS selectors (NO :contains()). Avoid duplicate actions."
            )
        },
        {
            "role": "user",
            "content": (
                "Here is the form content:\n" + "\n\n".join(sections) +
                "\n\nRespond with a JSON array of actions to fill the form and click next."
            )
        }
    ]

def _build_section_prompt(section_text, index):
    return _build_full_prompt([f"Section {index}:\n{section_text}"])

def _parse_json(text):
    try:
        match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
        return json.loads(match.group()) if match else None
    except Exception as e:
        print(f"[ParseError] {e}")
        return None

def analyze_page_with_context(html, screenshot_path, previous_action=None):
    try:
        with open(screenshot_path, "rb") as img_file:
            b64_image = base64.b64encode(img_file.read()).decode("utf-8")

        base_prompt = """
You are an automation agent reviewing a job application step.

🧾 You have the HTML of the current page and a screenshot.

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
"""

        messages = [
            {"role": "system", "content": "You are a smart form-filling automation agent."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": base_prompt + "\n\nHTML Snapshot:\n" + html[:14000]},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}}
                ]
            }
        ]

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=1000
        )

        content = response.choices[0].message.content
        match = re.search(r"\{.*\}", content.strip(), re.DOTALL)
        return json.loads(match.group()) if match else {"summary": content, "suggested_action": None}

    except Exception as e:
        print(f"[LLM ERROR] {e}")
        return {"summary": f"Error from LLM: {e}", "suggested_action": None}
