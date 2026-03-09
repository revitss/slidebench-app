import os
os.environ["OMP_NUM_THREADS"] = "1"  # Improves OpenCV performance
import time
from datetime import datetime
import numpy as np
import cv2
from sklearn.cluster import KMeans
import pandas as pd
from pathlib import Path
from tkinter import messagebox

from utils import external_folder, resource_path
from controller import activate_filter, led_on, move_to_position, led_off, led_intensity
from camera_functions import capture_image_array
from communication import read_current_position
#from utils import mm_to_steps

FILTERS = ['w', 'r', 'g', 'b']

# === WAITS UNTIL MOTOR IS ON DESIRED POSITION ===
def desired_position(target_position):
    while True:
        current = read_current_position()
        if current is not None and current == target_position:
            break
        time.sleep(0.1)

# === IMG PROCESSING ===
def compute_distances_to_center(img):
    
    # gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # Converts the img to gray scale with opencv method
    gray_img = np.mean(img, axis=2).astype(np.uint8)  # Converts the img to gray scale with as an average of the three channels

    _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU) # Binarize the img with OTSU threshold method

    num_labels, label_map, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8) # Data from process binary img 
    
    if num_labels < 10:
        print("Less than 10 blolbs found")
        return np.zeros(8, dtype=float)
    
    areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
    top_areas = sorted(areas, key=lambda x: x[1], reverse=True)[:9] 
    
    area_values = np.array([a[1] for a in top_areas])
    median = np.median(area_values)
    mad = np.median(np.abs(area_values - median))

    # Evaluate the similarity criterion (for example 10%)
    if mad / median > 0.2:
        print("There's not similitude between the blobs")
        return np.zeros(8, dtype=float)

    centers = []
    for i, _ in top_areas:
        x, y, w, h, _ = stats[i]
        roi = gray_img[y:y+h, x:x+w]
        mask = (label_map[y:y+h, x:x+w] == i).astype(np.uint8)
        I = (roi * mask).astype(np.float32)

        total_intensity = I.sum()

        yy, xx = np.indices(I.shape)
        cx = (xx * I).sum() / total_intensity + x
        cy = (yy * I).sum() / total_intensity + y
        centers.append((cx, cy))

    centers = np.array(centers)

    # group in three rows
    Y_coords = centers[:, 1].reshape(-1, 1)
    kmeans = KMeans(n_clusters=3, n_init='auto')
    row_labels = kmeans.fit_predict(Y_coords)

    rows = [[] for _ in range(3)]
    for label, point in zip(row_labels, centers):
        rows[label].append(point)

    rows.sort(key=lambda row: np.mean([p[1] for p in row]))  # order from top to bottom 

    ordered_grid = []
    for row in rows:
        ordered_row = sorted(row, key=lambda p: p[0])  # order from left to right
        ordered_grid.extend(ordered_row)

    center = ordered_grid[4]  # center

    distances = [
        np.hypot(cx - center[0], cy - center[1])
        for i, (cx, cy) in enumerate(ordered_grid) if i != 4
    ]

    return np.round(np.array(distances), 2)


# --- Folder for store reference data

DATA_FOLDER = Path(external_folder("data"))
REFERENCE_FOLDER = DATA_FOLDER / "reference"
REFERENCE_PATH = REFERENCE_FOLDER / "reference_y0.npy"

