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
from selenium.common.exceptions import TimeoutException

from page_capture import save_page_snapshot
from analyze_form import analyze_form_page
from playbook_manager import load_playbook, save_playbook
from playbook_executor import execute_playbook_actions
from llm_agent import analyze_page_with_context

RESUME_PATH = os.path.abspath("./resume.pdf")
COVER_LETTER_PATH = os.path.abspath("./cover_letter.pdf")

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
    max_steps = 10

    resume_uploaded = False
    cover_letter_uploaded = False

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

        while step_counter < max_steps:
            current_url = driver.current_url
            domain = urlparse(current_url).netloc
            print(f"\n--- Processing Step {step_counter + 1} ---")
            print(f"Current URL: {current_url}")

            state_signature = hash(current_url + "_" + str(len(driver.page_source)))
            if state_signature in visited_states:
                print("Detected a repeating page state. Ending automation.")
                break
            visited_states.add(state_signature)

            html_path, screenshot_path = save_page_snapshot(driver, job_id, job_title, f"step_{step_counter + 1}")
            current_html = open(html_path, encoding="utf-8").read()

            playbook = load_playbook(domain)
            actions_to_execute = []

            if not playbook or 'actions' not in playbook:
                print("No playbook found. Generating new actions...")
                new_actions = analyze_form_page(current_html[:400000], screenshot_path)
                if new_actions:
                    playbook = {"actions": new_actions}
                    save_playbook(domain, playbook)
                    actions_to_execute = new_actions
                else:
                    print("LLM failed to generate actions.")
                    break
            else:
                print(f"Loaded existing playbook for {domain}.")
                for action in playbook['actions']:
                    key = f"{action['action']}|{action['selector']}|{action.get('value')}"
                    if key not in executed_action_keys:
                        actions_to_execute.append(action)

            for idx, action in enumerate(actions_to_execute):
                field = action.get("field", "Unknown")
                print(f"Executing action {idx+1}: {action['action']} - {field}")

                # Skip if already handled
                if "resume" in field.lower() and resume_uploaded:
                    continue
                if "cover letter" in field.lower() and cover_letter_uploaded:
                    continue

                success = execute_playbook_actions(driver, [action], RESUME_PATH, COVER_LETTER_PATH)
                executed_action_keys.add(f"{action['action']}|{action['selector']}|action.get('value')")

                post_html_path, post_screenshot_path = save_page_snapshot(driver, job_id, job_title, f"post_action_{idx+1}_{field.replace(' ', '_')}")
                post_html = open(post_html_path, encoding="utf-8").read()

                print("Analyzing effect of last action with LLM...")
                summary_analysis = analyze_page_with_context(post_html[:400000], post_screenshot_path)
                print(f"\n🖼️ Screenshot summary:\n{post_screenshot_path}")
                print(f"🧾 HTML summary:\n{post_html_path}")
                print(f"🔮 LLM-suggested next action:\n{summary_analysis}\n")

                summary_text = summary_analysis.get("summary", "").lower()
                if "resume uploaded" in summary_text:
                    resume_uploaded = True
                if "cover letter uploaded" in summary_text:
                    cover_letter_uploaded = True
                if "error" in summary_text:
                    print("❌ LLM reported an error, stopping.")
                    break

                time.sleep(2)

            step_counter += 1

    except Exception as e:
        print(f"[Error] Unexpected exception: {e}")
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()
