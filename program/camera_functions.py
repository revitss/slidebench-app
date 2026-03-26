import cv2
import os
import time
import threading
from tkinter import simpledialog, messagebox
from PIL import Image, ImageTk
import numpy as np
from pygrabber.dshow_graph import FilterGraph
from utils import resource_path, external_folder

# --- Global state variables --- #
# These variables are shared across all functions in this module.
# They keep track of the current state of the camera, recording, and file saving.

camera_active = False       # True if the camera is currently streaming live video
recording = False           # True if a video recording is currently in progress
cap = None                  # OpenCV VideoCapture object, used to read frames from the camera
video_writer = None         # OpenCV VideoWriter object, used to write frames to a video file
last_preview_image = None   # Stores the last captured still image (PIL Image) for saving
image_path = None           # Stores the file path of the last saved image
save_folder = external_folder("media")  # Default folder where images and videos are saved
custom_folder_selected = False          # True if the user manually selected a save folder
width, height = (1920, 1080)            # Resolution used when opening the camera
camera_index = 2                        # Index of the camera device to use (0, 1, 2, ...)


# --- Camera setup --- #

def set_camera_index(index):
    """
    Sets which camera device to use.
    When multiple cameras are connected, each is assigned a number (0, 1, 2...).
    This function updates the global index so all subsequent camera operations
    use the correct device.
    """
    global camera_index
    # Overwrite the global camera_index with the new value
    camera_index = index


def refresh_cameras():
    """
    Scans the computer for connected camera devices and returns their names.
    Called when the connection window opens so the user can select a camera.
    """
    try:
        # Use pygrabber to query all connected camera devices
        graph = FilterGraph()
        cameras = graph.get_input_devices()
        # Return the list if cameras were found, otherwise return a placeholder
        return cameras if cameras else ["No cameras found"]
    except Exception as e:
        messagebox.showwarning("Error", f"Error detecting cameras: {e}")


# --- File management --- #

def set_save_folder(path):
    """
    Updates the folder where images and videos will be saved.
    Called when the user clicks 'Select Folder' in the GUI.
    From this point on, files are saved directly in the selected folder
    without creating daily subfolders.
    """
    global save_folder, custom_folder_selected
    # Update the save folder to the user selected path
    save_folder = path
    # Mark that the user has chosen a custom folder
    # this flag is checked by get_save_destination()
    custom_folder_selected = True


def get_save_destination():
    """
    Determines and returns the correct folder for saving the current image.
    Checks whether the user has manually selected a folder:
    - If yes: returns that folder directly.
    - If no: creates and returns a daily subfolder inside media/.
    """
    if custom_folder_selected:
        # User selected a custom folder, save directly there
        return save_folder
    else:
        # No custom folder selected, use the default daily folder
        return create_daily_folder()


def create_daily_folder():
    """
    Creates and returns a folder named after today's date inside the default save folder.
    For example: media/2024-06-15/
    Keeps images organized by day automatically.
    If the folder already exists, it is not recreated.
    """
    # Get today's date as a string e.g. "2024-06-15"
    date_str = time.strftime("%Y-%m-%d")
    # Build the full path: media/2024-06-15/
    day_folder = os.path.join(save_folder, date_str)
    # Create the folder if it doesn't exist, do nothing if it already does
    os.makedirs(day_folder, exist_ok=True)
    return day_folder


def get_filename():
    """
    Asks the user for a custom filename and returns the final name with .png extension.
    If the user cancels or leaves it empty, a default time-based name is used
    e.g. 'img_143025.png'.
    """
    # Generate a default name based on the current time as fallback
    timestamp = time.strftime("%H%M%S")
    default_name = f"img_{timestamp}.png"
    # Show a dialog asking the user for a custom name
    custom_name = simpledialog.askstring("Save Image", "Custom name?\n(Do not include .png)")
    # Use custom name if provided, otherwise use the default
    return (custom_name + ".png") if custom_name else default_name


