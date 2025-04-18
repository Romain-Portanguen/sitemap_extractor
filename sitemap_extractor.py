"""
Sitemap Extractor CLI
--------------------
Extracts URLs from a sitemap XML (local or remote, including sitemap indexes) and exports them in various formats.
Handles most anti-bot protections, with an interactive Playwright fallback for manual extraction if needed.

Limitations:
- Some servers use advanced fingerprinting and will only serve the sitemap to real browsers. In such cases, download the sitemap manually and use this script in local file mode.
"""

import typer
from typing import Optional, List, Set
from pathlib import Path
import requests
import xml.etree.ElementTree as ET
import json
import pandas as pd
import yaml
import sys
import questionary
import os
import random
import time

# Try to import Playwright for advanced extraction
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

app = typer.Typer(help="Extract URLs from a sitemap XML file (local or remote) and export them in various formats.")

# User agents for anti-bot evasion
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

MAX_SITEMAP_DEPTH = 20  # To avoid infinite loops in sitemap indexes


def log_public_ip():
    """Log the public IP used for requests."""
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
        typer.echo(f"[Info] Public IP used for requests: {ip}")
    except Exception as e:
        typer.echo(f"[Warning] Could not determine public IP: {e}", err=True)


def apply_stealth(page):
    """Inject JS to hide Playwright fingerprint (canvas, WebGL, audio, etc.)."""
    stealth_js = """
    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
    Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
    window.chrome = { runtime: {} };
    Object.defineProperty(navigator, 'platform', {get: () => 'Win32'});
    Object.defineProperty(navigator, 'userAgent', {get: () => navigator.userAgent.replace('HeadlessChrome', 'Chrome')});
    // Canvas fingerprint spoof
    const getContext = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = function(type, ...args) {
        const context = getContext.apply(this, [type, ...args]);
        if (type === '2d') {
            const getImageData = context.getImageData;
            context.getImageData = function(...args) {
                const imageData = getImageData.apply(this, args);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] = imageData.data[i] ^ 0x12;
                }
                return imageData;
            };
        }
        return context;
    };
    // WebGL fingerprint spoof
    const getParameter = WebGLRenderingContext.prototype.getParameter;
    WebGLRenderingContext.prototype.getParameter = function(parameter) {
        if (parameter === 37445) return 'Intel Inc.';
        if (parameter === 37446) return 'Intel Iris OpenGL Engine';
        return getParameter.apply(this, [parameter]);
    };
    // Audio fingerprint spoof
    const getChannelData = AudioBuffer.prototype.getChannelData;
    AudioBuffer.prototype.getChannelData = function() {
        const data = getChannelData.apply(this, arguments);
        for (let i = 0; i < data.length; i += 100) {
            data[i] = data[i] + 0.0001;
        }
        return data;
    };
    delete navigator.__proto__.permissions;
    window.navigator.permissions = {
        query: (parameters) => {
            return Promise.resolve({ state: parameters.name === 'notifications' ? 'denied' : 'granted' });
        }
    };
    Object.defineProperty(window, 'outerWidth', {get: () => window.innerWidth});
    Object.defineProperty(window, 'outerHeight', {get: () => window.innerHeight});
    """
    page.add_init_script(stealth_js)


