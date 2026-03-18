import os
# Set the number of threads for OpenCV to 1 to avoid performance issues
# with multithreading when running alongside other parallel processes
os.environ["OMP_NUM_THREADS"] = "1"
import time
from datetime import datetime
import numpy as np
import cv2
from sklearn.cluster import KMeans
import pandas as pd
from pathlib import Path
from tkinter import messagebox

from utils import external_folder
from controller import activate_filter, led_on, move_to_position, led_off, led_intensity
from camera_functions import capture_image_array
from communication import read_current_position

# List of optical filters used in measurements, in order
# w = white, r = red, g = green, b = blue
FILTERS = ['w', 'r', 'g', 'b']

# --- Folder structure for storing reference and measurement data --- #
# DATA_FOLDER is the top level folder outside the program directory
DATA_FOLDER = Path(external_folder("data"))
# REFERENCE_FOLDER stores the reference images and distances taken at position 0
REFERENCE_FOLDER = DATA_FOLDER / "reference"
# REFERENCE_PATH is the specific file where the reference distance array is saved
REFERENCE_PATH = REFERENCE_FOLDER / "reference_y0.npy"


def desired_position(target_position):
    """
    Blocks execution until the motor reaches the target position.
    Continuously reads the current motor position every 100ms and
    only returns when the position matches the target exactly.
    This is used to ensure the motor has fully stopped before
    capturing an image.

    Parameters
    ----------
    target_position : float
        The position in mm that the motor must reach before continuing.
    """
    while True:
        # Read the current motor position from the Arduino
        current = read_current_position()
        # Check if the position has been reached
        if current is not None and current == target_position:
            break
        # Wait 100ms before checking again to avoid hammering the serial port
        time.sleep(0.1)

