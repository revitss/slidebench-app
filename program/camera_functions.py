import cv2
import os
import time
import threading
from tkinter import simpledialog
from PIL import Image, ImageTk
import numpy as np
from pygrabber.dshow_graph import FilterGraph
from utils import resource_path, external_folder

camera_active = False
recording = False
cap = None
video_writer = None
last_preview_image = None
photo_path = None
# save_folder = "..\\media"
save_folder = external_folder("media")
width, height = (1920, 1080)
camera_index = 2


def set_camera_index(index):
    """
    Updates the global camera index used to open the video stream.
    """
    global camera_index
    camera_index = index


def refresh_cameras():
    """Return a list of connected camera device names."""
    try:
        graph = FilterGraph()
        cameras = graph.get_input_devices()
        return cameras if cameras else ["No cameras found"]
    except Exception as e:
        print(f"Error detecting cameras: {e}")


def create_daily_folder():
    """Creates a folder named with the current date for saving media files."""
    date_str = time.strftime("%Y-%m-%d")
    day_folder = os.path.join(save_folder, date_str)
    os.makedirs(day_folder, exist_ok=True)
    return day_folder



def add_grid(img, grid_type="both"):
    """Add a grid overlay to an image for alignment assistance."""
    img = img.copy()
    h, w, _ = img.shape
    color = (255, 255, 0)
    thickness = 1

    if grid_type in ['4x4', 'both']:
        for i in range(1, 4):
            x = w * i // 4
            y = h * i // 4
            cv2.line(img, (x, 0), (x, h), color, thickness)
            cv2.line(img, (0, y), (w, y), color, thickness)
    if grid_type in ['radial', 'both']:
        center = (w // 2, h // 2)
        for r in range(50, min(w, h) // 2, 100):
            cv2.circle(img, center, r, color, thickness)
    return img


def toggle_camera(camera_label, btn):
    """Turns the camera on or off for live preview."""
    global camera_active, cap
    if not camera_active:
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not cap.isOpened():
            print("Unable to open camera.")
            return
        camera_active = True
        update_frame(camera_label)
        btn.config(text="Deactivate Camera")
    else:
        camera_active = False
        cap.release()
        btn.config(text="Activate Camera")
        try:
            # default_img = Image.open("image.png").resize((400, 400))
            default_img = Image.open(resource_path("resources\\image.png")).resize((400, 400))
            default_img_tk = ImageTk.PhotoImage(default_img)
            camera_label.imgtk = default_img_tk
            camera_label.config(image=default_img_tk)
        except:
            camera_label.config(image='')


def update_frame(camera_label):
    """Continuously updates the camera preview."""
    if camera_active:
        ret, frame = cap.read()
        if ret:
            frame = frame[::-1, ::-1, ::-1]
            frame = frame[:, 420:1500, :]
            frame = np.ascontiguousarray(frame)

            frame_with_grid = add_grid(frame, grid_type='both')

            img = Image.fromarray(frame_with_grid).resize((400, 400))
            img_tk = ImageTk.PhotoImage(img)
            camera_label.imgtk = img_tk
            camera_label.config(image=img_tk)
        camera_label.after(10, lambda: update_frame(camera_label))


def take_photo(camera_label, last_photo_label, btn_save_photo):
    """Captures a still image from the camera preview."""
    global cap, last_preview_image
    ret, frame = cap.read()
    if ret:
        frame = frame[::-1, ::-1, ::-1]
        frame_rgb = frame[:, 420:1500, :]

        last_preview_image = Image.fromarray(frame_rgb)

        preview_frame = add_grid(frame_rgb, grid_type='both')

        # Display preview
        img_resized = Image.fromarray(preview_frame).resize((400, 400))
        img_tk = ImageTk.PhotoImage(img_resized)
        last_photo_label.imgtk = img_tk
        last_photo_label.config(image=img_tk)

        btn_save_photo.grid()


def save_current_photo(btn_save_photo):
    """Saves the last captured photo to disk."""
    global last_preview_image, photo_path
    if last_preview_image is None:
        print("No photo to save.")
        return

    day_folder = create_daily_folder()
    timestamp = time.strftime("%H%M%S")
    default_name = f"photo_{timestamp}.jpg"
    custom_name = simpledialog.askstring("Save Photo", "Custom name?\n(Do not include .jpg)")
    filename = (custom_name + ".jpg") if custom_name else default_name
    destination = os.path.join(day_folder, filename)
    try:
        last_preview_image.save(destination)
        photo_path = destination
        print(f"📸 Photo saved as {filename} in {day_folder}")
        btn_save_photo.grid_remove()
    except Exception as e:
        print(f"Error saving photo: {e}")


def start_recording():
    """Begins recording a video from the live feed."""
    global recording, video_writer
    recording = True
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    day_folder = create_daily_folder()
    filename = time.strftime("video_%H%M%S.mp4")
    path = os.path.join(day_folder, filename)

    ret, frame = cap.read()
    if not ret:
        print("Could not read initial frame for recording.")
        recording = False
        return

    frame = frame[::-1, ::-1, :]
    frame = frame[:, 420:1500, :]
    frame = np.ascontiguousarray(frame)

    height, width = frame.shape[:2]

    video_writer = cv2.VideoWriter(path, fourcc, 15, (width, height))
    threading.Thread(target=record_video, daemon=True).start()


def stop_recording():
    """Stops recording and releases the video writer."""
    global recording, video_writer
    recording = False
    if video_writer:
        video_writer.release()


def record_video():
    """Continuously writes frames to the current video file."""
    global cap
    while recording and camera_active:
        ret, frame = cap.read()
        if ret:
            frame = frame[::-1, ::-1, ::-1]
            frame = frame[:, 420:1500, :]
            frame = np.ascontiguousarray(frame)
            video_writer.write(frame)


def toggle_recording(btn):
    """Toggles between starting and stopping a recording."""
    global recording
    if not recording:
        start_recording()
        btn.config(text="Stop Recording")
    else:
        stop_recording()
        btn.config(text="Record Video")


def update_photo_display(label, path):
    """Updates an image label with the provided file path."""
    try:
        img = Image.open(path).resize((400, 400))
        img_tk = ImageTk.PhotoImage(img)
        label.imgtk = img_tk
        label.config(image=img_tk)
    except:
        pass


# --- Automatic measurement mode support --- #

def turn_off_camera_auto():
    """Stops and releases the camera used in automatic mode."""
    global cap, camera_active
    if cap and camera_active:
        cap.release()
        camera_active = False


def start_live_view(target_label):
    """Starts live camera view inside a given Tkinter label."""
    global cap, camera_active

    if not camera_active:
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        if not cap.isOpened():
            print("Unable to open camera.")
            return
        camera_active = True

    def update():
        if camera_active:
            ret, frame = cap.read()
            if ret:
                frame = frame[::-1, ::-1, ::-1]
                frame = frame[:, 420:1500, :]
                frame = np.ascontiguousarray(frame)

                img = Image.fromarray(frame).resize((300, 300))
                img_tk = ImageTk.PhotoImage(img)
                target_label.imgtk = img_tk
                target_label.config(image=img_tk)
            target_label.after(10, update)

    update()


# --- Automatic measurement image capture --- #

def capture_image_array():
    """Captures a single frame from the camera as a NumPy array."""
    global cap
    if not cap or not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    ret, frame = cap.read()
    if ret:
        frame = frame[:, 420:1500, :]
        frame = cv2.flip(frame, 1)
        return frame
    else:
        print("Failed to capture image.")
        return None

