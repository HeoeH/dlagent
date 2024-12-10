# import base64
# import datetime
# from pathlib import Path
# from typing_extensions import Annotated, Optional
# from io import BytesIO
# from PIL import Image

# from playwright.async_api import Page
# from agentq.core.web_driver.playwright import PlaywrightManager
# from agentq.utils.logger import logger

# async def get_screenshot(
#     webpage: Optional[Page] = None,
#     folder_path: Optional[Path] = None
# ) -> Annotated[
#     tuple[str, str], "Returns a tuple with a base64 encoded screenshot and the file path of the saved screenshot."
# ]:
#     """
#     Captures and returns a base64 encoded screenshot of the current page (only the visible viewport and not the full page),
#     and saves the screenshot to a file.

#     Returns:
#     - Tuple containing:
#       - Base64 encoded string of the screenshot image.
#       - File path of the saved screenshot.
#     """

#     try:
#         # Create and use the PlaywrightManager
#         browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
#         if webpage is not None:
#             page = webpage
#         else:
#             page = await browser_manager.get_current_page()
#         logger.info("page {page}")

#         if not page:
#             logger.info("No active page found. OpenURL command opens a new page.")
#             raise ValueError("No active page found. OpenURL command opens a new page.")

#         await page.wait_for_load_state("domcontentloaded")

#         # Capture the screenshot
#         logger.info("about to capture")
#         screenshot_bytes = await page.screenshot(full_page=False, timeout=60000)

#         # Encode the screenshot as base64
#         base64_screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")

#         # Save the screenshot to a file
#         timestamp = get_formatted_timestamp()
#         # 确定 result 文件夹的路径
#         base_folder = Path("result").resolve()
#         base_folder.mkdir(parents=True, exist_ok=True)  # 确保 result 文件夹存在
#         file_path=""
#         # 如果未提供子文件夹名称，使用默认名称
#         if folder_path is not None:
        
#             # 创建子文件夹
#             folder_name = base_folder / folder_path
#             folder_name.mkdir(parents=True, exist_ok=True)  # 确保子文件夹存在
            
#             # 构造截图文件路径
#             file_path = folder_name / f"screenshot_{timestamp}.png"
            
#             # 确保路径为绝对路径
#             file_path = file_path.resolve()

#             with open(file_path, "wb") as f:
#                 f.write(screenshot_bytes)

#         return f"data:image/png;base64,{base64_screenshot}", str(file_path)

#     except Exception as e:
#         raise ValueError(
#             "Failed to capture screenshot. Make sure a page is open and accessible."
#         ) from e

# def get_formatted_timestamp() -> str:
#     """Return a formatted timestamp."""
#     return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


import base64
import datetime
from pathlib import Path
from typing_extensions import Annotated, Optional
from io import BytesIO
from PIL import Image

from playwright.async_api import Page
from agentq.core.web_driver.playwright import PlaywrightManager
from agentq.utils.logger import logger

async def get_screenshot(
    webpage: Optional[Page] = None,
    task_id: Optional[str] = None
) -> Annotated[
    tuple[str, str], "Returns a tuple with a base64 encoded screenshot and the file path of the saved screenshot."
]:
    """
    Captures and returns a base64 encoded screenshot of the current page (only the visible viewport and not the full page),
    and saves the screenshot to a file.

    Returns:
    - Tuple containing:
      - Base64 encoded string of the screenshot image.
      - File path of the saved screenshot.
    """

    try:
        # Create and use the PlaywrightManager
        browser_manager = PlaywrightManager(browser_type="chromium", headless=False)
        if webpage is not None:
            page = webpage
        else:
            page = await browser_manager.get_current_page()
        logger.info("page {page}")

        if not page:
            logger.info("No active page found. OpenURL command opens a new page.")
            raise ValueError("No active page found. OpenURL command opens a new page.")

        await page.wait_for_load_state("domcontentloaded")

        # Capture the screenshot
        logger.info("about to capture")
        screenshot_bytes = await page.screenshot(full_page=False, timeout=60000)

        # Encode the screenshot as base64
        base64_screenshot = base64.b64encode(screenshot_bytes).decode("utf-8")

        # Save the screenshot to a file
        timestamp = get_formatted_timestamp()
        # 确定 result 文件夹的路径
        base_folder = Path(f"/dataset/wangzh/omni_dc/dlagent_result/optim3/{task_id}").resolve()
        base_folder.mkdir(parents=True, exist_ok=True)  # 确保 result 文件夹存在
        
        # 构造截图文件路径
        file_path = base_folder / f"screenshot_{timestamp}.png"
        
        # 确保路径为绝对路径
        file_path = file_path.resolve()

        with open(file_path, "wb") as f:
            f.write(screenshot_bytes)

        return f"data:image/png;base64,{base64_screenshot}", str(file_path)

    except Exception as e:
        raise ValueError(
            "Failed to capture screenshot. Make sure a page is open and accessible."
        ) from e

def get_formatted_timestamp() -> str:
    """Return a formatted timestamp."""
    return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")