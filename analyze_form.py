import os
import openai
from openai import OpenAI
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing
from html_processor import extract_form_sections # Import the new function

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API (ensure your API key is set as an environment variable)
# The API key is typically read from the OPENAI_API_KEY environment variable.
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def analyze_form_page(html_content: str, screenshot_path: str = None) -> dict:
    """
    Process HTML to extract form sections, send extracted information and screenshot
    to the LLM to analyze the page and identify interactive elements and actions.
    Returns a dictionary (playbook actions for this page) parsed from the LLM's JSON output.
    """
    # Prepare the prompt for the model
    system_message = (
        "You are a form-filling assistant. You will receive extracted text sections from a job application form page. "
        "Identify all interactive fields (text inputs, file uploads, dropdowns) and the action button (Next/Submit) on the page based on the provided information. "
        "Determine what input is required for each field (e.g., 'name', 'email', 'resume file', etc.). "
        "Then, output a JSON array of actions in order: each action should have 'action' (fill/click/upload), "
        "'selector' (a CSS or XPath selector for the element - infer based on the field description if not explicitly provided), 'field' (a description of the field or button), "
        "and 'value' if it's a fill action (use placeholders like [NAME], [EMAIL], [PHONE], [RESUME_PATH] for personal data inputs). "
        "Ensure the JSON is valid."
    )

    # Use html_processor to extract relevant sections
    extracted_sections = extract_form_sections(html_content)

    # Combine extracted sections into a single message for the LLM
    # Use a clear separator between sections
    user_message_parts = ["Extracted Form Sections:"]
    for i, section in enumerate(extracted_sections):
        user_message_parts.append(f"\n--- Section {i+1} ---\n{section}")

    user_message = "\n".join(user_message_parts)

    # If GPT-4 Vision is available and screenshot_path is provided, we could attach the image as well.
    # (Pseudo-code, actual attachment depends on OpenAI API support for image.)
    # if screenshot_path:
    #     user_message += f"\nScreenshot: (attached image from {screenshot_path})"


    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # Using a model that supports vision and larger context
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0,  # for deterministic output
        )
        output_text = response.choices[0].message.content
        print(f"Raw LLM output: '{output_text}'") # Print raw output for debugging
        # Extract JSON string from markdown code block if present
        if output_text.strip().startswith("```json"):
            json_string = output_text.strip()[len("```json"):].rstrip("```")
        else:
            json_string = output_text.strip()

        # The model is instructed to give JSON. We attempt to parse it:
        actions = json.loads(json_string)
        print("LLM analysis successful, received actions JSON.")
        return actions
    except json.JSONDecodeError as e:
        print(f"[Error] LLM output is not valid JSON: {e}")
        print(f"Faulty output: {output_text}")
        return {}
    except Exception as e:
        print(f"[Error] LLM analysis failed: {e}")
        return {}

# Example usage (if standalone test):
if __name__ == "__main__":
    # Read an HTML file (captured in previous step) and analyze it.
    # Use the actual path to the captured HTML
    sample_html_path = "screenshots/application_step1.html"
    # Assuming a screenshot is also available at this path
    sample_screenshot_path = "screenshots/application_step1.png"

    if os.path.exists(sample_html_path):
        with open(sample_html_path, "r", encoding="utf-8") as f:
            html_data = f.read()
        # Pass both html_data and sample_screenshot_path to the function
        actions = analyze_form_page(html_data, sample_screenshot_path)
        print("Actions JSON:", json.dumps(actions, indent=2))
    else:
        print(f"Sample HTML not found at {sample_html_path}. Please ensure the file exists.")