def compute_distances_to_center(img):
    """
    Analyzes an image to find 9 blob points arranged in a 3x3 grid
    and computes the distances from each of the 8 outer blobs to the
    center blob using intensity-weighted centroids.

    The function performs the following steps:
    1. Convert to grayscale
    2. Binarize using Otsu thresholding
    3. Find connected components (blobs)
    4. Select the 9 largest blobs
    5. Validate blob similarity
    6. Compute intensity-weighted center for each blob
    7. Group blobs into 3 rows using KMeans clustering
    8. Order blobs left to right, top to bottom
    9. Compute distances from each outer blob to the center blob

    Parameters
    ----------
    img : numpy array
        The input image as a NumPy array (RGB, shape HxWx3).

    Returns
    -------
    numpy array
        Array of 8 distances in pixels, rounded to 2 decimal places.
        Returns an array of zeros if detection fails.
    """
    # Convert to grayscale by averaging the three color channels equally
    # This avoids bias towards any particular color channel
    gray_img = np.mean(img, axis=2).astype(np.uint8)

    # Binarize the grayscale image using Otsu's method
    # Otsu automatically finds the optimal threshold value
    # Result: binary image where blobs are white (255) and background is black (0)
    _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Find all connected white regions (blobs) in the binary image
    # Returns: number of blobs, a label map, stats per blob, and centroids
    # connectivity=8 means diagonal pixels are considered connected
    num_labels, label_map, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)

    # We expect exactly 9 blobs (the 3x3 grid) plus 1 for the background
    # If fewer than 10 labels found, the detection failed
    if num_labels < 10:
        messagebox.showwarning("Error", "Less than 10 blobs found")
        return np.zeros(8, dtype=float)

    # Build a list of (label_index, area) for all blobs except background (index 0)
    areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
    # Sort by area descending and keep only the 9 largest blobs
    # This filters out any small noise blobs
    top_areas = sorted(areas, key=lambda x: x[1], reverse=True)[:9]

    # Validate that the 9 selected blobs have similar areas
    # If they are very different, the detection is unreliable
    area_values = np.array([a[1] for a in top_areas])
    median = np.median(area_values)
    # MAD (Median Absolute Deviation) measures how spread out the areas are
    mad = np.median(np.abs(area_values - median))

    # If the spread is more than 20% of the median, reject the detection
    if mad / median > 0.2:
        messagebox.showwarning("There's not similitude between the blobs")
        return np.zeros(8, dtype=float)

    # Compute the intensity-weighted centroid for each of the 9 blobs
    # This gives a more accurate center position than a simple geometric center
    centers = []
    for i, _ in top_areas:
        # Get the bounding box of this blob: x, y = top left corner, w, h = size
        x, y, w, h, _ = stats[i]
        # Extract the grayscale region of interest for this blob
        roi = gray_img[y:y+h, x:x+w]
        # Create a binary mask for only the pixels belonging to this blob
        mask = (label_map[y:y+h, x:x+w] == i).astype(np.uint8)
        # Multiply the grayscale values by the mask to isolate blob pixels
        I = (roi * mask).astype(np.float32)
        # Sum of all intensity values, used as the weight denominator
        total_intensity = I.sum()
        # Create coordinate grids for the ROI
        yy, xx = np.indices(I.shape)
        # Compute weighted centroid: sum(coordinate * intensity) / sum(intensity)
        # Add x and y offsets to convert from ROI coordinates to image coordinates
        cx = (xx * I).sum() / total_intensity + x
        cy = (yy * I).sum() / total_intensity + y
        centers.append((cx, cy))

    # Convert the list of center points to a NumPy array for easier processing
    centers = np.array(centers)

    # Group the 9 blob centers into 3 rows using KMeans clustering on Y coordinates
    # This separates the top, middle and bottom rows of the 3x3 grid
    Y_coords = centers[:, 1].reshape(-1, 1)  # extract Y coordinates as column vector
    kmeans = KMeans(n_clusters=3, n_init='auto')
    # Assign each center to one of 3 row clusters
    row_labels = kmeans.fit_predict(Y_coords)

    # Group centers by their assigned row label
    rows = [[] for _ in range(3)]
    for label, point in zip(row_labels, centers):
        rows[label].append(point)

    # Sort rows from top to bottom by their average Y coordinate
    # (higher Y value = lower on screen)
    rows.sort(key=lambda row: np.mean([p[1] for p in row]))

    # Within each row, sort points from left to right by X coordinate
    ordered_grid = []
    for row in rows:
        ordered_row = sorted(row, key=lambda p: p[0])
        ordered_grid.extend(ordered_row)
    # Now ordered_grid contains all 9 points in reading order:
    # [1, 2, 3, 4, 5, 6, 7, 8, 9] where 5 is the center

    # The center blob is always at index 4 (position 5 in the grid)
    center = ordered_grid[4]

    # Compute Euclidean distance from each of the 8 outer blobs to the center
    # Skip index 4 (the center itself)
    distances = [
        np.hypot(cx - center[0], cy - center[1])
        for i, (cx, cy) in enumerate(ordered_grid) if i != 4
    ]

    # Round to 2 decimal places and return as a NumPy array
    return np.round(np.array(distances), 2)


