import os
import json
import requests
import platform
import zipfile
import shutil

REPO = "HarbourMasters/2ship2harkinian"

# WORKING DIRECTORY = folder containing this script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(SCRIPT_DIR, "version.json")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")


def load_local_version():
    if not os.path.exists(VERSION_FILE):
        return None
    with open(VERSION_FILE, "r") as f:
        return json.load(f)


def save_local_version(version):
    with open(VERSION_FILE, "w") as f:
        json.dump({"installed_version": version, "repo": REPO}, f, indent=4)


def get_os_target_word():
    sys = platform.system().lower()

    if sys == "windows":
        return "Win64"
    if sys == "linux":
        return "Linux"
    if sys == "darwin":
        return "Mac"

    raise RuntimeError(f"Unsupported OS: {sys}")


def get_latest_release():
    url = f"https://api.github.com/repos/{REPO}/releases/latest"
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def download_asset(asset):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    url = asset["browser_download_url"]
    filepath = os.path.join(DOWNLOAD_DIR, asset["name"])

    print(f"Downloading: {asset['name']}")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    print(f"Saved to: {filepath}")
    return filepath


def extract_zip(filepath):
    print(f"Extracting {filepath} ...")
    with zipfile.ZipFile(filepath, "r") as zip_ref:
        zip_ref.extractall(SCRIPT_DIR)
    print("Extraction complete.")


def clear_downloads():
    """Remove the downloads folder entirely, then recreate it empty."""
    if os.path.exists(DOWNLOAD_DIR):
        print("Clearing downloads folder...")
        shutil.rmtree(DOWNLOAD_DIR)


def install_or_update():
    local = load_local_version()
    installed = local["installed_version"] if local else None

    if installed:
        print(f"Installed version: {installed}")
    else:
        print("No version.json found — fresh install.")

    release = get_latest_release()
    latest = release["tag_name"]
    assets = release["assets"]

    print(f"Latest version online: {latest}")

    if installed == latest:
        print("Already up-to-date.")
        return

    target_word = get_os_target_word().lower()

    # Match SoH pattern: end with -<OS>.zip
    candidates = [
        a for a in assets
        if a["name"].lower().endswith(f"-{target_word}.zip")
    ]

    if not candidates:
        raise RuntimeError(f"No matching asset for OS '{target_word}'")

    asset = candidates[0]
    print(f"Selected asset: {asset['name']}")

    zip_path = download_asset(asset)
    extract_zip(zip_path)

    save_local_version(latest)
    print("version.json updated.")

    # NEW: Clean up downloads folder
    clear_downloads()
    print("Downloads cleaned up.")


if __name__ == "__main__":
    install_or_update()
