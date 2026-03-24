import os
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from controller import (move_left, move_right, stop_motor, set_speed, move_motor, move_to_position,
    activate_filter, led_on, led_off, led_intensity)
from communication import (send_command, read_current_position, arduino, refresh_ports, connect_arduino, disconnect_arduino)
from camera_functions import (set_camera_index, toggle_camera, take_image, capture_image_array, set_save_folder, save_current_image,
    toggle_recording, update_image_display, refresh_cameras)
import camera_functions
from automatic_gui import open_auto_mode_window
from utils import resource_path
from focal_measurements import compute_distances_to_center, format_distances
from updater import check_for_updates
import numpy as np


def open_window_conexion():
    """
    Opens the initial connection window where the user selects the Arduino
    COM port and the camera device before launching the main interface.
    This is the first window the user sees when the program starts.
    """
    # Create the root Tkinter window for the connection dialog
    win = tk.Tk()
    win.title("Device Connection")

    # Define the window size
    window_width = 350
    window_height = 200

    # Get the screen dimensions to calculate the centered position
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()

    # Calculate the top left corner so the window appears centered
    center_x = (screen_width // 2) - (window_width // 2)
    center_y = (screen_height // 2) - (window_height // 2)
    win.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    # Prevent the user from resizing this small dialog window
    win.resizable(False, False)

    # --- COM Port Selection ---
    # Label and dropdown for selecting the Arduino serial port
    tk.Label(win, text="Select COM Port:", font=("Helvetica", 12)).pack(pady=5)
    port_combo = ttk.Combobox(win, width=30, state="readonly")  # readonly prevents manual typing
    port_combo.pack(pady=5)

    # --- Camera Selection ---
    # Label and dropdown for selecting the camera device
    tk.Label(win, text="Select Camera:", font=("Helvetica", 12)).pack(pady=5)
    camera_combo = ttk.Combobox(win, width=30, state="readonly")
    camera_combo.pack(pady=5)

    def refresh():
        """
        Scans for available COM ports and cameras and updates the dropdowns.
        Called automatically when the window opens and when Refresh is clicked.
        """
        # Get the list of available serial ports and populate the dropdown
        ports = refresh_ports()
        port_combo['values'] = ports
        port_combo.set("")  # Clear current selection

        # Get the list of available cameras and populate the dropdown
        cameras = refresh_cameras()
        camera_combo['values'] = cameras
        camera_combo.set("")  # Clear current selection

    def connect():
        """
        Reads the selected port and camera, validates the selection,
        sets the camera index, connects to Arduino, and launches the main GUI.
        """
        # Read the currently selected values from the dropdowns
        selected_port = port_combo.get()
        selected_camera = camera_combo.get()

        # Validate that both a port and a camera have been selected
        if not selected_port:
            messagebox.showwarning("No Port", "Please select a COM port.")
            return
        if not selected_camera:
            messagebox.showwarning("No Camera", "Please select a camera.")
            return

        # Get a fresh list of cameras to find the index of the selected one
        cameras = refresh_cameras()
        try:
            # Find the position of the selected camera in the list
            cam_index = cameras.index(selected_camera)
        except ValueError:
            # If camera is not found, default to index 0
            cam_index = 0

        # Update the global camera index in camera_functions
        set_camera_index(cam_index)

        # Attempt to connect to the Arduino on the selected COM port
        if connect_arduino(selected_port):
            # Connection successful — close this window and open the main GUI
            win.destroy()
            start_interface()
        else:
            # Connection failed — show error and let the user try again
            messagebox.showerror("Connection Error", "Failed to connect to Arduino.")

    # --- Buttons ---
    # Connect button triggers the connection and launches the main GUI
    tk.Button(win, text="Connect", command=connect).pack(pady=5)
    # Refresh button rescans for ports and cameras
    tk.Button(win, text="Refresh", command=refresh).pack(pady=5)

    # Automatically scan for ports and cameras when the window first opens
    refresh()
    
    # Check for updates when the app first opens
    win.after(1000, check_for_updates)
    win.mainloop()
    
    # Start the Tkinter event loop for this window
    win.mainloop()


def select_filter(filter, boton, all_buttons):
    """
    Activates the selected optical filter and highlights the corresponding button.
    Resets all other filter buttons to their default color first, then
    highlights the selected one with the color returned by activate_filter().

    Parameters
    ----------
    filter : str
        The filter key to activate ('r', 'g', 'b', or 'w').
    boton : tk.Button
        The button that was clicked, to be highlighted.
    all_buttons : list of tk.Button
        All filter buttons, used to reset their colors before highlighting.
    """
    # Send the filter command to the Arduino and get back the highlight color
    color = activate_filter(filter)
    # Reset all filter buttons to the default system color
    for b in all_buttons:
        b.config(bg="SystemButtonFace")
    # Highlight the selected filter button with its assigned color
    boton.config(bg=color)


def build_camera_view(parent, font, no_camera_tk, no_image_tk):
    """
    Builds and returns the camera view section of the main GUI.
    This section shows two image labels:
    - The top one displays the live camera feed.
    - The bottom one displays the last captured image for preview.

    Parameters
    ----------
    parent : tk.Frame
        The parent frame to place this section in.
    font : tuple
        The font settings to use for the section title.
    no_camera_tk : ImageTk.PhotoImage
        The placeholder image shown when the camera is off.
    no_image_tk : ImageTk.PhotoImage
        The placeholder image shown when no image has been taken yet.

    Returns
    -------
    tuple (tk.Label, tk.Label)
        camera_label: the label showing the live feed.
        last_image_label: the label showing the last captured image.
    """
    # Create the labeled frame container for this section
    camera_frame = tk.LabelFrame(parent, text="Live Camera View", font=font, padx=10, pady=10)
    # Place it in column 2 of the main layout, aligned to the top
    camera_frame.grid(row=0, column=2, sticky="n", padx=10, pady=10)
    # Allow the column to expand to fill available space
    camera_frame.columnconfigure(0, weight=1)

    # Top label: displays the live camera feed or the placeholder when camera is off
    camera_label = tk.Label(camera_frame, image=no_camera_tk, bd=2, relief="groove", bg="black")
    camera_label.grid(row=0, column=0, padx=1, pady=1)

    # Bottom label: displays the last captured image or a placeholder
    last_image_label = tk.Label(camera_frame, image=no_image_tk, bd=2, relief="groove", bg="black")
    last_image_label.grid(row=1, column=0, padx=5, pady=10)

    # Return both labels so they can be passed to build_camera_controls
    return camera_label, last_image_label


def build_camera_controls(parent, font, camera_label, last_image_label):
    """
    Builds the camera controls section of the main GUI.
    Contains buttons for activating the camera, capturing images,
    recording video, selecting a save folder, opening images,
    saving images, and running a distance measurement.
    Also displays a reference image and a results text area.

    Parameters
    ----------
    parent : tk.Frame
        The parent frame to place this section in.
    font : tuple
        The font settings for the section title.
    camera_label : tk.Label
        The live camera feed label, passed to toggle_camera and take_image.
    last_image_label : tk.Label
        The image preview label, passed to take_image and update_image_display.

    Returns
    -------
    tk.Button
        btn_save_image: the save button, returned so take_image can show it
        after a image is captured.
    """
    # Create the labeled frame container for this section
    btns_frame = tk.LabelFrame(parent, text="Camera Controls", font=font, padx=10, pady=10)
    # Place it in column 1 of the main layout, aligned to the top
    btns_frame.grid(row=0, column=1, sticky="n", padx=10, pady=10)

    # Button to turn the live camera feed on or off
    btn_toggle_camera = tk.Button(btns_frame, text="Activate Camera", width=20, height=2)
    btn_toggle_camera.grid(row=0, column=0, padx=5, pady=5)

    # Button to capture a still image from the live feed
    btn_image = tk.Button(btns_frame, text="Capture Image", width=20, height=2)
    btn_image.grid(row=1, column=0, padx=5, pady=5)

    # Button to start or stop video recording
    btn_record = tk.Button(btns_frame, text="Start/Stop Recording", width=20, height=2)
    btn_record.grid(row=2, column=0, padx=5, pady=5)

    def select_folder():
        """
        Opens a folder browser dialog and updates the save folder
        in camera_functions if the user selects a valid folder.
        """
        # Open the system folder browser dialog
        folder = filedialog.askdirectory()
        if folder:
            # Update the global save folder in camera_functions
            set_save_folder(folder)

    # Button to open the folder browser and change the save location
    btn_folder = tk.Button(btns_frame, text="Select Folder", width=20, height=2, command=select_folder)
    btn_folder.grid(row=3, column=0, padx=5, pady=5)

    # Button to open an existing image file and display it in last_image_label
    # Opens a file browser filtered to common image formats
    btn_show_image = tk.Button(btns_frame, text="Open Image", width=20, height=2,
                               command=lambda: update_image_display(
                                   last_image_label,
                                   filedialog.askopenfilename(
                                       title='Select Image',
                                       filetypes=[('Image files', '*.jpg *.jpeg *.png *.bmp')]
                                   )))
    btn_show_image.grid(row=4, column=0, padx=5, pady=5)

    # Button to save the last captured image to disk
    # Calls save_current_image which handles folder selection and naming
    btn_save_image = tk.Button(btns_frame, text="Save Image", width=20, height=2,
                               command=lambda: save_current_image(btn_save_image))
    btn_save_image.grid(row=5, column=0, padx=5, pady=5)

    # Button to trigger the distance measurement on a captured image
    btn_measurement = tk.Button(btns_frame, text="Measure distances", width=20, height=2)
    btn_measurement.grid(row=6, column=0, padx=5, pady=5)

    # --- Reference image --- #
    # Load the reference image showing the 3x3 blob grid layout
    # This helps the user understand which points are being measured
    img_path = resource_path(os.path.join("resources", "points.png"))
    img = Image.open(img_path).resize((170, 170))
    # Convert to Tkinter compatible format
    image = ImageTk.PhotoImage(img)
    # Display the reference image in a label below the buttons
    img_label = tk.Label(btns_frame, image=image)
    img_label.grid(row=9, column=0, pady=10)
    # Keep a reference to prevent Python garbage collecting the image
    img_label.image = image

    # --- Measurement results area --- #
    # Title label above the results text area
    tk.Label(btns_frame, text="Measurement Results", font=("Helvetica", 10, "bold")).grid(row=10, column=0)
    # Text widget to display the distance measurement results
    # state='disabled' prevents the user from typing in it
    result_text = tk.Text(btns_frame, height=12, width=30, font=("Courier", 10))
    result_text.grid(row=11, column=0, pady=10)
    result_text.configure(state='disabled')

    def test_measurement():
        """
        Captures an image from the camera, computes the distances between
        the blob points and the center, and displays the results in the
        results text area. Shows a warning if the capture or detection fails.
        """
        # Capture a single frame from the camera as a NumPy array
        img = capture_image_array()
        if img is None:
            # Camera failed to capture, show error and stop
            messagebox.showwarning("Error", "Could not capture image.")
            return

        # Run the blob detection and distance calculation on the captured image
        distances = compute_distances_to_center(img)

        if np.all(distances == 0):
            # All distances are zero means no valid blobs were detected
            messagebox.showwarning("Error", "Could not find blobs in image.")
            return

        # Enable the text widget temporarily to update its content
        result_text.configure(state='normal')
        # Clear any previous results
        result_text.delete('1.0', tk.END)
        # Insert the formatted distance results
        result_text.insert(tk.END, format_distances(distances))
        # Disable again to prevent user edits
        result_text.configure(state='disabled')

    # Assign the test_measurement function to the measure button
    btn_measurement.config(command=test_measurement)
    # Assign toggle_camera passing both the feed label and the button itself
    # so the button text can be updated when toggled
    btn_toggle_camera.config(command=lambda: toggle_camera(camera_label, btn_toggle_camera))
    # Assign take_image passing both display labels and the save button
    # so the save button can be shown after a image is taken
    btn_image.config(command=lambda: take_image(camera_label, last_image_label, btn_save_image))
    # Assign toggle_recording passing the button so its text can be updated
    btn_record.config(command=lambda: toggle_recording(btn_record))

    # Return the save button so start_interface can pass it to take_image
    return btn_save_image


def build_controller(parent, font, root):
    """
    Builds the device control section of the main GUI.
    Contains controls for motor movement, absolute positioning,
    a digital position display, LED light source control,
    optical filter selection, and the automatic mode button.

    Parameters
    ----------
    parent : tk.Frame
        The parent frame to place this section in.
    font : tuple
        The font settings for labels and titles.
    root : tk.Tk
        The main window, needed to get the default button color
        and to pass to the automatic mode window.

    Returns
    -------
    tk.Label
        position_display: the digital position label, returned so
        start_interface can update it with the current motor position.
    """
    # Create the labeled frame container for the entire controller section
    motor_frame = tk.LabelFrame(parent, text="Device Control", font=font, padx=10, pady=10)
    # Place it in column 0 of the main layout, aligned to the top
    motor_frame.grid(row=0, column=0, sticky="n", padx=10, pady=10)

    # --- [MOTOR CONTROL] ---
    # Two buttons for continuous movement while held down
    btn_left = tk.Button(motor_frame, text="◀ Back (Left)", font=("Arial", 14))
    btn_right = tk.Button(motor_frame, text="▶ Forward (Right)", font=("Arial", 14))
    # Bind ButtonPress to start moving and ButtonRelease to stop
    btn_left.bind("<ButtonPress>", move_left)
    btn_left.bind("<ButtonRelease>", stop_motor)
    btn_right.bind("<ButtonPress>", move_right)
    btn_right.bind("<ButtonRelease>", stop_motor)
    btn_left.grid(row=0, column=0, padx=5, pady=5)
    btn_right.grid(row=0, column=1, padx=5, pady=5)

    # Speed slider to control how fast the motor moves (1 = slowest, 10 = fastest)
    tk.Label(motor_frame, text="Speed:", font=font).grid(row=1, column=0, columnspan=2)
    speed_slider = tk.Scale(motor_frame, from_=1, to=10, orient=tk.HORIZONTAL,
                            length=300, tickinterval=1, command=set_speed)
    speed_slider.set(5)  # Default speed is 5
    speed_slider.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    # Entry field for specifying how many mm to move
    tk.Label(motor_frame, text="Distance to move (mm):", font=font).grid(row=3, column=0, columnspan=2)
    mm_entry = tk.Entry(motor_frame, width=15)
    mm_entry.grid(row=4, column=0, columnspan=2, pady=5)

    # Radio buttons to select the direction of movement
    direction = tk.StringVar(value="f")  # Default direction is forward
    radio_frame = tk.Frame(motor_frame)
    radio_frame.grid(row=5, column=0, columnspan=2)
    tk.Radiobutton(radio_frame, text="Forward", variable=direction, value="f", font=font).pack(side="left")
    tk.Radiobutton(radio_frame, text="Backward", variable=direction, value="b", font=font).pack(side="left")

    # Allow pressing Enter in the mm entry field to trigger the move
    mm_entry.bind("<Return>", lambda event: [
        move_motor(mm_entry.get(), direction.get()),
        mm_entry.master.focus_set()  # Return focus to the frame after moving
    ])
    # Move button: moves the motor by the specified distance in the selected direction
    btn_move = tk.Button(motor_frame, text="Move", width=20, height=2,
                         command=lambda: [
                             move_motor(mm_entry.get(), direction.get()),
                             mm_entry.master.focus_set()
                         ])
    btn_move.grid(row=6, column=0, columnspan=2, pady=10)

    # --- [GO TO ABSOLUTE POSITION] ---
    # Entry field for specifying an absolute position in mm
    tk.Label(motor_frame, text="Go to position (mm):", font=font).grid(row=7, column=0, columnspan=2)
    go_entry = tk.Entry(motor_frame, width=15)
    go_entry.grid(row=8, column=0, columnspan=2, pady=5)

    # Allow pressing Enter in the go entry field to trigger the move
    go_entry.bind("<Return>", lambda event: [
        move_to_position(go_entry.get()),
        go_entry.master.focus_set()
    ])
    # Go button: moves the motor to the specified absolute position
    btn_go = tk.Button(motor_frame, text="Go", width=20,
                       command=lambda: [
                           move_to_position(go_entry.get()),
                           go_entry.master.focus_set()
                       ])
    btn_go.grid(row=9, column=0, columnspan=2, pady=5)

    # --- [DIGITAL VISOR] ---
    # A styled label that shows the current motor position like a digital display
    # Red text on dark background to resemble a physical digital readout
    position_display = tk.Label(
        motor_frame,
        text="000.00 mm",
        font=("Courier", 20, "bold"),
        fg="#FF3C3C",       # red text color
        bg="#1A1A1A",       # dark background color
        width=10,
        relief="sunken",
        bd=6
    )
    position_display.grid(row=10, column=0, columnspan=2, pady=(10, 5))

    # --- [LED CONTROL] ---
    tk.Label(motor_frame, text="Light Source Control", font=font).grid(
        row=11, column=0, columnspan=2, pady=(10, 0))

    # Get the default system button color to restore buttons when toggled off
    default_btn_color = root.cget("bg")

    def toggle_light(state):
        """
        Turns the LED light source on or off and updates button appearance.
        When turned on, also applies the current intensity slider value.
        Highlights the active button with a grey color to show current state.
        """
        if state == "on":
            led_on()
            # Read the current intensity value from the slider and apply it
            current_intensity = led_slider.get()
            led_intensity(current_intensity)
            # Highlight the ON button and reset the OFF button
            btn_light_on.config(bg="#BCBCBC", fg="black")
            btn_light_off.config(bg=default_btn_color, fg="black")
        elif state == "off":
            led_off()
            # Highlight the OFF button and reset the ON button
            btn_light_off.config(bg="#BCBCBC", fg="black")
            btn_light_on.config(bg=default_btn_color, fg="black")

    # Buttons to turn the light on and off
    btn_light_on = tk.Button(motor_frame, text="Turn On", width=15,
                             command=lambda: toggle_light("on"))
    btn_light_off = tk.Button(motor_frame, text="Turn Off", width=15,
                              command=lambda: toggle_light("off"))
    btn_light_on.grid(row=12, column=0, pady=5)
    btn_light_off.grid(row=12, column=1, pady=5)

    # Intensity slider: controls the brightness of the LED (1 = dimmest, 10 = brightest)
    # Sends a command directly to the Arduino every time the slider is moved
    tk.Label(motor_frame, text="Intensity:", font=font).grid(row=13, column=0, columnspan=2)
    led_slider = tk.Scale(motor_frame, from_=1, to=10, orient=tk.HORIZONTAL,
                          length=300, tickinterval=1,
                          command=lambda val: send_command(f"led{val}"))
    led_slider.set(5)  # Default intensity is 5
    led_slider.grid(row=14, column=0, columnspan=2, padx=5, pady=5)

    # --- [FILTER CONTROL] ---
    tk.Label(motor_frame, text="Filters", font=font).grid(
        row=15, column=0, columnspan=2, pady=(10, 5))
    filter_frame = tk.Frame(motor_frame)
    filter_frame.grid(row=16, column=0, columnspan=2)

    # Define the available filters with their display name and command key
    filters = [("Red", "r"), ("Green", "g"), ("Blue", "b"), ("White", "w")]
    filter_buttons = []  # Keep track of all filter buttons for color reset

    for name, key in filters:
        # Create a button for each filter
        btn = tk.Button(filter_frame, text=name, width=10)
        # When clicked, activate the filter and highlight this button
        # c=key and b=btn capture the loop variables to avoid closure issues
        btn.config(command=lambda c=key, b=btn: select_filter(c, b, filter_buttons))
        btn.pack(side="left", padx=5)
        # Add to the list so all buttons can be reset when a new one is selected
        filter_buttons.append(btn)

    # --- [AUTOMATIC MODE] ---
    # Button to open the automatic measurement window
    btn_auto = tk.Button(motor_frame, text="Automatic Mode", width=20, height=2,
                         command=lambda: open_auto_mode_window(root))
    btn_auto.grid(row=18, column=0, columnspan=2, pady=10)

    # Return the position display label so start_interface can update it
    return position_display


def start_interface():
    """
    Creates and launches the main application window.
    Sets up a scrollable canvas as the base layout, then builds
    the three main sections by calling the builder functions:
    - build_controller: motor, LED, and filter controls
    - build_camera_view: live feed and image preview
    - build_camera_controls: camera buttons and measurement tools
    Also handles the position update loop and window close behavior.
    """
    # Create the main application window
    root = tk.Tk()
    root.title("Slidebench Control")

    # Define and center the window on the screen
    window_width = 1200
    window_height = 700
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    # Font used for all section titles and labels throughout the interface
    font_settings = ("Helvetica", 12, "bold")

    # Load the placeholder images shown when camera is off or no image taken
    image_default = resource_path(os.path.join("resources", "image.png"))
    image1_default = resource_path(os.path.join("resources", "image1.png"))
    no_camera_img = Image.open(image_default).resize((400, 400))
    no_image_img = Image.open(image1_default).resize((400, 400))
    # Convert to Tkinter compatible format
    no_camera_tk = ImageTk.PhotoImage(no_camera_img)
    no_image_tk = ImageTk.PhotoImage(no_image_img)

    # --- Scrollable layout --- #
    # A canvas with a scrollbar allows the content to scroll if the
    # window is too small to show everything at once
    canvas = tk.Canvas(root)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    # Link the scrollbar to the canvas scroll position
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    # Create a regular frame inside the canvas to hold all widgets
    main_frame = tk.Frame(canvas)

    def resize_frame(event):
        """Updates the canvas window width when the outer window is resized."""
        canvas.itemconfig(main_window, width=event.width)

    # Embed the main_frame inside the canvas
    main_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
    # Bind the resize event to keep the frame width in sync
    canvas.bind("<Configure>", resize_frame)

    def on_configure(event):
        """Updates the canvas scroll region when the frame content changes size."""
        canvas.configure(scrollregion=canvas.bbox("all"))

    # Bind frame size changes to update the scrollable area
    main_frame.bind("<Configure>", on_configure)
    # Allow mouse wheel scrolling on all widgets
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # Configure column weights for the three section layout
    main_frame.columnconfigure(0, weight=1)  # controller section
    main_frame.columnconfigure(1, weight=2)  # camera controls section
    main_frame.columnconfigure(2, weight=1)  # camera view section

    # --- Build the three main sections --- #
    # Build controller and get back the position display label
    position_display = build_controller(main_frame, font_settings, root)
    # Build camera view and get back both image labels
    camera_label, last_image_label = build_camera_view(
        main_frame, font_settings, no_camera_tk, no_image_tk)
    # Build camera controls, passing the labels from camera view
    build_camera_controls(main_frame, font_settings, camera_label, last_image_label)

    def on_closing():
        """
        Handles cleanup when the user closes the main window.
        Turns off the LED, releases the camera and video writer if active,
        closes the Arduino serial connection, and destroys the window.
        """
        # Turn off the LED light source before closing
        led_off()
        # Release the camera if it is currently open
        if camera_functions.cap:
            camera_functions.cap.release()
        # Release the video writer if a recording is in progress
        if camera_functions.recording and camera_functions.video_writer:
            camera_functions.video_writer.release()
        # Close the Arduino serial connection if it is open
        disconnect_arduino()
        # Destroy the main window and exit the application
        root.destroy()

    def update_position():
        """
        Reads the current motor position from the Arduino and updates
        the digital position display every 50 milliseconds.
        Uses root.after() to schedule itself repeatedly without blocking the GUI.
        """
        # Read the current position in mm from the Arduino
        mm = read_current_position()
        if mm is not None:
            # Update the display label with the new position value
            position_display.config(text=f"{mm:.2f} mm")
        # Schedule this function to run again after 50ms
        root.after(50, update_position)

    # Register the on_closing function to run when the X button is clicked
    root.protocol("WM_DELETE_WINDOW", on_closing)
    # Start the position update loop
    update_position()
    # Start the Tkinter event loop — this blocks until the window is closed
    root.mainloop()