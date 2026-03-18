import tkinter as tk
from tkinter import simpledialog
from camera_functions import start_live_view, turn_off_camera_auto
from focal_measurements import automatic_measurement, save_measurement_data, do_reference
import threading
from pathlib import Path

# Global variable that holds the reference to the automatic measurement window.
# It is None when the window is closed, and holds the window object when it is open.
# This prevents the user from opening multiple instances of the same window.
_auto_window = None


class ToolTip:
    """
    A class that adds a floating tooltip to any Tkinter widget.
    When the mouse hovers over the widget, a small popup appears with
    the tooltip text. When the mouse leaves, the popup disappears.
    """
    
    def __init__(self, widget, text):
        """
        Initializes the tooltip and binds it to the given widget.
        
        Parameters
        ----------
        widget : tk widget
            The widget that will trigger the tooltip on hover.
        text : str
            The text to display inside the tooltip.
        """
        self.widget = widget
        self.text = text
        self.tip_window = None  # Will hold the tooltip Toplevel window when visible
        # Bind the mouse enter event to show the tooltip
        widget.bind("<Enter>", self.show_tip)
        # Bind the mouse leave event to hide the tooltip
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        """
        Creates and displays the tooltip window near the widget.
        If the tooltip is already visible or there is no text, does nothing.
        """
        # Don't show if already visible or no text is set
        if self.tip_window or not self.text:
            return
        # Calculate the position of the tooltip — slightly offset from the widget
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        # Create a new top level window for the tooltip
        self.tip_window = tw = tk.Toplevel(self.widget)
        # Remove the window title bar and borders to make it look like a tooltip
        tw.wm_overrideredirect(True)
        # Position the tooltip window on the screen
        tw.wm_geometry(f"+{x}+{y}")
        # Create the label inside the tooltip window with the tooltip text
        label = tk.Label(
            tw,
            text=self.text,
            background="#333333",   # dark background
            foreground="white",     # white text
            relief="solid",
            borderwidth=1,
            justify="left",
            wraplength=220,         # wrap text after 220 pixels
            padx=6,
            pady=4,
            font=("Arial", 9)
        )
        label.pack()

    def hide_tip(self, event=None):
        """
        Destroys the tooltip window when the mouse leaves the widget.
        Resets tip_window to None so it can be shown again next time.
        """
        if self.tip_window:
            # Destroy the tooltip window to make it disappear
            self.tip_window.destroy()
        # Reset to None so show_tip can create it again next time
        self.tip_window = None


