"""Base scraper with common scraping functionality."""

import asyncio
import logging
from typing import Optional

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from ..callbacks import ProgressCallback, SilentCallback
from ..core import (
    click_see_more_buttons,
    detect_rate_limit,
    extract_text_safe,
    handle_modal_close,
    human_delay,
    is_logged_in,
    long_delay,
    medium_delay,
    retry_async,
    scroll_to_bottom,
    scroll_to_half,
    short_delay,
)
from ..core.exceptions import AuthenticationError, ScrapingError

logger = logging.getLogger(__name__)


class BaseScraper:
    """Base class with common scraping functionality."""

    def __init__(self, page: Page, callback: Optional[ProgressCallback] = None):
        """
        Initialize base scraper.

        Args:
            page: Playwright page object
            callback: Progress callback (defaults to SilentCallback)
        """
        self.page = page
        self.callback = callback or SilentCallback()

    async def ensure_logged_in(self) -> None:
        """
        Verify user is authenticated.

        Raises:
            AuthenticationError: If not logged in
        """
        if not await is_logged_in(self.page):
            raise AuthenticationError(
                "Not logged in. Please authenticate before scraping."
            )

    async def check_rate_limit(self) -> None:
        """
        Check for rate limiting.

        Raises:
            RateLimitError: If rate limiting is detected
        """
        await detect_rate_limit(self.page)

    async def scroll_page_to_bottom(
        self,
        pause_time: float = 1.0,
        max_scrolls: int = 10,
        randomize_pause: bool = True,
    ) -> None:
        """
        Scroll to bottom of page with pauses.

        Args:
            pause_time: Base time to pause between scrolls
            max_scrolls: Maximum number of scroll attempts
            randomize_pause: If True, randomize pause time for human-like behavior
        """
        await scroll_to_bottom(self.page, pause_time, max_scrolls, randomize_pause)

    async def scroll_page_to_half(self, add_delay: bool = True) -> None:
        """Scroll to middle of page with optional human-like delay."""
        await scroll_to_half(self.page, add_delay)

    async def scroll_element_into_view(self, selector: str) -> None:
        """
        Scroll element into view.

        Args:
            selector: CSS selector of element
        """
        try:
            element = self.page.locator(selector).first
            await element.scroll_into_view_if_needed()
        except Exception as e:
            logger.debug(f"Could not scroll element into view: {selector} - {e}")

    async def click_all_see_more_buttons(self, max_attempts: int = 10) -> int:
        """
        Click all 'Show more' / 'See more' buttons.

        Args:
            max_attempts: Maximum number of buttons to click

        Returns:
            Number of buttons clicked
        """
        return await click_see_more_buttons(self.page, max_attempts)

    async def close_modals(self) -> bool:
        """
        Close any popup modals.

        Returns:
            True if a modal was closed
        """
        return await handle_modal_close(self.page)

    async def safe_extract_text(
        self, selector: str, default: str = "", timeout: float = 2000
    ) -> str:
        """
        Safely extract text from element.

        Args:
            selector: CSS selector
            default: Default value if not found
            timeout: Timeout in milliseconds

        Returns:
            Extracted text or default
        """
        return await extract_text_safe(self.page, selector, default, timeout)

    @retry_async(max_attempts=3, backoff=2.0, exceptions=(PlaywrightTimeoutError,))
    async def safe_click(
        self, selector: str, timeout: float = 5000, add_delay: bool = True
    ) -> bool:
        """
        Safely click an element with retry and human-like delays.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
            add_delay: If True, add human-like delays before and after click

        Returns:
            True if clicked, False if not found
        """
        try:
            # Add human-like delay before clicking
            if add_delay:
                await short_delay(0.3, 1.0)

            element = self.page.locator(selector).first
            await element.click(timeout=timeout)

            # Add human-like delay after clicking
            if add_delay:
                await short_delay(0.5, 1.5)

            return True
        except PlaywrightTimeoutError:
            logger.debug(f"Could not click element: {selector}")
            return False
        except Exception as e:
            logger.warning(f"Error clicking element {selector}: {e}")
            return False

    async def wait_for_navigation_complete(self, timeout: float = 30000) -> None:
        """
        Wait for page to finish navigating and loading.

        Args:
            timeout: Timeout in milliseconds
        """
        try:
            await self.page.wait_for_load_state("networkidle", timeout=timeout)
        except PlaywrightTimeoutError:
            logger.warning("Navigation did not complete within timeout")

    async def navigate_and_wait(
        self,
        url: str,
        wait_until: str = "domcontentloaded",
        timeout: int = 60000,
        add_delay: bool = True,
    ) -> None:
        """
        Navigate to URL and wait for page load with human-like delay.

        Args:
            url: URL to navigate to
            wait_until: Wait condition (domcontentloaded, networkidle, load)
            timeout: Timeout in milliseconds (default: 60000 = 60s)
            add_delay: If True, add human-like delay after navigation
        """
        logger.info(f"Navigating to: {url}")
        # Use type: ignore to bypass strict typing
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)  # type: ignore
        await self.check_rate_limit()

        # Add human-like delay after navigation to simulate reading/loading
        if add_delay:
            await medium_delay(1.0, 3.0)

    async def extract_list_items(
        self, container_selector: str, item_selector: str, timeout: float = 5000
    ) -> list:
        """
        Extract list items from a container.

        Args:
            container_selector: CSS selector for container
            item_selector: CSS selector for items within container
            timeout: Timeout in milliseconds

        Returns:
            List of Playwright locator objects
        """
        try:
            container = self.page.locator(container_selector).first
            await container.wait_for(timeout=timeout)
            items = container.locator(item_selector).all()
            return await items
        except PlaywrightTimeoutError:
            logger.warning(f"Container not found: {container_selector}")
            return []
        except Exception as e:
            logger.error(f"Error extracting list items: {e}")
            return []

    async def get_attribute_safe(
        self, selector: str, attribute: str, default: str = "", timeout: float = 2000
    ) -> str:
        """
        Safely get element attribute.

        Args:
            selector: CSS selector
            attribute: Attribute name
            default: Default value if not found
            timeout: Timeout in milliseconds

        Returns:
            Attribute value or default
        """
        try:
            element = self.page.locator(selector).first
            value = await element.get_attribute(attribute, timeout=timeout)
            return value if value else default
        except:
            return default

    async def wait_and_focus(
        self, duration: float = 1.0, randomize: bool = True
    ) -> None:
        """
        Wait and focus window (helps with dynamic loading).

        Args:
            duration: Base time to wait in seconds
            randomize: If True, randomize the wait time for human-like behavior
        """
        if randomize:
            # Randomize around the base duration (50% to 200% of base)
            await human_delay(duration * 0.5, duration * 2.0)
        else:
            await asyncio.sleep(duration)
        try:
            # Bring page to front
            await self.page.bring_to_front()
        except:
            pass

    async def count_elements(self, selector: str) -> int:
        """
        Count elements matching selector.

        Args:
            selector: CSS selector

        Returns:
            Number of matching elements
        """
        try:
            return await self.page.locator(selector).count()
        except:
            return 0

    async def element_exists(self, selector: str, timeout: float = 1000) -> bool:
        """
        Check if element exists.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds

        Returns:
            True if element exists
        """
        try:
            await self.page.wait_for_selector(
                selector, timeout=timeout, state="attached"
            )
            return True
        except:
            return False