def do_reference():
    
    # motor to 0 position
    move_to_position(0)
    time.sleep(1)

    # turn on the led
    led_on()
    led_intensity(10)
    time.sleep(1)  

    # y0 = []
    y0 = np.zeros((4,8))
    captured_images = []

    # --- Take image and do distances
    for idx, f in enumerate(FILTERS):
        activate_filter(f)
        time.sleep(1)

        img = capture_image_array()
        if img is None:
            messagebox.showwarning("Error", f"Cannot take the image with filter: {f}")
            return
        
        # compute distances
        distances = compute_distances_to_center(img)
        if np.any(distances == 0):
            led_off()
            activate_filter('w')
            
            messagebox.showwarning("Error",
                                   f"The measurements were wrong in image with filter {f}.\n"
                                   "Please ensure better darkness conditions.")
            return

        y0[idx] = distances
        captured_images.append((f, img))

    # --- Create or clean the reference folder
    
    if REFERENCE_FOLDER.exists():
        for archivo in REFERENCE_FOLDER.iterdir():
            try:
                if archivo.is_file():
                    archivo.unlink()
            except Exception as e:
                print(f"Cannot remove {archivo}: {e}")
    else:
        REFERENCE_FOLDER.mkdir(parents=True, exist_ok=True)
        
    for f, img in captured_images:
        img_path = REFERENCE_FOLDER / f"{f}.png"
        cv2.imwrite(str(img_path), img)

    # --- Save vector reference distances
    np.save(REFERENCE_PATH, y0)

    # --- Turn off led and activate filter w
    led_off()
    activate_filter('w')

    messagebox.showinfo(
        "Reference taken",
        f"Reference and images saved in:\n{REFERENCE_FOLDER.resolve()}"
    )
    

def focal_distance_with_table(y0, img1, img2, dz, modo=1):
    # compute distances
    y1 = compute_distances_to_center(img1)
    y2 = compute_distances_to_center(img2)

    # Define indices
    spots_p = np.array([4, 1, 3, 6])
    spots_l = np.array([2, 0, 5, 7])
    inv_p = np.array([3, 6, 4, 1])
    inv_l = np.array([5, 7, 2, 0])

    # Changes to usage three modes
    modos = {
        1: (y1, y2, spots_p, spots_l, spots_p, spots_l),
        2: (y1, -y2, spots_p, spots_l, inv_p, inv_l),
        3: (-y1, -y2, inv_p, inv_l, inv_p, inv_l)
    }

    y1_eff, y2_eff, idx_y1p, idx_y1l, idx_y2p, idx_y2l = modos[modo]

    # Compute focal length for l and p
    f_p = (y0[spots_p] / (y1_eff[idx_y1p] - y2_eff[idx_y2p])) * dz
    f_l = (y0[spots_l] / (y1_eff[idx_y1l] - y2_eff[idx_y2l])) * dz

    # Do tables
    def stats_and_table(name, idx, idx_y1, idx_y2, y1v, y2v, f_vals):
        mean_f = np.mean(f_vals)
        std_f = np.std(f_vals)
        table = pd.DataFrame({
            '': [name, '', '', ''],
            'Spot Number': [1, 2, 3, 4],
            'y0 (px)': y0[idx],
            'y1 (px)': y1v[idx_y1],
            'y2 (px)': y2v[idx_y2],
            'f (mm)': np.round(f_vals, 2),
            'f ± δf (mm)': [f'{round(mean_f, 2)} ± {round(std_f, 2)}', '', '', '']
        })
        # summary = pd.DataFrame([{
        #     'Spot Number': name,
        #     'y0 (px)': '',
        #     'y1 (px)': '',
        #     'y2 (px)': '',
        #     'f (mm)': round(mean_f, 2),
        #     'f ± δf (mm)': f"{round(mean_f, 2)} ± {round(std_f, 2)}"
        # }])
        return mean_f, std_f, table

    mean_fp, std_fp, tab_p = stats_and_table('p', spots_p, idx_y1p, idx_y2p, y1_eff, y2_eff, f_p)
    mean_fl, std_fl, tab_l = stats_and_table('l', spots_l, idx_y1l, idx_y2l, y1_eff, y2_eff, f_l)

    # Compute errors
    delta_f = mean_fp - mean_fl
    err_delta_f = np.hypot(std_fp, std_fl)
    effective_f = mean_fp + delta_f
    err_effective_f = np.hypot(std_fp, err_delta_f)

    sum_ef = pd.DataFrame([
        {
            'Spot Number': '',
            'y0 (px)': '',
            'y1 (px)': '',
            'y2 (px)': 'effective focal length',
            'f (mm)': '',
            'f ± δf (mm)': f"{round(effective_f, 2)} ± {round(err_effective_f, 2)}"
        },
        {
            'Spot Number': '',
            'y0 (px)': '',
            'y1 (px)': '',
            'y2 (px)': 'delta_f',
            'f (mm)': '',
            'f ± δf (mm)': f"{round(delta_f, 2)} ± {round(err_delta_f, 2)}"
        }
    ])
    
    empty_rows = pd.DataFrame([
    {col: '' for col in tab_p.columns}
    for _ in range(2)   # change to 2 if you want 2 rows
    ])

    # Concatenate the tables
    final_table = pd.concat([tab_p, tab_l, empty_rows, sum_ef], ignore_index=True)

    # return (
    #     np.round([mean_fp, std_fp], 3),
    #     np.round([mean_fl, std_fl], 3),
    #     np.round([effective_f, err_effective_f, delta_f], 3),
    #     final_table
    # )
    return (
        np.round([effective_f, err_effective_f, delta_f], 3),
        final_table
    )

