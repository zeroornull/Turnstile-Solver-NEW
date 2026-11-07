from typing import Optional
from urllib.parse import urlsplit

# Bootstrap runs in the page's MAIN world (inline <script>), so it can see
# `window.turnstile` and receive Turnstile's callbacks. patchright's
# page.evaluate runs in an isolated world and cannot read JS globals, so every
# captured value is mirrored into a DOM attribute, which IS shared across
# worlds and readable via page.evaluate.
BOOTSTRAP_JS = """<script>
(function () {
  window.__ts = { token: '', error: '', timeout: false, widgetId: null };
  var root = document.documentElement;
  window.__tsToken = function (t) {
    window.__ts.token = t || '';
    try { root.setAttribute('data-ts-token', t || ''); } catch (e) {}
  };
  window.__tsError = function (code) {
    window.__ts.error = String(code);
    try { root.setAttribute('data-ts-error', String(code)); } catch (e) {}
    return false;
  };
  window.__tsTimeout = function () {
    window.__ts.timeout = true;
    try { root.setAttribute('data-ts-timeout', '1'); } catch (e) {}
  };
})();
</script>"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Turnstile</title>
<!--BOOTSTRAP-->
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { background: #1a1a1a; display: flex; justify-content: center;
       align-items: center; min-height: 100vh; }
</style>
</head>
<body>
<!--WIDGET-->
<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
</body></html>"""

# All hidden inputs, first non-empty wins. Also honour the callback-mirrored
# attribute (used when a widget has data-response-field="false").
TOKEN_VALUE_JS = """() => {
  const inputs = [...document.querySelectorAll('input[name="cf-turnstile-response"]')];
  const fromInput = inputs.map(e => e.value).find(v => v && v.length) || '';
  return fromInput || document.documentElement.getAttribute('data-ts-token') || '';
}"""

# Read the diagnostic attributes so the solver can react to 600* / 300* errors.
TS_STATE_JS = """() => ({
  error: document.documentElement.getAttribute('data-ts-error') || '',
  timeout: document.documentElement.getAttribute('data-ts-timeout') || '',
})"""

# Injected into the real page (main world) before any site script runs. It
# defines the widget's otherwise-missing `javascriptCallback` and mirrors any
# token into a DOM attribute. Safe: if the site defines its own callback later,
# that assignment simply overwrites this one and still lands in the same input.
MAIN_WORLD_HOOK_JS = """(() => {
  const root = document.documentElement;
  const capture = (t) => { try { root.setAttribute('data-ts-token', t || ''); } catch (e) {} };
  if (typeof window.javascriptCallback !== 'function') {
    window.javascriptCallback = capture;
  }
  // Mirror hidden-input values too (covers widgets without a callback).
  const mirror = () => {
    const vals = [...document.querySelectorAll('input[name="cf-turnstile-response"]')]
      .map(e => e.value).filter(v => v && v.length);
    if (vals.length) capture(vals[0]);
  };
  try {
    new MutationObserver(mirror).observe(document.documentElement,
      { subtree: true, childList: true, attributes: true,
        attributeFilter: ['value'] });
  } catch (e) {}
  document.addEventListener('DOMContentLoaded', mirror);
})();"""


def route_glob(url: str) -> str:
    """Glob matching ONLY the navigation to `url` (never /cdn-cgi/ subresources)."""
    parts = urlsplit(url)
    path = parts.path or '/'
    if path == '/':
        return f'{parts.scheme}://{parts.netloc}/'
    return url


def build_route_html(sitekey: str, action: Optional[str] = None,
                     cdata: Optional[str] = None) -> str:
    attrs = f'class="cf-turnstile" data-sitekey="{sitekey}"'
    attrs += ' data-callback="__tsToken"'
    attrs += ' data-error-callback="__tsError"'
    attrs += ' data-timeout-callback="__tsTimeout"'
    attrs += ' data-theme="auto"'
    attrs += ' data-retry="auto" data-retry-interval="5000"'
    if action:
        attrs += f' data-action="{action}"'
    if cdata:
        attrs += f' data-cdata="{cdata}"'
    widget = f'<div {attrs}></div>'
    return (HTML_TEMPLATE
            .replace('<!--BOOTSTRAP-->', BOOTSTRAP_JS)
            .replace('<!--WIDGET-->', widget))
