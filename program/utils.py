import sys
import os
import pandas as pd

# PATHS FUNCTIONS TO FIX RESOURCE USAGE PROBLEMS

def resource_path(relative_path):
    """
    Returns the absolute path to a resource file.

    Parameters
    ----------
    relative_path : str
        The relative path to the resource file.

    Returns
    -------
    str
        The absolute path to the resource file.
    """

    # Base path when running from source (e.g., inside "program/")
    dev_base = os.path.dirname(os.path.abspath(__file__))

    # Base path when running as a frozen .exe built with PyInstaller
    # PyInstaller extracts the bundled files to a temporary folder stored in _MEIPASS
    if getattr(sys, "frozen", False):
        exe_base = sys._MEIPASS
    else:
        exe_base = None

    candidates = []

    # 1) Try the provided relative path inside the appropriate base directory
    if exe_base:
        candidates.append(os.path.join(exe_base, relative_path))
    candidates.append(os.path.join(dev_base, relative_path))

    # 2) If the path doesn't already include "program/", try adding it
    # This helps in cases where PyInstaller bundles everything inside a "program" folder
    if not relative_path.startswith("program" + os.sep) and not relative_path.startswith("program/"):
        if exe_base:
            candidates.append(os.path.join(exe_base, "program", relative_path))
        candidates.append(os.path.join(dev_base, relative_path))  # redundant but harmless

    # 3) Finally, try only the filename in the base folder of the .exe
    if exe_base:
        candidates.append(os.path.join(exe_base, os.path.basename(relative_path)))

    # Return the first path that actually exists
    for p in candidates:
        if os.path.exists(p):
            return p

    return candidates[0]


def external_folder(folder_name):
    """
    Returns the absolute path to an external folder that lives outside the program folder.
    This is useful for folders that store runtime data, user-generated files, logs, etc.

    Parameters
    ----------
    folder_name : str
        The name of the folder to access or create.

    Returns
    -------
    str
        The absolute path to the external folder.
    """

    if getattr(sys, "frozen", False):
        # Running as a compiled .exe → use the directory where the executable is located
        base_dir = os.path.dirname(sys.executable)
    else:
        # Running from source → go one level up from the "program" directory
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Build the full path to the folder
    path = os.path.join(base_dir, folder_name)

    # Ensure the folder exists (creates it if necessary)
    os.makedirs(path, exist_ok=True)

    return path

# READS THE CSV FILE AND FUNCTIONS TO DO THE CONVERSION FROM STEPS TO MM AND VICE VERSA 

csv_path = resource_path("resources\\mm_to_steps.csv")
conversion_df = pd.read_csv(csv_path)


def mm_to_steps(mm_value):
    """
    Converts a distance in millimeters to motor steps using the lookup table
    defined in 'mm_to_steps.csv'.

    Parameters
    ----------
    mm_value : float or int
        The distance in millimeters to convert.

    Returns
    -------
    int
        The corresponding number of motor steps.

    Raises
    ------
    ValueError
        If the given millimeter value is not found in the conversion table.
    """
    # Round to two decimals to match the precision in the CSV file
    mm_value = round(float(mm_value), 2)

    # Search for rows where the 'millimeters' column matches mm_value
    matches = conversion_df.index[conversion_df['millimeters'] == mm_value]

    if not matches.empty:
        index = matches[0]
        return int(conversion_df.loc[index, 'steps'])
    else:
        raise ValueError(f"Value {mm_value} mm not found in conversion table.")


def steps_to_mm(steps_value):
    """
    Converts a motor step count to millimeters using the same lookup table.

    Parameters
    ----------
    steps_value : int
        The number of steps to convert.

    Returns
    -------
    float or None
        The corresponding distance in millimeters, or None if not found.
    """
    # Search for rows where the 'steps' column matches steps_value
    matches = conversion_df.index[conversion_df['steps'] == steps_value]

    if not matches.empty:
        index = matches[0]
        return float(conversion_df.loc[index, 'millimeters'])
    else:
        return None



"""
pyinstaller --onefile --windowed --name="SlideBench" --icon="program/resources/icon.ico" \
--hidden-import cv2 \
--collect-all cv2 \
--add-data "program;program" \
--add-data "data;data" \
--add-data "media;media" \
program/main.py

pyinstaller --onefile --windowed --name="SlideBench" --icon="program/resources/icon.ico" \
--hidden-import cv2 \
--collect-all cv2 \
--add-data "program;program" \
program/main.py

"""