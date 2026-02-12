"""Tests for offline HTML parsing - validates scraper against saved HTML snapshots."""

import asyncio
import time
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from linkedin_scraper.callbacks import SilentCallback
from linkedin_scraper.core.utils import (
    human_delay,
    long_delay,
    medium_delay,
    short_delay,
)
from linkedin_scraper.models import Skill
from linkedin_scraper.scrapers.person import PersonScraper

# Path to saved HTML files
OUTPUT_DIR = Path(__file__).parent.parent / "output"


@pytest.fixture
def experience_html_path():
    """Path to saved experience details HTML."""
    path = OUTPUT_DIR / "details_experience_20260211_135215.html"
    if not path.exists():
        pytest.skip(f"Experience HTML file not found at {path}")
    return path


@pytest.fixture
def education_html_path():
    """Path to saved education details HTML."""
    path = OUTPUT_DIR / "details_education_20260211_135215.html"
    if not path.exists():
        pytest.skip(f"Education HTML file not found at {path}")
    return path


@pytest.fixture
def certifications_html_path():
    """Path to saved certifications details HTML."""
    path = OUTPUT_DIR / "details_certifications_20260211_135215.html"
    if not path.exists():
        pytest.skip(f"Certifications HTML file not found at {path}")
    return path


@pytest.fixture
def interests_html_path():
    """Path to saved interests details HTML."""
    path = OUTPUT_DIR / "details_interests_20260211_135215.html"
    if not path.exists():
        pytest.skip(f"Interests HTML file not found at {path}")
    return path


@pytest.fixture
def skills_html_path():
    """Path to saved skills details HTML."""
    path = OUTPUT_DIR / "details_skills_20260211_135215.html"
    if not path.exists():
        pytest.skip(f"Skills HTML file not found at {path}")
    return path


@pytest.mark.asyncio
async def test_parse_experiences_from_html(experience_html_path):
    """Test parsing experiences from saved HTML file."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Load saved HTML via file:// URL
        await page.goto(f"file://{experience_html_path}", wait_until="domcontentloaded")

        callback = SilentCallback()
        scraper = PersonScraper(page, callback)

        # Find experience items
        main_element = page.locator("main")
        items = await main_element.locator(
            '[componentkey^="entity-collection-item"]'
        ).all()

        assert len(items) > 0, "Should find entity-collection-items in experience HTML"

        # Parse all experiences
        experiences = []
        for item in items:
            result = await scraper._parse_experience_item(item)
            if result:
                if isinstance(result, list):
                    experiences.extend(result)
                else:
                    experiences.append(result)

        await browser.close()

        # Verify we got experiences
        assert len(experiences) >= 4, (
            f"Should have at least 4 experiences, got {len(experiences)}"
        )

        # Verify first experience has required fields
        first_exp = experiences[0]
        assert first_exp.position_title is not None
        assert first_exp.institution_name is not None

        # Check that nested positions are parsed (Docwize has 2 positions)
        docwize_experiences = [
            e for e in experiences if "Docwize" in (e.institution_name or "")
        ]
        assert len(docwize_experiences) >= 2, "Should parse nested Docwize positions"


@pytest.mark.asyncio
async def test_parse_educations_from_html(education_html_path):
    """Test parsing educations from saved HTML file."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"file://{education_html_path}", wait_until="domcontentloaded")

        callback = SilentCallback()
        scraper = PersonScraper(page, callback)

        main_element = page.locator("main")
        items = await main_element.locator(
            '[componentkey^="entity-collection-item"]'
        ).all()

        assert len(items) > 0, "Should find entity-collection-items in education HTML"

        educations = []
        for item in items:
            edu = await scraper._parse_education_item(item)
            if edu:
                educations.append(edu)

        await browser.close()

        assert len(educations) >= 2, (
            f"Should have at least 2 educations, got {len(educations)}"
        )

        # Verify first education
        first_edu = educations[0]
        assert first_edu.institution_name is not None
        assert (
            "University" in first_edu.institution_name
            or "School" in first_edu.institution_name
            or "Pretoria" in first_edu.institution_name
        )