# --- Grid overlay --- #

def add_grid(img, grid_type="both"):
    """
    Draws a grid overlay on top of an image for alignment assistance.
    Two types available:
    - '4x4': vertical and horizontal lines dividing the image into a 4x4 grid.
    - 'radial': concentric circles centered in the image.
    - 'both': draws both (default).
    Does not modify the original image, works on a copy.
    """
    # Work on a copy so the original image is not modified
    img = img.copy()
    # Get image dimensions
    h, w, _ = img.shape
    color = (255, 255, 0)   # yellow color for the grid lines
    thickness = 1           # line thickness in pixels

    if grid_type in ['4x4', 'both']:
        # Draw 3 vertical and 3 horizontal lines to create a 4x4 grid
        for i in range(1, 4):
            x = w * i // 4  # x position of vertical line
            y = h * i // 4  # y position of horizontal line
            cv2.line(img, (x, 0), (x, h), color, thickness)    # vertical line
            cv2.line(img, (0, y), (w, y), color, thickness)    # horizontal line

    if grid_type in ['radial', 'both']:
        # Draw concentric circles from the center outward
        center = (w // 2, h // 2)   # center of the image
        # Start at radius 50, increase by 100 until reaching the edge
        for r in range(50, min(w, h) // 2, 100):
            cv2.circle(img, center, r, color, thickness)

    return img


# --- Live camera preview --- #

def toggle_camera(camera_label, btn):
    """
    Turns the live camera preview on or off in the main GUI.
    When turned on: opens the camera, starts the live feed, updates button text.
    When turned off: stops the feed, releases the camera, shows placeholder image.
    """
    global camera_active, cap
    if not camera_active:
        # Open the camera device at the specified index
        cap = cv2.VideoCapture(camera_index)
        # Set the resolution
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        # Check if the camera opened successfully
        if not cap.isOpened():
            messagebox.showwarning("Error", "Unable to open camera in toggle_camera.")
            return
        # Mark the camera as active and start the live frame loop
        camera_active = True
        update_frame(camera_label)
        btn.config(text="Deactivate Camera")
    else:
        # Mark camera as inactive — this stops the update_frame loop
        camera_active = False
        # Release the camera resource so other programs can use it
        cap.release()
        btn.config(text="Activate Camera")
        try:
            # Load and display the default placeholder image
            default_img = Image.open(resource_path(os.path.join("resources", "image.png"))).resize((400, 400))
            default_img_tk = ImageTk.PhotoImage(default_img)
            # Keep a reference to prevent garbage collection
            camera_label.imgtk = default_img_tk
            camera_label.config(image=default_img_tk)
        except (FileNotFoundError, OSError):
            # If placeholder image is missing, just clear the label
            camera_label.config(image='')


def update_frame(camera_label):
    """
    Reads one frame from the camera and updates the live preview display.
    Called repeatedly every 10ms using Tkinter's after() method to create
    a smooth live feed. Stops automatically when camera_active is False.
    """
    if camera_active:
        # Read the next frame from the camera
        ret, frame = cap.read()
        if ret:
            # Flip vertically [::-1 on axis 0], horizontally [::-1 on axis 1]
            # and convert BGR to RGB [::-1 on axis 2] all in one operation
            frame = frame[::-1, ::-1, ::-1]
            # Crop to the region of interest (removes black borders)
            frame = frame[:, 420:1500, :]
            # Make the array contiguous in memory for performance
            frame = np.ascontiguousarray(frame)
            # Add the alignment grid on top of the frame
            frame_with_grid = add_grid(frame, grid_type='both')
            # Convert to PIL Image and resize for display
            img = Image.fromarray(frame_with_grid).resize((400, 400))
            # Convert to Tkinter compatible format
            img_tk = ImageTk.PhotoImage(img)
            # Keep a reference to prevent garbage collection
            camera_label.imgtk = img_tk
            # Update the label with the new frame
            camera_label.config(image=img_tk)

        # Schedule this function to run again after 10ms
        # this creates the continuous live feed loop
        camera_label.after(10, lambda: update_frame(camera_label))


# --- Image capture --- #

def take_image(camera_label, last_image_label, btn_save_image):
    """
    Captures a single still image from the live camera feed.
    Stores the image in memory for saving later and displays it
    in the image preview label. Shows the save button after capture.
    """
    global cap, last_preview_image
    # Read one frame from the camera
    ret, frame = cap.read()
    if ret:
        # Flip vertically, horizontally and convert BGR to RGB for display
        frame = frame[::-1, ::-1, ::-1]
        # Crop to the region of interest
        frame_rgb = frame[:, 420:1500, :]
        # Store the image as a PIL Image in memory so it can be saved later
        # when the user clicks the Save button
        last_preview_image = Image.fromarray(frame_rgb)
        # Add the alignment grid for the preview display
        preview_frame = add_grid(frame_rgb, grid_type='both')
        # Resize for display and convert to Tkinter format
        img_resized = Image.fromarray(preview_frame).resize((400, 400))
        img_tk = ImageTk.PhotoImage(img_resized)
        # Keep a reference to prevent garbage collection
        last_image_label.imgtk = img_tk
        # Update the image preview label with the captured image
        last_image_label.config(image=img_tk)
        # Make the save button visible now that a image is available
        btn_save_image.grid()


def save_current_image(btn_save_image):
    """
    Saves the last captured image to disk.
    Determines the save location, asks the user for a filename,
    and writes the image file. Shows a warning if no image was captured yet.
    """
    global last_preview_image, image_path
    # Check if there is an image to save
    if last_preview_image is None:
        messagebox.showwarning("Error", "No image to save.")
        return
    # Get the correct folder depending on whether user selected a custom one
    folder = get_save_destination()
    # Ask the user for a filename
    filename = get_filename()
    # Build the full file path
    destination = os.path.join(folder, filename)
    try:
        # Save the PIL Image to disk as a PNG file
        last_preview_image.save(destination)
        # Store the path for future reference
        image_path = destination
        # Notify the user that the save was successful
        messagebox.showinfo("Saving succeeded", f"Image saved as {filename} in {folder}")
    except Exception as e:
        messagebox.showwarning("Error", f"Error saving image: {e}")


def update_image_display(label, path):
    """
    Opens an image file and displays it in a Tkinter label widget.
    Used when the user clicks 'Open Image' to browse an existing file.
    Silently ignores errors if the file cannot be opened.
    """
    try:
        # Open the image file and resize it for display
        img = Image.open(path).resize((400, 400))
        # Convert to Tkinter compatible format
        img_tk = ImageTk.PhotoImage(img)
        # Keep a reference to prevent garbage collection
        label.imgtk = img_tk
        # Update the label with the new image
        label.config(image=img_tk)
    except (FileNotFoundError, OSError):
        # If the file is missing or unreadable, leave the label unchanged
        pass


# --- Video recording --- #

def start_recording():
    """
    Starts recording a video from the live camera feed.
    Creates a new video file in a daily subfolder, reads the first frame
    to determine the resolution, then starts a background recording thread.
    """
    global recording, video_writer
    # Set recording flag to True so record_video loop keeps running
    recording = True
    # Define the video codec (MP4 format)
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    # Get today's folder and build the video file path
    day_folder = create_daily_folder()
    filename = time.strftime("video_%H%M%S.mp4")
    path = os.path.join(day_folder, filename)
    # Read one frame to determine the actual frame dimensions
    ret, frame = cap.read()
    if not ret:
        messagebox.showwarning("Error", "Could not read initial frame for recording.")
        recording = False
        return
    # Process the frame the same way as the live feed
    frame = frame[::-1, ::-1, :]
    frame = frame[:, 420:1500, :]
    frame = np.ascontiguousarray(frame)
    # Use local variables to avoid overwriting the global width and height
    frame_height, frame_width = frame.shape[:2]
    # Create the VideoWriter object that will write frames to the file
    video_writer = cv2.VideoWriter(path, fourcc, 15, (frame_width, frame_height))
    # Start the recording loop in a background thread
    # daemon=True means the thread will stop if the main program exits
    threading.Thread(target=record_video, daemon=True).start()


def stop_recording():
    """
    Stops the current video recording and releases the video writer.
    Setting recording to False causes the record_video loop to exit.
    """
    global recording, video_writer
    # Setting this to False stops the while loop in record_video()
    recording = False
    if video_writer:
        # Release the writer to finalize and close the video file
        video_writer.release()


def record_video():
    """
    Continuously reads frames from the camera and writes them to the video file.
    Runs in a background thread. Stops when recording or camera_active is False.
    """
    global cap
    # Keep recording as long as both flags are True
    while recording and camera_active:
        ret, frame = cap.read()
        if ret:
            # Flip vertically and horizontally
            # note: only 2 axes flipped here, BGR is kept for the video writer
            frame = frame[::-1, ::-1, :]
            # Crop to the region of interest
            frame = frame[:, 420:1500, :]
            frame = np.ascontiguousarray(frame)
            # Write the frame to the video file
            video_writer.write(frame)


def toggle_recording(btn):
    """
    Toggles between starting and stopping a video recording.
    Updates the button text to reflect the current state.
    """
    global recording
    if not recording:
        # Start recording and update button text
        start_recording()
        btn.config(text="Stop Recording")
    else:
        # Stop recording and reset button text
        stop_recording()
        btn.config(text="Record Video")


# --- Automatic measurement mode support --- #

def turn_off_camera_auto():
    """
    Stops and releases the camera when the automatic measurement window is closed.
    Releases the camera resource so it can be reused by the main GUI.
    """
    global cap, camera_active
    if cap and camera_active:
        # Release the camera hardware resource
        cap.release()
        # Mark the camera as inactive
        camera_active = False


def start_live_view(target_label):
    """
    Starts a live camera preview in the automatic measurement window.
    Opens the camera if not already active, then continuously updates
    the target label with live frames every 10ms.
    """
    global cap, camera_active

    if not camera_active:
        # Open the camera device
        cap = cv2.VideoCapture(camera_index)
        # Set the resolution using the global variables
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        if not cap.isOpened():
            messagebox.showwarning("Error", "Unable to open camera in start_live_view function.")
            return
        camera_active = True

    def update():
        """Inner function that reads and displays one frame, then schedules itself again."""
        if camera_active:
            ret, frame = cap.read()
            if ret:
                # Flip vertically, horizontally and convert BGR to RGB for display
                frame = frame[::-1, ::-1, ::-1]
                # Crop to the region of interest
                frame = frame[:, 420:1500, :]
                frame = np.ascontiguousarray(frame)
                # Resize smaller than main GUI since this is a side panel view
                img = Image.fromarray(frame).resize((300, 300))
                img_tk = ImageTk.PhotoImage(img)
                # Keep reference to prevent garbage collection
                target_label.imgtk = img_tk
                target_label.config(image=img_tk)
            # Schedule the next frame update after 10ms
            target_label.after(10, update)

    # Start the update loop
    update()


def capture_image_array():
    """
    Captures a single frame from the camera and returns it as a NumPy array.
    Unlike take_image() which is for GUI preview, this is used for scientific
    measurements. Returns raw image data for processing by measurement functions.
    Opens the camera automatically if not already open.
    """
    global cap
    # If the camera is not open, open it before capturing
    if not cap or not cap.isOpened():
        cap = cv2.VideoCapture(camera_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    ret, frame = cap.read()
    if ret:
        # Crop to the region of interest
        frame = frame[:, 420:1500, :]
        # Flip vertically, horizontally, it's in BGR format
        frame = frame[::-1, ::-1]
        return frame
    else:
        messagebox.showwarning("Error", "Failed to capture image in capture_image_array.")
        return None