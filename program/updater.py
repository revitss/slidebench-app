import requests
import webbrowser
from tkinter import messagebox

APP_VERSION = "1.0.0"  
GITHUB_REPO = "revitss/slidebench-app" 

def check_for_updates():
    """
    Checks GitHub for the latest release and compares it with the
    current app version. If a newer version is available, asks the
    user if they want to download it.
    """
    try:
        # Call the GitHub API to get the latest release information
        url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        response = requests.get(url, timeout=5)

        # If the request failed, silently ignore
        if response.status_code != 200:
            return

        # Extract the latest version tag e.g. "v1.0.1"
        latest_version = response.json()["tag_name"]
        # Remove the 'v' prefix to compare with APP_VERSION
        latest_clean = latest_version.lstrip("v")

        # Compare with current version
        if latest_clean != APP_VERSION:
            # A new version is available — ask the user
            answer = messagebox.askyesno(
                "Update available",
                f"A new version of SlideBench is available!\n\n"
                f"Current version: v{APP_VERSION}\n"
                f"New version: {latest_version}\n\n"
                f"Do you want to download it?"
            )
            if answer:
                # Open the browser at the latest release page
                webbrowser.open(
                    f"https://github.com/{GITHUB_REPO}/releases/latest"
                )

    except requests.ConnectionError:
        # No internet connection — silently ignore
        pass
    except Exception as e:
        # Any other error — silently ignore so the app still launches
        print(f"Update check failed: {e}")