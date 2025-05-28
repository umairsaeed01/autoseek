import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException, TimeoutException
from page_capture import save_page_snapshot
from llm_agent import analyze_page_with_context
import html_processor
 
def execute_playbook_actions(driver, actions, resume_path, cover_letter_path):
    resume_uploaded = False
    cover_letter_uploaded = False
 
    for idx, action in enumerate(actions):
        action_type = action.get("action")
        selector = action.get("selector")
        field = action.get("field", "Unknown field")
        value = action.get("value", "")
 
        print(f"\nExecuting action {idx+1}: {action_type} - {field}")
 
        try:
            # Determine how to find the element
            if action.get("field") == "resume file":
                element = driver.find_element(By.ID, "resume-fileFile")
            elif action.get("field") == "cover letter file":
                # Wait for the cover letter file input to be present and interactable
                try:
                    element = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.ID, "coverLetter-fileFile"))
                    )
                except TimeoutException:
                    print("Cover letter file input not found, trying alternative selector...")
                    element = driver.find_element(By.CSS_SELECTOR, "input[type='file'][data-testid='cover-letter-upload']")
            else:
                element = driver.find_element(By.XPATH, selector) if action.get("use_xpath") else driver.find_element(By.CSS_SELECTOR, selector)
 
            if action_type == "click":
                try:
                    element.click()
                except ElementNotInteractableException:
                    print(f"Element not interactable for clicking '{field}'. Scrolling into view and retrying.")
                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    time.sleep(1)
                    element.click()
                print(f"Clicked: {field}")
 
            elif action_type == "upload":
                upload_path = resume_path if value == "[RESUME_PATH]" else cover_letter_path
                driver.execute_script("arguments[0].scrollIntoView(true);", element)
                time.sleep(1)
                element.send_keys(upload_path)
                print(f"Uploaded file for: {field} (Path: {upload_path})")
                if value == "[RESUME_PATH]":
                    resume_uploaded = True
                elif value == "[COVER_LETTER_PATH]":
                    cover_letter_uploaded = True
 
            time.sleep(3 if action_type == "upload" else 1.5)
 
            # Save snapshot
            snapshot_name = f"steppost_action_{idx+1}_{field.replace(' ', '_')}"
            html_path, screenshot_path = save_page_snapshot(driver, "seek_application", "PostAction", snapshot_name)
 
            # Get current HTML
            with open(html_path, "r", encoding="utf-8") as f:
                current_html = f.read()
 
            # Analyze step via LLM
            try:
                print("Analyzing effect of last action with LLM...")
                # Extract sections from the current HTML
                current_sections = html_processor.extract_form_sections(current_html)
                result = analyze_page_with_context(driver, {
                    "sections": current_sections,
                    "current_step": idx + 1
                })

                if isinstance(result, dict):
                    print(f"🖼️ Screenshot summary: {result.get('screenshot_summary', 'N/A')}")
                    print(f"🧾 HTML summary: {result.get('html_summary', 'N/A')}")
                    print(f"🔮 LLM-suggested next action: {result.get('suggested_action', 'N/A')}")
                    # Check for completion based on LLM analysis
                    if "no more form fields" in result.get('html_summary', '').lower() or "application complete" in result.get('screenshot_summary', '').lower():
                         print("✅ LLM analysis indicates form is completed.")
                         return True
                else:
                    print(f"❌ LLM analysis failed or returned unexpected format: {result}")
                    pass
 
            except Exception as llm_error:
                print(f"❌ LLM Error during analysis: {llm_error}")
                pass
 
        except NoSuchElementException:
            print(f"[Error] Element not found for action '{action_type}' with selector: {selector}")
            return False
        except Exception as e:
            print(f"[Error] Unexpected error during action '{field}': {e}")
            return False
 
    return True