@pytest.mark.asyncio
async def test_parse_certifications_from_html(certifications_html_path):
    """Test parsing certifications from saved HTML file."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(
            f"file://{certifications_html_path}", wait_until="domcontentloaded"
        )

        callback = SilentCallback()
        scraper = PersonScraper(page, callback)

        main_element = page.locator("main")

        # Certifications use a different structure - p elements grouped by content
        all_p = await main_element.locator("p").all()

        assert len(all_p) > 0, "Should find p elements in certifications HTML"

        # Group p elements into certification items
        current_group = []
        grouped_items = []

        for p in all_p:
            text = await p.text_content()
            if text:
                text = text.strip()
                if text in ["Licenses & certifications"]:
                    continue
                if text.startswith("Show credential") or text.startswith("Skills:"):
                    if current_group:
                        grouped_items.append(current_group)
                        current_group = []
                    continue
                current_group.append(text)
                if "Credential ID" in text or len(current_group) >= 5:
                    grouped_items.append(current_group)
                    current_group = []

        if current_group:
            grouped_items.append(current_group)

        # Parse groups into accomplishments
        certs = []
        for group in grouped_items:
            if len(group) >= 2:
                cert = scraper._parse_accomplishment_from_texts(group, "certification")
                if cert:
                    certs.append(cert)

        await browser.close()

        assert len(certs) >= 5, (
            f"Should have at least 5 certifications, got {len(certs)}"
        )

        # Verify certification has required fields
        first_cert = certs[0]
        assert first_cert.title is not None
        assert first_cert.issuer is not None
        assert first_cert.category == "certification"


@pytest.mark.asyncio
async def test_parse_interests_from_html(interests_html_path):
    """Test parsing interests from saved HTML file."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"file://{interests_html_path}", wait_until="domcontentloaded")

        main_element = page.locator("main")

        # Interests use figure elements for company logos
        figures = await main_element.locator("figure").all()

        assert len(figures) > 0, "Should find figure elements in interests HTML"

        interests = []
        for figure in figures:
            sibling_div = figure.locator("xpath=following-sibling::div[1]")
            if await sibling_div.count() > 0:
                p_els = await sibling_div.locator("p").all()
                if p_els:
                    name = await p_els[0].text_content()
                    if name:
                        name = name.strip()
                        if name and name != "Interests" and len(name) > 1:
                            link = figure.locator(
                                'xpath=ancestor::a[contains(@href, "/company/")]'
                            )
                            href = (
                                await link.get_attribute("href")
                                if await link.count() > 0
                                else None
                            )
                            interests.append({"name": name, "url": href})

        await browser.close()

        assert len(interests) >= 5, (
            f"Should have at least 5 interests, got {len(interests)}"
        )

        # Verify first interest
        first_interest = interests[0]
        assert first_interest["name"] is not None
        assert len(first_interest["name"]) > 1


