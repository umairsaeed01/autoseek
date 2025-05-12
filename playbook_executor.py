import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import ElementNotInteractableException, NoSuchElementException
from page_capture import save_page_snapshot
import html_processor

def execute_playbook_actions(driver, actions, resume_path, cover_letter_path):
    for idx, action in enumerate(actions):
        action_type = action.get("action")
        selector = action.get("selector")
        field = action.get("field", "Unknown field")
        value = action.get("value", "")

        print(f"Executing action {idx+1}: {action_type} - {field}")

        try:
            # Determine how to find the element (CSS selector or XPath)
            if action.get("use_xpath"):
                element = driver.find_element(By.XPATH, selector)
            else:
                element = driver.find_element(By.CSS_SELECTOR, selector)

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

            # ✅ Add delay based on action type
            time.sleep(3 if action_type == "upload" else 1.5)

            # ✅ Take snapshot and review HTML to decide next step
            snapshot_name = f"post_action_{idx+1}_{field.replace(' ', '_')}"
            html_path, screenshot_path = save_page_snapshot(driver, "seek_application", "PostAction", snapshot_name)

            with open(html_path, "r", encoding="utf-8") as f:
                current_html = f.read()

            remaining_sections = html_processor.extract_form_sections(current_html)

            if not remaining_sections:
                print("✅ Form seems completed. No remaining sections.")
                return True

        except NoSuchElementException:
            print(f"[Error] Element not found for action '{action_type}' with selector: {selector}")
            return False
        except Exception as e:
            print(f"[Error] Unexpected error during action '{field}': {e}")
            return False

    return True