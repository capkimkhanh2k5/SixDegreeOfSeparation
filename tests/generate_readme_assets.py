import asyncio
from playwright.async_api import async_playwright
import os

ASSETS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../assets"))

async def generate_assets():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        print(f"Saving assets to: {ASSETS_DIR}")
        if not os.path.exists(ASSETS_DIR):
            os.makedirs(ASSETS_DIR)

        # 1. Home Page - Light Mode (Default)
        print("Capturing Home Page (Light)...")
        try:
            await page.goto("http://localhost:8000", wait_until="networkidle")
            # Ensure we are in light mode (if there's a toggle, we might need to force it, but usually default is light or system)
            # Let's assume default is fine for now, or we can try to toggle if we know the selector.
            # Based on previous files, there is a theme toggle [data-testid="theme-btn"]
            
            # Wait a bit for animations
            await page.wait_for_timeout(2000)
            await page.screenshot(path=os.path.join(ASSETS_DIR, "home_light.png"))
        except Exception as e:
            print(f"Error capturing home_light: {e}")

        # 2. Home Page - Dark Mode
        print("Capturing Home Page (Dark)...")
        try:
            # Click theme toggle
            await page.click('[data-testid="theme-btn"]')
            await page.wait_for_timeout(1000) # Wait for transition
            await page.screenshot(path=os.path.join(ASSETS_DIR, "home_dark.png"))
        except Exception as e:
            print(f"Error capturing home_dark: {e}")

        # 3. Search Result (Interactive)
        print("Capturing Search Result...")
        try:
            # Reload to reset state or just use current state
            # We are in dark mode now, which looks cool for results
            
            # Fill inputs
            inputs = await page.locator('input[type="text"]').all()
            if len(inputs) >= 2:
                await inputs[0].fill("Taylor Swift")
                await page.wait_for_timeout(500)
                await inputs[1].fill("Kanye West") # Shorter path hopefully
                
                # Click Search
                # Try to find the button again
                button = await page.wait_for_selector('button:has-text("Find Connection"), button:has-text("Search")', timeout=3000)
                if button:
                    await button.click()
                    
                    # Wait for results
                    # Wait for "Kanye West" to appear in the graph/result area
                    try:
                        await page.wait_for_selector('text="Kanye West"', timeout=60000)
                        await page.wait_for_timeout(2000) # Wait for layout to settle
                        await page.screenshot(path=os.path.join(ASSETS_DIR, "search_result.png"))
                    except Exception as e:
                         print(f"Timeout waiting for search results: {e}")
            else:
                print("Could not find inputs for search result capture")

        except Exception as e:
            print(f"Error capturing search_result: {e}")

        await browser.close()

async def record_video():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Record video to assets directory
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=ASSETS_DIR,
            record_video_size={"width": 1280, "height": 800}
        )
        page = await context.new_page()

        print("Recording Video...")
        try:
            await page.goto("http://localhost:8000", wait_until="networkidle")
            
            # Perform search
            inputs = await page.locator('input[type="text"]').all()
            if len(inputs) >= 2:
                # Type slowly to look natural
                await inputs[0].type("Taylor Swift", delay=100)
                await page.wait_for_timeout(500)
                await inputs[1].type("Kanye West", delay=100)
                await page.wait_for_timeout(500)
                
                button = await page.wait_for_selector('button:has-text("Find Connection"), button:has-text("Search")', timeout=3000)
                if button:
                    await button.click()
                    
                    # Wait for results and let animation play
                    await page.wait_for_selector('text="Kanye West"', timeout=60000)
                    await page.wait_for_timeout(5000) # Record 5 seconds of result
            
        except Exception as e:
            print(f"Error recording video: {e}")
        
        await context.close() # Save video
        await browser.close()
        
        # Rename the video file (it has a random name)
        # Find the latest .webm file in assets
        files = [f for f in os.listdir(ASSETS_DIR) if f.endswith(".webm")]
        if files:
            # Assuming the last one is ours or we clean up before
            latest_video = max([os.path.join(ASSETS_DIR, f) for f in files], key=os.path.getctime)
            new_name = os.path.join(ASSETS_DIR, "demo.webm")
            if os.path.exists(new_name):
                os.remove(new_name)
            os.rename(latest_video, new_name)
            print(f"Video saved to {new_name}")

if __name__ == "__main__":
    asyncio.run(generate_assets())
    asyncio.run(record_video())
