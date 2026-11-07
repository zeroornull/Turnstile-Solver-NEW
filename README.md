# 🚀 Cloudflare Turnstile + Challenge Solver

Local API solver for Cloudflare Turnstile and IUAM (Under Attack Mode) — harvests tokens and cf_clearance cookies via a real browser.

[![Version](https://img.shields.io/badge/version-2.0.0-blue)](https://github.com/D3-vin/Turnstile-Solver-NEW/releases)
[![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-Educational%20Use-green)](LICENSE)

[![Telegram Channel](https://img.shields.io/badge/Telegram-Channel-blue?logo=telegram)](https://t.me/D3_vin)
[![Telegram Chat](https://img.shields.io/badge/Telegram-Chat-blue?logo=telegram)](https://t.me/D3vin_chat)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-black?logo=github)](https://github.com/D3-vin/Turnstile-Solver-NEW)

[Features](#features) • [Quick Start](#quick-start) • [Usage](#usage) • [API](#api-documentation) • [Contact](#contact)

[English](#) | [Русский](README_RU.md)

---

> **New in 2.0:** IUAM support — pass Cloudflare "Under Attack" interstitials and harvest `cf_clearance` via the new `/cf_clearance` endpoint. Modular architecture (`turnstile` / `cf_clearance` / `core`), in-memory task storage, quiet logs.

## Features

- 🎯 **Turnstile solving** - Camoufox (anti-detect Firefox) with trusted checkbox clicks, hostname-correct stub + real-page fallback
- 🛡️ **IUAM / Challenge pass** - Managed Challenge + JS Challenge interstitials, harvests `cf_clearance` with the full replay bundle (cookies, User-Agent, headers)
- 🚀 **Multi-threaded** - Solve multiple tasks simultaneously with a concurrency limit
- 🌐 **Anti-detect by default** - Camoufox (default); Chrome, Edge, Chromium also supported
- 🔌 **Proxy support** - All formats from `proxies.txt`, plus per-request proxy for `/cf_clearance`
- 📊 **REST API** - Async task model (create task → poll result), easy to integrate
- 📦 **No database** - Tasks live in memory, nothing to maintain

---

## Quick Start

### 1. Install

```bash
git clone https://github.com/D3-vin/Turnstile-Solver-NEW.git
cd Turnstile-Solver-NEW
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 2. Install a browser

```bash
python -m camoufox fetch                # default browser (anti-detect Firefox)
python -m patchright install chromium   # optional fallback browser
```

### 3. Run

```bash
python api.py
```

Server starts on `http://0.0.0.0:5072`.

### Docker (browser included)

The Docker image bundles Camoufox (anti-detect Firefox) and Chromium at build time.
No browser or Python packages are downloaded when the container starts, and the
host only needs Docker. The initial image build requires internet access.

Prebuilt image (`linux/amd64` and `linux/arm64`), published by GitHub Actions
to this repository's GitHub Packages:
`ghcr.io/zeroornull/turnstile-solver-new:latest`.
`docker pull` selects the architecture that matches the host.
If the package is private, authenticate with `docker login ghcr.io` using a
GitHub account with package access and a classic PAT with `read:packages`.

```bash
docker pull ghcr.io/zeroornull/turnstile-solver-new:latest
docker run -d --name turnstile-solver --init --restart unless-stopped \
  --shm-size=1g -p 127.0.0.1:5072:5072 \
  ghcr.io/zeroornull/turnstile-solver-new:latest
```

Or build locally:

```bash
docker build -t turnstile-solver:local .
docker run -d --name turnstile-solver --init --restart unless-stopped \
  --shm-size=1g -p 127.0.0.1:5072:5072 turnstile-solver:local
```

Open `http://127.0.0.1:5072`. Docker runs the bundled Camoufox in headless mode,
so no display server is needed. Chrome, Edge and system Chrome are not included.
Append CLI options after the image name, for example `turnstile-solver:local --thread 2 --debug`.

The API has no authentication; keep the localhost port binding unless access is
protected separately. Proxy credentials are excluded from the image; mount your
`proxies.txt` at `/app/proxies.txt` read-only and pass `--proxy` when needed.

To deploy without downloading browsers or packages on the target machine:

```bash
docker save -o turnstile-solver.tar turnstile-solver:local
# Copy the archive to a machine with a matching CPU architecture, then:
docker load -i turnstile-solver.tar
```

Run the loaded image with the command above; add `--pull=never` to prevent image
pulls. Solving still requires network access to the target site. See the
[Chinese Docker guide](docs/docker.zh-CN.md) for proxy mounts, port configuration
and a network-disabled browser/API smoke test.

---

## Usage

```bash
python api.py [options]

Options:
  --no-headless           Show the browser window (default: headless)
  --browser_type string   camoufox (default) | chromium | chrome | msedge
  --thread int            Max concurrent solves (default 4)
  --proxy                 Use random proxy from proxies.txt
  --useragent string      Custom User-Agent
  --debug                 Verbose logging + HTTP access logs
  --host string           Listen address (default "0.0.0.0")
  --port string           Listen port (default "5072")
```

Test client:

```bash
python test_solve.py                            # Turnstile (bypass.city)
python test_solve.py --type cf_clearance        # IUAM (ivasms.com)
python test_solve.py --type cf_clearance --proxy http://user:pass@ip:port
```

---

## API Documentation

### Solve Turnstile

```
GET /turnstile?url=https://example.com&sitekey=0x4AAAAAAA
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `url` | string | Page where Turnstile is validated | Yes |
| `sitekey` | string | Turnstile site key | Yes |
| `action` | string | Widget `data-action` binding | No |
| `cdata` | string | Widget `data-cdata` binding | No |
| `proxy` | string | Per-request proxy (Turnstile is bound to the exit IP) | No |

### Pass IUAM (cf_clearance)

```
GET /cf_clearance?url=https://protected.com&proxy=http://user:pass@ip:port
```

| Parameter | Type | Description | Required |
|-----------|------|-------------|----------|
| `url` | string | Cloudflare-protected page URL | Yes |
| `proxy` | string | Per-request proxy (cf_clearance is bound to the exit IP) | No |
| `timeout` | int | Solve timeout, seconds (default 60) | No |

Both endpoints return a task:

```json
{ "errorId": 0, "taskId": "d2cbb257-9c37-4f9c-9bc7-1eaee72d96a8" }
```

### Get Result

```
GET /result?id=d2cbb257-9c37-4f9c-9bc7-1eaee72d96a8
```

Processing:

```json
{ "status": "processing" }
```

Turnstile ready:

```json
{ "errorId": 0, "status": "ready", "solution": { "token": "0.KBtT-r..." } }
```

cf_clearance ready:

```json
{
  "errorId": 0,
  "status": "ready",
  "solution": {
    "cf_clearance": { "name": "cf_clearance", "value": "...", "domain": ".example.com" },
    "cookies": [ "..." ],
    "user_agent": "Mozilla/5.0 ...",
    "headers": { "User-Agent": "...", "Accept-Language": "..." },
    "proxy": "http://...",
    "warning": "cf_clearance is bound to IP + JA3/TLS + User-Agent..."
  }
}
```

> ⚠️ Replay `cf_clearance` only from the same IP, with the returned `user_agent`, over a client with a matching TLS fingerprint (curl-impersonate or a real browser).

---

## Project Structure

```
Turnstile-Solver-NEW/
├── api.py               # Quart app: routes, in-memory tasks, CLI
├── test_solve.py        # Test client (turnstile / cf_clearance)
├── requirements.txt
├── core/
│   ├── browser.py       # Browser config, launch, context, proxy helpers
│   ├── logger.py        # Colored logger
│   └── templates.py     # Turnstile HTML template, JS snippets, route glob
├── turnstile/
│   └── solve.py         # Route-intercept + real-page Turnstile solving
└── cf_clearance/
    └── solve.py         # IUAM interstitial pass + cf_clearance harvest
```

---

## Troubleshooting

### "Browser not found"
Run `python -m camoufox fetch` (default browser) or `python -m patchright install chromium` (fallback).

### "Port already in use"
Change it: `python api.py --port 5080`.

### cf_clearance not set (challenge unsolved)
Datacenter IPs are scored harshly — run with `--no-headless` and/or a residential proxy.

### Turnstile token never appears (error 600010 / status=fail)
Cloudflare returns `600010` ("bot behavior detected") for headless Chromium and
datacenter IPs. The default **Camoufox** browser passes the real challenge where
plain headless Chromium does not. If it still fails, supply a residential proxy:
`--proxy` (from `proxies.txt`) or per-request `/turnstile?...&proxy=http://user:pass@ip:port`.
`600*` errors are retryable; the solver retries both the hostname-correct stub
and the real page. Tokens are single-use and must be replayed within 300s.

---

## Contact

- **GitHub**: https://github.com/D3-vin/Turnstile-Solver-NEW
- **Telegram Channel**: [@D3_vin](https://t.me/D3_vin)
- **Telegram Chat**: [@D3vin_chat](https://t.me/D3vin_chat)

### ❤️ Support the Project

- **EVM:** 0xeba21af63e707ce84b76a87d0ba82140048c057e (ETH, BNB, etc)
- **TRON:** TEfECnyz5G1EkFrUqnbFcWLVdLvAgW9Raa
- **TON:** UQCJ7KC2zxV_zKwLahaHf9jxy0vsWRcvQFie_FUBJW-9LcEW
- **BTC:** bc1qdag98y5yahs6wf7rsfeh4cadsjfzmn5ngpjrcf
- **SOL:** EwXXR4VqmWSNz1sjhZ8qcQ882i4URwAwhixSPEbDzyv6
- **SUI:** 0x76da9b74c61508fbbd0b3e1989446e036b0622f252dd8d07c3fce759b239b47d

---

## License

Educational use only - see [LICENSE](LICENSE) file.

**⚠️ Disclaimer**: This tool is for educational purposes only. Use at your own risk. The author is not responsible for API blocking, IP bans, or any other consequences.
