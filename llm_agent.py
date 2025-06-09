import os
import json
import base64
import re
import time
from dotenv import load_dotenv
from openai import OpenAI # Import OpenAI client
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

load_dotenv()
# The OpenAI client will automatically look for the OPENAI_API_KEY environment variable
# We will pass the client instance to the functions that need it.

# MODEL_NAME = "gpt-3.5-turbo" # Or another suitable OpenAI model
# MAX_CHARS_SINGLE = 15000 # Keep this if needed for context splitting, but OpenAI handles larger contexts

def sanitize_actions(actions):
    seen = set()
    valid = []

    for a in actions:
        # key to identify duplicates of click/upload steps
        key = (a["action"], a["selector"], a.get("field",""))
        # if it's an upload or click on resume/cover letter and we've seen it, skip
        if key in seen and a["action"] in ("upload","click") \
           and any(k in a.get("field","").lower() for k in ("resume","cover letter")):
            continue

        seen.add(key)

        # Add proper wait conditions for uploads
        if a["action"] == "upload":
            a["wait_for"] = "upload_complete"
            a["verify"] = "file_uploaded"
            # Add specific upload button selector
            if "upload" in a["field"].lower():
                a["selector"] = "span.azpfys0._1fz17ikav._1fz17ik9r._1fz17ik5f._1fz17ik5b._1fz17ikgv._1fz17iki3._1fz17ikhn._1fz17ik0._1fz17iki._1ojf5opa"
            
        # Add proper verification for continue button
        if "continue" in a.get("field","").lower():
            a["wait_for"] = "button_visible"
            a["verify"] = "button_clickable"
            # Add specific continue button selectors
            a["selectors"] = [
                "button[data-testid='continue-button']",
                "#app > div > div.azpfys0._1fz17ik9j > div.azpfys0._1fz17ikb7._1fz17ikaw._1fz17ika3._1fz17ik9s._1fz17ikp > div > div.azpfys0._1fz17ikcr._1fz17ikt > div.azpfys0._1fz17ik5b._1fz17ikhf._1fz17ik77 > div.azpfys0._1fz17ik5b._1fz17ikh3._1fz17ikgj._1fz17ikhb > div > button",
                "//*[@id='app']/div/div[1]/div[4]/div/div[3]/div[2]/div[4]/div/button",
                "button.azpfys0.azpfys7._1fz17ik5b._1fz17ikp._1fz17ik63._1fz17ikh._1ojf5op0"
            ]
            # drop any prior continue, then append this one
            valid = [x for x in valid if "continue" not in x.get("field","").lower()]
            valid.append(a)
        else:
            valid.append(a)

    return valid

