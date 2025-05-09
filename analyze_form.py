import os
import openai
from openai import OpenAI
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing
from html_processor import extract_form_sections # Import the new function
from llm_agent import generate_playbook # Import the LLM agent function
from playbook_manager import load_playbook, save_playbook # Import playbook manager functions
from urllib.parse import urlparse # Import urlparse to extract domain

# Load environment variables from .env file
load_dotenv()

# Check if the API key was loaded
openai_api_key = os.getenv("OPENAI_API_KEY")
if not openai_api_key:
    print("[ERROR] OPENAI_API_KEY environment variable not found after loading .env")
    # Depending on desired behavior, you might exit or raise an error here.
    # For now, we'll proceed, but the OpenAI client initialization will likely fail.

# Configure OpenAI API (ensure your API key is set as an environment variable)
# The API key is typically read from the OPENAI_API_KEY environment variable.
client = OpenAI(api_key=openai_api_key)

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
    # Example usage demonstrating playbook caching
    # In a real application, you would get the URL and HTML from the browser automation step

    # Define a sample URL and HTML path for demonstration
    sample_url = "https://www.example.com/job/application"
    sample_html_path = "screenshots/application_step1.html" # Use an existing sample HTML

    # Extract domain from the sample URL
    domain = urlparse(sample_url).netloc
    print(f"Processing form for domain: {domain}")

    # Attempt to load playbook from cache
    playbook = load_playbook(domain)

    if playbook is None:
        print("No cached playbook found. Generating new playbook...")
        # Read the sample HTML content
        if os.path.exists(sample_html_path):
            with open(sample_html_path, "r", encoding="utf-8") as f:
                html_data = f.read()

            # Extract form sections using html_processor
            extracted_sections = extract_form_sections(html_data)

            # Generate playbook using llm_agent
            # Note: analyze_form_page function is not used directly here as we are
            # demonstrating the caching logic that would wrap it.
            playbook = generate_playbook(extracted_sections)

            # Save the generated playbook to cache
            if playbook: # Only save if playbook generation was successful
                save_playbook(domain, playbook)
        else:
            print(f"Sample HTML not found at {sample_html_path}. Cannot generate playbook.")
            playbook = None # Ensure playbook is None if HTML not found
    else:
        print("Using cached playbook.")

    # Print the resulting playbook
    if playbook:
        print("\nFinal Playbook:")
        print(json.dumps(playbook, indent=2))
    else:
        print("\nFailed to obtain a playbook.")