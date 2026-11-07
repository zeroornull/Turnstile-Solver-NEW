import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple

from patchright.async_api import async_playwright

from .logger import get_logger

logger = get_logger()

CHROMIUM_LIKE = ('chromium', 'chrome', 'msedge')

# UA / Sec-CH-UA are built from the ACTUAL launched browser major version.
# A hardcoded Chrome 150 UA against a 157 binary is a detectable mismatch
# (navigator.userAgentData cannot be spoofed via HTTP headers).
CHROME_UA_TEMPLATE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/{v}.0.0.0 Safari/537.36"
)
SEC_CH_UA_TEMPLATE = (
    '"Chromium";v="{v}", "Not=A?Brand";v="24", "Google Chrome";v="{v}"'
)

PROXIES_PATH = Path(__file__).resolve().parent.parent / 'proxies.txt'

@dataclass
class BrowserConfig:
    browser_type: str = 'camoufox'
    headless: bool = True
    useragent: Optional[str] = None
    sec_ch_ua: Optional[str] = None
    proxy_support: bool = False
    debug: bool = False
    browser_version: Optional[str] = field(default=None, repr=False)

    @property
    def major(self) -> str:
        if self.browser_version:
            return self.browser_version.split('.')[0]
        return '150'

    @property
    def resolved_ua(self) -> str:
        return self.useragent or CHROME_UA_TEMPLATE.format(v=self.major)

    @property
    def resolved_sec_ch_ua(self) -> str:
        return self.sec_ch_ua or SEC_CH_UA_TEMPLATE.format(v=self.major)


def parse_proxy(proxy: str) -> dict:
    if '://' not in proxy:
        proxy = f'http://{proxy}'
    scheme, rest = proxy.split('://', 1)
    if '@' in rest:
        auth, addr = rest.split('@', 1)
        user, pwd = auth.split(':', 1)
        return {'server': f'{scheme}://{addr}', 'username': user, 'password': pwd}
    parts = rest.split(':')
    if len(parts) == 5:
        return {
            'server': f'{parts[0]}://{parts[1]}:{parts[2]}',
            'username': parts[3],
            'password': parts[4],
        }
    return {'server': proxy}


def pick_proxy(proxy_support: bool) -> Optional[str]:
    if not proxy_support:
        return None
    try:
        proxies = [line.strip() for line in PROXIES_PATH.read_text().splitlines() if line.strip()]
        return random.choice(proxies) if proxies else None
    except FileNotFoundError:
        logger.warning(f"Proxy file not found: {PROXIES_PATH}")
        return None


async def launch_browser(config: BrowserConfig) -> Tuple[object, object]:
    if config.browser_type == 'camoufox':
        try:
            from camoufox.async_api import AsyncCamoufox
            driver = AsyncCamoufox(headless=config.headless, os='macos',
                                   i_know_what_im_doing=True)
            browser = await driver.start()
            return driver, browser
        except Exception as e:
            logger.warning(f"camoufox unavailable ({e}), falling back to chromium")
            config.browser_type = 'chromium'


    driver = await async_playwright().start()
    args = ['--headless=new'] if config.headless else []
    args += [
        '--disable-blink-features=AutomationControlled',
        '--enable-unsafe-swiftshader',
        '--window-size=1280,720',
    ]
    browser = await driver.chromium.launch(
        channel=config.browser_type, headless=False, args=args)
    try:
        config.browser_version = browser.version
    except Exception:
        pass
    return driver, browser


def context_options(config: BrowserConfig, proxy: Optional[str]) -> dict:
    opts = {'viewport': {'width': 1280, 'height': 720}}
    if config.browser_type in CHROMIUM_LIKE and config.headless:
        opts['user_agent'] = config.resolved_ua
        opts['extra_http_headers'] = {
            'sec-ch-ua': config.resolved_sec_ch_ua,
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
        }
    elif config.useragent:
        opts['user_agent'] = config.useragent
    if proxy:
        opts['proxy'] = parse_proxy(proxy)
    return opts


async def close_browser(driver, browser, debug: bool = False) -> None:
    try:
        if browser:
            await browser.close()
    except Exception as e:
        if debug:
            logger.debug(f"Browser close error: {e}")
    try:
        if driver and hasattr(driver, 'stop'):
            await driver.stop()
    except Exception as e:
        if debug:
            logger.debug(f"Driver stop error: {e}")
