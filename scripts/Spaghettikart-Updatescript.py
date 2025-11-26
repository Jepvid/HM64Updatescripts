import os
import json
import requests
import platform
import zipfile
import shutil

REPO = "HarbourMasters/Spaghettikart"

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


def get_os_tag():
    sys = platform.system().lower()

    if sys == "windows":
        return "windows"

    if sys == "linux":
        return "linux-old"

    if sys == "darwin":
        raise RuntimeError("⚠️ Spaghettikart has no macOS build available.")

    raise RuntimeError(f"Unsupported OS: {sys}")


def get_latest_any_release():
    """
    Fetches all releases (including pre-releases) and returns the newest one.
    """
    url = f"https://api.github.com/repos/{REPO}/releases"
    r = requests.get(url)
    r.raise_for_status()

    releases = r.json()
    if not releases:
        raise RuntimeError("No releases or pre-releases found.")

    return releases[0]  # GitHub sorts newest → oldest


def download_asset(asset):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    url = asset["browser_download_url"]
    dest = os.path.join(DOWNLOAD_DIR, asset["name"])

    print(f"Downloading: {asset['name']}")

    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

    print(f"Downloaded to: {dest}")
    return dest


def extract_zip(filepath):
    print(f"Extracting {filepath} ...")
    with zipfile.ZipFile(filepath, "r") as z:
        z.extractall(SCRIPT_DIR)
    print("Extraction complete.")


def clear_downloads():
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)


def install_or_update():
    local = load_local_version()
    installed = local["installed_version"] if local else None

    release = get_latest_any_release()
    latest = release["tag_name"]
    assets = release["assets"]

    print(f"Installed version: {installed}")
    print(f"Latest online version: {latest}")

    if installed == latest:
        print("Already up-to-date.")
        return

    os_tag = get_os_tag()

    # Match filenames containing OS tag
    candidates = [
        a for a in assets
        if os_tag in a["name"].lower()
           and a["name"].lower().endswith(".zip")
    ]

    if not candidates:
        raise RuntimeError(f"No asset found for: {os_tag}")

    asset = candidates[0]
    print(f"Selected asset: {asset['name']}")

    zip_path = download_asset(asset)
    extract_zip(zip_path)
    save_local_version(latest)
    clear_downloads()

    print(f"Updated to version {latest}")


if __name__ == "__main__":
    install_or_update()
