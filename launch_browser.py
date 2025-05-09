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
from playbook_manager import load_playbook, save_playbook
from playbook_executor import execute_playbook_actions

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

        visited_states = set()
        domain_safe = None

        while True:
            current_url = driver.current_url
            domain = urlparse(current_url).netloc
            print(f"Current domain: {domain}")
            html_file_path, screenshot_path = save_page_snapshot(driver, job_id, job_title, f"step_{step_counter}")

            if os.path.exists(html_file_path):
                with open(html_file_path, "r", encoding="utf-8") as f:
                    current_html = f.read()
                if "application submitted" in current_html.lower():
                    print("Application submitted.")
                    break
            else:
                print(f"[Error] HTML not found: {html_file_path}")

            if domain_safe is None:
                domain_safe = "".join(c if c.isalnum() else "_" for c in domain)

            playbook = load_playbook(domain)
            if playbook is None:
                print("Generating new playbook...")
                with open(html_file_path, "r", encoding="utf-8") as f:
                    captured_html = f.read()
                truncated_html = captured_html[:400000]
                playbook = analyze_form_page(truncated_html, screenshot_path)
                if playbook:
                    save_playbook(domain, playbook)
                else:
                    print("Playbook generation failed.")
                    break

            if playbook and 'actions' in playbook:
                success = execute_playbook_actions(driver, playbook['actions'], RESUME_PATH, COVER_LETTER_PATH)
                if not success:
                    print("Failed to execute actions.")
                    break
            else:
                print("Playbook has no actions.")

            old_url = driver.current_url
            old_html_len = len(driver.page_source)
            print("Waiting for page change...")
            content_changed = False
            for _ in range(15):
                time.sleep(1)
                if driver.current_url != old_url or len(driver.page_source) != old_html_len:
                    content_changed = True
                    break

            if not content_changed:
                print("No page change detected. Exiting.")
                break

            state_signature = hash(driver.current_url + "_" + str(len(driver.page_source)))
            if state_signature in visited_states:
                print("Detected a loop. Exiting.")
                break
            visited_states.add(state_signature)

            step_counter += 1
            print(f"Step {step_counter} complete.")

    except Exception as e:
        print(f"[Error] {e}")
    finally:
        driver.quit()
        print("Browser closed.")

if __name__ == "__main__":
    main()