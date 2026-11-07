"""Run inside a started container with --network none; see docs/docker.zh-CN.md."""

import ctypes
import json
import os
import time
import unittest
from urllib.error import URLError
from urllib.request import ProxyHandler, build_opener

from core.browser import BrowserConfig, close_browser, context_options, launch_browser


class ApiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_url = os.environ.get("SMOKE_BASE_URL", "http://127.0.0.1:5072")
        cls.http = build_opener(ProxyHandler({}))
        deadline = time.monotonic() + 30
        while True:
            try:
                with cls.http.open(cls.base_url + "/", timeout=2) as response:
                    cls.index_status = response.status
                    cls.index_html = response.read().decode()
                break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.25)

    def test_index(self):
        self.assertEqual(self.index_status, 200)
        self.assertIn("Turnstile Solver API", self.index_html)

    def test_validation_routes(self):
        routes = {
            "/turnstile": "ERROR_WRONG_PAGEURL",
            "/cf_clearance": "ERROR_WRONG_PAGEURL",
            "/result?id=docker-smoke-missing": "ERROR_WRONG_CAPTCHA_ID",
        }
        for path, error_code in routes.items():
            with self.subTest(path=path):
                with self.http.open(self.base_url + path, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    result = json.load(response)
                self.assertEqual(result["errorId"], 1)
                self.assertEqual(result["errorCode"], error_code)


class BrowserSmokeTests(unittest.IsolatedAsyncioTestCase):
    def test_camoufox_system_libs_available(self):
        """Camoufox's libmozgtk.so needs libgtk-3.so.0. Without it the default
        browser fails to start and the solver silently falls back to Chromium,
        which Cloudflare rejects with 600010."""
        ctypes.CDLL("libgtk-3.so.0")

    async def test_bundled_chromium_renders_without_network(self):
        config = BrowserConfig(browser_type="chromium")
        driver = browser = None
        try:
            driver, browser = await launch_browser(config)
            context = await browser.new_context(**context_options(config, None))
            page = await context.new_page()
            await page.set_content(
                "<title>Docker browser smoke test</title><h1>Bundled Chromium works</h1>"
            )
            self.assertEqual(await page.title(), "Docker browser smoke test")
            self.assertEqual(await page.locator("h1").inner_text(), "Bundled Chromium works")
            print(f"Bundled Chromium version: {browser.version}", flush=True)
            await context.close()
        finally:
            await close_browser(driver, browser, debug=True)

    async def test_token_reader_uses_first_non_empty_input(self):
        """A page can hold several widgets; an empty first input must not mask a token."""
        from core.templates import TOKEN_VALUE_JS, build_route_html, route_glob

        self.assertEqual(route_glob("https://example.com/login"), "https://example.com/login")
        self.assertEqual(route_glob("https://example.com"), "https://example.com/")
        self.assertIn('data-callback="__tsToken"', build_route_html("0xKEY"))

        config = BrowserConfig(browser_type="chromium")
        driver = browser = None
        try:
            driver, browser = await launch_browser(config)
            context = await browser.new_context(**context_options(config, None))
            page = await context.new_page()
            await page.set_content(
                '<input name="cf-turnstile-response" value="">'
                '<input name="cf-turnstile-response" value="TOKEN-2">'
            )
            self.assertEqual(await page.evaluate(TOKEN_VALUE_JS), "TOKEN-2")
            await context.close()
        finally:
            await close_browser(driver, browser, debug=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
