import os
import time
from typing import Any, Dict, Optional, Union

from playwright.async_api import Page
from typing_extensions import Annotated

from agentq.config.config import SOURCE_LOG_FOLDER_PATH
from agentq.core.web_driver.playwright import PlaywrightManager
from agentq.utils.dom_helper import wait_for_non_loading_dom_state
from agentq.utils.get_detailed_accessibility_tree import do_get_accessibility_info
from agentq.utils.logger import logger


async def highlight_interactive_elements(
    webpage: Optional[Page] = None,
) -> Annotated[str, "Returns the full URL of the current active web site/page."]:
    """
    Returns the full URL of the current page

    Parameters:

    Returns:
    - Full URL the browser's active page.
    """
    # Create and use the PlaywrightManager
    browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
    if webpage is not None:
        page = webpage
    else:
        page = await browser_manager.get_current_page()

    if not page:
        raise ValueError("No active page found. OpenURL command opens a new page.")

    await page.wait_for_load_state("domcontentloaded")
    
    last_mmid = await page.evaluate("""
        () => {
            const interactiveSelectors = [
                'button', 'a[href]', 'input', 'select', 'textarea',
                '[contenteditable]', '[tabindex]', '[role="button"]', '[role="link"]',
                '[role="checkbox"]', '[role="menuitem"]', '[role="option"]', '[role="radio"]',
                '[role="switch"]', '[role="tab"]', '[role="treeitem"]'
            ].join(',');
            const interactiveElements = document.querySelectorAll(interactiveSelectors);
            let id = 0;
            interactiveElements.forEach(element => {
                const origAriaAttribute = element.getAttribute('aria-keyshortcuts');
                const mmid = `${++id}`;
                element.setAttribute('mmid', mmid);
                element.setAttribute('aria-keyshortcuts', mmid);
                if (origAriaAttribute) {
                    element.setAttribute('orig-aria-keyshortcuts', origAriaAttribute);
                }

                // Add a border to the element
                element.style.border = '1px solid red';

                // Create a div to display the mmid
                const mmidDiv = document.createElement('div');
                mmidDiv.textContent = `MMID: ${mmid}`;
                mmidDiv.style.position = 'absolute';
                mmidDiv.style.top = '0';
                mmidDiv.style.left = '0';
                mmidDiv.style.backgroundColor = 'rgba(255, 255, 255, 0.8)';
                mmidDiv.style.color = 'black';
                mmidDiv.style.fontSize = '12px';
                mmidDiv.style.padding = '2px';
                mmidDiv.style.pointerEvents = 'none';  // Make sure the div does not interfere with user interaction

                // Append the mmid div to the body and position it relative to the element
                document.body.appendChild(mmidDiv);
                const rect = element.getBoundingClientRect();
                mmidDiv.style.transform = `translate(${rect.left}px, ${rect.top}px)`;
            });
            return id;
        }
    """)
    print(f"Highlighted {last_mmid} interactive elements")