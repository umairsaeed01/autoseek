import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def handle_review_page(driver):
    """
    We're on /apply/review.
    Wait for & click the Submit application button.
    """
    try:
        print("[Review Handler] Processing review page...")
        
        # Wait for the submit button to be clickable using data-testid
        wait = WebDriverWait(driver, 15)
        submit_btn = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR,
            "button[data-testid='review-submit-application']"
        )))
        
        # Click the submit button
        submit_btn.click()
        print("[Review Handler] Clicked Submit application")
        
        # Let the click register
        time.sleep(1)
        
        # Check if we're still on the review page
        if "/apply/review" in driver.current_url:
            print("[Review Handler] Still on review page, might need additional handling")
            return False
            
        print("[Review Handler] Successfully submitted application")
        return True
        
    except Exception as e:
        print(f"[Review Handler] Error handling review page: {e}")
        return False 