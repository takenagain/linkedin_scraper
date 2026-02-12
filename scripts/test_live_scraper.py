#!/usr/bin/env python3
"""
Test script to verify the updated PersonScraper works with live LinkedIn profiles.

This script:
1. Authenticates to LinkedIn using the li_at cookie from environment
2. Scrapes a profile using the PersonScraper
3. Prints all scraped data for verification

Usage:
    cd linkedin_scraper
    source .env  # or export LINKEDIN_COOKIE=your_cookie
    uv run python scripts/test_live_scraper.py [profile_url]

If no profile URL is provided, defaults to: https://www.linkedin.com/in/ritajit-majumdar-59683442/

Environment Variables:
    LINKEDIN_COOKIE: The li_at cookie value from an authenticated LinkedIn session
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from linkedin_scraper import (
    BrowserManager,
    ConsoleCallback,
    PersonScraper,
    login_with_cookie,
)
from linkedin_scraper.core.exceptions import AuthenticationError, ScrapingError

# Default profile URL to scrape if none provided
DEFAULT_PROFILE_URL = "https://www.linkedin.com/in/ritajit-majumdar-59683442/"


async def test_scraper(profile_url: str, cookie: str) -> None:
    """Test the PersonScraper against a live profile."""

    print(f"\n{'=' * 60}")
    print("LinkedIn Scraper Live Test")
    print(f"{'=' * 60}")
    print(f"Profile: {profile_url}")
    print(f"Cookie length: {len(cookie)}")
    print(f"{'=' * 60}\n")

    async with BrowserManager(headless=True) as browser:
        page = browser.page

        # Authenticate
        print("🔐 Authenticating with cookie...")
        try:
            await login_with_cookie(page, cookie)
            print("✅ Authentication successful\n")
        except AuthenticationError as e:
            print(f"❌ Authentication failed: {e}")
            return

        # Create scraper with console callback for progress
        callback = ConsoleCallback()
        scraper = PersonScraper(page, callback)

        # Scrape profile
        print("🔍 Scraping profile...")
        try:
            person = await scraper.scrape(profile_url)
        except ScrapingError as e:
            print(f"❌ Scraping failed: {e}")
            return

        # Print results
        print(f"\n{'=' * 60}")
        print("SCRAPING RESULTS")
        print(f"{'=' * 60}\n")

        print(f"📛 Name: {person.name}")
        print(f"📍 Location: {person.location}")
        print(f"💼 Open to Work: {person.open_to_work}")

        if person.about:
            print(f"\n📝 About ({len(person.about)} chars):")
            print(f"   {person.about[:200]}{'...' if len(person.about) > 200 else ''}")
        else:
            print("\n📝 About: (not found)")

        print(f"\n{'=' * 60}")
        print(f"EXPERIENCES ({len(person.experiences or [])})")
        print(f"{'=' * 60}")
        for i, exp in enumerate(person.experiences or [], 1):
            print(f"\n  [{i}] {exp.position_title}")
            print(f"      Company: {exp.institution_name}")
            print(f"      Dates: {exp.from_date} - {exp.to_date}")
            if exp.duration:
                print(f"      Duration: {exp.duration}")
            if exp.location:
                print(f"      Location: {exp.location}")
            if exp.linkedin_url:
                print(f"      URL: {exp.linkedin_url[:60]}...")

        print(f"\n{'=' * 60}")
        print(f"EDUCATIONS ({len(person.educations or [])})")
        print(f"{'=' * 60}")
        for i, edu in enumerate(person.educations or [], 1):
            print(f"\n  [{i}] {edu.institution_name}")
            if edu.degree:
                print(f"      Degree: {edu.degree}")
            print(f"      Dates: {edu.from_date} - {edu.to_date}")
            if edu.linkedin_url:
                print(f"      URL: {edu.linkedin_url[:60]}...")

        print(f"\n{'=' * 60}")
        print(f"ACCOMPLISHMENTS ({len(person.accomplishments or [])})")
        print(f"{'=' * 60}")
        for i, acc in enumerate(person.accomplishments or [], 1):
            print(f"\n  [{i}] [{acc.category}] {acc.title}")
            if acc.issuer:
                print(f"      Issuer: {acc.issuer}")
            if acc.issued_date:
                print(f"      Date: {acc.issued_date}")

        print(f"\n{'=' * 60}")
        print(f"INTERESTS ({len(person.interests or [])})")
        print(f"{'=' * 60}")
        for i, interest in enumerate(person.interests or [], 1):
            print(f"  [{i}] [{interest.category}] {interest.name}")

        print(f"\n{'=' * 60}")
        print(f"SKILLS ({len(person.skills or [])})")
        print(f"{'=' * 60}")
        for i, skill in enumerate(person.skills or [], 1):
            endorsements_str = (
                f" ({skill.endorsements} endorsements)" if skill.endorsements else ""
            )
            category_str = f" [{skill.category}]" if skill.category else ""
            print(f"  [{i}]{category_str} {skill.name}{endorsements_str}")

        print(f"\n{'=' * 60}")
        print(f"CONTACTS ({len(person.contacts or [])})")
        print(f"{'=' * 60}")
        for i, contact in enumerate(person.contacts or [], 1):
            label_str = f" ({contact.label})" if contact.label else ""
            print(f"  [{i}] [{contact.type}] {contact.value}{label_str}")

        # Summary
        print(f"\n{'=' * 60}")
        print("SUMMARY")
        print(f"{'=' * 60}")
        print(
            f"  ✅ Name: {'Yes' if person.name and person.name != 'Unknown' else 'No'}"
        )
        print(f"  ✅ Location: {'Yes' if person.location else 'No'}")
        print(f"  ✅ About: {'Yes' if person.about else 'No'}")
        print(f"  ✅ Experiences: {len(person.experiences or [])}")
        print(f"  ✅ Educations: {len(person.educations or [])}")
        print(f"  ✅ Accomplishments: {len(person.accomplishments or [])}")
        print(f"  ✅ Interests: {len(person.interests or [])}")
        print(f"  ✅ Skills: {len(person.skills or [])}")
        print(f"  ✅ Contacts: {len(person.contacts or [])}")

        # Export to JSON for debugging
        json_path = Path("output") / "scraped_profile.json"
        json_path.parent.mkdir(exist_ok=True)
        with open(json_path, "w") as f:
            json.dump(person.to_dict(), f, indent=2, default=str)
        print(f"\n📄 Full data saved to: {json_path}")


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python test_live_scraper.py [profile_url]")
        print("\nExample:")
        print("  python test_live_scraper.py https://linkedin.com/in/username")
        print(f"\nIf no profile URL is provided, defaults to: {DEFAULT_PROFILE_URL}")
        print("\nEnvironment:")
        print("  LINKEDIN_COOKIE: Required - the li_at cookie value")
        # Don't exit - use default profile URL
        profile_url = DEFAULT_PROFILE_URL
    else:
        profile_url = sys.argv[1]

    # Get cookie from environment
    cookie = os.environ.get("LINKEDIN_COOKIE")
    if not cookie:
        # Try loading from .env
        env_path = Path(__file__).parent.parent / ".env"
        if env_path.exists():
            print(f"Loading cookie from {env_path}")
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
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

    await test_scraper(profile_url, cookie)

    print(f"\n{'=' * 60}")
    print("✅ Test complete!")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    asyncio.run(main())
