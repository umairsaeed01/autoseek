import os
import json
import hashlib
import time
from openai import OpenAI
from PyPDF2 import PdfReader

# ------------------------------------------------------------
# 1) PATHS & CONSTANTS
# ------------------------------------------------------------
RESUME_SUMMARY_PATH = os.path.abspath("./resume_summary.txt")
RESUME_PDF_PATH = os.path.abspath("./resume.pdf")

# ------------------------------------------------------------
# 2) LOAD OR GENERATE RÉSUMÉ SUMMARY
# ------------------------------------------------------------
RÉSUMÉ_SUMMARY = ""

# Check if we need to generate a new summary
need_new_summary = True

if os.path.exists(RESUME_SUMMARY_PATH):
    with open(RESUME_SUMMARY_PATH, "r", encoding="utf-8") as f:
        RÉSUMÉ_SUMMARY = f.read().strip()
        if RÉSUMÉ_SUMMARY:  # Only if we have actual content
            print(f"[DEBUG] Loaded résumé summary ({len(RÉSUMÉ_SUMMARY)} chars):")
            print(RÉSUMÉ_SUMMARY[:200], "…")
            need_new_summary = False
        else:
            print("[DEBUG] Found empty résumé summary file, will generate new summary")

if need_new_summary:
    print("[DEBUG] Generating new résumé summary from PDF...")
    # ------------------------------------------------------------
    # 3) LOAD AND EXTRACT TEXT FROM resume.pdf
    # ------------------------------------------------------------
    if not os.path.exists(RESUME_PDF_PATH):
        raise FileNotFoundError(f"Cannot find resume PDF at {RESUME_PDF_PATH}")

    reader = PdfReader(RESUME_PDF_PATH)
    raw_text = []
    for page in reader.pages:
        text = page.extract_text() or ""
        raw_text.append(text)
    raw_text = "\n".join(raw_text).strip()

    if not raw_text:
        raise RuntimeError("Extracted no text from resume.pdf. Check that the PDF is not corrupted.")

    print(f"[DEBUG] Extracted {len(raw_text)} chars from PDF")

    # ------------------------------------------------------------
    # 4) CALL GPT-3.5-TURBO TO PRODUCE A STRUCTURED SUMMARY
    # ------------------------------------------------------------
    llm = OpenAI()  # assumes your OPENAI_API_KEY is set in env

    # Build a prompt that asks for a multi-section résumé summary
    system_message = {
        "role": "system",
        "content": "You are a résumé-parsing assistant. Produce a structured summary under these headings: Education, Employment History, Projects, Skills (hard and soft). Return the summary in plain text format with clear section headers."
    }
    user_message = {
        "role": "user",
        "content": (
            "Below is the full text of my résumé (PDF-extracted). "
            "Please return a concise, multi-section summary under the exact headings:\n"
            "  • Education\n"
            "  • Employment History\n"
            "  • Projects\n"
            "  • Skills (separate hard vs. soft skills)\n\n"
            "Here is my résumé text:\n\n"
            "```\n"
            + raw_text[:25000]  # trim if it's extremely long; GPT-3.5-turbo can handle ~16k tokens 
            + "\n```"
        )
    }

    print("[DEBUG] Sending résumé text to GPT-3.5-turbo for summarization...")
    response = llm.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[system_message, user_message],
        temperature=0.0,
    )
    
    # ——— GPT-3.5-turbo usage logging ———
    try:
        usage = response.usage
        pt = usage.prompt_tokens
        ct = usage.completion_tokens
        tt = usage.total_tokens
        ir, orate = (0.03, 0.06) if "gpt-4" in response.model else (0.0015, 0.002)
        ic = pt * ir / 1000
        oc = ct * orate / 1000
        tc = ic + oc
        print(f"[{response.model} usage] prompt={pt}, completion={ct}, total={tt} tokens;"
              f" cost_input=${ic:.4f}, cost_output=${oc:.4f}, cost_total=${tc:.4f}")
    except Exception:
        print(f"[{response.model} usage] ⚠️ failed to read response.usage")
    # ———————————————————————

    RÉSUMÉ_SUMMARY = response.choices[0].message.content.strip()
    print(f"[DEBUG] Generated résumé summary ({len(RÉSUMÉ_SUMMARY)} chars):")
    print(RÉSUMÉ_SUMMARY[:200], "…")

    # ------------------------------------------------------------
    # 5) WRITE THE GENERATED SUMMARY TO resume_summary.txt
    # ------------------------------------------------------------
    with open(RESUME_SUMMARY_PATH, "w", encoding="utf-8") as f:
        f.write(RÉSUMÉ_SUMMARY)

    # ------------------------------------------------------------
    # 6) PRINT THE SUMMARY TO VERIFY
    # ------------------------------------------------------------
    print("\n" + "="*40)
    print("[DEBUG] Generated résumé summary (saved to resume_summary.txt):\n")
    print(RÉSUMÉ_SUMMARY)
    print("="*40 + "\n")

# At this point, RÉSUMÉ_SUMMARY is guaranteed to be non-empty
assert RÉSUMÉ_SUMMARY, "Résumé summary is still empty after summarization!" 