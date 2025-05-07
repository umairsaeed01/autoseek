import os
from selenium.webdriver.common.by import By

def capture_step(driver, session_dir: str, step_name: str):
    """
    Capture a full-page screenshot and HTML source of the current page.
    Saves files into the given session directory with the step_name prefix.
    """
    # Ensure the session directory exists
    os.makedirs(session_dir, exist_ok=True)

    # Define file paths
    img_path = os.path.join(session_dir, f"{step_name}.png")
    html_path = os.path.join(session_dir, f"{step_name}.html")

    # Adjust window size to capture full page
    try:
        # Execute JS to get total page width/height for full-page screenshot
        total_width = driver.execute_script("return document.body.parentNode.scrollWidth")
        total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
        driver.set_window_size(total_width, total_height)
    except Exception as e:
        print(f"Warning: Could not resize window for full screenshot: {e}")
        # Continue anyway with current window size

    # Take screenshot of the full page by screenshotting the <body> element (to avoid scrollbar in image)
    try:
        body = driver.find_element(By.TAG_NAME, "body")
        body.screenshot(img_path)
        print(f"Saved screenshot: {img_path}")
    except Exception as e:
        print(f"[Error] Failed to capture screenshot: {e}")

    # Save HTML source
    try:
        html_source = driver.page_source
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_source)
        print(f"Saved page HTML: {html_path}")
    except Exception as e:
        print(f"[Error] Failed to save HTML source: {e}")

# Example usage (if running standalone for a test):
if __name__ == "__main__":
    # Assume `driver` is already at the target page from previous step.
    # We would not normally call this as a standalone script without an existing driver,
    # but for demonstration, let's say driver is passed or globally available.
    try:
        session_folder = "resources/session_001"
        # For first page, we label the step with job title and step number.
        job_title_slug = "job-title"  # TODO: update with actual job title or ID, formatted filesystem-safe.
        step_label = f"{job_title_slug}_step1"
        capture_step(driver, session_folder, step_label)
    finally:
        driver.quit()  # close browser after capturing if this were standalone