def do_reference():
    """
    Captures reference images and distance measurements at position 0
    for all four filters and saves them to disk.

    The reference data (y0) represents the blob distances when the screen
    is at the zero position. This is used later as the baseline for
    computing focal lengths.

    The function:
    1. Moves the motor to position 0
    2. Turns on the LED at full intensity
    3. Captures one image per filter
    4. Computes distances for each image
    5. Saves the images and distance array to the reference folder
    """
    # Move motor to the reference position (0 mm)
    move_to_position(0)
    # Wait for the motor to reach position 0 and stabilize
    time.sleep(1)

    # Turn on the LED at maximum intensity for consistent illumination
    led_on()
    led_intensity(10)
    # Wait for the LED to stabilize
    time.sleep(1)

    # Initialize a 4x8 array to store the reference distances
    # 4 rows = one per filter, 8 columns = one per blob distance
    y0 = np.zeros((4, 8))
    # List to store the captured images for saving to disk later
    captured_images = []

    # --- Capture one image per filter and compute distances --- #
    for idx, f in enumerate(FILTERS):
        # Activate the current filter
        activate_filter(f)
        # Wait for the filter to physically move into position
        time.sleep(1)

        # Capture a frame from the camera
        img = capture_image_array()
        if img is None:
            messagebox.showwarning("Error", f"Cannot take the image with filter: {f}")
            return

        # Compute the 8 blob distances for this image
        distances = compute_distances_to_center(img)
        if np.any(distances == 0):
            # If any distance is zero, the detection failed
            # Turn off the LED and reset filter before showing the error
            led_off()
            activate_filter('w')
            messagebox.showwarning("Error",
                                   f"The measurements were wrong in image with filter {f}.\n"
                                   "Please ensure better darkness conditions.")
            return

        # Store the distances for this filter in the reference array
        y0[idx] = distances
        # Store the image for saving to disk after all filters are done
        captured_images.append((f, img))

    # --- Save reference data to disk --- #

    if REFERENCE_FOLDER.exists():
        # If the reference folder already exists, delete all existing files
        # to replace them with the new reference data
        for archivo in REFERENCE_FOLDER.iterdir():
            try:
                if archivo.is_file():
                    archivo.unlink()  # delete the file
            except Exception as e:
                messagebox.showwarning("Error", f"Cannot remove {archivo}: {e}")
    else:
        # Create the reference folder if it doesn't exist yet
        REFERENCE_FOLDER.mkdir(parents=True, exist_ok=True)

    # Save each reference image as a PNG file named after its filter
    for f, img in captured_images:
        img_path = REFERENCE_FOLDER / f"{f}.png"
        cv2.imwrite(str(img_path), img)

    # Save the full reference distance array as a .npy binary file
    # This will be loaded later by automatic_measurement()
    np.save(REFERENCE_PATH, y0)

    # Reset the hardware: turn off LED and set filter back to white
    led_off()
    activate_filter('w')

    # Notify the user that the reference was saved successfully
    messagebox.showinfo(
        "Reference taken",
        f"Reference and images saved in:\n{REFERENCE_FOLDER.resolve()}"
    )