def open_auto_mode_window(root):
    """
    Opens the automatic measurement window as a child of the main window.
    If the window is already open, brings it to the front instead of
    opening a duplicate. This is controlled by the _auto_window global.
    """
    global _auto_window

    # Check if the window already exists and is still open
    if _auto_window is not None and tk.Toplevel.winfo_exists(_auto_window):
        # Just bring the existing window to the front
        _auto_window.lift()
        return

    # Dictionary to store all measurement data between the measurement
    # and save steps. This acts as shared memory between the inner functions.
    measurement_data = {
        "results": {},       # focal length results per filter (w, r, g, b)
        "images_z1": [],     # list of captured images at position z1
        "images_z2": [],     # list of captured images at position z2
        "tables": {},        # result tables per filter for saving
        "path_base": ""      # base folder path where data will be saved
    }

    # --- Window setup ---
    # Create the window as a child of the main window (Toplevel)
    _auto_window = tk.Toplevel(root)
    _auto_window.title("Automatic Mode - Focal Measurement")

    # Calculate screen dimensions to center the window
    window_width = 1080
    window_height = 600
    screen_width = _auto_window.winfo_screenwidth()
    screen_height = _auto_window.winfo_screenheight()
    # Calculate top left corner position to center the window
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    _auto_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
    _auto_window.resizable(True, True)

    # --- Layout ---
    # The window is divided into two frames:
    # left_frame: contains all controls, inputs, buttons and results
    # right_frame: contains the live camera preview
    left_frame = tk.Frame(_auto_window, bg="#f0f0f0", width=756, height=600)
    left_frame.grid(row=0, column=0, sticky="nsew")

    right_frame = tk.Frame(_auto_window, bg="#ffffff", width=324, height=600)
    right_frame.grid(row=0, column=1, sticky="nsew")

    # Allow both frames to expand when the window is resized
    _auto_window.grid_rowconfigure(0, weight=1)
    # Left frame gets 3x more space than the right frame
    _auto_window.grid_columnconfigure(0, weight=3)
    _auto_window.grid_columnconfigure(1, weight=1)

    # --- Helper to append text to the results area ---
    def append_result(message):
        """
        Appends a message to the results text area.
        The text widget must be temporarily enabled before writing,
        then disabled again to prevent the user from editing it.
        """
        # Enable writing temporarily
        result_text.configure(state='normal')
        # Insert the message at the end of the current text
        result_text.insert(tk.END, message)
        # Disable again to prevent user edits
        result_text.configure(state='disabled')

    # --- Display measurement results ---
    def show_results(local_results):
        """
        Clears the results area and displays the focal length results
        for each filter (white, red, green, blue).
        Called from the main thread after the measurement thread finishes.
        """
        # Enable writing to clear and update the text area
        result_text.configure(state='normal')
        # Clear all previous content
        result_text.delete(1.0, tk.END)

        # Loop through each filter and display its results
        for flt in ['w', 'r', 'g', 'b']:
            # Write the filter header
            result_text.insert(tk.END, f"Filter {flt.upper()}:\n")
            # Get the data dictionary for this filter
            data = local_results.get(flt)

            # If data is missing or not a dictionary, show a placeholder
            if not isinstance(data, dict):
                result_text.insert(tk.END, "  Data not available.\n\n")
                continue

            # Extract the focal length values from the dictionary
            focal = data.get('effective_focal', 0)
            err_focal = data.get('error_effective_focal', 0)
            delta_f = data.get('delta_f', 0)

            # Display the results formatted to 2 decimal places
            result_text.insert(tk.END, f"  Effective focal length: {focal:.2f} ± {err_focal:.2f} mm\n")
            result_text.insert(tk.END, f"  Δf: {delta_f:.2f} mm\n\n")

        # Disable again to prevent user edits
        result_text.configure(state='disabled')

    # --- Start automatic measurement ---
    def start_measurement():
        """
        Reads the z1 and z2 positions from the input fields and starts
        the automatic measurement process in a background thread.
        Running in a background thread prevents the GUI from freezing
        while the measurement is in progress.
        """
        try:
            # Read and convert the input values to floats
            # This will raise ValueError if the input is not a valid number
            z1 = float(entry_z1.get())
            z2 = float(entry_z2.get())

            def task():
                """
                The actual measurement task that runs in the background thread.
                After finishing, it schedules show_results() to run in the
                main thread using after(0), since GUI updates must happen
                in the main thread.
                """
                # Get the currently selected calculation mode (1, 2 or 3)
                mode = mode_var.get()
                # Run the full automatic measurement and unpack all return values
                r, iz1, iz2, t, pb = automatic_measurement(z1, z2, mode)
                # Store all results in the shared dictionary for later saving
                measurement_data["results"] = r
                measurement_data["images_z1"] = iz1
                measurement_data["images_z2"] = iz2
                measurement_data["tables"] = t
                measurement_data["path_base"] = pb
                # Schedule show_results to run in the main thread
                # after(0) means "run as soon as possible in the main thread"
                _auto_window.after(0, lambda: show_results(r))

            # Start the task in a background thread
            # daemon=True means the thread stops if the main program exits
            threading.Thread(target=task, daemon=True).start()

        except ValueError:
            # If z1 or z2 are not valid numbers, show an error message
            result_text.configure(state='normal')
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "Invalid input.\n")
            result_text.configure(state='disabled')

    # --- Save measurement data to disk ---
    def save_data():
        """
        Saves the measurement results, images and tables to disk.
        First checks that a measurement has been run and data is available.
        Then optionally asks the user for a custom folder name.
        """
        # Check that all required data is available before saving
        if (measurement_data["results"]
                and measurement_data["tables"]
                and measurement_data["path_base"]
                and measurement_data["images_z1"] is not None
                and measurement_data["images_z2"] is not None):

            # Ask user for an optional custom folder name
            # If cancelled or left empty, the default path is used
            folder_name = simpledialog.askstring(
                "Save as...", "Enter folder name (optional):", parent=_auto_window
            )

            try:
                # Convert the stored path string to a Path object for easier manipulation
                path_base = Path(measurement_data["path_base"])

                if folder_name and folder_name.strip():
                    # Build a new path using the custom folder name as a sibling of the base path
                    new_path = path_base.parent / folder_name.strip()
                    # Create the folder if it doesn't exist
                    new_path.mkdir(parents=True, exist_ok=True)
                    # Update the stored path to the new custom folder
                    measurement_data["path_base"] = new_path
                else:
                    # No custom name given, keep the original path
                    measurement_data["path_base"] = path_base

                # Read z1 and z2 again for passing to the save function
                z1 = float(entry_z1.get())
                z2 = float(entry_z2.get())

                # Call the save function with all collected data
                save_measurement_data(
                    measurement_data["images_z1"],
                    measurement_data["images_z2"],
                    measurement_data["tables"],
                    measurement_data["path_base"],
                    z1,
                    z2
                )
                # Notify the user that saving was successful
                append_result("\n Data saved successfully.\n")
            except Exception as e:
                # Show the error message if something went wrong
                append_result(f"\n Error saving data: {e}\n")
        else:
            # No measurement has been run yet, nothing to save
            append_result("\n No data to save yet.\n")

    # --- Capture reference image ---
    def capture_with_preview():
        """
        Captures a reference image in a background thread.
        The reference image is used as a baseline for the focal measurement.
        Running in a thread prevents the GUI from freezing during capture.
        """
        def reference_task():
            """Inner function that runs do_reference() in the background."""
            try:
                # Capture the reference image
                do_reference()
            except Exception as e:
                # Show any errors in the results area
                append_result(f"\n Error capturing reference: {e}\n")

        # Start the reference capture in a background thread
        threading.Thread(target=reference_task, daemon=True).start()

    # --- Helper to create a mode radio button with a tooltip help icon ---
    def add_mode_option(parent, text, tooltip_text, value):
        """
        Creates a row containing a radio button and a help icon with a tooltip.
        The radio button lets the user select the calculation mode.
        The help icon shows a description of the mode when hovered.

        Parameters
        ----------
        parent : tk widget
            The parent frame to place the row in.
        text : str
            The label text for the radio button.
        tooltip_text : str
            The description shown in the tooltip when hovering the help icon.
        value : int
            The value assigned to mode_var when this option is selected.
        """
        # Create a horizontal frame to hold both the radio button and help icon
        row = tk.Frame(parent, bg="#f0f0f0")
        row.pack(anchor="w", pady=2)

        # Create the radio button linked to mode_var
        rb = tk.Radiobutton(row, text=text, variable=mode_var, value=value, bg="#f0f0f0")
        rb.pack(side="left")

        # Create the orange help icon label
        help_icon = tk.Label(
            row,
            text="❓",
            fg="white",
            bg="#ff7f50",           # orange background
            font=("Arial", 8, "bold"),
            width=2,
            height=1,
            cursor="question_arrow",# change cursor to question mark on hover
            relief="ridge",
            borderwidth=1
        )
        help_icon.pack(side="left", padx=6)
        # Attach the tooltip to the help icon
        ToolTip(help_icon, tooltip_text)

    # --- Input controls ---
    font_settings = ("Helvetica", 14, "bold")
    # Title label at the top of the left frame
    tk.Label(left_frame, text="Automatic Controls", font=font_settings, bg="#f0f0f0").pack(pady=30)

    # z1 input: the first screen position for the measurement
    tk.Label(left_frame, text="Position z₁ (mm):", font=("Helvetica", 12), bg="#f0f0f0").pack()
    entry_z1 = tk.Entry(left_frame)
    entry_z1.pack(pady=5)

    # z2 input: the second screen position for the measurement
    tk.Label(left_frame, text="Position z₂ (mm):", font=("Helvetica", 12), bg="#f0f0f0").pack()
    entry_z2 = tk.Entry(left_frame)
    entry_z2.pack(pady=5)

    # --- Measurement mode selection ---
    # mode_var stores the currently selected mode (1, 2 or 3)
    # Must be defined before add_mode_option is called
    mode_var = tk.IntVar(value=1)   # default to mode 1

    # Frame to group the mode selection widgets together
    frame_mode = tk.Frame(left_frame, bg="#f0f0f0")
    frame_mode.pack(pady=10)

    tk.Label(frame_mode, text="Calculation Mode:", bg="#f0f0f0", font=("Helvetica", 12, "bold")).pack(anchor="w")

    # Add each mode option as a radio button with a tooltip description
    add_mode_option(frame_mode, "Mode 1",
        "Use this mode when both planes z1 and z2 are between the principal planes "
        "and the focal point. Note: this configuration is also used for negative lenses.", 1)

    add_mode_option(frame_mode, "Mode 2",
        "Use this mode when plane z1 is between the principal planes and the focal point, "
        "and z2 is located after the focal point.", 2)

    add_mode_option(frame_mode, "Mode 3",
        "Use this mode when both planes z1 and z2 are located after the focal point.", 3)

    # --- Action buttons ---
    # All three main action buttons are placed side by side in a frame
    button_frame = tk.Frame(left_frame, bg="#f0f0f0")
    button_frame.pack(pady=30)

    # Button to capture the reference image before starting the measurement
    tk.Button(button_frame, text="Capture Reference", font=("Helvetica", 10, "bold"),
              command=capture_with_preview).pack(side="left", padx=10)

    # Button to start the full automatic measurement process
    tk.Button(button_frame, text="Start Automatic Measurement", font=("Helvetica", 10, "bold"),
              command=start_measurement).pack(side="left", padx=10)

    # Button to save the measurement results and images to disk
    tk.Button(button_frame, text="Save Data", font=("Helvetica", 10, "bold"),
              command=save_data).pack(side="left", padx=10)

    # --- Results area ---
    # Text widget to display measurement results and status messages
    # state='disabled' prevents the user from typing in it
    result_text = tk.Text(left_frame, height=18, width=60, font=("Courier", 10))
    result_text.pack(pady=10)
    result_text.configure(state='disabled')

    # --- Close button ---
    # Destroys the window, resets the global reference, and turns off the camera
    tk.Button(left_frame, text="Close", font=font_settings,
              command=lambda: (_auto_window.destroy(), _reset(), turn_off_camera_auto())).pack(pady=10)

    # --- Live camera view on the right panel ---
    # Black label that will display the live camera feed
    camera_label = tk.Label(right_frame, bg="black")
    # Center the camera label inside the right frame
    camera_label.place(relx=0.5, rely=0.5, anchor="center")
    # Start the live camera feed inside the label
    start_live_view(camera_label)

    # Handle the window X button the same way as the Close button
    # This ensures the camera is released and the global is reset
    _auto_window.protocol("WM_DELETE_WINDOW",
                          lambda: (_auto_window.destroy(), _reset(), turn_off_camera_auto()))


def _reset():
    """
    Resets the global _auto_window reference to None.
    Called when the window is closed so that open_auto_mode_window()
    knows it can open a new window next time it is called.
    """
    global _auto_window
    _auto_window = None