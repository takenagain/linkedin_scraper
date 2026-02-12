#!/usr/bin/env python3
"""
Diagnostic script to fetch live LinkedIn HTML for selector analysis.

This script:
1. Authenticates to LinkedIn using the li_at cookie from environment
2. Navigates to a profile and all its detail pages
3. Saves HTML content and screenshots for analysis
4. Tests current selectors and reports which ones work/fail
5. Generates a selector report JSON file

Usage:
    cd linkedin_scraper
    source .env  # or export LINKEDIN_COOKIE=your_cookie
    uv run python scripts/fetch_live_html.py https://linkedin.com/in/username

Environment Variables:
    LINKEDIN_COOKIE: The li_at cookie value from an authenticated LinkedIn session
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import Page, async_playwright

# Default profile URL to scrape if none provided
DEFAULT_PROFILE_URL = "https://www.linkedin.com/in/ritajit-majumdar-59683442/"


async def human_delay(min_seconds: float = 0.5, max_seconds: float = 10.0) -> None:
    """
    Introduce a human-like random delay between actions.

    This helps avoid rate limiting and scraping detection by LinkedIn.
    The delay follows a slightly weighted distribution toward shorter delays
    while still having occasional longer pauses.
    """
    # Use a beta distribution to weight toward shorter delays but allow longer ones
    # Beta(2, 5) gives a distribution weighted toward lower values
    beta_sample = random.betavariate(2, 5)
    delay = min_seconds + (max_seconds - min_seconds) * beta_sample
    print(f"   ⏳ Waiting {delay:.1f}s (human-like delay)...")
    await asyncio.sleep(delay)


# Selectors to test from person.py
SELECTORS_TO_TEST = {
    # Main profile
    "name_h1": "h1",
    "location_old": ".text-body-small.inline.t-black--light.break-words",
    "location_fallback": ".text-body-small",
    "profile_card": "[data-view-name='profile-card']",
    "open_to_work_img": ".pv-top-card-profile-picture img",
    # Section headings
    "experience_heading": "h2:has-text('Experience')",
    "education_heading": "h2:has-text('Education')",
    "interests_heading": "h2:has-text('Interests')",
    # List structures
    "pvs_list_container": ".pvs-list__container",
    "pvs_list_item": ".pvs-list__paged-list-item",
    "profile_entity": "div[data-view-name='profile-component-entity']",
    # Text extraction
    "aria_hidden_span": "span[aria-hidden='true']",
    # Tabs and dialogs
    "tab_role": "[role='tab']",
    "tabpanel_role": "[role='tabpanel']",
    "dialog_role": "[role='dialog']",
    "dialog_element": "dialog",
    # Links
    "any_link": "a",
    "list_items_ul": "ul > li",
    "list_items_ol": "ol > li",
    # Main element
    "main": "main",
}

# Pages to fetch
PAGES_TO_FETCH = [
    ("profile_main", ""),
    ("details_experience", "details/experience/"),
    ("details_education", "details/education/"),
    ("details_interests", "details/interests/"),
    ("details_certifications", "details/certifications/"),
    ("details_honors", "details/honors/"),
    ("details_publications", "details/publications/"),
    ("details_projects", "details/projects/"),
    ("overlay_contact", "overlay/contact-info/"),
]


async def setup_browser_with_cookie(cookie: str):
    """Set up Playwright browser with LinkedIn cookie."""
    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    )

    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    )

    # Set the li_at cookie
    await context.add_cookies(
        [
            {
                "name": "li_at",
                "value": cookie,
                "domain": ".linkedin.com",
                "path": "/",
                "httpOnly": True,
                "secure": True,
            }
        ]
    )

    page = await context.new_page()

    return playwright, browser, context, page


async def test_selectors(page: Page, selectors: dict[str, str]) -> dict[str, dict]:
    """Test which selectors find elements on the current page."""
    results = {}

    for name, selector in selectors.items():
        try:
            elements = await page.locator(selector).all()
            count = len(elements)

            # Get sample text from first element if found
            sample_text = None
            if count > 0:
                try:
                    text = await elements[0].text_content()
                    if text:
                        sample_text = text.strip()[:100]
                except:
                    pass

            results[name] = {
                "selector": selector,
                "found": count > 0,
                "count": count,
                "sample_text": sample_text,
            }
        except Exception as e:
            results[name] = {
                "selector": selector,
                "found": False,
                "count": 0,
                "error": str(e),
            }

    return results


async def save_page_content(
    page: Page,
    output_dir: Path,
    page_name: str,
    timestamp: str,
) -> tuple[Path, Path]:
    """Save page HTML and screenshot."""
    html_path = output_dir / f"{page_name}_{timestamp}.html"
    screenshot_path = output_dir / f"{page_name}_{timestamp}.png"

    # Save HTML
    html_content = await page.content()
    html_path.write_text(html_content, encoding="utf-8")

    # Save screenshot
    await page.screenshot(path=str(screenshot_path), full_page=True)

    return html_path, screenshot_path


async def analyze_page_structure(page: Page) -> dict:
    """Analyze the current page structure for debugging."""
    analysis = {}

    # Get all headings
    headings = {}
    for level in range(1, 7):
        h_elements = await page.locator(f"h{level}").all()
        if h_elements:
            texts = []
            for el in h_elements[:10]:  # Limit to first 10
                try:
                    text = await el.text_content()
                    if text:
                        texts.append(text.strip()[:50])
                except:
                    pass
            if texts:
                headings[f"h{level}"] = texts
    analysis["headings"] = headings

    # Get data attributes
    data_attrs = await page.evaluate("""
        () => {
            const elements = document.querySelectorAll('[data-view-name]');
            const attrs = new Set();
            elements.forEach(el => attrs.add(el.getAttribute('data-view-name')));
            return Array.from(attrs).slice(0, 20);
        }
    """)
    analysis["data_view_names"] = data_attrs

    # Get role attributes
    roles = await page.evaluate("""
        () => {
            const elements = document.querySelectorAll('[role]');
            const roles = {};
            elements.forEach(el => {
                const role = el.getAttribute('role');
                roles[role] = (roles[role] || 0) + 1;
            });
            return roles;
        }
    """)
    analysis["roles"] = roles

    # Get common class patterns
    classes = await page.evaluate("""
        () => {
            const elements = document.querySelectorAll('[class*="pvs-"], [class*="pv-"], [class*="artdeco-"]');
            const classSet = new Set();
            elements.forEach(el => {
                el.classList.forEach(cls => {
                    if (cls.startsWith('pvs-') || cls.startsWith('pv-') || cls.startsWith('artdeco-')) {
                        classSet.add(cls);
                    }
                });
            });
            return Array.from(classSet).slice(0, 50);
        }
    """)
    analysis["linkedin_classes"] = classes

    return analysis


async def fetch_profile_html(
    profile_url: str,
    output_dir: Path,
    cookie: str,
) -> dict:
    """
    Fetch and save HTML from all profile sections.

    Args:
        profile_url: LinkedIn profile URL
        output_dir: Directory to save HTML and screenshots
        cookie: LinkedIn li_at cookie value

    Returns:
        Dictionary with results for each page
    """
    # Normalize URL
    if not profile_url.endswith("/"):
        profile_url += "/"

    print(f"\n🕐 Note: Using human-like random delays (0.5-10s) between actions")
    print(f"   to avoid LinkedIn rate limiting and scraping detection.\n")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "timestamp": datetime.now().isoformat(),
        "profile_url": profile_url,
        "pages": {},
        "selector_tests": {},
        "structure_analysis": {},
    }

    print(f"\n{'=' * 60}")
    print(f"LinkedIn HTML Diagnostic Tool")
    print(f"{'=' * 60}")
    print(f"Profile: {profile_url}")
    print(f"Output: {output_dir}")
    print(f"Timestamp: {timestamp}")
    print(f"{'=' * 60}\n")

    playwright, browser, context, page = await setup_browser_with_cookie(cookie)

    try:
        for page_idx, (page_name, page_path) in enumerate(PAGES_TO_FETCH):
            page_url = urljoin(profile_url, page_path)
            print(f"\n📄 Fetching: {page_name} ({page_idx + 1}/{len(PAGES_TO_FETCH)})")
            print(f"   URL: {page_url}")

            # Add human-like delay between page navigations (except for first page)
            if page_idx > 0:
                await human_delay(1.0, 5.0)

            try:
                # Navigate to page
                await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)

                # Wait for main content with human-like delay
                try:
                    await page.wait_for_selector("main", timeout=10000)
                except:
                    print(f"   ⚠️  'main' element not found, continuing anyway...")

                # Human-like wait for dynamic content to load
                await human_delay(1.5, 4.0)

                # Scroll to load lazy content with human-like behavior
                await page.evaluate(
                    "window.scrollTo(0, document.body.scrollHeight / 2)"
                )
                await human_delay(0.5, 2.0)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await human_delay(0.8, 2.5)

                # Save content
                html_path, screenshot_path = await save_page_content(
                    page, output_dir, page_name, timestamp
                )
                print(f"   ✅ Saved HTML: {html_path.name}")
                print(f"   ✅ Saved screenshot: {screenshot_path.name}")

                # Test selectors
                selector_results = await test_selectors(page, SELECTORS_TO_TEST)
                results["selector_tests"][page_name] = selector_results

                # Count working selectors
                working = sum(1 for r in selector_results.values() if r.get("found"))
                total = len(selector_results)
                print(f"   📊 Selectors: {working}/{total} found elements")

                # Analyze structure
                structure = await analyze_page_structure(page)
                results["structure_analysis"][page_name] = structure

                results["pages"][page_name] = {
                    "url": page_url,
                    "html_file": str(html_path),
                    "screenshot_file": str(screenshot_path),
                    "success": True,
                }

            except Exception as e:
                print(f"   ❌ Error: {e}")
                results["pages"][page_name] = {
                    "url": page_url,
                    "success": False,
                    "error": str(e),
                }

        # Generate summary report
        print(f"\n{'=' * 60}")
        print("SELECTOR SUMMARY")
        print(f"{'=' * 60}")

        # Aggregate selector results across pages
        selector_summary = {}
        for selector_name in SELECTORS_TO_TEST:
            found_on_pages = []
            for page_name, page_results in results["selector_tests"].items():
                if page_results.get(selector_name, {}).get("found"):
                    found_on_pages.append(page_name)

            selector_summary[selector_name] = {
                "selector": SELECTORS_TO_TEST[selector_name],
                "found_on": found_on_pages,
                "working": len(found_on_pages) > 0,
            }

            status = "✅" if found_on_pages else "❌"
            print(f"  {status} {selector_name}: {SELECTORS_TO_TEST[selector_name]}")
            if found_on_pages:
                print(f"      Found on: {', '.join(found_on_pages)}")

        results["selector_summary"] = selector_summary

        # Save report
        report_path = output_dir / f"selector_report_{timestamp}.json"
        with open(report_path, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\n📋 Report saved: {report_path.name}")

    finally:
        await browser.close()
        await playwright.stop()

    return results


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python fetch_live_html.py [profile_url] [output_dir]")
        print("\nExample:")
        print("  python fetch_live_html.py https://linkedin.com/in/username")
        print(f"\nIf no profile URL is provided, defaults to: {DEFAULT_PROFILE_URL}")
        print("\nEnvironment:")
        print("  LINKEDIN_COOKIE: Required - the li_at cookie value")
        # Don't exit - use default profile URL
        profile_url = DEFAULT_PROFILE_URL
        output_dir = Path("output")
    else:
        profile_url = sys.argv[1]
        output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("output")

    # Get cookie from environment
    cookie = os.environ.get("LINKEDIN_COOKIE")
    if not cookie:
        # Try loading from .env
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            print(f"Loading cookie from {env_path}")
            with open(env_path) as f:
                for line in f:
                    if line.startswith("LINKEDIN_COOKIE="):
                        cookie = line.split("=", 1)[1].strip().strip('"').strip("'")
                        break

    if not cookie:
        print("❌ Error: LINKEDIN_COOKIE environment variable not set")
        print("\nTo set the cookie:")
        print("  export LINKEDIN_COOKIE=your_li_at_cookie_value")
        print("\nOr create a .env file with:")
        print('  LINKEDIN_COOKIE="your_li_at_cookie_value"')
        sys.exit(1)

    print(f"🔑 Cookie found (length: {len(cookie)})")

    await fetch_profile_html(profile_url, output_dir, cookie)

    print(f"\n{'=' * 60}")
    print("✅ Done! Check the output directory for HTML files and report.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
