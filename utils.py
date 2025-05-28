# utils.py

import os
import time
from llm_agent import analyze_page_with_context # Use the new function name


def save_snapshot(driver, step_name):
    html_dir = f"resources/html/seek_application"
    ss_dir = f"resources/screenshots/seek_application"
    os.makedirs(html_dir, exist_ok=True)
    os.makedirs(ss_dir, exist_ok=True)

    timestamp = step_name
    html_path = f"{html_dir}/AI-Engineer-Intelqe_{timestamp}.html"
    ss_path = f"{ss_dir}/AI-Engineer-Intelqe_{timestamp}.png"

    with open(html_path, "w") as f:
        f.write(driver.page_source)

    driver.save_screenshot(ss_path)
    return html_path, ss_path


def analyze_state_with_llm(driver):
    html_path, image_path = save_snapshot(driver, step_name=f"analyze_{int(time.time())}")
    response_text = analyze_page_with_context(driver, {
        "html_path": html_path,
        "image_path": image_path
    })

    return {
        "screenshot": image_path,
        "html": html_path,
        "suggested_action": response_text
    }