def read_sitemap(source: str) -> str:
    """
    Download and return the sitemap XML content from a local file or URL.
    Tries requests with anti-bot headers, then Playwright (interactive) as fallback.
    """
    if source.startswith("http://") or source.startswith("https://"):
        last_exc = None
        # Try up to 3 times with requests and anti-bot headers
        for attempt in range(3):
            user_agent = random.choice(USER_AGENTS)
            headers = {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "DNT": "1",
                "Referer": "https://www.google.com/",
                "sec-ch-ua": '"Chromium";v="122", "Not:A-Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
                "Sec-Fetch-User": "?1"
            }
            cookies = {
                "sessionid": str(random.randint(100000, 999999)),
                "_ga": str(random.randint(100000, 999999)),
                "_gid": str(random.randint(100000, 999999)),
            }
            try:
                resp = requests.get(source, headers=headers, cookies=cookies, timeout=15)
                if resp.status_code == 200:
                    resp.encoding = resp.apparent_encoding or resp.encoding
                    return resp.text
                else:
                    typer.echo(f"[Warning] HTTP {resp.status_code} for {source} (attempt {attempt+1}/3)", err=True)
                    typer.echo(f"[Debug] Headers: {headers}", err=True)
            except Exception as e:
                last_exc = e
                typer.echo(f"[Warning] Error fetching {source} (attempt {attempt+1}/3): {e}", err=True)
            time.sleep(random.uniform(2, 5) * (attempt + 1))
        # Playwright fallback: interactive mode for manual extraction
        if PLAYWRIGHT_AVAILABLE:
            typer.echo(f"[Info] Falling back to Playwright (interactive mode) for {source}", err=True)
            typer.echo("A Chromium window will open. If needed, interact with the page (solve captchas, click, scroll, reload, etc.), then return to this terminal and press Enter to capture the sitemap content.")
            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=False)
                    context = browser.new_context(
                        user_agent="Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
                        viewport={"width": 1280, "height": 800}
                    )
                    page = context.new_page()
                    apply_stealth(page)
                    nav_failed = False
                    try:
                        page.goto(source, timeout=30000, wait_until="domcontentloaded")
                    except Exception as e:
                        nav_failed = True
                        typer.echo(f"[Warning] Playwright navigation failed: {e}", err=True)
                        typer.echo("[Info] The browser will remain open. You can reload the page manually or interact as needed.", err=True)
                    if not nav_failed:
                        try:
                            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        except Exception:
                            pass  # Ignore JS errors if any
                    input("\n[Action required] When the sitemap is fully loaded and visible in the browser, press Enter here to capture the content...")
                    try:
                        content = page.content()
                        browser.close()
                        return content
                    except Exception as e:
                        typer.echo(f"[Error] Could not capture the page content: {e}", err=True)
                        typer.echo("[Help] If you see the sitemap in the browser, you can save it manually and use the script in local file mode.", err=True)
                        browser.close()
                        raise requests.RequestException(f"Playwright failed for {source}: {e}")
            except Exception as e:
                typer.echo(f"[Error] Playwright failed for {source}: {e}", err=True)
                raise requests.RequestException(f"Playwright failed for {source}: {e}")
        else:
            typer.echo("[Error] Playwright is not installed. Run 'pip install playwright' and 'playwright install' to enable advanced extraction.", err=True)
        raise requests.RequestException(f"Failed to fetch {source} after 3 attempts. Last error: {last_exc}")
    else:
        with open(source, "r", encoding="utf-8") as f:
            return f.read()


def is_sitemap_index(xml_content: str) -> bool:
    """Detect if the XML is a sitemap index."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError:
        return False
    return root.tag.endswith('sitemapindex')


def extract_sitemaps_from_index(xml_content: str) -> List[str]:
    """Extract child sitemap URLs from a sitemap index XML."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        typer.echo(f"Error parsing XML: {e}", err=True)
        raise typer.Exit(1)
    ns = {}
    if root.tag.startswith('{'):
        uri = root.tag.split('}')[0].strip('{')
        ns = {'ns': uri}
        loc_tag = './/ns:loc'
    else:
        loc_tag = './/loc'
    sitemaps = [elem.text.strip() for elem in root.findall(loc_tag, ns) if elem.text]
    return sitemaps


def extract_urls_from_sitemap(xml_content: str) -> List[str]:
    """Extract URLs from a sitemap XML (not an index)."""
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        typer.echo(f"Error parsing XML: {e}", err=True)
        raise typer.Exit(1)
    ns = {}
    if root.tag.startswith('{'):
        uri = root.tag.split('}')[0].strip('{')
        ns = {'ns': uri}
        loc_tag = './/ns:loc'
    else:
        loc_tag = './/loc'
    urls = [elem.text.strip() for elem in root.findall(loc_tag, ns) if elem.text]
    return urls


def extract_all_urls(source: str, depth: int = 0, visited: Optional[Set[str]] = None) -> List[str]:
    """
    Recursively extract all URLs from a sitemap or sitemap index, following child sitemaps.
    """
    if visited is None:
        visited = set()
    if source in visited:
        return []
    visited.add(source)
    try:
        xml_content = read_sitemap(source)
    except requests.RequestException as e:
        typer.echo(f"[Warning] Could not fetch {source}: {e}", err=True)
        return []
    if is_sitemap_index(xml_content):
        if depth >= MAX_SITEMAP_DEPTH:
            typer.echo(f"Max sitemap index depth reached at {source}", err=True)
            return []
        typer.echo(f"Sitemap index detected: {source}\nFetching child sitemaps...")
        child_sitemaps = extract_sitemaps_from_index(xml_content)
        all_urls = []
        for child in child_sitemaps:
            typer.echo(f"  -> {child}")
            try:
                all_urls.extend(extract_all_urls(child, depth + 1, visited))
            except Exception as e:
                typer.echo(f"[Warning] Could not parse {child}: {e}", err=True)
                continue
        return all_urls
    else:
        try:
            return extract_urls_from_sitemap(xml_content)
        except Exception as e:
            typer.echo(f"[Warning] Could not parse {source}: {e}", err=True)
            return []


