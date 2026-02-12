"""Core modules for LinkedIn scraper."""

from .auth import (
    is_logged_in,
    load_credentials_from_env,
    login_with_cookie,
    login_with_credentials,
    wait_for_manual_login,
    warm_up_browser,
)
from .browser import BrowserManager
from .exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    LinkedInScraperException,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)
from .utils import (
    click_see_more_buttons,
    detect_rate_limit,
    extract_text_safe,
    handle_modal_close,
    human_delay,
    is_page_loaded,
    long_delay,
    medium_delay,
    retry_async,
    scroll_to_bottom,
    scroll_to_half,
    short_delay,
    wait_for_element_smart,
)

__all__ = [
    # Browser
    "BrowserManager",
    # Auth
    "login_with_credentials",
    "login_with_cookie",
    "is_logged_in",
    "wait_for_manual_login",
    "load_credentials_from_env",
    "warm_up_browser",
    # Exceptions
    "LinkedInScraperException",
    "AuthenticationError",
    "RateLimitError",
    "ElementNotFoundError",
    "ProfileNotFoundError",
    "NetworkError",
    "ScrapingError",
    # Utils
    "retry_async",
    "detect_rate_limit",
    "wait_for_element_smart",
    "extract_text_safe",
    "scroll_to_bottom",
    "scroll_to_half",
    "click_see_more_buttons",
    "handle_modal_close",
    "is_page_loaded",
    "human_delay",
    "short_delay",
    "medium_delay",
    "long_delay",
]
