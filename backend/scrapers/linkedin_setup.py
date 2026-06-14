"""LinkedIn 쿠키 설정 (최초 1회 실행)

실행: python -m scrapers.linkedin_setup
브라우저 창에서 LinkedIn 로그인만 하면 자동 감지 후 저장됩니다.
"""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

_COOKIE_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"
_TIMEOUT_SEC = 300  # 로그인 대기 최대 5분


def _is_logged_in(context) -> bool:
    return any(c["name"] == "li_at" for c in context.cookies())


def main():
    print("브라우저 창이 열립니다. LinkedIn에 로그인해주세요.")
    print(f"로그인이 감지되면 자동으로 쿠키가 저장됩니다 (최대 {_TIMEOUT_SEC // 60}분 대기).")
    print(f"저장 위치: {_COOKIE_FILE}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")

        deadline = time.time() + _TIMEOUT_SEC
        while time.time() < deadline:
            if _is_logged_in(context):
                cookies = context.cookies()
                _COOKIE_FILE.parent.mkdir(parents=True, exist_ok=True)
                _COOKIE_FILE.write_text(
                    json.dumps(cookies, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                print(f"\n로그인 감지됨. 쿠키 저장 완료 ({len(cookies)}개)")
                time.sleep(2)
                browser.close()
                return
            time.sleep(2)

        print("\n시간 초과: 로그인이 감지되지 않았습니다. 다시 실행해주세요.")
        browser.close()


if __name__ == "__main__":
    main()
