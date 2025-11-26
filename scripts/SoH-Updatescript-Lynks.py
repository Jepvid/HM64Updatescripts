#!/usr/bin/env python3
"""
update_from_pr_description.py

Downloads the correct soh-<os>.zip artifact for a given PR by reading
the PR description (Markdown links) and falling back to scraping the PR HTML
if needed. Uses nightly.link URLs so no GitHub login is required.
"""

import os
import re
import json
import requests
import platform
import zipfile
import shutil
import sys
from typing import Optional, Dict

# -------- CONFIG --------
REPO = "TheLynk/Shipwright"
PR_NUMBER = 11

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(SCRIPT_DIR, "version.json")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")

ARTIFACT_OS_MAP = {
    "windows": "soh-windows.zip",
    "linux": "soh-linux.zip",
    "darwin": "soh-mac.zip",
}

USER_AGENT = "Mozilla/5.0 (update_from_pr_script)"


# -------- Helpers --------
def load_local_version() -> Optional[dict]:
    if not os.path.exists(VERSION_FILE):
        return None
    with open(VERSION_FILE, "r") as f:
        return json.load(f)


def save_local_version(download_url: str):
    with open(VERSION_FILE, "w") as f:
        json.dump({
            "download_url": download_url,
            "repo": REPO,
            "pr_number": PR_NUMBER
        }, f, indent=4)


def get_os_key() -> str:
    sysname = platform.system().lower()
    if sysname in ARTIFACT_OS_MAP:
        return sysname
    raise RuntimeError(f"Unsupported OS: {sysname}")


# -------- Fetch PR description (API) --------
def fetch_pr_body(repo: str, pr_number: int) -> str:
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(url, headers=headers)
    r.raise_for_status()
    data = r.json()
    return data.get("body") or ""


# -------- Parse Markdown links from PR body --------
def extract_markdown_links_from_body(body: str) -> Dict[str, str]:
    """
    Finds markdown links where link text is soh-<os>.zip, e.g.
    [soh-linux.zip](https://nightly.link/...)
    Returns dict: { "soh-linux.zip": "https://..." }
    """
    links = {}
    # Markdown link pattern: [text](url)
    # Use a regex tolerant of line breaks inside parentheses (rare).
    pattern = re.compile(r"\[([^\]]+)\]\(\s*(https?://[^\s)]+)\s*\)", flags=re.IGNORECASE)
    for m in pattern.finditer(body):
        text = m.group(1).strip()
        url = m.group(2).strip()
        # normalize text (lower)
        if re.match(r"^soh-(windows|linux|mac)\.zip$", text, flags=re.IGNORECASE):
            links[text.lower()] = url
    return links


# -------- Fallback: scrape PR HTML (if body didn't have links) --------
def fetch_pr_html(pr_url: str) -> str:
    headers = {"User-Agent": USER_AGENT}
    r = requests.get(pr_url, headers=headers)
    r.raise_for_status()
    return r.text


def extract_nightly_links_from_html(html: str) -> Dict[str, str]:
    """
    Scrape for occurrences where the visible text is soh-<os>.zip and
    the href points to nightly.link.
    """
    links = {}
    # Match either: <a ...>soh-linux.zip</a> ... href="https://nightly.link/..."
    # We'll search for pairs in a small window to reduce false positives.
    # This pattern captures the link text and subsequent nightly.link URL.
    pattern = re.compile(
        r"(soh-(?:windows|linux|mac)\.zip)[\s\S]{0,200}?href=[\"'](https://nightly\.link/[^\s\"'>]+)[\"']",
        flags=re.IGNORECASE,
    )
    for m in pattern.finditer(html):
        name = m.group(1).strip().lower()
        url = m.group(2).strip()
        links[name] = url
    return links


# -------- Download & extract --------
def download_file(url: str, filename: str) -> str:
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    filepath = os.path.join(DOWNLOAD_DIR, filename)
    print(f"Downloading: {url} -> {filepath}")
    with requests.get(url, stream=True, headers={"User-Agent": USER_AGENT}) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    print(f"Saved to: {filepath}")
    return filepath


def extract_zip(filepath: str):
    print(f"Extracting: {filepath} -> {SCRIPT_DIR}")
    with zipfile.ZipFile(filepath, "r") as z:
        z.extractall(SCRIPT_DIR)
    print("Extraction done.")


def clear_downloads():
    if os.path.exists(DOWNLOAD_DIR):
        print("Clearing downloads folder...")
        shutil.rmtree(DOWNLOAD_DIR)


# -------- Main logic --------
def install_or_update_from_pr():
    os_key = get_os_key()
    target_filename = ARTIFACT_OS_MAP[os_key].lower()

    local = load_local_version()

    # 1) Try PR body first
    print(f"Fetching PR #{PR_NUMBER} description via API...")
    try:
        body = fetch_pr_body(REPO, PR_NUMBER)
    except Exception as e:
        print(f"Warning: failed to fetch PR body via API: {e}")
        body = ""

    links = {}
    if body:
        links = extract_markdown_links_from_body(body)
        if links:
            print("Found artifact links in PR body (markdown links).")
    else:
        print("PR body empty or unavailable.")

    # 2) Fallback: scrape PR HTML if no links found in body
    if not links:
        pr_url = f"https://github.com/{REPO}/pull/{PR_NUMBER}"
        print("Falling back to scraping PR HTML for artifact links...")
        try:
            html = fetch_pr_html(pr_url)
            links = extract_nightly_links_from_html(html)
            if links:
                print("Found artifact links in PR HTML.")
        except Exception as e:
            print(f"Failed to fetch/scrape PR HTML: {e}")

    if not links:
        raise RuntimeError("No soh-<os>.zip artifact links found in PR body or HTML.")

    if target_filename not in links:
        available = ", ".join(sorted(links.keys()))
        raise RuntimeError(f"Artifact for this OS ('{target_filename}') not found. Available links: {available}")

    download_url = links[target_filename]
    print(f"Selected artifact for OS '{os_key}': {target_filename} -> {download_url}")

    # Skip if already downloaded
    if local and local.get("download_url") == download_url:
        print("Already up-to-date with this artifact URL.")
        return

    # Download (nightly.link returns a zip) and extract
    zip_path = download_file(download_url, target_filename)
    extract_zip(zip_path)

    save_local_version(download_url)
    print("version.json updated.")

    # Cleanup
    clear_downloads()


# -------- Entry --------
if __name__ == "__main__":
    try:
        install_or_update_from_pr()
    except Exception as exc:
        print("Error:", exc)
        sys.exit(1)
