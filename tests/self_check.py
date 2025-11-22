import asyncio
from playwright.async_api import async_playwright
import sys

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Subscribe to console logs
        page.on("console", lambda msg: print(f"CONSOLE: {msg.text}"))
        page.on("pageerror", lambda exc: print(f"PAGE ERROR: {exc}"))

        print("Navigating to http://localhost:8000...")
        try:
            await page.goto("http://localhost:8000", timeout=60000)
        except Exception as e:
            print(f"Failed to load page: {e}")
            sys.exit(1)

        print("Page loaded. Entering search terms...")
        
        try:
            # Wait for inputs to be visible
            await page.wait_for_selector('input[placeholder="e.g., Taylor Swift"]', state='visible', timeout=30000)
        except Exception as e:
            print(f"Timeout waiting for inputs: {e}")
            print("Dumping body HTML:")
            print(await page.inner_html("body"))
            sys.exit(1)
        
        # Fill inputs
        await page.fill('input[placeholder="e.g., Taylor Swift"]', "Taylor Swift")
        await page.fill('input[placeholder="e.g., Kevin Bacon"]', "Ho Chi Minh")
        
        print("Clicking search...")
        # Click search button
        await page.click('button:has-text("Find Connection")')
        
        print("Waiting for results...")
        # Wait for result container or specific success element
        # We wait up to 60 seconds as requested
        try:
            # Look for "Ho Chi Minh" in the results area, or a specific path container
            # Adjust selector to be more specific if possible, e.g., .path-result
            await page.wait_for_selector('text="Ho Chi Minh"', timeout=60000)
            
            # Check if it's an error message or a valid path
            content = await page.content()
            if "No path found" in content or "Error" in content:
                print("Path not found or error occurred.")
                print(content[:500]) # Print snippet
                sys.exit(1)
                
            print("✅ Path found!")
            sys.exit(0)
            
        except Exception as e:
            print(f"Timeout or error waiting for results: {e}")
            sys.exit(1)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
