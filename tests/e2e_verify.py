#!/usr/bin/env python3
"""
E2E Verification Test for Six Degrees of Wikipedia
Target: Taylor Swift -> Ho Chi Minh

This script uses Playwright to automate browser testing.
Exit Code 0 = SUCCESS (Path Found)
Exit Code 1 = FAIL (No Path / Connection Error)
"""

import sys
import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

async def run_e2e_test():
    """
    Runs the E2E test to verify Taylor Swift -> Ho Chi Minh path finding.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        try:
            print("🚀 Navigating to http://localhost:5173")
            await page.goto("http://localhost:5173", wait_until="networkidle", timeout=10000)
            
            print("📝 Entering 'Taylor Swift' in Start input")
            # Find the first input (Start Journey input)
            inputs = await page.locator('input[type="text"]').all()
            if len(inputs) < 2:
                print("❌ FAIL: Could not find both input fields")
                return 1
            
            start_input = inputs[0]
            await start_input.fill("Taylor Swift")
            await page.wait_for_timeout(500)  # Wait for autocomplete
            
            print("📝 Entering 'Ho Chi Minh' in End input")
            end_input = inputs[1]
            await end_input.fill("Ho Chi Minh")
            
            print("🔍 Clicking Search/Find Path button")
            # Try multiple button selectors
            button = None
            button_selectors = [
                'button:has-text("Search")',
                'button:has-text("Find Path")',
                'button:has-text("Find")',
                'button[type="submit"]',
                'button'
            ]
            
            for selector in button_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=3000)
                    if button:
                        break
                except:
                    continue
            
            if not button:
                print("❌ FAIL: Could not find Search button")
                return 1
            
            await button.click()
            
            print("⏳ Waiting up to 60 seconds for results...")
            
            # Wait for any result container to appear
            result_selectors = [
                'text="Ho Chi Minh"',  # Look for the target text
                '[class*="path"]',
                '[class*="result"]',
                '[class*="graph"]',
                '[id*="path"]',
                '[id*="result"]'
            ]
            
            result_found = False
            for selector in result_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=60000)
                    result_found = True
                    print(f"✅ Result container found: {selector}")
                    break
                except PlaywrightTimeoutError:
                    continue
            
            if not result_found:
                print("❌ FAIL: Timeout - No result container appeared within 60 seconds")
                return 1
            
            # Critical check: Verify "Ho Chi Minh" appears in the results area (not just input)
            page_content = await page.content()
            
            # Check if we can find "Ho Chi Minh" in a path/result context
            # (not just the input field)
            try:
                # Look for the text in any visible element that's not an input
                result_text = await page.locator('body :not(input):has-text("Ho Chi Minh")').first.text_content(timeout=5000)
                if result_text and "Ho Chi Minh" in result_text:
                    print("✅ SUCCESS: Path Found! 'Ho Chi Minh' appears in results.")
                    
                    # Try to get the full path for logging
                    try:
                        path_elements = await page.locator('[class*="path"] *').all_text_contents()
                        if path_elements:
                            print(f"📍 Path: {' -> '.join([p.strip() for p in path_elements if p.strip()])}")
                    except:
                        pass
                    
                    return 0
            except PlaywrightTimeoutError:
                pass
            
            # Fallback: Check if error message is displayed
            error_selectors = [
                'text="No path found"',
                'text="error"',
                '[class*="error"]'
            ]
            
            for selector in error_selectors:
                try:
                    error = await page.wait_for_selector(selector, timeout=2000)
                    if error:
                        error_text = await error.text_content()
                        print(f"❌ FAIL: Error message displayed: {error_text}")
                        return 1
                except:
                    continue
            
            print("❌ FAIL: 'Ho Chi Minh' not found in results (only in input)")
            return 1
            
        except PlaywrightTimeoutError as e:
            print(f"❌ FAIL: Timeout Error - {e}")
            return 1
        except Exception as e:
            print(f"❌ FAIL: Unexpected Error - {e}")
            import traceback
            traceback.print_exc()
            return 1
        finally:
            await browser.close()

def main():
    """Main entry point"""
    exit_code = asyncio.run(run_e2e_test())
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
