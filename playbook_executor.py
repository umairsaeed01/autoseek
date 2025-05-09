# File: playbook_executor.py

import time
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException, ElementNotInteractableException, ElementClickInterceptedException, WebDriverException

def execute_playbook_actions(driver, actions, resume_path, cover_letter_path):
    """
    Execute a sequence of actions (playbook) on the current page using Selenium WebDriver.
    Supports action types: 'click', 'upload', 'input_text'.
    Replaces placeholders [RESUME_PATH] and [COVER_LETTER_PATH] with the given file paths.
    
    Parameters:
        driver (WebDriver): The Selenium WebDriver instance controlling the browser.
        actions (list): List of action dictionaries from the playbook JSON.
        resume_path (str): File path to the resume PDF to upload.
        cover_letter_path (str): File path to the cover letter PDF to upload.
    
    Returns:
        bool: True if all actions executed successfully, False if any action failed.
    """
    for idx, action in enumerate(actions, start=1):
        action_type = action.get('action')
        selector = action.get('selector')
        field_desc = action.get('field', '(unnamed field)')
        value = action.get('value', None)
        # Replace file path placeholders in the value if present
        if value:
            if '[RESUME_PATH]' in value:
                value = value.replace('[RESUME_PATH]', resume_path)
            if '[COVER_LETTER_PATH]' in value:
                value = value.replace('[COVER_LETTER_PATH]', cover_letter_path)
        # Log the action about to be performed for debugging
        print(f"Executing action {idx}: {action_type} - {field_desc}")
        try:
            # Determine how to find the element (CSS selector or XPath for text contains)
            element = None
            if selector and ':contains(' in selector:
                # Convert a pseudo-selector with :contains(text) into an XPath expression
                import re
                # Example selector: "button:contains('Upload')"
                match = re.match(r"^(?P<base>.+?):contains\(['\"](?P<text>[^'\"]+)['\"]\)$", selector)
                if not match:
                    raise ValueError(f"Unsupported selector format: {selector}")
                base_selector = match.group('base')
                text = match.group('text')
                # Build an XPath that matches elements of type base_selector containing the text
                # Parse the base selector (could include tag, id, class, and attribute selectors)
                tag_name = "*"
                xpath_conditions = []
                base = base_selector
                # If base selector contains an explicit tag name at the start
                tag_match = re.match(r"^([a-zA-Z][a-zA-Z0-9]*)", base)
                if tag_match:
                    tag_name = tag_match.group(1)
                    base = base[len(tag_name):]  # remove the tag from the base string
                # Check for ID in base (e.g., #some-id)
                id_match = re.search(r"#([A-Za-z0-9_\-]+)", base)
                if id_match:
                    id_value = id_match.group(1)
                    xpath_conditions.append(f"@id='{id_value}'")
                # Check for classes in base (e.g., .class1.class2)
                classes = re.findall(r"\.([A-Za-z0-9_\-]+)", base)
                for cls in classes:
                    # Use contains() on @class to ensure class is present (whole word match)
                    xpath_conditions.append(f"contains(concat(' ', normalize-space(@class), ' '), ' {cls} ')")
                # Check for other attribute selectors in base (e.g., [name='value'])
                attr_matches = re.findall(r"\[([^=\]]+)=['\"]([^'\"]+)['\"]\]", base)
                for attr_name, attr_val in attr_matches:
                    xpath_conditions.append(f"@{attr_name}='{attr_val}'")
                # Always include the text condition from :contains
                xpath_conditions.append(f"contains(., '{text}')")
                # Form the final XPath string
                condition_str = " and ".join(xpath_conditions)
                xpath_expr = f"//{tag_name}[{condition_str}]"
                # Find the element using XPath
                element = driver.find_element(By.XPATH, xpath_expr)
            else:
                # Use CSS selector to find the element
                element = driver.find_element(By.CSS_SELECTOR, selector)
            
            # Perform the action on the found element
            if action_type == 'click':
                # Attempt to click the element, with fallbacks if necessary
                try:
                    element.click()
                except ElementNotInteractableException:
                    # If element is present but not interactable (perhaps hidden off-screen), try scrolling and clicking via JS
                    print(f"Element not interactable for clicking '{field_desc}'. Scrolling into view and retrying.")
                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    try:
                        element.click()
                    except Exception:
                        # Final fallback: force click via JavaScript
                        driver.execute_script("arguments[0].click();", element)
                except ElementClickInterceptedException:
                    # If click is intercepted by another element (e.g., overlay), use JavaScript click as fallback
                    print(f"Click intercepted for '{field_desc}'. Using JavaScript click.")
                    driver.execute_script("arguments[0].click();", element)
                print(f"Clicked: {field_desc}")
            
            elif action_type == 'input_text':
                # If input field, clear it first to avoid appending to existing text
                try:
                    element.clear()
                except Exception:
                    pass  # ignore if clear is not applicable
                element.send_keys(value or "")
                print(f"Entered text for: {field_desc}")
            
            elif action_type == 'upload':
                # Ensure the file input is visible/enabled before sending file path
                if not element.is_displayed():
                    try:
                        driver.execute_script("arguments[0].style.display = 'block';", element)
                    except Exception as e:
                        print(f"Warning: Could not unhide file input for '{field_desc}'. Attempting file upload regardless.")
                element.send_keys(value or "")
                print(f"Uploaded file for: {field_desc} (Path: {value})")
            
            else:
                # Unrecognized action types are skipped
                print(f"Warning: Unknown action type '{action_type}' for '{field_desc}'. Skipping this action.")
            
        except NoSuchElementException:
            # Element not found for the given selector
            print(f"Error: Element not found for '{field_desc}' (selector: {selector}).")
            return False  # Stop execution on failure
        except WebDriverException as e:
            # Handle other Selenium errors (e.g., invalid file path, etc.)
            print(f"Error: WebDriver exception during action '{field_desc}' - {e}")
            return False
        
        # Short pause after each action to allow the page to react (if needed)
        time.sleep(0.5)
    return True