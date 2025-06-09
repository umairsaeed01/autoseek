import os
import time
import json
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from page_capture import save_page_snapshot
from analyze_form import analyze_form_page
from playbook_manager import load_playbook, save_playbook
from playbook_executor import execute_playbook_actions
from llm_agent import analyze_page_with_context, generate_playbook
from openai import OpenAI
from html_processor import extract_form_sections
from dynamic_handler import handle_dynamic_questions

RESUME_PATH = os.path.abspath("./resume.pdf")
COVER_LETTER_PATH = os.path.abspath("./cover_letter.pdf")

def debug_print(message, level="INFO"):
    """Helper function for consistent debug output"""
    print(f"[{level}] {message}")

def dispatch_special_pages(driver):
    """
    After any Continue click, check if we're on a "special" page:
      • /apply/role-requirements  → call role_requirements_handler
      • /apply/profile            → call profile_handler
      • /apply/review             → call review_handler
    Returns True if we dispatched (so the main loop should break/stop).
    """
    time.sleep(0.5)  # allow URL to settle
    url = driver.current_url

    # 1) Role Requirements page
    if "/apply/role-requirements" in url:
        print("[Dispatcher] Detected role-requirements page, dispatching to handler")
        if not handle_dynamic_questions(driver):
            raise RuntimeError("Dynamic handler failed to fill the form.")
        return True

    # 2) Profile page
    if "/apply/profile" in url:
        print("[Dispatcher] Detected profile page, dispatching to handler")
        from profile_handler import handle_profile_page
        if handle_profile_page(driver):
            print("[Dispatcher] Profile page handled successfully")
            return True
        else:
            print("[Dispatcher] Profile page handling failed")
            return False

    # 3) Review page
    if "/apply/review" in url:
        print("[Dispatcher] Detected review page, dispatching to handler")
        from review_handler import handle_review_page
        if handle_review_page(driver):
            print("[Dispatcher] Review page handled successfully")
            return True
        else:
            print("[Dispatcher] Review page handling failed")
            return False

    return False

def try_click_continue(driver):
    """Try to click the continue button using multiple selectors"""
    selectors = [
        "button[data-testid='continue-button']",
        "#app > div > div.azpfys0._1fz17ik9j > div.azpfys0._1fz17ikb7._1fz17ikaw._1fz17ika3._1fz17ik9s._1fz17ikp > div > div.azpfys0._1fz17ikcr._1fz17ikt > div.azpfys0._1fz17ik5b._1fz17ikhf._1fz17ik77 > div.azpfys0._1fz17ik5b._1fz17ikh3._1fz17ikgj._1fz17ikhb > div > button",
        "//*[@id='app']/div/div[1]/div[4]/div/div[3]/div[2]/div[4]/div/button",
        "button.azpfys0.azpfys7._1fz17ik5b._1fz17ikp._1fz17ik63._1fz17ikh._1ojf5op0"
    ]
    
    for selector in selectors:
        try:
            # Wait for button to be clickable
            button = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR if not selector.startswith("//") else By.XPATH, selector))
            )
            # Scroll to button
            driver.execute_script("arguments[0].scrollIntoView(true);", button)
            time.sleep(1)  # Wait for scroll
            # Click button
            button.click()
            print(f"[SUCCESS] Clicked continue button using selector: {selector}")
            
            # Check if we need to dispatch to special page handler
            if dispatch_special_pages(driver):
                return True
                
            return True
        except Exception as e:
            print(f"[DEBUG] Could not click continue button with selector {selector}: {e}")
            continue
    return False

