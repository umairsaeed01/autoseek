# page_capture.py (final version with structured paths and slugged titles)
import os
from selenium.webdriver.common.by import By
from file_utils import slugify_title, ensure_dir, get_unique_filename

def save_page_snapshot(driver, job_id, job_title, step):
    """
    Save current page HTML and screenshot in a structured folder:
    - HTML in resources/html/<job_id>/
    - Screenshot in resources/screenshots/<job_id>/
    Filenames include a slug of the job title and step.
    """
    # Prepare directories
    base_html_dir = os.path.join("resources", "html", str(job_id))
    base_screenshot_dir = os.path.join("resources", "screenshots", str(job_id))
    ensure_dir(base_html_dir)
    ensure_dir(base_screenshot_dir)

    # Generate a slug for the job title for filenames
    slug_title = slugify_title(job_title)
    if not slug_title:
        slug_title = str(job_id)  # fallback to job_id if title is empty

    # Compose base name for files (e.g., "Software-Engineer_step1")
    base_name = f"{slug_title}_step{step}"

    # Get unique file paths to avoid overwrite
    html_path = get_unique_filename(base_html_dir, base_name, "html")
    screenshot_path = get_unique_filename(base_screenshot_dir, base_name, "png")

    # Capture content
    html_content = driver.page_source
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    # Disable window resizing
    # driver.set_window_size(1920, 1080)  # Comment out or remove this line

    # Take full-page screenshot
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.screenshot(screenshot_path)
    except Exception:
        driver.save_screenshot(screenshot_path)

    print(f"Saved page snapshot: HTML -> {html_path}, Screenshot -> {screenshot_path}")
    return html_path, screenshot_path