@pytest.mark.asyncio
async def test_parse_skills_from_html(skills_html_path):
    """Test parsing skills from saved HTML file."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(f"file://{skills_html_path}", wait_until="domcontentloaded")

        callback = SilentCallback()
        scraper = PersonScraper(page, callback)

        main_element = page.locator("main")

        # Skills can use entity-collection-items or other structures
        skill_items = await main_element.locator(
            '[componentkey^="entity-collection-item"]'
        ).all()

        # If no entity items, try ul > li
        if not skill_items:
            skill_items = await main_element.locator("ul > li").all()

        assert len(skill_items) > 0, "Should find skill items in skills HTML"

        # Parse skills
        skills = []
        for item in skill_items:
            skill = await scraper._parse_skill_item(item)
            if skill:
                skills.append(skill)

        await browser.close()

        # Verify we got skills
        assert len(skills) >= 1, f"Should have at least 1 skill, got {len(skills)}"

        # Verify first skill has required fields
        first_skill = skills[0]
        assert first_skill.name is not None
        assert len(first_skill.name) > 0


def test_date_parsing_with_en_dash():
    """Test that date parsing handles en-dash (–) correctly.

    This test doesn't require Playwright since it only tests the parsing methods.
    """
    from linkedin_scraper.scrapers.person import PersonScraper

    # Create a mock page and callback for the scraper
    class MockPage:
        pass

    class MockCallback:
        async def on_start(self, *args):
            pass

        async def on_progress(self, *args):
            pass

        async def on_complete(self, *args):
            pass

        async def on_error(self, *args):
            pass

    scraper = PersonScraper(MockPage(), MockCallback())

    # Test work times with en-dash
    from_date, to_date, duration = scraper._parse_work_times(
        "Jan 2020 – Dec 2022 · 2 yrs"
    )
    assert from_date == "Jan 2020"
    assert to_date == "Dec 2022"
    assert duration == "2 yrs"

    # Test education times with en-dash
    from_date, to_date = scraper._parse_education_times("2017 – 2020")
    assert from_date == "2017"
    assert to_date == "2020"

    # Test with regular hyphen (should still work)
    from_date, to_date, duration = scraper._parse_work_times(
        "Jan 2020 - Dec 2022 · 2 yrs"
    )
    assert from_date == "Jan 2020"
    assert to_date == "Dec 2022"

    # Test with em-dash (—)
    from_date, to_date, duration = scraper._parse_work_times(
        "Jan 2020 — Dec 2022 · 2 yrs"
    )
    assert from_date == "Jan 2020"
    assert to_date == "Dec 2022"


@pytest.mark.asyncio
async def test_human_delay_functions():
    """Test that human delay functions work correctly.

    Verifies that:
    - Delays are within expected ranges
    - Different delay functions have different ranges
    - Returned delay time matches actual wait time (approximately)
    """
    # Test short_delay
    start = time.time()
    delay = await short_delay(0.05, 0.1)
    elapsed = time.time() - start
    assert 0.05 <= delay <= 0.1, f"short_delay returned {delay}, expected 0.05-0.1"
    assert abs(elapsed - delay) < 0.05, (
        f"Actual delay {elapsed} differs from returned {delay}"
    )

    # Test medium_delay
    start = time.time()
    delay = await medium_delay(0.05, 0.1)
    elapsed = time.time() - start
    assert 0.05 <= delay <= 0.1, f"medium_delay returned {delay}, expected 0.05-0.1"
    assert abs(elapsed - delay) < 0.05, (
        f"Actual delay {elapsed} differs from returned {delay}"
    )

    # Test long_delay
    start = time.time()
    delay = await long_delay(0.05, 0.1)
    elapsed = time.time() - start
    assert 0.05 <= delay <= 0.1, f"long_delay returned {delay}, expected 0.05-0.1"
    assert abs(elapsed - delay) < 0.05, (
        f"Actual delay {elapsed} differs from returned {delay}"
    )

    # Test human_delay with custom range
    start = time.time()
    delay = await human_delay(0.1, 0.2)
    elapsed = time.time() - start
    assert 0.1 <= delay <= 0.2, f"human_delay returned {delay}, expected 0.1-0.2"
    assert abs(elapsed - delay) < 0.05, (
        f"Actual delay {elapsed} differs from returned {delay}"
    )


def test_human_delay_randomness():
    """Test that human delay functions produce varied results.

    Runs multiple delays and checks that they're not all the same,
    indicating randomness is working.
    """
    import asyncio

    async def collect_delays():
        delays = []
        for _ in range(5):
            delay = await human_delay(0.01, 0.1)
            delays.append(delay)
        return delays

    delays = asyncio.run(collect_delays())

    # Check that we got varied delays (not all the same)
    unique_delays = set(round(d, 4) for d in delays)
    assert len(unique_delays) > 1, (
        "All delays were the same - randomness may not be working"
    )

    # Check all delays are within range
    for delay in delays:
        assert 0.01 <= delay <= 0.1, f"Delay {delay} outside expected range 0.01-0.1"