def output_urls(urls: List[str], fmt: str, output: Optional[Path]):
    """Export the list of URLs in the chosen format."""
    fmt = fmt.lower()
    if fmt == "txt":
        content = "\n".join(urls)
        if output:
            output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
    elif fmt == "json":
        content = json.dumps(urls, indent=2, ensure_ascii=False)
        if output:
            output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
    elif fmt == "csv":
        df = pd.DataFrame(urls, columns=["url"])
        if output:
            df.to_csv(output, index=False)
        else:
            print(df.to_csv(index=False), end="")
    elif fmt == "xlsx":
        df = pd.DataFrame(urls, columns=["url"])
        if output:
            df.to_excel(output, index=False)
        else:
            print("[XLSX output cannot be displayed in terminal. Please specify an output file with --output/-o]", file=sys.stderr)
    elif fmt == "yaml":
        content = yaml.dump(urls, allow_unicode=True)
        if output:
            output.write_text(content, encoding="utf-8")
        else:
            print(content, end="")
    else:
        typer.echo(f"Unsupported format: {fmt}", err=True)
        raise typer.Exit(1)


def interactive_mode():
    """Run the interactive CLI mode for less technical users."""
    # Show public IP in the interactive title
    try:
        ip = requests.get("https://api.ipify.org", timeout=10).text
        ip_str = f" (IP: {ip})"
    except Exception:
        ip_str = " (IP: unknown)"
    typer.echo(f"\n--- Sitemap Extractor (Interactive Mode) ---{ip_str}\n")
    # 1. Source type
    source_type = questionary.select(
        "Where is your sitemap?",
        choices=["Local file", "URL"]
    ).ask()
    if source_type == "Local file":
        source = questionary.path(
            "Enter the path to your sitemap XML file:",
            validate=lambda p: os.path.isfile(p) or "File does not exist"
        ).ask()
    else:
        source = questionary.text(
            "Enter the sitemap URL:"
        ).ask()
    # 2. Output format
    fmt = questionary.select(
        "Choose output format:",
        choices=["txt", "json", "csv", "xlsx", "yaml"]
    ).ask()
    # 3. Output destination
    output_choice = questionary.select(
        "How do you want to get the result?",
        choices=["Display in terminal", "Save to file"]
    ).ask()
    if output_choice == "Save to file":
        default_name = f"urls.{fmt}"
        output_path = questionary.text(
            f"Enter output file name:",
            default=default_name
        ).ask()
        output = Path(output_path)
    else:
        output = None
    # 4. Run extraction
    typer.echo("\nExtracting URLs...\n")
    try:
        urls = extract_all_urls(source)
        if not urls:
            typer.echo("No URLs found in the sitemap.", err=True)
            raise typer.Exit(1)
        typer.echo(f"Total URLs extracted: {len(urls)}")
        output_urls(urls, fmt, output)
        typer.echo("\nDone!")
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def main(
    source: Optional[str] = typer.Argument(None, help="Path to the local sitemap XML file or URL."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path. If not set, print to stdout."),
    format: str = typer.Option("txt", "--format", "-f", help="Output format: txt, json, csv, xlsx, yaml."),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Run in interactive mode.")
):
    """
    Extract URLs from a sitemap XML file (local or remote) and export them in various formats.
    """
    log_public_ip()
    if interactive:
        interactive_mode()
        raise typer.Exit()
    if not source:
        typer.echo("Error: You must provide a source (file path or URL) unless using --interactive.", err=True)
        raise typer.Exit(1)
    try:
        urls = extract_all_urls(source)
        if not urls:
            typer.echo("No URLs found in the sitemap.", err=True)
            raise typer.Exit(1)
        typer.echo(f"Total URLs extracted: {len(urls)}")
        output_urls(urls, format, output)
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app() 