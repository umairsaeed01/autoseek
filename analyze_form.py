import os
import json
from dotenv import load_dotenv
from bs4 import BeautifulSoup # Import BeautifulSoup for HTML parsing
from html_processor import extract_form_sections # Import the new function
from llm_agent import generate_playbook # Import the LLM agent function
from playbook_manager import load_playbook, save_playbook # Import playbook manager functions
from urllib.parse import urlparse # Import urlparse to extract domain

# Load environment variables from .env file
load_dotenv()

# Check if the API key was loaded - This is now handled in llm_agent.py

# Configure OpenAI API (ensure your API key is set as an environment variable)
# The API key is typically read from the OPENAI_API_KEY environment variable.
import openai
from openai import OpenAI

# Initialize the OpenAI client
# The client will automatically look for the OPENAI_API_KEY environment variable
client = OpenAI()

from llm_agent import generate_playbook # Ensure generate_playbook is imported

def analyze_form_page(html_content: str, screenshot_path: str = None) -> dict:
    """
    Process HTML to extract form sections, send extracted information and screenshot
    to the LLM to analyze the page and identify interactive elements and actions.
    Returns a dictionary (playbook actions for this page) parsed from the LLM's JSON output.
    """
    # The core LLM interaction logic is now handled within llm_agent.py's generate_playbook function.
    # We will call that function directly.

    # Use html_processor to extract relevant sections
    extracted_sections = extract_form_sections(html_content)

    # Generate playbook using llm_agent
    # Pass extracted sections and potentially screenshot path to the LLM agent
    # The llm_agent will handle the API interaction and JSON parsing
    # Pass the OpenAI client instance to the LLM agent functions
    playbook_actions = generate_playbook(client, extracted_sections, screenshot_path=screenshot_path)

    if playbook_actions:
        print("LLM analysis successful, received actions JSON.")
        return playbook_actions
    else:
        print("[Error] LLM analysis failed or returned empty.")
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
            # Pass the OpenAI client instance to the LLM agent function
            playbook = generate_playbook(client, extracted_sections)

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