def automatic_measurement(z1, z2, modo=1):
    z1, z2 = sorted([z1, z2])
    dz = abs(z2 - z1)

    led_on()
    led_intensity(10)
    # imagees_z1 = np.zeros((4, 1080, 1080, 3), dtype=np.uint8)
    # imagese_z2 = np.zeros((4, 1080, 1080, 3), dtype=np.uint8)

    # Suggested folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    medicion_folder = f"medicion_z1_{z1}_z2_{z2}_{timestamp}"
    data_dir = external_folder("data")
    path_base = os.path.join(data_dir, medicion_folder)

    for idx, z_mm in enumerate([z1, z2]):
        
        move_to_position(z_mm)
        desired_position(z_mm)
        time.sleep(1)

        images_actual = np.zeros((4, 1080, 1080, 3))

        for jdx, f in enumerate(FILTERS):
        
            activate_filter(f)
            time.sleep(1)
            
            img = capture_image_array()
            time.sleep(1)

            if img is not None:
                images_actual[jdx] = img
            if jdx == 3:
                activate_filter('w')
                time.sleep(1)
                

        if idx == 0:
            images_z1 = images_actual
        else:
            images_z2 = images_actual

    led_off()
    move_to_position(0)
    # activate_filter('w')

    # Reads the reference data
    
    if not os.path.exists(REFERENCE_PATH):
        raise FileNotFoundError(f"No reference file in {REFERENCE_PATH}. Take reference data first.")

    y0 = np.load(REFERENCE_PATH)

    results = {}
    tables = {}

    for i, filter in enumerate(FILTERS):
        try:
            y0_row = y0[i]
            img1 = images_z1[i]
            img2 = images_z2[i]

            ress, table = focal_distance_with_table(y0_row, img1, img2, dz, modo=modo)

            res_eff_f, res_err_eff_f, delta_f = ress

            # delta_f = average_focal_p - average_focal_l
            # err_delta_f = np.hypot(std_focal_p,std_focal_l)

            results[filter] = {
                "effective_focal": res_eff_f,
                "error_effective_focal": res_err_eff_f,
                "delta_f": delta_f
            }

            tables[filter] = table

        except Exception as e:
            print(f"Error in filter '{filter}': {e}")
            results[filter] = {"error": str(e)}
            tables[filter] = pd.DataFrame({'Error': [str(e)]})

    return results, images_z1, images_z2, tables, path_base


def save_measurement_data(images_z1, images_z2, tables, path_base, z1, z2):

    os.makedirs(path_base, exist_ok=True)

    for idx, img_set in enumerate([images_z1, images_z2]):
        for i, f in enumerate(FILTERS):
            filename = f"z{idx+1}_{f}.jpg"
            path_img = os.path.join(path_base, filename)
            if i < len(img_set):
                cv2.imwrite(path_img, img_set[i])
    excel_filename = f"focal_z1_{z1:.2f}_z2_{z2:.2f}.xlsx"

    excel_path = os.path.join(path_base, excel_filename)
    with pd.ExcelWriter(excel_path) as writer:
        for filter, tabla in tables.items():
            tabla.to_excel(writer, sheet_name=f"Filter_{filter.upper()}", index=False)