def focal_distance_with_table(y0, img1, img2, dz, modo=1):
    """
    Computes the effective focal length from two images taken at different
    screen positions and a reference distance array.

    The focal length is computed using the formula:
        f = (y0 / (y1 - y2)) * dz

    where y0 is the reference distance, y1 and y2 are the distances at
    positions z1 and z2, and dz = |z2 - z1| is the screen displacement.

    Three calculation modes are available depending on the physical
    configuration of the lens and screen positions:
    - Mode 1: both z1 and z2 are before the focal point
    - Mode 2: z1 is before and z2 is after the focal point
    - Mode 3: both z1 and z2 are after the focal point

    Parameters
    ----------
    y0 : numpy array
        Reference distances (8 values) captured at position 0.
    img1 : numpy array
        Image captured at position z1.
    img2 : numpy array
        Image captured at position z2.
    dz : float
        The absolute distance between z1 and z2 in mm.
    modo : int
        Calculation mode (1, 2, or 3). Default is 1.

    Returns
    -------
    tuple
        (results_array, final_table)
        results_array: [effective_f, err_effective_f, delta_f] rounded to 3 decimals
        final_table: pandas DataFrame with the full measurement table
    """
    # Compute the blob distances for both images
    y1 = compute_distances_to_center(img1)
    y2 = compute_distances_to_center(img2)

    # Define which distance indices belong to the p and l measurement groups
    # These correspond to specific blob positions in the 3x3 grid
    spots_p = np.array([4, 1, 3, 6])   # indices for p group blobs
    spots_l = np.array([2, 0, 5, 7])   # indices for l group blobs
    # Inverse indices used when the screen is past the focal point
    inv_p = np.array([3, 6, 4, 1])
    inv_l = np.array([5, 7, 2, 0])

    # Each mode applies different sign conventions and index orderings
    # to account for whether the distances are measured before or after
    # the focal point where the image flips
    modos = {
        1: (y1,  y2,  spots_p, spots_l, spots_p, spots_l),  # both before focal point
        2: (y1, -y2,  spots_p, spots_l, inv_p,   inv_l),    # z1 before, z2 after
        3: (-y1, -y2, inv_p,   inv_l,   inv_p,   inv_l)     # both after focal point
    }

    # Unpack the effective y values and index arrays for the selected mode
    y1_eff, y2_eff, idx_y1p, idx_y1l, idx_y2p, idx_y2l = modos[modo]

    # Compute focal lengths for p and l groups using the focal length formula
    # f = (y0 / (y1 - y2)) * dz
    f_p = (y0[spots_p] / (y1_eff[idx_y1p] - y2_eff[idx_y2p])) * dz
    f_l = (y0[spots_l] / (y1_eff[idx_y1l] - y2_eff[idx_y2l])) * dz

    def stats_and_table(name, idx, idx_y1, idx_y2, y1v, y2v, f_vals):
        """
        Computes statistics and builds a formatted DataFrame for one
        measurement group (either p or l).

        Parameters
        ----------
        name : str
            The group name ('p' or 'l'), shown in the first column.
        idx : numpy array
            The blob indices for this group, used to look up y0 values.
        idx_y1 : numpy array
            The indices to use when looking up y1 values.
        idx_y2 : numpy array
            The indices to use when looking up y2 values.
        y1v : numpy array
            The effective y1 distance array (may be negated depending on mode).
        y2v : numpy array
            The effective y2 distance array (may be negated depending on mode).
        f_vals : numpy array
            The 4 computed focal length values for this group.

        Returns
        -------
        tuple (float, float, pd.DataFrame)
            mean_f: mean focal length
            std_f: standard deviation of focal lengths
            table: formatted DataFrame with all measurement details
        """
        # Compute mean and standard deviation of the focal lengths
        mean_f = np.mean(f_vals)
        std_f = np.std(f_vals)

        # Build the results table with one row per spot
        table = pd.DataFrame({
            '': [name, '', '', ''],         # group name only in first row
            'Spot Number': [1, 2, 3, 4],    # spot numbers 1 to 4
            'y0 (px)': y0[idx],             # reference distances
            'y1 (px)': y1v[idx_y1],         # distances at z1
            'y2 (px)': y2v[idx_y2],         # distances at z2
            'f (mm)': np.round(f_vals, 2),  # individual focal lengths
            # Mean ± std shown only in the first row, rest left empty
            'f ± δf (mm)': [f'{round(mean_f, 2)} ± {round(std_f, 2)}', '', '', '']
        })
        return mean_f, std_f, table

    # Build the tables and compute statistics for both groups
    mean_fp, std_fp, tab_p = stats_and_table('p', spots_p, idx_y1p, idx_y2p, y1_eff, y2_eff, f_p)
    mean_fl, std_fl, tab_l = stats_and_table('l', spots_l, idx_y1l, idx_y2l, y1_eff, y2_eff, f_l)

    # Compute the effective focal length and its uncertainty
    # delta_f is the difference between the two group focal lengths
    delta_f = mean_fp - mean_fl
    # Error propagation: combine uncertainties in quadrature (sqrt of sum of squares)
    err_delta_f = np.hypot(std_fp, std_fl)
    # Effective focal length combines both group results
    effective_f = mean_fp + delta_f
    # Propagate the uncertainty of effective_f
    err_effective_f = np.hypot(std_fp, err_delta_f)

    # Build a summary DataFrame with the final results
    sum_ef = pd.DataFrame([
        {
            # First row shows the effective focal length result
            'Spot Number': '',
            'y0 (px)': '',
            'y1 (px)': '',
            'y2 (px)': 'effective focal length',
            'f (mm)': '',
            'f ± δf (mm)': f"{round(effective_f, 2)} ± {round(err_effective_f, 2)}"
        },
        {
            # Second row shows delta_f
            'Spot Number': '',
            'y0 (px)': '',
            'y1 (px)': '',
            'y2 (px)': 'delta_f',
            'f (mm)': '',
            'f ± δf (mm)': f"{round(delta_f, 2)} ± {round(err_delta_f, 2)}"
        }
    ])

    # Add 2 empty rows between the measurement tables and the summary
    # for visual separation in the Excel output
    empty_rows = pd.DataFrame([
        {col: '' for col in tab_p.columns}
        for _ in range(2)
    ])

    # Stack all tables vertically: p group, l group, spacer, summary
    final_table = pd.concat([tab_p, tab_l, empty_rows, sum_ef], ignore_index=True)

    # Return the key results rounded to 3 decimals and the full table
    return (
        np.round([effective_f, err_effective_f, delta_f], 3),
        final_table
    )


