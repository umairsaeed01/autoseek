# llm_agent.py
import json
import openai
import os # Import os to access environment variables
from openai import OpenAI # Import OpenAI class
from dotenv import load_dotenv # Import load_dotenv

# Load environment variables from .env file
load_dotenv()

# You should set your OpenAI API key in an environment variable or elsewhere before calling this.
# e.g., openai.api_key = "sk-...yourkey..."

# Configure OpenAI API (ensure your API key is set as an environment variable)
# The API key is typically read from the OPENAI_API_KEY environment variable.
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("[ERROR] OPENAI_API_KEY environment variable not found.")

client = OpenAI(api_key=openai_api_key)


MODEL_NAME = "gpt-4o"        # default LLM model, using gpt-4o as it supports vision and larger context
MAX_CHARS_SINGLE = 15000    # character threshold for single prompt (approx tokens for GPT-4 8k)

def generate_playbook(form_sections, model=MODEL_NAME):
    """
    Analyze the form sections using an LLM and generate a playbook (list of actions).
    If the form is too large, it will process in chunks and merge results.
    Returns a Python object (dict or list) representing the JSON playbook.
    """
    # Combine all sections text to assess length
    combined_text = "\n\n".join(form_sections)
    if len(combined_text) <= MAX_CHARS_SINGLE:
        # Send one prompt with all sections
        prompt_content = _build_full_prompt(form_sections)
        print(f"[LLM] Sending full form to LLM (length {len(combined_text)} chars)...")
        response = client.chat.completions.create(
            model=model,
            messages=prompt_content,
            temperature=0  # for deterministic output
        )
        reply = response.choices[0].message.content # Access content using dot notation
        plan = _parse_json(reply)
    else:
        # Content too large, handle chunk by chunk
        print(f"[LLM] Form is large (length {len(combined_text)} chars). Splitting into sections.")
        partial_plans = []
        for idx, section_text in enumerate(form_sections, start=1):
            print(f"[LLM] Processing section {idx}/{len(form_sections)} with LLM...")
            prompt_content = _build_section_prompt(section_text, idx)
            response = client.chat.completions.create(
                model=model,
                messages=prompt_content,
                temperature=0
            )
            reply = response.choices[0].message.content # Access content using dot notation
            # Parse each section's plan (expected to be a JSON array or object)
            part_plan = _parse_json(reply)
            if part_plan:
                # If the response is a list of actions, extend; if it's an object with 'actions', extend that.
                if isinstance(part_plan, list):
                    partial_plans.extend(part_plan)
                elif isinstance(part_plan, dict) and 'actions' in part_plan:
                    partial_plans.extend(part_plan['actions'])
                else:
                    # If it's neither a list nor an object with 'actions', append the whole thing
                    partial_plans.append(part_plan)
        # Combine partial plans into one final list of actions
        # Assuming the final playbook should be a dict with an 'actions' key
        plan = {"actions": partial_plans}
    print("[LLM] Playbook generation complete.")
    return plan

def _build_full_prompt(sections):
    """Construct the prompt messages for the full form analysis."""
    # We use chat format: a system message + one user message.
    system_msg = {
        "role": "system",
        "content": (
            "You are a job application assistant AI. You will receive sections of an online job application form. "
            "Your task is to provide a JSON-formatted plan (a playbook) of actions to fill out the form. "
            "The JSON should contain a list of actions (clicks, text inputs, file uploads, etc.) needed to complete the form."
        )
    }
    # Combine all sections into a single user prompt
    form_description = "\n\n".join(sections)
    user_msg = {
        "role": "user",
        "content": (
            f"Here is the form content divided into sections:\n{form_description}\n\n"
            "Based on this, produce a JSON object called 'actions' that details how to fill out this form step by step. "
            "Include actions like selecting options, uploading files, entering text, and clicking buttons. "
            "Use identifiers (like field names or ids) from the form for each action. Respond ONLY with JSON."
        )
    }
    return [system_msg, user_msg]

def _build_section_prompt(section_text, section_index):
    """Construct the prompt messages for a single section of the form."""
    system_msg = {
        "role": "system",
        "content": (
            "You are a job application assistant AI. You will receive a part of a job application form and provide a plan in JSON."
        )
    }
    user_msg = {
        "role": "user",
        "content": (
            f"Section {section_index} of the form:\n{section_text}\n\n"
            "Provide the JSON actions (as an array) for just this section of the form. Respond with a JSON array of actions."
        )
    }
    return [system_msg, user_msg]

def _parse_json(response_text):
    """Parse the JSON from the model's response safely. Returns a Python object or None if failed."""
    try:
        # The model might include text before/after JSON, attempt to isolate JSON:
        content = response_text.strip()
        # Find first brace in the text
        start_idx = content.find('{')
        start_idx_list = content.find('[')
        if start_idx_list != -1 and (start_idx_list < start_idx or start_idx == -1):
            start_idx = start_idx_list
        if start_idx != -1:
            content = content[start_idx:]
        # Now content should start with { or [ if it's valid JSON
        plan = json.loads(content)
        return plan
    except Exception as e:
        print(f"[Error] Failed to parse JSON from LLM response: {e}")
        print("Response was:", response_text)
        return None

# Example usage (if standalone test):
if __name__ == "__main__":
    # This is a placeholder example. In a real scenario, you would get form_sections
    # from html_processor.extract_form_sections.
    sample_sections = [
        "Resumé:\nUpload a resumé\n[INPUT: type=radio, name=resume-method] Upload a file\n[INPUT: type=file, name=resume-file, file upload] Accepted file types: .doc, .docx, .pdf, .txt and .rtf (5MB limit).\n[INPUT: type=radio, name=resume-method] Use existing resumé\n[SELECT, name=resume-select, options=Please select a resumé, Resume1.pdf, Resume2.docx, ... (+5 more options)]\n[INPUT: type=radio, name=resume-method] Don't include a resumé\n",
        "Cover letter:\nUpload a cover letter\n[INPUT: type=radio, name=coverLetter-method] Yes, upload file\n[INPUT: type=file, name=coverLetter-file, file upload]\n[INPUT: type=radio, name=coverLetter-method] Don't include a cover letter\n"
    ]

    print("Generating playbook for sample sections...")
    playbook = generate_playbook(sample_sections)
    print("\nGenerated Playbook:")
    print(json.dumps(playbook, indent=2))