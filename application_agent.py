import os
import time
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from urllib.parse import urlparse

from page_capture import save_page_snapshot
from html_processor import extract_form_sections
from llm_agent import generate_playbook
from playbook_manager import load_playbook, save_playbook

class ApplicationAgent:
    def __init__(self, driver: WebDriver, job_id: str, job_title: str, resume_path: str, cover_letter_path: str):
        self.driver = driver
        self.job_id = job_id
        self.job_title = job_title
        self.resume_path = resume_path
        self.cover_letter_path = cover_letter_path
        self.step_counter = 0

    def run_application(self, start_url: str):
        print(f"Starting application process for job: {self.job_title} ({self.job_id})")
        self.driver.get(start_url)
        time.sleep(5) # Initial wait

        # Initial capture after navigating to the job page
        self.step_counter += 1
        self._capture_page(f"nav_{self.step_counter}")

        # Assuming the first action is to click 'Apply' or similar to get to the form
        # This part might need to be handled outside the main loop if it's a fixed first step
        # For now, let's assume the loop starts on the first form page.
        # We'll need to adjust launch_browser.py to click 'Apply' before calling run_application.

        application_complete = False
        while not application_complete:
            current_url = self.driver.current_url
            domain = urlparse(current_url).netloc
            print(f"Processing step {self.step_counter} on domain: {domain}")

            # Capture current page state
            html_file_path, screenshot_path = self._capture_page(f"step_{self.step_counter}")

            if not os.path.exists(html_file_path):
                print(f"[Error] Captured HTML file not found: {html_file_path}. Exiting application process.")
                application_complete = True
                continue

            with open(html_file_path, "r", encoding="utf-8") as f:
                captured_html = f.read()

            # Process HTML to find form sections
            form_sections = extract_form_sections(captured_html)

            if not form_sections:
                print("No more form sections found on this page. Application likely complete.")
                application_complete = True
                continue

            # Attempt to load existing playbook
            playbook = load_playbook(domain)

            if playbook is None:
                print(f"No playbook found for {domain}. Generating new playbook...")
                # Analyze the captured HTML using the LLM to generate playbook
                print(f"Analyzing captured HTML from: {html_file_path}")
                # Truncate HTML content to avoid exceeding token limits if necessary
                max_html_length = 400000
                truncated_html = captured_html[:max_html_length]
                playbook = generate_playbook(truncated_html, screenshot_path)

                if playbook:
                    # Save the generated playbook
                    save_playbook(domain, playbook)
                    print("Generated and saved new playbook.")
                else:
                    print("[Warning] LLM did not generate a valid playbook.")
                    # Decide how to handle this - maybe try again or exit?
                    application_complete = True # Exit if no playbook generated
                    continue


            if playbook and 'actions' in playbook:
                print(f"Executing playbook actions for {domain}...")
                if not self._execute_playbook_actions(playbook['actions']):
                     print("[Error] Failed to execute all playbook actions. Exiting.")
                     application_complete = True # Exit on action execution failure
                     continue
                print("Finished executing playbook actions.")
            else:
                 print("[Warning] Playbook is empty or missing 'actions'. Cannot proceed.")
                 application_complete = True # Exit if playbook is invalid

            # After executing actions, wait for the next page to load
            time.sleep(5)
            self.step_counter += 1 # Increment step counter for the *next* page capture

        print("Application process finished.")


    def _capture_page(self, step_name: str):
        """Captures the current page HTML and screenshot."""
        print(f"Capturing page state for step: {step_name}")
        html_path, screenshot_path = save_page_snapshot(self.driver, self.job_id, self.job_title, step_name)
        print(f"Saved page snapshot: HTML -> {html_path}, Screenshot -> {screenshot_path}")
        return html_path, screenshot_path

    def _execute_playbook_actions(self, actions: list):
        """Executes a list of actions using Selenium."""
        success = True
        for action in actions:
            try:
                selector = action.get('target') or action.get('selector') # Allow 'target' or 'selector'
                action_type = action.get('action')
                value = action.get('value')
                description = action.get('description', 'No description')

                print(f"Executing action: {action_type} on {selector} ({description})")

                if not selector:
                    print(f"[Warning] Action skipped due to missing selector: {action}")
                    success = False # Mark as failure but continue
                    continue

                # Use WebDriverWait for robustness
                wait = WebDriverWait(self.driver, 10)
                element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))

                if action_type == 'click':
                    element.click()
                elif action_type == 'type':
                    if value is not None:
                        element.send_keys(value)
                elif action_type == 'upload':
                    if value == '[RESUME_PATH]':
                        upload_path = self.resume_path
                    elif value == '[COVER_LETTER_PATH]':
                        upload_path = self.cover_letter_path
                    else:
                        print(f"[Warning] Unknown upload value placeholder: {value}. Skipping upload.")
                        success = False # Mark as failure but continue
                        continue
                    print(f"Uploading file: {upload_path}")
                    element.send_keys(upload_path)
                # Add other action types as needed (e.g., select dropdown)
                else:
                    print(f"[Warning] Unknown action type: {action_type}. Skipping action.")
                    success = False # Mark as failure but continue

                time.sleep(1) # Short pause after each action

            except Exception as action_e:
                print(f"[Error] Failed to execute action {action}: {action_e}")
                success = False # Mark as failure but continue with next action
                # Optionally, break here if any action failure should stop the process:
                # break

        return success # Return overall success status

# Example Usage (will be called from launch_browser.py)
# if __name__ == "__main__":
#     # This part would be in launch_browser.py
#     from selenium import webdriver
#     from selenium.webdriver.chrome.service import Service
#     from webdriver_manager.chrome import ChromeDriverManager
#     import os
#
#     # Define absolute paths for resume and cover letter
#     RESUME_PATH = os.path.abspath("./resume.pdf")
#     COVER_LETTER_PATH = os.path.abspath("./cover_letter.pdf")
#
#     service = Service(ChromeDriverManager().install())
#     driver = webdriver.Chrome(service=service)
#
#     job_id = "test_job_123"
#     job_title = "Test Engineer"
#     start_url = "http://example.com/job/apply" # Replace with actual URL
#
#     agent = ApplicationAgent(driver, job_id, job_title, RESUME_PATH, COVER_LETTER_PATH)
#
#     try:
#         agent.run_application(start_url)
#     except Exception as e:
#         print(f"An error occurred during the application process: {e}")
#     finally:
#         driver.quit()