# Modified to accept OpenAI client instance
def generate_playbook(client: OpenAI, sections, screenshot_path=None, model="gpt-3.5-turbo"):
    # First check if we have a valid cached playbook
    cached_playbook = load_cached_playbook()
    if cached_playbook and is_valid_playbook(cached_playbook):
        print("[INFO] Using cached playbook")
        return cached_playbook

    combined = "\n\n".join(sections)

    messages = [
        {
            "role": "system",
            "content": """You are a reliable form automation agent. Your task is to generate a sequence of actions for job application forms.
            Output your plan in JSON format only, with a top-level key 'actions' containing an array of action objects.

IMPORTANT RULES:
1. For file uploads:
   - First click the radio button for upload option
   - Then click the upload button (span containing 'Upload' text)
   - Wait for upload confirmation (look for span with data-testid='upload-success-filename')
   - DO NOT try to click any upload button after file selection
   - Wait for upload confirmation before proceeding
   - Only generate continue/next button action after both files are uploaded

2. For continue/next buttons:
   - Only generate continue button action after both files are uploaded
   - Use these selectors in order:
     * button[data-testid='continue-button']
     * #app > div > div.azpfys0._1fz17ik9j > div.azpfys0._1fz17ikb7._1fz17ikaw._1fz17ika3._1fz17ik9s._1fz17ikp > div > div.azpfys0._1fz17ikcr._1fz17ikt > div.azpfys0._1fz17ik5b._1fz17ikhf._1fz17ik77 > div.azpfys0._1fz17ik5b._1fz17ikh3._1fz17ikgj._1fz17ikhb > div > button
     * //*[@id='app']/div/div[1]/div[4]/div/div[3]/div[2]/div[4]/div/button
     * button.azpfys0.azpfys7._1fz17ik5b._1fz17ikp._1fz17ik63._1fz17ikh._1ojf5op0

3. Action Sequence:
   - Resume upload:
     * Click radio button for resume upload
     * Click upload button
     * Wait for upload confirmation
   - Cover letter upload:
     * Click radio button for cover letter upload
     * Click upload button
     * Wait for upload confirmation
   - Wait for both uploads to complete
   - Click continue/next button

4. State Management:
   - Track upload status using data-testid='upload-success-filename'
   - Verify each action's success
   - Include proper wait conditions

Generate actions in this JSON format:
{
  "actions": [
    {
      "action": "click|upload|wait",
      "selector": "valid_css_selector",
      "field": "description",
      "wait_for": "condition",
      "verify": "success_condition"
    }
  ]
}"""
        },
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Here is the form content:\n" + combined + "\n\nGenerate actions to upload resume and cover letter, then click continue."}
            ]
        }
    ]

    if screenshot_path:
        try:
            with open(screenshot_path, "rb") as img_file:
                b64_image = base64.b64encode(img_file.read()).decode("utf-8")
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{b64_image}"
                }
            })
        except FileNotFoundError:
            print(f"[Warning] Screenshot not found at {screenshot_path}. Proceeding without image.")
        except Exception as e:
            print(f"[Error] Could not process screenshot {screenshot_path}: {e}")

    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            response_format={"type": "json_object"}
        )

        # ——— GPT-3.5-turbo usage logging ———
        try:
            usage = response.usage
            pt = usage.prompt_tokens
            ct = usage.completion_tokens
            tt = usage.total_tokens
            ir, orate = (0.03, 0.06) if model.startswith("gpt-4") else (0.0015, 0.002)
            ic = pt * ir / 1000
            oc = ct * orate / 1000
            tc = ic + oc
            print(f"[{model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
                  f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
        except Exception:
            print(f"[{model} usage] ⚠️ failed to read response.usage")
        # ———————————————————————

        content = response.choices[0].message.content
        print(f"Raw LLM output (generate_playbook): '{content}'")
        plan = _parse_json(content)

        if plan and "actions" in plan:
            # Add continue button action if not present
            has_continue = False
            for action in plan["actions"]:
                if "continue" in action.get("field", "").lower() and action["action"] == "click":
                    has_continue = True
                    break
            
            if not has_continue:
                plan["actions"].append({
                    "action": "click",
                    "selector": "button[data-testid='continue-button']",
                    "field": "continue button",
                    "wait_for": "button_visible",
                    "verify": "button_clickable"
                })
            
            plan["actions"] = sanitize_actions(plan["actions"])
            print(f"[LLM] Plan sanitized to {len(plan['actions'])} actions.")
            # Save the generated playbook
            save_playbook(plan)
            return plan
        else:
            print("[LLM] generate_playbook failed, returning empty plan.")
            return {"actions": []}

    except Exception as e:
        print(f"[LLM ERROR in generate_playbook] {e}")
        # Return a fallback plan
        return {
            "actions": [
                {"action": "click", "selector": "input[name='resume-method'][value='upload']", "field": "select resume upload"},
                {"action": "upload", "selector": "input[name='file'][data-field='resume']", "field": "resume file", "value": "[RESUME_PATH]"},
                {"action": "click", "selector": "input[name='coverLetter-method'][value='upload']", "field": "select cover letter upload"},
                {"action": "upload", "selector": "input[name='file'][data-field='cover_letter']", "field": "cover letter file", "value": "[COVER_LETTER_PATH]"},
                {"action": "click", "selector": "button[data-testid='continue-button']", "field": "continue button"}
            ]
        }

def load_cached_playbook():
    """Load cached playbook if it exists"""
    try:
        with open("playbooks/www_seek_com_au.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"[Error] Could not load cached playbook: {e}")
        return None

def is_valid_playbook(playbook):
    """Check if the playbook has all required actions"""
    if not playbook or "actions" not in playbook:
        return False
        
    actions = playbook["actions"]
    has_resume_upload = False
    has_cover_letter_upload = False
    has_continue_button = False
    
    for action in actions:
        if "resume" in action.get("field", "").lower() and action["action"] == "upload":
            has_resume_upload = True
        elif "cover letter" in action.get("field", "").lower() and action["action"] == "upload":
            has_cover_letter_upload = True
        elif "continue" in action.get("field", "").lower() and action["action"] == "click":
            has_continue_button = True
            
    return has_resume_upload and has_cover_letter_upload and has_continue_button

def save_playbook(playbook):
    """Save the generated playbook"""
    try:
        os.makedirs("playbooks", exist_ok=True)
        with open("playbooks/www_seek_com_au.json", "w") as f:
            json.dump(playbook, f, indent=2)
        print("[INFO] Playbook saved successfully")
    except Exception as e:
        print(f"[Error] Could not save playbook: {e}")

# These functions are no longer directly used by generate_playbook in the new structure
# def _build_full_prompt(sections):
#     return [
#         {
#             "role": "system",
#             "content": (
#                 "You are a reliable form automation agent. Analyze the structure of job application pages and "
#                 "generate JSON actions using proper CSS selectors (NO :contains()). Avoid duplicate actions."
#             )
#         },
#         {
#             "role": "user",
#             "content": (
#                 "Here is the form content:\n" + "\n\n".join(sections) +
#                 "\n\nRespond with a JSON array of actions to fill the form and click next."
#             )
#         }
#     ]

# def _build_section_prompt(section_text, index):
#     return _build_full_prompt([f"Section {index}:\n{section_text}"])

def _parse_json(text):
    if not text:
        return None
    try:
        match = re.search(r"\{.*\}", text.strip(), re.DOTALL)
        if match:
            json_string = match.group()
            if json_string.strip().startswith("```json"):
                json_string = json_string.strip()[len("```json"):].rstrip("```")
            return json.loads(json_string)
        else:
            print("[ParseError] No JSON object found in LLM output.")
            return None
    except json.JSONDecodeError as e:
        print(f"[ParseError] JSON decoding failed: {e}. Input text: {text[:200]}...")
        return None
    except Exception as e:
        print(f"[ParseError] An unexpected error occurred during JSON parsing: {e}")
        return None


# Modified to accept OpenAI client instance
def analyze_page_with_context(driver, context, model="gpt-3.5-turbo"):
    """
    Analyze the current page state and suggest next action.
    
    Args:
        driver: Selenium WebDriver instance
        context: Dictionary containing context about the current state
        model: The OpenAI model to use (default: "gpt-3.5-turbo")
    """
    try:
        # Get page content
        page_content = driver.page_source
        
        # Get visible text
        visible_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Get all input fields and their states
        input_fields = []
        for element in driver.find_elements(By.CSS_SELECTOR, "input, textarea, select"):
            try:
                field_info = {
                    "type": element.get_attribute("type"),
                    "name": element.get_attribute("name"),
                    "id": element.get_attribute("id"),
                    "class": element.get_attribute("class"),
                    "placeholder": element.get_attribute("placeholder"),
                    "value": element.get_attribute("value"),
                    "is_enabled": element.is_enabled(),
                    "is_displayed": element.is_displayed()
                }
                input_fields.append(field_info)
            except:
                continue
                
        # Get all buttons and their states
        buttons = []
        for element in driver.find_elements(By.CSS_SELECTOR, "button, [role='button'], input[type='submit']"):
            try:
                button_info = {
                    "text": element.text,
                    "type": element.get_attribute("type"),
                    "class": element.get_attribute("class"),
                    "is_enabled": element.is_enabled(),
                    "is_displayed": element.is_displayed()
                }
                buttons.append(button_info)
            except:
                continue

        # Filter to only upload-related content
        MAX_LEN = 12000  # Maximum length for any text field
        visible_text = visible_text[:MAX_LEN]
        page_content = page_content[:MAX_LEN]
        
        # Filter input fields to only those related to uploads
        upload_fields = [f for f in input_fields if any(k in str(f).lower() for k in ["resume", "cover", "upload", "file"])]
        input_fields = upload_fields or input_fields[:5]  # Keep at most 5 fields if no upload-related ones found
        
        # Filter buttons to only those related to uploads or continue
        upload_buttons = [b for b in buttons if any(k in str(b).lower() for k in ["upload", "continue", "next", "submit"])]
        buttons = upload_buttons or buttons[:3]  # Keep at most 3 buttons if no upload-related ones found

        # Prepare context for LLM
        llm_context = {
            "page_content": page_content,
            "visible_text": visible_text,
            "input_fields": input_fields,
            "buttons": buttons,
            "context": context or {}  # Ensure context is never None
        }

        # Call LLM to analyze the page
        client = OpenAI()
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": """You are an expert at analyzing web pages and determining the next actions needed to complete a task.
                You will be given the page content, visible text, input fields, buttons, and context about what we're trying to do.
                Your job is to:
                1. Analyze the current state of the page
                2. Determine what information we need to fill in
                3. Generate the next action to take
                
                For each action, you should specify:
                - action: "click", "type", or "upload"
                - field: A description of what we're interacting with
                - selector: The CSS selector to find the element
                - value: The value to type or file to upload (for type/upload actions)
                - wait_for: What to wait for before proceeding ("time", "upload_complete", "button_visible")
                - verify: What to verify after the action ("button_clickable", "file_uploaded")
                
                For continue buttons, include multiple selectors to try.
                For uploads, ensure proper wait and verification conditions.
                Avoid duplicate actions for the same field.
                
                Output your analysis in JSON format only with this exact structure:
                {
                    "summary": "Brief description of current state",
                    "suggested_action": {
                        "action": "click|type|upload",
                        "field": "description",
                        "selector": "css_selector",
                        "value": "optional_value",
                        "wait_for": "condition",
                        "verify": "success_condition"
                    }
                }"""},
                {"role": "user", "content": json.dumps(llm_context)}
            ],
            temperature=0.7,
            max_tokens=1000,
            response_format={"type": "json_object"}
        )

        # ——— GPT-3.5-turbo usage logging ———
        try:
            usage = response.usage
            pt = usage.prompt_tokens
            ct = usage.completion_tokens
            tt = usage.total_tokens
            ir, orate = (0.03, 0.06) if model.startswith("gpt-4") else (0.0015, 0.002)
            ic = pt * ir / 1000
            oc = ct * orate / 1000
            tc = ic + oc
            print(f"[{model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
                  f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
        except Exception:
            print(f"[{model} usage] ⚠️ failed to read response.usage")
        # ———————————————————————

        # Parse the response
        try:
            content = response.choices[0].message.content
            print(f"Raw LLM output: {content}")
            
            # Try to parse the JSON response
            result = json.loads(content)
            
            # Validate the response structure
            if not isinstance(result, dict):
                raise ValueError("Response is not a dictionary")
                
            if "summary" not in result:
                raise ValueError("Response missing 'summary' field")
                
            if "suggested_action" not in result:
                raise ValueError("Response missing 'suggested_action' field")
                
            if result["suggested_action"] is not None:
                required_fields = ["action", "field", "selector"]
                for field in required_fields:
                    if field not in result["suggested_action"]:
                        raise ValueError(f"Suggested action missing required field: {field}")
            
            return result
            
        except json.JSONDecodeError as e:
            print(f"[ParseError] JSON decoding failed: {e}")
            print(f"Raw content: {content}")
            return {
                "summary": "Error parsing LLM response",
                "suggested_action": {
                    "action": "click",
                    "selector": "button[data-testid='continue-button']",
                    "field": "continue button",
                    "wait_for": "button_visible",
                    "verify": "button_clickable"
                }
            }
        except Exception as e:
            print(f"[ParseError] Error validating response: {e}")
            return {
                "summary": f"Error validating response: {e}",
                "suggested_action": {
                    "action": "click",
                    "selector": "button[data-testid='continue-button']",
                    "field": "continue button",
                    "wait_for": "button_visible",
                    "verify": "button_clickable"
                }
            }

    except Exception as e:
        print(f"[LLM ERROR in analyze_page_with_context] {e}")
        # Return a fallback action
        return {
            "summary": f"Error from LLM: {e}",
            "suggested_action": {
                "action": "click",
                "selector": "button[data-testid='continue-button']",
                "field": "continue button",
                "wait_for": "button_visible",
                "verify": "button_clickable"
            }
        }

def execute_actions(driver, actions):
    for action in actions:
        try:
            print(f"\n[Executor] Executing action: {action['action']} on {action.get('field', '')}")
            
            # Handle wait conditions
            if action.get("wait_for") == "time":
                print(f"[Executor] Waiting {action['wait_time']} seconds...")
                time.sleep(action["wait_time"])
                continue
                
            # Handle upload completion wait
            if action.get("wait_for") == "upload_complete":
                print("[Executor] Waiting for upload to complete...")
                time.sleep(5)  # Initial wait for upload to start
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.upload-success"))
                    )
                    print("[Executor] Upload completed successfully")
                except:
                    print("[Executor] Upload completion indicator not found, continuing anyway")
                continue

            # Handle button visibility wait
            if action.get("wait_for") == "button_visible":
                print("[Executor] Waiting for button to be visible...")
                try:
                    # Try each selector until one works
                    for selector in action.get("selectors", [action["selector"]]):
                        try:
                            element = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            if element.is_displayed():
                                print(f"[Executor] Found visible button with selector: {selector}")
                                action["selector"] = selector
                                break
                        except:
                            continue
                except:
                    print("[Executor] Button not found, continuing anyway")

            # Execute the action
            if action["action"] == "click":
                # Handle multiple selectors for continue button
                if "continue" in action.get("field", "").lower():
                    # Use the new dispatcher for continue button clicks
                    from launch_browser_updated import click_continue_and_dispatch
                    if click_continue_and_dispatch(driver):
                        print("[Executor] Dispatched to profile handler, exiting action loop")
                        return  # Exit the action loop
                    continue
                else:
                    element = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, action["selector"]))
                    )
                    element.click()
                    print("[Executor] Clicked element successfully")

            elif action["action"] == "type":
                element = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, action["selector"]))
                )
                element.clear()
                element.send_keys(action["value"])
                print("[Executor] Typed value successfully")

            elif action["action"] == "upload":
                # Find the file input element
                file_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
                )
                
                # Get the absolute path of the file
                file_path = os.path.abspath(action["value"])
                if not os.path.exists(file_path):
                    print(f"[Executor] File not found: {file_path}")
                    continue
                    
                # Upload the file
                file_input.send_keys(file_path)
                print(f"[Executor] Uploaded file: {file_path}")
                
                # Wait for upload to complete
                time.sleep(5)  # Initial wait for upload to start
                try:
                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.upload-success"))
                    )
                    print("[Executor] Upload completed successfully")
                except:
                    print("[Executor] Upload completion indicator not found, continuing anyway")

            # Verify action completion if specified
            if action.get("verify") == "button_clickable":
                try:
                    WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, action["selector"]))
                    )
                    print("[Executor] Verified button is clickable")
                except:
                    print("[Executor] Button verification failed")
            elif action.get("verify") == "file_uploaded":
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "div.upload-success"))
                    )
                    print("[Executor] Verified file was uploaded")
                except:
                    print("[Executor] File upload verification failed")

            # Add a small delay between actions
            time.sleep(2)

        except Exception as e:
            print(f"[Executor] Error executing action: {str(e)}")
            continue
