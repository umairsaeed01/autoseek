import json
import re
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI
from resume_summarizer import RÉSUMÉ_SUMMARY

def handle_dynamic_questions(driver):
    wait = WebDriverWait(driver, 10)
    form = driver.find_element(By.CSS_SELECTOR, "form")
    questions = []

    # --- single-choice selects ---
    for sel in form.find_elements(By.TAG_NAME, "select"):
        q_text = sel.find_element(By.XPATH, "preceding::strong[1]").text.strip()
        name  = sel.get_attribute("name")
        options = [
            opt.text.strip()
            for opt in sel.find_elements(By.TAG_NAME, "option")
            if opt.get_attribute("value")
        ]
        questions.append({
            "question": q_text,
            "type"    : "select",
            "name"    : name,
            "options" : options
        })

    # --- multi-choice checkboxes ---
    # assume each question block shares one <strong> for the question text
    seen = set()
    for cb in form.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
        # find the nearest ancestor that contains the question <strong>
        wrapper = cb.find_element(By.XPATH, "ancestor::div[.//strong][1]")
        q_text = wrapper.find_element(By.TAG_NAME, "strong").text.strip()
        if q_text in seen:
            continue
        seen.add(q_text)

        # collect all inputs + labels under this wrapper
        opts = []
        for inp in wrapper.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            opt_id = inp.get_attribute("id")
            label = wrapper.find_element(By.CSS_SELECTOR, f"label[for='{opt_id}']").text.strip()
            opts.append({"id": opt_id, "label": label})

        questions.append({
            "question": q_text,
            "type"    : "multiselect",
            "options" : opts
        })

    if not questions:
        print("[Dynamic] No questions found on page")
        return False

    print(f"[Dynamic] Found {len(questions)} questions to answer")

    system_msg = {
        "role": "system",
        "content": """
You are a job-application assistant. You will be given a JSON array of questions of two kinds:
- type "select": choose exactly one of the provided options.
- type "multiselect": choose zero or more items; return `selected` as an array of label strings.

Respond **only** with a JSON object of the form:
```json
{ "answers": [ { "question": "...", "selected": ... }, … ] }
```"""
    }

    user_msg = {
        "role": "user",
        "content": (
            "Résumé summary:\n\"\"\"\n" + RÉSUMÉ_SUMMARY + "\n\"\"\"\n\n"
            + json.dumps(questions, indent=2)
        )
    }

    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[system_msg, user_msg],
        temperature=0.0
    )

    # ——— GPT-3.5-turbo usage logging ———
    try:
        usage = resp.usage
        pt = usage.prompt_tokens
        ct = usage.completion_tokens
        tt = usage.total_tokens
        ir, orate = (0.03, 0.06) if "gpt-4" in resp.model else (0.0015, 0.002)
        ic = pt * ir / 1000
        oc = ct * orate / 1000
        tc = ic + oc
        print(f"[{resp.model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
              f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
    except Exception:
        print(f"[{resp.model} usage] ⚠️ failed to read response.usage")
    # ———————————————————————

    raw = resp.choices[0].message.content
    print("[Dynamic] LLM raw response:\n", raw)   # Debug print

    # strip markdown fences if present
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", raw, re.DOTALL)
    if m:
        raw = m.group(1)
        print("[Dynamic] Extracted JSON from code fence")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print("[Dynamic] JSON parse error:", e)
        print("[Dynamic] full raw:", raw)
        return False

    for ans in data["answers"]:
        q_text = ans["question"]
        # find the scraped question entry again
        entry = next(e for e in questions if e["question"] == q_text)

        if entry["type"] == "select":
            select_el = form.find_element(By.NAME, entry["name"])
            select_el.send_keys(ans["selected"])

        elif entry["type"] == "multiselect":
            # ans["selected"] is a list of labels
            for choice in ans["selected"]:
                opt = next(o for o in entry["options"] if o["label"] == choice)
                checkbox = driver.find_element(By.ID, opt["id"])
                if not checkbox.is_selected():
                    checkbox.click()

    # Click Continue using data-testid selector
    continue_btn = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='continue-button']"))
    )
    continue_btn.click()
    wait.until(EC.staleness_of(form))
    return True 