def automatic_measurement(z1, z2, modo=1):
    """
    Runs the full automatic focal length measurement procedure.

    The procedure:
    1. Sorts z1 and z2 so z1 < z2 and computes dz
    2. Turns on the LED at full intensity
    3. Moves to z1, captures images for all 4 filters
    4. Moves to z2, captures images for all 4 filters
    5. Turns off the LED and returns to position 0
    6. Loads the reference data from disk
    7. Computes focal length for each filter
    8. Returns all results, images, tables and the suggested save path

    Parameters
    ----------
    z1 : float
        First screen position in mm.
    z2 : float
        Second screen position in mm.
    modo : int
        Calculation mode (1, 2, or 3). Default is 1.

    Returns
    -------
    tuple
        (results, images_z1, images_z2, tables, path_base)
        results: dict with focal length results per filter
        images_z1: array of 4 images captured at z1
        images_z2: array of 4 images captured at z2
        tables: dict of DataFrames with detailed results per filter
        path_base: suggested folder path for saving the data
    """
    # Ensure z1 is always the smaller position
    z1, z2 = sorted([z1, z2])
    # Compute the screen displacement used in the focal length formula
    dz = abs(z2 - z1)

    # Turn on the LED at maximum intensity for consistent illumination
    led_on()
    led_intensity(10)

    # Build a timestamped folder name for saving this measurement
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    measurement_folder = f"measurement_z1_{z1}_z2_{z2}_{timestamp}"
    data_dir = external_folder("data")
    # Full path to the suggested save folder
    path_base = os.path.join(data_dir, measurement_folder)

    # Capture images at both positions z1 and z2
    for idx, z_mm in enumerate([z1, z2]):

        # Move the motor to the target position
        move_to_position(z_mm)
        # Wait until the motor physically reaches the position
        desired_position(z_mm)
        # Extra wait for mechanical stabilization
        time.sleep(1)

        # Initialize an array to store the 4 images at this position
        # Shape: (4 filters, height, width, 3 channels)
        images_actual = np.zeros((4, 1080, 1080, 3))

        # Capture one image per filter at this position
        for jdx, f in enumerate(FILTERS):
            # Activate the current filter and wait for it to move
            activate_filter(f)
            time.sleep(1)

            # Capture a frame from the camera
            img = capture_image_array()
            time.sleep(1)

            if img is not None:
                # Store the captured image in the array
                images_actual[jdx] = img

            if jdx == 3:
                # After the last filter, reset to white filter
                activate_filter('w')
                time.sleep(1)

        # Store the images for this position
        if idx == 0:
            images_z1 = images_actual   # images captured at z1
        else:
            images_z2 = images_actual   # images captured at z2

    # Turn off the LED and return the motor to position 0
    led_off()
    move_to_position(0)

    # Check that a reference file exists before proceeding
    if not os.path.exists(REFERENCE_PATH):
        raise FileNotFoundError(
            f"No reference file in {REFERENCE_PATH}. Take reference data first.")

    # Load the reference distance array saved by do_reference()
    y0 = np.load(REFERENCE_PATH)

    # Dictionaries to collect results and tables for each filter
    results = {}
    tables = {}

    # Compute focal length for each filter independently
    for i, flt in enumerate(FILTERS):
        try:
            # Extract the reference distances for this filter
            y0_row = y0[i]
            # Extract the images for this filter at both positions
            img1 = images_z1[i]
            img2 = images_z2[i]

            # Compute the focal length and build the results table
            ress, table = focal_distance_with_table(y0_row, img1, img2, dz, modo=modo)
            # Unpack the three result values
            res_eff_f, res_err_eff_f, delta_f = ress

            # Store the results in the dictionary keyed by filter name
            results[flt] = {
                "effective_focal": res_eff_f,
                "error_effective_focal": res_err_eff_f,
                "delta_f": delta_f
            }
            # Store the table for saving to Excel later
            tables[flt] = table

        except Exception as e:
            # If computation fails for a filter, store the error and continue
            messagebox.showwarning("Error", f"Error in filter '{flt}': {e}")
            results[flt] = {"error": str(e)}
            tables[flt] = pd.DataFrame({'Error': [str(e)]})

    # Return everything needed for display and saving
    return results, images_z1, images_z2, tables, path_base


