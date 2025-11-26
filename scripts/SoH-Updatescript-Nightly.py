import os
import json
import requests
import platform
import zipfile
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(SCRIPT_DIR, "version.json")
DOWNLOAD_DIR = os.path.join(SCRIPT_DIR, "downloads")

REPO = "HarbourMasters/Shipwright"
BRANCH = "develop"
NIGHTLY_BASE = f"https://nightly.link/{REPO}/workflows/generate-builds/{BRANCH}"


def load_local_version():
    if os.path.exists(VERSION_FILE):
        with open(VERSION_FILE, "r") as f:
            return json.load(f)
    return None


def save_local_version(commit_sha):
    with open(VERSION_FILE, "w") as f:
        json.dump({"latest_commit": commit_sha}, f, indent=4)


def get_latest_commit_sha():
    url = f"https://api.github.com/repos/{REPO}/commits/{BRANCH}"
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    return data["sha"]


def get_os_zip_name():
    sys = platform.system().lower()
    if sys == "windows":
        return "soh-windows.zip"
    elif sys == "linux":
        return "soh-linux.zip"
    elif sys == "darwin":
        return "soh-mac.zip"
    else:
        raise RuntimeError(f"Unsupported OS: {sys}")


def download_nightly(zip_name):
    url = f"{NIGHTLY_BASE}/{zip_name}"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    dest = os.path.join(DOWNLOAD_DIR, zip_name)

    print(f"Downloading nightly: {zip_name}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)
    print(f"Downloaded to: {dest}")
    return dest


def extract_zip(filepath):
    print(f"Extracting {filepath} ...")
    with zipfile.ZipFile(filepath, "r") as zip_ref:
        zip_ref.extractall(SCRIPT_DIR)
    print("Extraction complete.")


def clear_downloads():
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)


def install_latest_nightly():
    local = load_local_version()
    installed_commit = local["latest_commit"] if local else None

    latest_commit = get_latest_commit_sha()
    print(f"Latest commit SHA on branch '{BRANCH}': {latest_commit}")

    if installed_commit == latest_commit:
        print("Already up-to-date.")
        clear_downloads()
        return

    zip_name = get_os_zip_name()
    zip_path = download_nightly(zip_name)
    extract_zip(zip_path)
    save_local_version(latest_commit)
    clear_downloads()
    print(f"Nightly updated to commit: {latest_commit}")


if __name__ == "__main__":
    install_latest_nightly()
