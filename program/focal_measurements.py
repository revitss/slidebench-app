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
from camara import capture_image_array
from communication import read_current_position
#from utils import mm_to_steps

# === CONFIGURACIONES ===

# === ESPERA HASTA QUE EL MOTOR LLEGUE A DESTINO ===
def desired_position(target_position):
    while True:
        current = read_current_position()
        if current is not None and current == target_position:
            break
        time.sleep(0.1)

# === IMG PROCESSING ===
def compute_distances_to_center(img, threshold_method='otsu', fixed_threshold_value=10):
    
    # gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # Converts the img to gray scale with opencv method
    gray_img = np.mean(img, axis=2).astype(np.uint8)  # Converts the img to gray scale with as an average of the three channels

    if threshold_method == 'otsu':
        _, binary = cv2.threshold(gray_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    elif threshold_method == 'fixed':
        _, binary = cv2.threshold(gray_img, fixed_threshold_value, 255, cv2.THRESH_BINARY)

    num_labels, label_map, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    
    if num_labels < 10:
        return np.zeros(8, dtype=float)
    
    areas = [(i, stats[i, cv2.CC_STAT_AREA]) for i in range(1, num_labels)]
    top_areas = sorted(areas, key=lambda x: x[1], reverse=True)[:9] 
    
    area_values = np.array([a[1] for a in top_areas])
    median = np.median(area_values)
    mad = np.median(np.abs(area_values - median))

    # Evaluar el criterio de similitud (por ejemplo 10%)
    if mad / median > 0.1:
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

    return np.array(distances)


# Folder for data

DATA_FOLDER = Path(external_folder("data"))
REFERENCE_FOLDER = DATA_FOLDER / "reference"
REFERENCE_PATH = REFERENCE_FOLDER / "referencia.npy"

def do_reference():
    
    # motor to 0 position
    # move_to_position_ventana(0)
    move_to_position(0)
    time.sleep(0.5)

    # turn on the led
    led_on()
    led_intensity(10)
    time.sleep(1)  

    filtros = ['w', 'r', 'g', 'b']
    y0 = []

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

    # --- Take image and do distances
    for f in filtros:
        activate_filter(f)
        time.sleep(1)

        img = capture_image_array()
        if img is None:
            messagebox.showwarning("Error", f"Cannot take the image with filter: {f}")
            continue

        # save images in reference folder
        img_path = REFERENCE_FOLDER / f"{f}.png"
        cv2.imwrite(str(img_path), img)

        # compute distances
        distances = compute_distances_to_center(img)
        y0.append(distances)

    # --- Save vector reference distances
    np.save(REFERENCE_PATH, np.array(y0))

    # --- Turn of led and activate filter w
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

    # changes to usage three modes
    modos = {
        1: (y1, y2, spots_p, spots_l, spots_p, spots_l),
        2: (y1, -y2, spots_p, spots_l, inv_p, inv_l),
        3: (-y1, -y2, inv_p, inv_l, inv_p, inv_l)
    }

    y1_eff, y2_eff, idx_p, idx_l, idx_y2p, idx_y2l = modos[modo]

    # Compute focal length for l and p
    f_p = (y0[idx_p] / (y1_eff[idx_p] - y2_eff[idx_y2p])) * dz
    f_l = (y0[idx_l] / (y1_eff[idx_l] - y2_eff[idx_y2l])) * dz

    # Do tables
    def stats_and_table(name, idx, y1v, y2v, f_vals):
        mean_f = np.mean(f_vals)
        std_f = np.std(f_vals)
        table = pd.DataFrame({
            'Spot Number': [1, 2, 3, 4],
            'y0 (pixels)': y0[idx],
            'y1 (pixels)': y1v[idx],
            'y2 (pixels)': y2v[idx],
            'f (mm)': np.round(f_vals, 2),
            'f ± δf (mm)': ''
        })
        summary = pd.DataFrame([{
            'Spot Number': name,
            'y0 (pixels)': '',
            'y1 (pixels)': '',
            'y2 (pixels)': '',
            'f (mm)': round(mean_f, 2),
            'f ± δf (mm)': f"{round(mean_f, 2)} ± {round(std_f, 2)}"
        }])
        return mean_f, std_f, table, summary

    mean_p, std_p, tab_p, sum_p = stats_and_table('p', idx_p, y1_eff, y2_eff, f_p)
    mean_l, std_l, tab_l, sum_l = stats_and_table('l', idx_l, y1_eff, y2_eff, f_l)

    # Compute errors
    delta_f = mean_p - mean_l
    err_delta_f = np.hypot(std_p, std_l)
    focal_efectiva = mean_p + delta_f
    err_focal_efectiva = np.hypot(std_p, err_delta_f)

    sum_ef = pd.DataFrame([
        {
            'Spot Number': 'efectiva',
            'y0 (pixels)': '',
            'y1 (pixels)': '',
            'y2 (pixels)': '',
            'f (mm)': round(focal_efectiva, 2),
            'f ± δf (mm)': f"{round(focal_efectiva, 2)} ± {round(err_focal_efectiva, 2)}"
        },
        {
            'Spot Number': 'delta_f',
            'y0 (pixels)': '',
            'y1 (pixels)': '',
            'y2 (pixels)': '',
            'f (mm)': round(delta_f, 2),
            'f ± δf (mm)': f"{round(delta_f, 2)} ± {round(err_delta_f, 2)}"
        }
    ])

    # Do tables
    tabla_final = pd.concat([tab_p, tab_l, sum_p, sum_l, sum_ef], ignore_index=True)

    return (
        np.round([mean_p, std_p], 3),
        np.round([mean_l, std_l], 3),
        np.round([focal_efectiva, err_focal_efectiva], 3),
        tabla_final
    )

def automatic_measurement(z1, z2, modo=1):
    z1, z2 = sorted([z1, z2])
    dz = abs(z2 - z1)

    led_on()
    led_intensity(10)
    imagenes_z1 = np.zeros((4, 1080, 1080, 3), dtype=np.uint8)
    imagenes_z2 = np.zeros((4, 1080, 1080, 3), dtype=np.uint8)

    # Suggested folder
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    medicion_folder = f"medicion_z1_{z1}_z2_{z2}_{timestamp}"
    data_dir = external_folder("data")
    path_base = os.path.join(data_dir, medicion_folder)

    filters = ['w', 'r', 'g', 'b']

    for idx, z_mm in enumerate([z1, z2]):
        # pasos = mm_to_steps(z_mm)
        # move_to_position_ventana(pasos)
        
        move_to_position(z_mm)
        desired_position(z_mm)

        images_actual = np.zeros((4, 1080, 1080, 3), dtype=np.uint8)

        for jdx, f in enumerate(filters):
            activate_filter(f)
            time.sleep(1.5)
            img = capture_image_array()
            time.sleep(0.3)

            if img is not None:
                images_actual[jdx] = img

        if idx == 0:
            images_z1 = images_actual
        else:
            images_z2 = images_actual

    led_off()
    move_to_position(0)
    activate_filter('w')

    # Reads the reference data
    
    referencia_path = REFERENCE_PATH
    if not os.path.exists(referencia_path):
        raise FileNotFoundError(f"No reference file in {referencia_path}. Take reference data first.")

    y0 = np.load(referencia_path)

    results = {}
    tables = {}

    for i, filter in enumerate(filters):
        try:
            y0_row = y0[i]
            img1 = images_z1[i]
            img2 = images_z2[i]

            res_p, res_l, res_eff, tabla = focal_distance_with_table(y0_row, img1, img2, dz, modo=modo)

            average_focal_p, std_focal_p = res_p
            average_focal_l, std_focal_l = res_l
            focal_efective, err_focal_efective = res_eff

            delta_f = average_focal_p - average_focal_l
            err_delta_f = np.hypot(std_focal_p,std_focal_l)

            results[filter] = {
                "focal_efectiva": round(float(focal_efective), 3),
                "error_focal_efectiva": round(float(err_focal_efective), 3),
                "delta_f": round(float(delta_f), 3),
                "error_delta_f": round(float(err_delta_f), 3)
            }

            tables[filter] = tabla

        except Exception as e:
            print(f"Error en filtro '{filter}': {e}")
            results[filter] = {"error": str(e)}
            tables[filter] = pd.DataFrame({'Error': [str(e)]})

    return results, images_z1, images_z2, tables, path_base


def save_measurement_data(images_z1, images_z2, tables, path_base, z1, z2):

    os.makedirs(path_base, exist_ok=True)
    filters = ['w', 'r', 'g', 'b']

    for idx, img_set in enumerate([images_z1, images_z2]):
        for i, f in enumerate(filters):
            filename = f"z{idx+1}_{f}.jpg"
            path_img = os.path.join(path_base, filename)
            if i < len(img_set):
                cv2.imwrite(path_img, img_set[i])
    excel_filename = f"focal_z1_{z1:.2f}_z2_{z2:.2f}.xlsx"

    excel_path = os.path.join(path_base, excel_filename)
    with pd.ExcelWriter(excel_path) as writer:
        for filter, tabla in tables.items():
            tabla.to_excel(writer, sheet_name=f"Filter_{filter.upper()}", index=False)