def save_measurement_data(images_z1, images_z2, tables, path_base, z1, z2):
    """
    Saves the measurement images and results tables to disk.

    Creates the save folder if it doesn't exist, then:
    - Saves all 8 images (4 filters x 2 positions) as PNG files
    - Saves all 4 results tables to a single Excel file with one sheet per filter

    Parameters
    ----------
    images_z1 : numpy array
        Array of 4 images captured at position z1.
    images_z2 : numpy array
        Array of 4 images captured at position z2.
    tables : dict
        Dictionary of DataFrames with results per filter.
    path_base : str or Path
        The folder path where all files will be saved.
    z1 : float
        The z1 position in mm, used in the Excel filename.
    z2 : float
        The z2 position in mm, used in the Excel filename.
    """
    # Create the save folder if it doesn't exist
    os.makedirs(path_base, exist_ok=True)

    # Save images for both positions
    for idx, img_set in enumerate([images_z1, images_z2]):
        for i, f in enumerate(FILTERS):
            # Build filename: z1_w.png, z1_r.png, z2_w.png, etc.
            filename = f"z{idx+1}_{f}.png"
            path_img = os.path.join(path_base, filename)
            if i < len(img_set):
                # Save the image using OpenCV
                cv2.imwrite(path_img, img_set[i])

    # Build the Excel filename including the z positions
    excel_filename = f"focal_z1_{z1:.2f}_z2_{z2:.2f}.xlsx"
    excel_path = os.path.join(path_base, excel_filename)

    # Save all filter tables to a single Excel file
    # Each filter gets its own sheet named Filter_W, Filter_R, etc.
    with pd.ExcelWriter(excel_path) as writer:
        for flt, tabla in tables.items():
            tabla.to_excel(writer, sheet_name=f"Filter_{flt.upper()}", index=False)
            
def format_distances(distances):
    """
    Formats the 8 computed distances into a human readable string
    showing which blob points are being measured relative to the center.

    The 9 blobs are arranged in a 3x3 grid numbered 1-9:
        1 | 2 | 3
        ---------
        4 | 5 | 6
        ---------
        7 | 8 | 9

    Point 5 is always the center. The 8 distances are split into two
    groups (p and l) which correspond to the two sets of measurement
    points used in the focal length calculation.

    Parameters
    ----------
    distances : numpy array
        Array of 8 distances in pixels computed by compute_distances_to_center().

    Returns
    -------
    str
        A formatted string showing each point pair and its distance.
    """
    # p points: the 4 distances used for the p measurement
    # Each tuple is (point_a, center_point, index_in_distances_array)
    p_map = [(6,5,4), (2,5,1), (4,5,3), (8,5,6)]
    # l points: the 4 distances used for the l measurement
    l_map = [(3,5,2), (1,5,0), (7,5,5), (9,5,7)]

    # Build the formatted string for p points
    text = "p points:\n"
    for i, (a, c, idx) in enumerate(p_map):
        # Format: "  1: 6─5  12.34 px"
        text += f"  {i+1}: {a}─{c}  {distances[idx]} px\n"

    # Build the formatted string for l points
    text += "\nl points:\n"
    for i, (a, c, idx) in enumerate(l_map):
        text += f"  {i+1}: {a}─{c}  {distances[idx]} px\n"

    return text            