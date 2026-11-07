import asyncio
import time
from typing import Optional, Tuple

from core.logger import get_logger
from core.templates import (
    MAIN_WORLD_HOOK_JS, TOKEN_VALUE_JS, TS_STATE_JS,
    build_route_html, route_glob,
)

logger = get_logger()

# Budgets. Each attempt re-navigates, which gives Cloudflare a fresh challenge
# (600* / 300* errors are retryable). Both strategies are tried so a site whose
# real page has no usable widget still falls back to the hostname-correct stub.
ROUTE_RETRIES = 3
ROUTE_WAIT_S = 16
REAL_RETRIES = 2
REAL_WAIT_S = 22

_INTERSTITIAL_JS = """() => {
  const html = document.documentElement ? document.documentElement.outerHTML : '';
  const t = (document.title || '').toLowerCase();
  return /just a moment|attention required|checking your browser|verifying you are human/.test(t)
    || /_cf_chl_opt|__cf_chl_|challenge-platform/.test(html);
}"""


async def _challenge_frames(page):
    """challenges.cloudflare.com frames that are actually the ~300x65 widget."""
    out = []
    for fr in page.frames:
        if 'challenges.cloudflare.com' not in (fr.url or ''):
            continue
        try:
            box = await (await fr.frame_element()).bounding_box()
        except Exception:
            continue
        if box and box['width'] >= 200 and box['height'] >= 40:
            out.append((fr, box))
    return out


async def _click_checkbox(page) -> bool:
    """Trusted click on the checkbox (UI lives in closed shadow roots)."""
    # 1) Humanised coordinate click at the left-edge checkbox. This works in
    #    both Chromium and Firefox/camoufox (closed shadow roots are pierced by
    #    hit-testing), unlike frame_locator which fails on Firefox.
    for _fr, box in await _challenge_frames(page):
        x, y = box['x'] + 30, box['y'] + box['height'] / 2
        try:
            await page.mouse.move(x - 30, y - 20, steps=10)
            await page.mouse.move(x, y, steps=12)
            await page.wait_for_timeout(120)
            await page.mouse.click(x, y)
            return True
        except Exception:
            continue
    # 2) CSR-aware frame_locator (Chromium, patchright >= 1.52.2).
    try:
        cb = page.frame_locator(
            "iframe[src*='challenges.cloudflare.com']").first.get_by_role('checkbox')
        if await cb.count() > 0:
            await cb.click(timeout=5000)
            return True
    except Exception:
        pass
    # 3) Positional click inside the frame's own coordinate space.
    for fr, _box in await _challenge_frames(page):
        try:
            await fr.locator('body').click(position={'x': 30, 'y': 32}, timeout=3000)
            return True
        except Exception:
            continue
    return False


async def click_turnstile_checkbox(page, attempts: int = 25) -> bool:
    """Compatibility wrapper used by cf_clearance.solve."""
    for _ in range(max(1, attempts)):
        if await _click_checkbox(page):
            return True
        await asyncio.sleep(1)
    return False


async def _wait_token(page, timeout_s: int, label: str) -> Optional[str]:
    deadline = time.monotonic() + timeout_s
    clicks = 0
    next_click = time.monotonic()
    last_error = ''
    while time.monotonic() < deadline:
        token = await page.evaluate(TOKEN_VALUE_JS)
        if token:
            return token
        if clicks < 3 and time.monotonic() >= next_click:
            if await _click_checkbox(page):
                clicks += 1
                logger.debug(f"{label}: click #{clicks}")
            next_click = time.monotonic() + 5
        try:
            state = await page.evaluate(TS_STATE_JS)
            if state['error'] and state['error'] != last_error:
                last_error = state['error']
                logger.debug(f"{label}: Turnstile error {last_error}")
        except Exception:
            pass
        await asyncio.sleep(0.5)
    return None


async def solve_route(page, url: str, sitekey: str, action: Optional[str] = None,
                      cdata: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Serve a controlled widget at the real hostname (correct domain binding)."""
    pattern = route_glob(url)
    page_data = build_route_html(sitekey, action, cdata)

    async def handle(route):
        await route.fulfill(status=200, content_type='text/html; charset=utf-8',
                            body=page_data)

    await page.route(pattern, handle)
    logger.info(f"Route-intercept {pattern}")
    for attempt in range(1, ROUTE_RETRIES + 1):
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        except Exception as e:
            logger.debug(f"route goto #{attempt}: {e}")
            continue
        token = await _wait_token(page, ROUTE_WAIT_S, f'route#{attempt}')
        if token:
            return token, pattern
    return None, pattern


async def solve_realpage(page, url: str, sitekey: str,
                         timeout_s: int = REAL_WAIT_S) -> Optional[str]:
    """Solve the widget that already exists on the real page (full CF context)."""
    logger.info(f"Real-page {url}")
    for attempt in range(1, REAL_RETRIES + 1):
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=45000)
        except Exception as e:
            logger.debug(f"real goto #{attempt}: {e}")
            continue

        # Main-world hook: defines the site's otherwise-undefined
        # javascriptCallback and mirrors tokens into a readable DOM attribute.
        try:
            await page.add_script_tag(content=MAIN_WORLD_HOOK_JS)
        except Exception:
            pass

        # If the page shows a CF interstitial and never renders a widget, give
        # up early so the route fallback gets its turn.
        widget_seen = False
        for _ in range(16):
            if await page.evaluate(
                "() => !!document.querySelector('[name=cf-turnstile-response], .cf-turnstile')"
            ):
                widget_seen = True
                break
            await asyncio.sleep(0.5)
        if not widget_seen:
            logger.info("Real-page: no Turnstile widget found")
            return None

        token = await _wait_token(page, timeout_s, f'real#{attempt}')
        if token:
            return token
        logger.debug(f"real#{attempt}: no token, retrying")
    return None


async def solve(page, url: str, sitekey: str, action: Optional[str] = None,
                cdata: Optional[str] = None) -> Tuple[Optional[str], str]:
    """Hostname-correct stub first (fast, universal), real page as fallback."""
    token, pattern = await solve_route(page, url, sitekey, action, cdata)
    if token:
        return token, 'route'
    logger.info("Route failed, trying real-page")
    try:
        await page.unroute(pattern)
    except Exception as e:
        logger.debug(f"unroute failed: {e}")
    token = await solve_realpage(page, url, sitekey)
    if token:
        return token, 'real-page'
    return None, 'failed'
