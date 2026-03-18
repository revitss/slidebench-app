import sys
import os
import pandas as pd
from tkinter import messagebox

# ==========================================================
#  PATH UTILITY FUNCTIONS
# ==========================================================
# These functions solve the problem of finding files correctly
# whether the program is running from source code during development
# or as a compiled .exe built with PyInstaller.
#
# When running from source: files are relative to the program/ folder.
# When running as .exe: PyInstaller bundles files into a temporary
# folder stored in sys._MEIPASS, so paths must be adjusted accordingly.


def resource_path(relative_path):
    """
    Returns the absolute path to a resource file (images, CSVs, icons, etc.).
    Handles both development (running from source) and production
    (running as a compiled .exe with PyInstaller) environments.

    The function tries several candidate paths in order and returns
    the first one that actually exists on disk.

    Parameters
    ----------
    relative_path : str
        The relative path to the resource file e.g. 'resources/image.png'.

    Returns
    -------
    str
        The absolute path to the resource file.
        If no candidate path exists, returns the first candidate as a fallback.
    """
    # When running from source, the base directory is the folder
    # where this utils.py file is located (i.e. the program/ folder)
    dev_base = os.path.dirname(os.path.abspath(__file__))

    # When running as a compiled .exe, PyInstaller extracts all bundled
    # files to a temporary folder whose path is stored in sys._MEIPASS
    if getattr(sys, "frozen", False):
        # Running as a compiled executable
        exe_base = sys._MEIPASS
    else:
        # Running from source code
        exe_base = None

    # Build a list of candidate paths to try in order
    candidates = []

    # Candidate 1: look for the file inside the PyInstaller temp folder (exe only)
    if exe_base:
        candidates.append(os.path.join(exe_base, relative_path))

    # Candidate 2: look for the file relative to the program/ source folder
    candidates.append(os.path.join(dev_base, relative_path))

    # Candidate 3: if the path doesn't already include 'program/', try adding it
    # This handles cases where PyInstaller bundles everything inside a program/ subfolder
    if not relative_path.startswith("program" + os.sep) and not relative_path.startswith("program/"):
        if exe_base:
            candidates.append(os.path.join(exe_base, "program", relative_path))

    # Candidate 4: try just the filename in the root of the PyInstaller temp folder
    # This is a last resort fallback for flattened bundle structures
    if exe_base:
        candidates.append(os.path.join(exe_base, os.path.basename(relative_path)))

    # Return the first candidate path that actually exists on disk
    for p in candidates:
        if os.path.exists(p):
            return p

    # If none of the candidates exist, return the first one as a fallback
    # The caller will get a FileNotFoundError when trying to open it,
    # which gives a clearer error message than returning None
    return candidates[0]


def external_folder(folder_name):
    """
    Returns the absolute path to a folder that lives outside the program directory.
    Used for folders that store runtime data such as captured images, measurements,
    logs, and reference files that should persist between program runs and should
    not be bundled inside the executable.

    When running from source: the folder is created one level above program/
    When running as .exe: the folder is created next to the .exe file

    If the folder does not exist, it is created automatically.

    Parameters
    ----------
    folder_name : str
        The name of the external folder to access or create e.g. 'media', 'data'.

    Returns
    -------
    str
        The absolute path to the external folder.
    """
    if getattr(sys, "frozen", False):
        # Running as a compiled .exe
        # Place the folder next to the executable file so the user can find it easily
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running from source code
        # Go one level up from program/ to place the folder at the project root
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Build the full path to the external folder
    path = os.path.join(base_dir, folder_name)

    # Create the folder if it does not already exist
    # exist_ok=True prevents an error if the folder already exists
    os.makedirs(path, exist_ok=True)

    return path


# ==========================================================
#  STEP / MM CONVERSION FUNCTIONS
# ==========================================================
# The motor is controlled in steps, but the user interface works in millimeters.
# A lookup table stored in a CSV file (mm_to_steps.csv) maps between the two.
# The CSV has two columns: 'millimeters' and 'steps'.
#
# The table is loaded once when the module is first imported so it does not
# need to be reloaded every time a conversion is requested.

# Build the path to the CSV file using resource_path to handle both
# development and compiled exe environments
csv_path = resource_path(os.path.join("resources", "mm_to_steps.csv"))

# Load the conversion table from the CSV file into a pandas DataFrame
# If the file is missing, show a clear error instead of crashing silently
try:
    conversion_df = pd.read_csv(csv_path)
except FileNotFoundError:
    messagebox.showwarning("Error", f"Error: conversion table not found at {csv_path}.")
    messagebox.showwarning("Error", "Motor step/mm conversions will not work until this file is present.")
    # Create an empty DataFrame so the rest of the module can still be imported
    # without crashing — functions will raise errors when actually called
    conversion_df = pd.DataFrame(columns=['millimeters', 'steps'])


def mm_to_steps(mm_value):
    """
    Converts a distance in millimeters to the equivalent number of motor steps
    by looking up the value in the conversion table loaded from the CSV file.

    The conversion is not a simple formula — it uses a lookup table because
    the relationship between mm and steps may be non-linear or calibrated
    empirically for this specific motor and leadscrew combination.

    Parameters
    ----------
    mm_value : float or int
        The distance in millimeters to convert.
        Will be rounded to 2 decimal places to match the CSV precision.

    Returns
    -------
    int
        The corresponding number of motor steps.

    Raises
    ------
    ValueError
        If the given mm value is not found in the conversion table.
    """
    # Round to 2 decimal places to match the precision stored in the CSV
    mm_value = round(float(mm_value), 2)

    # Search the 'millimeters' column for a row matching the requested value
    matches = conversion_df.index[conversion_df['millimeters'] == mm_value]

    if not matches.empty:
        # Get the index of the first matching row
        index = matches[0]
        # Return the corresponding step count as an integer
        return int(conversion_df.loc[index, 'steps'])
    else:
        # No match found — raise an error so the caller knows the conversion failed
        raise ValueError(f"Value {mm_value} mm not found in conversion table.")


def steps_to_mm(steps_value):
    """
    Converts a motor step count to the equivalent distance in millimeters
    by looking up the value in the conversion table loaded from the CSV file.

    Used by read_current_position() in communication.py to convert the
    raw step count reported by the Arduino into a human readable mm value
    for display in the GUI.

    Parameters
    ----------
    steps_value : int
        The number of motor steps to convert.

    Returns
    -------
    float or None
        The corresponding distance in millimeters,
        or None if the step count is not found in the conversion table.
    """
    # Search the 'steps' column for a row matching the requested step count
    matches = conversion_df.index[conversion_df['steps'] == steps_value]

    if not matches.empty:
        # Get the index of the first matching row
        index = matches[0]
        # Return the corresponding mm value as a float
        return float(conversion_df.loc[index, 'millimeters'])
    else:
        # No match found — show a warning and return None
        # Unlike mm_to_steps, this does not raise an error because it is called
        # continuously by the position update loop and a missing value is not critical
        messagebox.showwarning("Error", f"Warning: step value {steps_value} not found in conversion table.")
        return None


"""
pyinstaller --onefile --windowed --name="SlideBench" --icon="program/resources/icon.ico" \
--hidden-import cv2 \
--collect-all cv2 \
--hidden-import pygrabber \
--hidden-import sklearn \
--hidden-import serial \
--add-data "program/resources;resources" \
program/main.py
"""