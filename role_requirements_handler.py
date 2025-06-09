import os
import json
import hashlib
import time
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from openai import OpenAI

# ------------------------------------------------------------
# 1) PATHS & CONSTANTS
# ------------------------------------------------------------
RESUME_SUMMARY_PATH = os.path.abspath("./resume_summary.txt")
PLAYBOOK_PATH = os.path.abspath("./role_requirements_playbook.json")

# Create empty playbook if it doesn't exist
if not os.path.exists(PLAYBOOK_PATH):
    with open(PLAYBOOK_PATH, "w") as f:
        json.dump({}, f)

# Load latest playbook
with open(PLAYBOOK_PATH, "r") as f:
    playbook = json.load(f)

def save_playbook():
    """Save the role playbook to disk."""
    with open(PLAYBOOK_PATH, "w") as f:
        json.dump(playbook, f, indent=2)

# -------------------------------
# QA CACHE CONFIG
# -------------------------------
QA_CACHE_PATH = os.path.abspath("./role_requirements_qa_cache.json")

def load_qa_cache():
    if os.path.exists(QA_CACHE_PATH):
        with open(QA_CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_qa_cache(cache):
    with open(QA_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)

# ------------------------------------------------------------
# MAIN HANDLER FUNCTION
# ------------------------------------------------------------
def handle_role_requirements_page(driver):
    wait = WebDriverWait(driver, 10)
    # 1) wait for at least one question label to appear
    try:
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "label[for^='question-']")))
    except:
        print("[RoleReq] No questions found on page.")
        return False

    # 2) scrape all questions + options
    questions = []
    for lbl in driver.find_elements(By.CSS_SELECTOR, "label[for^='question-']"):
        q_id = lbl.get_attribute("for").strip()
        q_text = lbl.text.strip()
        if not q_text or not q_id:
            continue

        opts = []
        # try <select>
        try:
            sel = driver.find_element(By.CSS_SELECTOR, f"select[id='{q_id}']")
            for o in sel.find_elements(By.TAG_NAME, "option"):
                t = o.text.strip()
                if t: opts.append(t)
        except:
            # fallback: radio/checkbox
            for inp in driver.find_elements(By.CSS_SELECTOR, f"input[name^='{q_id}'], input[id^='{q_id}']"):
                rid = inp.get_attribute("id")
                if not rid: continue
                try:
                    lab2 = driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']")
                    opts.append(lab2.text.strip())
                except: 
                    pass

        if not opts:
            continue

        multi = bool(driver.find_elements(By.CSS_SELECTOR,
            f"input[type='checkbox'][name^='{q_id}']"))
        questions.append({
            "id":    q_id,
            "text":  q_text,
            "options": opts,
            "multi": multi
        })

    if not questions:
        print("[RoleReq] no valid Q→options sets scraped.")
        return False

    # 3) build a single prompt
    system = {
        "role": "system",
        "content":
            "You are an assistant that fills out job-application forms on my behalf.  "
            "I will give you a list of questions and their available options, plus my résumé summary.  "
            "For each question pick the option (or options) that best fit my background.  "
            "Return **only** valid JSON, in this exact shape:\n\n"
            "{\n"
            '  "answers": [\n'
            '    { "question": "<the full question text>",\n'
            '      "selected": "<one option>" | ["<opt1>","<opt2>"]\n'
            "    },\n"
            "    …\n"
            "  ]\n"
            "}"
    }
    user = {
        "role": "user",
        "content":
            "Résumé summary:\n\"\"\"\n" + RÉSUMÉ_SUMMARY + "\n\"\"\"\n\n"
            "Here are the questions + options:\n" +
            json.dumps(questions, indent=2)
    }

    client = OpenAI()
    rsp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[system, user],
        temperature=0.0
    )

    # ——— GPT-3.5-turbo usage logging ———
    try:
        usage = rsp.usage
        pt = usage.prompt_tokens
        ct = usage.completion_tokens
        tt = usage.total_tokens
        ir, orate = (0.03, 0.06) if "gpt-4" in rsp.model else (0.0015, 0.002)
        ic = pt * ir / 1000
        oc = ct * orate / 1000
        tc = ic + oc
        print(f"[{rsp.model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
              f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
    except Exception:
        print(f"[{rsp.model} usage] ⚠️ failed to read response.usage")
    # ———————————————————————

    raw = rsp.choices[0].message.content
    # strip any ```json fences if present:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        print("[RoleReq] ❌ could not parse JSON from LLM:")
        print(raw)
        return False

    answer_map = { ent["question"]: ent["selected"] 
                   for ent in data.get("answers", []) }

    # 4) apply each answer
    for q in questions:
        sel = answer_map.get(q["text"])
        if not sel:
            print(f'[RoleReq] no answer for "{q["text"]}" – skipping.')
            continue

        if isinstance(sel, list):
            # multi-select checkboxes
            for choice in sel:
                xpath = f"//label[contains(.,{json.dumps(choice)})]/preceding-sibling::input"
                driver.find_element(By.XPATH, xpath).click()
        else:
            # single <select> dropdown
            dd = driver.find_element(By.CSS_SELECTOR, f"select[id='{q['id']}']")
            for o in dd.find_elements(By.TAG_NAME, "option"):
                if o.text.strip() == sel:
                    o.click()
                    break

    # 5) click "Continue"
    btn = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "button[data-testid='continue-button']")))
    btn.click()
    return True 