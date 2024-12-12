from playwright.sync_api import Playwright, sync_playwright, expect
import os

def run(playwright: Playwright) -> None:
    # 使用本地Chrome浏览器
    browser = playwright.chromium.launch(
        headless=False,
        executable_path=r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        slow_mo=100  # 减慢操作速度方便观察
    )
    
    # 创建新的上下文
    context = browser.new_context(
        viewport={'width': 1920, 'height': 1080}  # 设置窗口大小
    )
    page = context.new_page()
    
    try:
        # 访问目标网站
        page.goto("https://www.ryanair.com", wait_until="networkidle", timeout=30000)
        
        # 登录操作，增加等待时间
        page.wait_for_selector("input[placeholder='用户名: tester']", timeout=10000)
        page.get_by_placeholder("用户名: tester").click()
        page.get_by_placeholder("用户名: tester").fill("tester")
        page.get_by_placeholder("密码: tester").fill("tester")
        page.get_by_role("button", name="登 录").click()
        
        # 等待登录成功并验证
        page.wait_for_selector("[title='工作台']", timeout=10000)
        expect(page.get_by_title("工作台")).to_be_visible()
        
        # 创建保存目录
        os.makedirs("auth", exist_ok=True)
        
        # 保存登录状态
        storage = context.storage_state(path="auth/login_state.json")
        print("登录状态已保存到 auth/login_state.json")
        
    except Exception as e:
        print(f"发生错误: {str(e)}")
        # 出错时截图
        page.screenshot(path="error_screenshot.png")
        
    finally:
        context.close()
        browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)