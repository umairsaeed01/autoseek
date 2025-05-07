import os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
import time
from page_capture import save_page_snapshot # Import the new function
from analyze_form import analyze_form_page
import json
from bs4 import BeautifulSoup # Import BeautifulSoup
# Load user profile for Chrome to maintain login (update the path to your actual profile).
# On macOS, Chrome profiles are typically under "~/Library/Application Support/Google/Chrome".
user_data_dir = "/Users/umairsaeed/Library/Application Support/Google/Chrome"
profile_dir = "Default"  # or use your custom profile name if not the default

# Configure Chrome options to use the profile
options = Options()
options.add_argument(f"--user-data-dir={user_data_dir}")
options.add_argument(f"--profile-directory={profile_dir}")
options.add_argument("--start-maximized")  # open browser maximized

# Initialize WebDriver (Chrome) with the specified options.
# This will launch Chrome with the given user profile.
service = Service(ChromeDriverManager().install())  # automatically install/update chromedriver
driver = webdriver.Chrome(service=service, options=options)

job_id = "seek_application" # Define a job ID
step_counter = 0 # Initialize step counter

try:
    # Navigate to the job posting URL on Seek
    job_url = "https://www.seek.com.au/job/83589298"  # TODO: replace with actual job URL
    print(f"Opening job page: {job_url}")
    driver.get(job_url)
    time.sleep(5)  # wait for page to fully load (adjust delay as needed or use WebDriver waits)
    step_counter += 1

    # Extract job title
    soup = BeautifulSoup(driver.page_source, 'html.parser')
    job_title_element = soup.select_one('h1._15uaf0e0._1li239b4z._15gbqyr0._15gbqyrl.ni6qyg4._15gbqyrp._15gbqyr21')
    job_title = job_title_element.get_text(strip=True) if job_title_element else 'N/A'

    # Capture after navigation and get the saved file paths
    html_path_nav, screenshot_path_nav = save_page_snapshot(driver, job_id, job_title, f"nav_{step_counter}")

    # Click the "Apply" button on the job page.
    # Assuming the apply button can be found by text or a data-automation attribute.
    apply_button = driver.find_element(By.XPATH, "//a[contains(., 'Apply') or contains(., 'apply')]")
    print("Clicking the Apply button...")
    apply_button.click()
    time.sleep(5)  # wait for redirect to application form
    step_counter += 1
    # Capture after clicking apply and get the saved file paths
    html_path_click, screenshot_path_click = save_page_snapshot(driver, job_id, job_title, f"click_apply_{step_counter}")

    print("Apply button clicked, should be on application form page now.")

    # Read the captured HTML file using the path returned by save_page_snapshot
    # Read the captured HTML file using the path returned by save_page_snapshot
    html_file_path = html_path_click # Use the path returned from the last capture
    screenshot_path = screenshot_path_click # Use the path returned from the last capture

    if os.path.exists(html_file_path):
        with open(html_file_path, "r", encoding="utf-8") as f:
            captured_html = f.read()

        # Truncate HTML content to avoid exceeding token limits
        max_html_length = 400000  # Adjust as needed based on model token limits
        truncated_html = captured_html[:max_html_length]
        print(f"Truncated HTML content to {len(truncated_html)} characters.")

        # Analyze the captured HTML using the LLM
        print(f"Analyzing captured HTML from: {html_file_path}")
        # Pass the screenshot path as well if analyze_form_page uses it
        form_actions = analyze_form_page(truncated_html, screenshot_path)

        # Print the analysis result
        print("LLM Analysis Result (Form Actions):")
        print(json.dumps(form_actions, indent=2))
    else:
        print(f"[Error] Captured HTML file not found: {html_file_path}")


except Exception as e:
    print(f"[Error] Exception during launching or clicking apply: {e}")
    driver.quit()
    raise

# At this point, the browser should have navigated into the first step of the application form.
# (We will capture the form in the next step.)