def main():
    profile_path = "/Users/umairsaeed/Library/Application Support/Firefox/Profiles/4219wmga.default-release"

    options = FirefoxOptions()
    options.set_preference("dom.webnotifications.enabled", False)
    options.add_argument("--width=1280")
    options.add_argument("--height=900")
    options.profile = profile_path

    debug_print("Initializing Firefox Service...")
    service = FirefoxService()
    debug_print("Firefox Service initialized.")

    debug_print("Launching Firefox with personal profile...")
    driver = webdriver.Firefox(service=service, options=options)
    debug_print("Firefox WebDriver initialized successfully.")

    driver.implicitly_wait(10)
    job_id = "seek_application"
    job_title = "N-A"
    step_counter = 0
    max_steps = 10

    # Initialize upload states
    upload_states = {
        'resume': False,
        'cover_letter': False
    }

    # Initialize OpenAI client
    client = OpenAI()

    try:
        job_url = "https://www.seek.com.au/job/84523589"
        debug_print(f"Opening job page: {job_url}")
        driver.get(job_url)

        debug_print("Waiting for Apply button...")
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, "//a[contains(., 'Apply') or contains(., 'apply')]"))
        )
        step_counter += 1

        soup = BeautifulSoup(driver.page_source, 'html.parser')
        job_title_element = soup.select_one('h1')
        job_title = job_title_element.get_text(strip=True) if job_title_element else 'N-A'

        save_page_snapshot(driver, job_id, job_title, f"nav_{step_counter}")

        apply_button = driver.find_element(By.XPATH, "//a[contains(., 'Apply') or contains(., 'apply')]")
        debug_print("Clicking Apply...")
        apply_button.click()
        time.sleep(5)
        step_counter += 1

        visited_states = set()
        executed_action_keys = set()
        consecutive_same_states = 0
        last_state = None

        while step_counter < max_steps:
            debug_print(f"\n=== Processing Step {step_counter + 1} ===", "INFO")

            # Check if both uploads are complete
            if upload_states['resume'] and upload_states['cover_letter']:
                debug_print("Both resume and cover letter uploaded successfully", "SUCCESS")
                # Add a 10-second delay before trying to click continue
                debug_print("Waiting 10 seconds before clicking continue button...", "INFO")
                time.sleep(10)
                # Try to click continue button after uploads
                if try_click_continue(driver):
                    debug_print("Successfully clicked continue button after uploads", "SUCCESS")
                    # Check if we need to dispatch to special page handler
                    if dispatch_special_pages(driver):
                        debug_print("Handed off to special page handler, exiting main loop", "SUCCESS")
                        break
                else:
                    debug_print("Could not find continue button, continuing with normal flow", "WARNING")

            current_url = driver.current_url
            domain = urlparse(current_url).netloc
            debug_print(f"Current URL: {current_url}", "INFO")

            # Check if we need to dispatch to special page handler
            if dispatch_special_pages(driver):
                debug_print("Handed off to special page handler, exiting main loop", "SUCCESS")
                break

            # Improved state detection
            current_state = hash(current_url + "_" + str(len(driver.page_source)))
            if current_state == last_state:
                consecutive_same_states += 1
                debug_print(f"Same state detected {consecutive_same_states} times", "DEBUG")
                if consecutive_same_states >= 3:
                    debug_print("Detected multiple consecutive same states. Ending automation.", "WARNING")
                    break
            else:
                consecutive_same_states = 0
                last_state = current_state
                debug_print("New state detected", "DEBUG")

            visited_states.add(current_state)

            html_path, screenshot_path = save_page_snapshot(driver, job_id, job_title, f"step_{step_counter + 1}")
            current_html = open(html_path, encoding="utf-8").read()

            playbook = load_playbook(domain)
            actions_to_execute = []

            if not playbook or 'actions' not in playbook:
                debug_print("No playbook found. Generating new actions...", "INFO")
                current_sections = extract_form_sections(current_html)
                new_actions = generate_playbook(client, current_sections, screenshot_path)
                if new_actions and "actions" in new_actions:
                    playbook = {"actions": new_actions.get("actions", [])}
                    save_playbook(domain, playbook)
                    actions_to_execute = playbook["actions"]
                    debug_print(f"Generated {len(actions_to_execute)} new actions", "INFO")
                else:
                    debug_print("LLM failed to generate actions.", "ERROR")
                    break
            else:
                debug_print(f"Loaded existing playbook for {domain}", "INFO")
                for action in playbook['actions']:
                    key = f"{action['action']}|{action['selector']}|{action.get('value', '')}"
                    if key not in executed_action_keys:
                        actions_to_execute.append(action)
                debug_print(f"Found {len(actions_to_execute)} actions to execute", "INFO")

            for idx, action in enumerate(actions_to_execute):
                field = action.get("field", "Unknown").lower()
                debug_print(f"Executing action {idx+1}: {action['action']} - {field}", "INFO")

                # Skip if already handled
                if "resume" in field and upload_states['resume']:
                    debug_print("Skipping resume upload - already completed", "INFO")
                    continue
                if "cover letter" in field and upload_states['cover_letter']:
                    debug_print("Skipping cover letter upload - already completed", "INFO")
                    continue

                success = execute_playbook_actions(driver, [action], RESUME_PATH, COVER_LETTER_PATH)
                executed_action_keys.add(f"{action['action']}|{action['selector']}|{action.get('value', '')}")

                # Check if we need to dispatch to special page handler after each action
                if dispatch_special_pages(driver):
                    debug_print("Handed off to special page handler, exiting action loop", "SUCCESS")
                    break

            # Handle any remaining special pages in sequence (role-requirements → profile → review)
            while dispatch_special_pages(driver):
                pass

            step_counter += 1

    except Exception as e:
        debug_print(f"Unexpected exception: {e}", "ERROR")
    finally:
        driver.quit()
        debug_print("Browser closed.", "INFO")

if __name__ == "__main__":
    main()
