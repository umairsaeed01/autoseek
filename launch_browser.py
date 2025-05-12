import os
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from page_capture import save_page_snapshot
from analyze_form import analyze_form_page
import html_processor

from playbook_manager import load_playbook, save_playbook
from playbook_executor import execute_playbook_actions

import re # Import re for sanitize_actions

def sanitize_actions(actions):
    valid_actions = []
    for action in actions:
        selector = action.get("selector", "")
        if ":contains(" in selector:
            # Convert to XPath if we detect :contains
            text_match = re.findall(r":contains\(['\"]?(.*?)['\"]?\)", selector)
            if text_match:
                text = text_match[0]
                # Simple XPath fallback assuming it's a button
                action["selector"] = f"//button[contains(text(), '{text}')]"
                action["use_xpath"] = True
            else:
                print(f"Warning: Skipping malformed selector with :contains(): {selector}")
                continue  # skip malformed
        else:
            action["use_xpath"] = False
        valid_actions.append(action)
    return valid_actions

RESUME_PATH = os.path.abspath("./resume.pdf")
COVER_LETTER_PATH = os.path.abspath("./cover_letter.pdf")

def main():
    profile_path = "/Users/umairsaeed/Library/Application Support/Firefox/Profiles/4219wmga.default-release"

    options = FirefoxOptions()
    options.set_preference("dom.webnotifications.enabled", False)
    options.add_argument("--width=1280")
    options.add_argument("--height=900")
    options.profile = profile_path  # Proper way to use existing Firefox profile

    print("Initializing Firefox Service...")
    service = FirefoxService()
    print("Firefox Service initialized.")

    print("Launching Firefox with personal profile...")
    driver = webdriver.Firefox(service=service, options=options)
    print("Firefox WebDriver initialized successfully.")

    driver.implicitly_wait(10)
    job_id = "seek_application"
    job_title = "N-A"
    step_counter = 0

    try:
        job_url = "https://www.seek.com.au/job/83589298"
        print(f"Opening job page: {job_url}")
        driver.get(job_url)

        print("Waiting for Apply button...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Apply') or contains(., 'apply')]"))
        )
        step_counter += 1

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        job_title_element = soup.select_one('h1')
        job_title = job_title_element.get_text(strip=True) if job_title_element else 'N-A'

        save_page_snapshot(driver, job_id, job_title, f"nav_{step_counter}")

        apply_button = driver.find_element(By.XPATH, "//a[contains(., 'Apply') or contains(., 'apply')]")
        print("Clicking Apply...")
        apply_button.click()
        time.sleep(5)
        step_counter += 1

        # Start the application process loop
        visited_states = set()
        executed_action_keys = set() # Track executed actions
        domain_safe = None
        max_steps = 10 # Limit the total number of steps to prevent infinite loops

        while step_counter < max_steps:
            current_url = driver.current_url
            domain = urlparse(current_url).netloc
            print(f"\n--- Processing Step {step_counter + 1} ---")
            print(f"Current URL: {current_url}")
            print(f"Current domain: {domain}")

            # Prevent infinite loops by tracking page states (using URL and content length hash)
            state_signature = hash(current_url + "_" + str(len(driver.page_source)))
            if state_signature in visited_states:
                print("Detected a repeating page state (possible loop). Ending automation.")
                break
            visited_states.add(state_signature)

            # Capture the current page state
            html_file_path, screenshot_path = save_page_snapshot(driver, job_id, job_title, f"step_{step_counter + 1}")

            # Read current HTML for analysis and completion check
            current_html = ""
            if os.path.exists(html_file_path):
                with open(html_file_path, "r", encoding="utf-8") as f:
                    current_html = f.read()
            else:
                print(f"[Error] Captured HTML file not found: {html_file_path}. Cannot proceed.")
                break

            # Check for form completion
            form_sections = html_processor.extract_form_sections(current_html)
            if not form_sections:
                print("No more form fields detected. Assuming application completed.")
                # Optional: Add a final check for submission confirmation text here if desired
                if "application submitted" in current_html.lower():
                     print("Submission confirmation text also found.")
                break # Exit the loop if no form sections are found

            print(f"Found {len(form_sections)} form sections on the page.")

            # Attempt to load existing playbook
            playbook = load_playbook(domain)

            actions_to_execute = []
            if playbook and 'actions' in playbook:
                print(f"Loaded existing playbook for {domain}.")
                # Filter out already executed actions
                for action in playbook['actions']:
                    action_key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}" # Create a unique key for the action
                    if action_key not in executed_action_keys:
                        actions_to_execute.append(action)
            else:
                print(f"No existing playbook found for {domain} or playbook is empty.")
                playbook = {"actions": []} # Initialize an empty playbook if none loaded

            # If there are no pending actions in the loaded playbook or if form sections still exist, trigger LLM
            # Only generate new actions if there are form sections remaining AND either no actions were loaded
            # or the loaded actions didn't resolve the form sections.
            if form_sections and (not actions_to_execute or len(form_sections) > 0): # Refined condition
                 print("Generating new actions via LLM...")
                 truncated_html = current_html[:400000] # Truncate HTML for LLM
                 raw_new_actions = analyze_form_page(truncated_html, screenshot_path)

                 if raw_new_actions:
                     print(f"LLM generated {len(raw_new_actions)} raw new actions.")
                     # Sanitize and filter new actions
                     sanitized_new_actions = sanitize_actions(raw_new_actions)
                     print(f"Sanitized to {len(sanitized_new_actions)} valid actions.")

                     # Append new actions to the playbook and save, deduplicating against executed actions
                     for action in sanitized_new_actions:
                         action_key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}"
                         if action_key not in executed_action_keys:
                             playbook['actions'].append(action) # Add to playbook for saving
                             actions_to_execute.append(action) # Add to list for current execution
                     save_playbook(domain, playbook)
                     print("Appended new actions to playbook and saved.")
                 else:
                     print("[Error] LLM failed to generate new actions. Cannot proceed.")
                     break # Exit loop if LLM fails

            if actions_to_execute:
                print(f"Executing {len(actions_to_execute)} actions...")
                success = execute_playbook_actions(driver, actions_to_execute, RESUME_PATH, COVER_LETTER_PATH)
                if not success:
                    print(f"[Error] Playbook execution failed for {domain}. Stopping automation.")
                    break # Stop the loop on failure
                else:
                    print("Finished executing actions.")
                    # Mark executed actions
                    for action in actions_to_execute:
                         action_key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}"
                         executed_action_keys.add(action_key)
            else:
                print("No actions to execute in this step.")


            # After executing actions, wait briefly for the page to react
            time.sleep(2) # Short pause

            # Add Smart Page Navigation Detection (Right After Upload)
            html_after_actions = driver.page_source.lower()

            # Add a final check for application submission success
            if "application has been submitted" in html_after_actions or "thanks for applying" in html_after_actions:
                print("🎉 Detected successful job application submission. Ending automation.")
                break

            if (
                "resume" in html_after_actions
                and "cover letter" in html_after_actions
                and any(x in html_after_actions for x in ["upload", "attach"])
                and "application submitted" not in html_after_actions # Ensure we haven't already detected submission
            ):
                print("It looks like the application form did not advance. Checking for final action buttons...")

                # Look for buttons that may indicate progression
                possible_buttons = driver.find_elements(By.TAG_NAME, "button")
                for button in possible_buttons:
                    try:
                        text = button.text.lower().strip()
                        if text in ["next", "continue", "submit application", "submit", "apply now", "send"]:
                            print(f"💡 Found possible navigation button: '{text}' — trying to click it")
                            driver.execute_script("arguments[0].scrollIntoView(true);", button)
                            time.sleep(1)
                            button.click()
                            time.sleep(3)
                            break # Exit the button loop after clicking one
                    except Exception as e:
                        print(f"⚠️ Could not click navigation button: {e}")
            # End Smart Page Navigation Detection

            # Check if the page has changed or updated significantly after actions
            # This is a simple check; more sophisticated checks might be needed for complex SPAs
            new_url = driver.current_url
            new_html_len = len(driver.page_source)
            if new_url == current_url and new_html_len == len(current_html):
                 print("Warning: Page content did not change after executing actions.")
                 # Decide how to handle this - maybe break or try LLM again?
                 # For now, we rely on the form_sections check at the start of the next loop iteration.
            else:
                 print("Page content updated.")

            # Add a Smart Loop Exit (Fail-Safe)
            # Check for too many identical file upload steps
            if step_counter > 4 and html_after_actions.count("resume") > 3 and html_after_actions.count("cover letter") > 3:
                print("⚠️ Repeated upload step detected multiple times. Assuming the form is stuck. Ending.")
                break
            # End Smart Loop Exit

            # Prevent infinite loops by tracking page states (using URL and content length hash)
            state_signature = hash(driver.current_url + "_" + str(len(driver.page_source)))
            if state_signature in visited_states:
                print("Detected a repeating page state (possible loop). Ending automation.")
                break
            visited_states.add(state_signature)

            # Increment step counter
            step_counter += 1

        # Check if the loop exited due to max steps limit
        if step_counter >= max_steps:
            print(f"Maximum number of steps ({max_steps}) reached. Ending automation.")


    except Exception as e:
        print(f"[Error] An unexpected exception occurred during the application process: {e}")

    finally:
        # Optional: Keep the browser open for inspection after completion or error
        # input("Press Enter to close the browser...")
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()