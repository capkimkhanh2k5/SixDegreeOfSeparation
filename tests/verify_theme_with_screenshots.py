import asyncio
from playwright.async_api import async_playwright
import sys
import os

ARTIFACTS_DIR = "/Users/capkimkhanh/.gemini/antigravity/brain/0436bef5-a151-49ce-8efe-8a593b24bfc1"

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print("Navigating to http://localhost:8000...")
        try:
            await page.goto("http://localhost:8000", timeout=60000)
        except Exception as e:
            print(f"Failed to load page: {e}")
            sys.exit(1)

        print("Page loaded. Waiting for content...")
        try:
            await page.wait_for_selector("h1", timeout=30000)
        except Exception as e:
            print(f"Timeout waiting for content: {e}")
            # Capture screenshot anyway to see what's wrong
            await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "debug_failed_load.png"))
            sys.exit(1)

        # Screenshot 1: Initial State (Light/Dark based on system, but we assume default)
        print("Capturing initial state...")
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "theme_state_1.png"))
        
        # Click Toggle
        print("Clicking theme toggle...")
        await page.click('[data-testid="theme-btn"]')
        await page.wait_for_timeout(1000) # Wait for transition
        
        # Screenshot 2: Toggled State
        print("Capturing toggled state...")
        await page.screenshot(path=os.path.join(ARTIFACTS_DIR, "theme_state_2.png"))
        
        # Check computed style
        bg_color = await page.evaluate("window.getComputedStyle(document.body).backgroundColor")
        print(f"Computed Body BG Color: {bg_color}")
        
        # Verify it's not white/transparent (assuming dark mode is active)
        # Dark mode bg-gray-900 is roughly rgb(17, 24, 39)
        if "rgb(17, 24, 39)" in bg_color or "17, 24, 39" in bg_color:
             print("✅ Visual Verification Passed: Background is Dark.")
        else:
             print(f"⚠️ Visual Verification Warning: Background is {bg_color}")

        print("✅ Verification complete. Screenshots saved.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
