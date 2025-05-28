from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def handle_profile_page(driver):
    """
    Handle the SEEK profile page after document upload.
    Simply waits for and clicks the Continue button at the bottom.
    
    Args:
        driver: Selenium WebDriver instance
    """
    try:
        print("[Profile Handler] Processing profile page...")
        
        # Wait for the continue button to be clickable
        wait = WebDriverWait(driver, 10)
        btn = wait.until(EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button[data-testid='continue-button']")
        ))
        
        # Click the continue button
        btn.click()
        print("[Profile Handler] Clicked continue button on profile page")
        
        # Wait for navigation
        time.sleep(2)
        
        # Check if we're still on the profile page
        if "/apply/profile" in driver.current_url:
            print("[Profile Handler] Still on profile page, might need additional handling")
            return False
            
        print("[Profile Handler] Successfully navigated from profile page")
        return True
        
    except Exception as e:
        print(f"[Profile Handler] Error handling profile page: {e}")
        return False 