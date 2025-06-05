import os
import json
import hashlib
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from openai import OpenAI

# ------------------------------------------------------------
# 1) LOAD (OR FALL BACK TO) A RÉSUMÉ SUMMARY
# ------------------------------------------------------------
RESUME_SUMMARY_PATH = os.path.abspath("./resume_summary.txt")
if os.path.exists(RESUME_SUMMARY_PATH):
    with open(RESUME_SUMMARY_PATH, "r", encoding="utf-8") as f:
        RÉSUMÉ_SUMMARY = f.read().strip()
else:
    RÉSUMÉ_SUMMARY = (
        "Software engineer with 3 years of Python/JavaScript experience; "
        "holds a graduate temporary work visa in Australia; "
        "ready to start immediately; "
        "current Police Check valid."
    )

# ------------------------------------------------------------
# 2) CACHE FOLDER FOR ROLE REQS
# ------------------------------------------------------------
CACHE_DIR = os.path.abspath("./role_requirements_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ------------------------------------------------------------
# 3) MAIN HANDLER FUNCTION
# ------------------------------------------------------------
def handle_role_requirements_page(driver):
    """
    This function is called when driver.current_url contains '/apply/role-requirements'.
    It scrapes all questions + their answer-options, then either:
      • Loads cached answers (if we've seen this question set before), or
      • Calls the LLM once to pick best answers, caches it, and uses those answers.
    Then it clicks/selects each option on the page.
    Returns True on success, False on error.
    """
    try:
        wait = WebDriverWait(driver, 10)

        # 1) WAIT FOR AT LEAST ONE QUESTION LABEL TO APPEAR
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "label[for^='question-']")))
        except TimeoutException:
            print("[RoleReq] No question labels appeared within 10s.")
            return False

        # 2) FIND ALL QUESTION LABELS
        label_elems = driver.find_elements(By.CSS_SELECTOR, "label[for^='question-']")
        questions = []  # each = {"text": str, "options": [str,...], "label_for": str}
        for lbl in label_elems:
            q_for = lbl.get_attribute("for").strip()
            q_text = lbl.text.strip()
            if not q_for or not q_text:
                continue

            # 2a) Look for a <select id="{q_for}"> inside the same form
            opts = []
            try:
                select_elem = driver.find_element(By.CSS_SELECTOR, f"select[id='{q_for}']")
                for opt in select_elem.find_elements(By.TAG_NAME, "option"):
                    txt = opt.text.strip()
                    if txt:
                        opts.append(txt)
            except:
                # No <select> with that id; fall back to searching radio inputs
                radio_name = q_for.replace("question-", "questionnaire.")
                try:
                    radios = driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{radio_name}']")
                    for r in radios:
                        rid = r.get_attribute("id")
                        label_text = ""
                        if rid:
                            try:
                                label_text = driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.strip()
                            except:
                                label_text = ""
                        if not label_text:
                            # fallback: parent span or container text
                            try:
                                label_text = r.find_element(By.XPATH, "./..").text.strip()
                            except:
                                label_text = ""
                        if label_text:
                            opts.append(label_text)
                except:
                    pass

            if opts:
                questions.append({
                    "text": q_text,
                    "options": opts,
                    "label_for": q_for
                })

        if not questions:
            print("[RoleReq] Found no questions with options.")
            return False

        # 3) COMPUTE A FINGERPRINT FOR THIS SET OF QUESTIONS
        fingerprint_source = ""
        for q in questions:
            fingerprint_source += q["text"] + "|" + "|".join(q["options"]) + "||"
        fp = hashlib.sha1(fingerprint_source.encode("utf-8")).hexdigest()[:12]
        cache_path = os.path.join(CACHE_DIR, f"{fp}.json")

        # 4) IF CACHED, LOAD answer_map; ELSE, CALL LLM ONCE AND SAVE
        if os.path.exists(cache_path):
            with open(cache_path, "r", encoding="utf-8") as f:
                answer_map = json.load(f)
            print(f"[RoleReq] Loaded cached answers for fingerprint {fp}")
        else:
            # Build a single prompt: résumé summary + each Q + its options.
            prompt_lines = [
                "You are an assistant filling out my job-application form.",
                "Here is a short summary of my résumé:",
                f"\"\"\"\n{RÉSUMÉ_SUMMARY}\n\"\"\"",
                "",
                "Below are several questions and their possible options. For each question, select exactly one option that best matches my résumé.",
                ""
            ]
            for q in questions:
                prompt_lines.append(f"Question: {q['text']}")
                prompt_lines.append("Options:")
                for opt in q["options"]:
                    prompt_lines.append(f"- {opt}")
                prompt_lines.append("")

            full_prompt = "\n".join(prompt_lines)

            # Call GPT-4o once, ask for JSON
            llm = OpenAI()
            response = llm.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a JSON-output agent. "
                            "When you reply, output exactly valid JSON with a top-level key \"answers\" "
                            "whose value is an array of objects like {\"question\": \"<question text>\", "
                            "\"selected_option\": \"<one chosen option>\"}. "
                            "Do not include any extraneous text."
                        )
                    },
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.0
            )
            text_out = response.choices[0].message.content
            parsed = json.loads(text_out)
            answers_list = parsed.get("answers", [])
            # Convert to { question_text: selected_option }
            answer_map = {a["question"]: a["selected_option"] for a in answers_list}

            # Cache it
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(answer_map, f, indent=2, ensure_ascii=False)
            print(f"[RoleReq] Saved new cache under {cache_path}")

        # 5) CLICK/SELECT EACH ANSWER ON THE PAGE
        for q in questions:
            chosen = answer_map.get(q["text"])
            if not chosen:
                print(f"[RoleReq] No cached choice for: \"{q['text']}\" → skipping.")
                continue

            # 5a) Try to click the <option> in its <select>
            clicked = False
            try:
                sel = driver.find_element(By.CSS_SELECTOR, f"select[id='{q['label_for']}']")
                for opt in sel.find_elements(By.TAG_NAME, "option"):
                    if opt.text.strip() == chosen:
                        opt.click()
                        clicked = True
                        break
            except:
                pass

            if clicked:
                continue

            # 5b) Otherwise, click the radio whose label text == chosen
            try:
                radio_name = q["label_for"].replace("question-", "questionnaire.")
                radios = driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{radio_name}']")
                for r in radios:
                    rid = r.get_attribute("id")
                    lab_text = ""
                    if rid:
                        try:
                            lab_text = driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.strip()
                        except:
                            lab_text = ""
                    if not lab_text:
                        try:
                            lab_text = r.find_element(By.XPATH, "./..").text.strip()
                        except:
                            lab_text = ""
                    if lab_text == chosen:
                        r.click()
                        clicked = True
                        break
                if not clicked:
                    print(f"[RoleReq] Could not match radio label \"{chosen}\" for question \"{q['text']}\".")
            except Exception as e:
                print(f"[RoleReq] Error clicking radio for \"{q['text']}\": {e}")

        # 6) FINAL "Continue" CLICK on role-requirements form
        try:
            cont_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-testid='continue-button']"))
            )
            cont_btn.click()
            print("[RoleReq] Clicked Continue after answering all questions.")
        except Exception as e:
            print(f"[RoleReq] Could not click Continue: {e}")

        return True

    except Exception as e:
        print(f"[RoleReq] ERROR in handle_role_requirements_page: {e}")
        return False 