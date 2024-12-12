from playwright.sync_api import Playwright, sync_playwright, expect
import json

def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=False)
    context = browser.new_context()
    storage_state = "data_webvoyager_training/IL_1/www.ryanair.com.json"
    
    # 读取并添加 cookies
    with open(storage_state, 'r') as f:
        cookies = json.load(f)
        if not isinstance(cookies, list):
            raise ValueError("Cookies should be a list of cookie objects")
        
        # 确保 sameSite 属性的值是正确的
        for cookie in cookies:
            if 'sameSite' not in cookie or cookie['sameSite'].lower() not in ['strict', 'lax', 'none']:
                cookie['sameSite'] = 'Lax'  # 设置默认值为 'Lax'
            else:
                cookie['sameSite'] = cookie['sameSite'].capitalize()
        
        context.add_cookies(cookies)
    
    page = context.new_page()
    page.goto('https://www.ryanair.com')
    # # 检查 cookies 是否正确应用
    context_cookies = context.cookies()
    print("Current cookies in context:")
    for cookie in context_cookies:
        print(cookie)
    
    page.pause()

    # Interact with login form
    # page.get_by_placeholder("Email or Guest Rewards #").fill("yjheeee@163.com")
    # page.get_by_placeholder("Password").fill("9b5uDp@&&BF2Z)a")
    # page.get_by_role("button", name="SIGN IN").click()
    # Continue with the test

    # 保存storage state 到指定的文件
    # storage = context.storage_state(path="./amtrak.json")


    context.close()
    browser.close()

with sync_playwright() as playwright:
    run(playwright)