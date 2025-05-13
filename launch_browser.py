import os
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException # Import NoSuchElementException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from page_capture import save_page_snapshot
from analyze_form import analyze_form_page
from playbook_manager import load_playbook, save_playbook
from playbook_executor import execute_playbook_actions
import html_processor
# Removed import for get_smart_step_summary
import re # Import re for sanitize_actions

RESUME_PATH = os.path.abspath("./resume.pdf")
COVER_LETTER_PATH = os.path.abspath("./cover_letter.pdf")

# Keep the sanitize_actions function
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

# Keep the wait_for_upload_completion function
def wait_for_upload_completion(driver, keyword="uploaded", timeout=15):
    try:
        WebDriverWait(driver, timeout).until(lambda d: keyword in d.page_source.lower())
        print("Upload completion detected.")
        return True
    except TimeoutException:
        print("Upload completion NOT detected within timeout.")
        return False

def main():
    profile_path = "/Users/umairsaeed/Library/Application Support/Firefox/Profiles/4219wmga.default-release"

    options = FirefoxOptions()
    options.set_preference("dom.webnotifications.enabled", False)
    options.add_argument("--width=1280")
    options.add_argument("--height=900")
    options.profile = profile_path

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

        visited_states = set()
        executed_action_keys = set()
        domain_safe = None
        max_steps = 10

        while step_counter < max_steps:
            current_url = driver.current_url
            domain = urlparse(current_url).netloc
            print(f"\n--- Processing Step {step_counter + 1} ---")
            print(f"Current URL: {current_url}")

            state_signature = hash(current_url + "_" + str(len(driver.page_source)))
            if state_signature in visited_states:
                print("Detected a repeating page state (possible loop). Ending automation.")
                break
            visited_states.add(state_signature)

            html_file_path, screenshot_path = save_page_snapshot(driver, job_id, job_title, f"step_{step_counter + 1}")

            if not os.path.exists(html_file_path):
                print(f"[Error] HTML snapshot not found: {html_file_path}")
                break

            with open(html_file_path, "r", encoding="utf-8") as f:
                current_html = f.read()

            # Removed call to get_smart_step_summary

            form_sections = html_processor.extract_form_sections(current_html)
            if not form_sections:
                print("No form sections found. Assuming application complete or next step pending.")
                break

            print(f"Found {len(form_sections)} form sections on the page.")
            playbook = load_playbook(domain)

            actions_to_execute = []
            if playbook and 'actions' in playbook:
                print(f"Loaded existing playbook for {domain}.")
                for action in playbook['actions']:
                    key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}"
                    if key not in executed_action_keys:
                        actions_to_execute.append(action)
            else:
                playbook = {"actions": []}

            if not actions_to_execute or form_sections:
                print("Generating actions with LLM...")
                try:
                    truncated_html = current_html[:400000] # Truncate HTML for LLM
                    raw_new_actions = analyze_form_page(truncated_html, screenshot_path) # Get raw actions

                    if raw_new_actions:
                        print(f"LLM generated {len(raw_new_actions)} raw new actions.")
                        # Sanitize the raw actions
                        sanitized_new_actions = sanitize_actions(raw_new_actions)
                        print(f"Sanitized to {len(sanitized_new_actions)} valid actions.")

                        # Append sanitized actions to playbook and actions_to_execute
                        for action in sanitized_new_actions:
                            key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}"
                            if key not in executed_action_keys:
                                playbook['actions'].append(action)
                                actions_to_execute.append(action)

                        save_playbook(domain, playbook)
                        print("Appended new actions to playbook and saved.")
                    else:
                        print("[Error] LLM failed to generate new actions. Cannot proceed.")
                        break
                except Exception as e:
                    print(f"[Error] Failed to generate new actions via LLM: {e}")
                    break

            if actions_to_execute:
                print(f"Executing {len(actions_to_execute)} actions...")
                # Execute actions one by one to allow post-action review in executor
                for idx, action in enumerate(actions_to_execute):
                    action_key = f"{action.get('action')}|{action.get('selector')}|{action.get('value')}"
                    if action_key in executed_action_keys:
                        continue # Skip if already executed

                    try:
                        print(f"Executing action {idx+1}: {action.get('action')} - {action.get('field')}")
                        # Pass only the current action to the executor
                        single_action_success = execute_playbook_actions(driver, [action], RESUME_PATH, COVER_LETTER_PATH)
                        if not single_action_success:
                            print(f"[Error] Failed to execute action {action}")
                            # Decide how to handle single action failure - break or continue?
                            # For now, break the loop on failure
                            break # Exit the actions execution loop
                        executed_action_keys.add(action_key) # Mark as executed after successful execution

                        # Add specific wait after upload
                        if action.get("action") == "upload":
                            wait_for_upload_completion(driver)

                    except WebDriverException as ex:
                        print(f"[Error] Unexpected error during action '{action.get('field')}': {ex}")
                        # Decide how to handle unexpected WebDriver errors - break or continue?
                        # For now, break the loop on error
                        break # Exit the actions execution loop

                # Check if the actions execution loop was broken due to failure
                # If single_action_success is False, it means the inner loop broke
                if 'single_action_success' in locals() and not single_action_success:
                    break # Exit the main application loop if an action failed


            else:
                print("No actions to execute in this step.")

            # Note: The post-action snapshot and form section check logic is now primarily
            # handled within the execute_playbook_actions function for each individual action.
            # The loop will continue to the next step if execute_playbook_actions returns True.


            # After executing actions (or if no actions), wait briefly before next step check
            time.sleep(2)

            # Check if the page has changed or updated significantly before the next step
            # This is a simple check; more sophisticated checks might be needed for complex SPAs
            # This check is now less critical as form_sections check is done after each action in executor
            # but keeping it as a fallback.
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
            html_after_actions = driver.page_source.lower() # Need to get current page source again
            if step_counter > 4 and html_after_actions.count("resume") > 3 and html_after_actions.count("cover letter") > 3:
                print("⚠️ Repeated upload step detected multiple times. Assuming the form is stuck. Ending.")
                break
            # End Smart Loop Exit


            # Increment step counter
            step_counter += 1

        # Check if the loop exited due to max steps limit
        if step_counter >= max_steps:
            print(f"Maximum number of steps ({max_steps}) reached. Ending automation.")


    except Exception as e:
        print(f"[Error] An unexpected exception occurred during the application process: {e}")

    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()