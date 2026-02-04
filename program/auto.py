import tkinter as tk
from tkinter import simpledialog
from camara import start_live_view, turn_off_camera_auto
from focal import automatic_measurement, save_measurement_data, do_reference
import threading
from pathlib import Path

_auto_window = None  # Prevent multiple windows from opening


class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tip_window or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            background="#333333",
            foreground="white",
            relief="solid",
            borderwidth=1,
            justify="left",
            wraplength=220,
            padx=6,
            pady=4,
            font=("Arial", 9)
        )
        label.pack()

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
        self.tip_window = None


def open_auto_mode_window(root):
    global _auto_window
    if _auto_window is not None and tk.Toplevel.winfo_exists(_auto_window):
        _auto_window.lift()
        return

    _auto_window = tk.Toplevel(root)
    _auto_window.title("Automatic Mode - Focal Measurement")
    _auto_window.geometry("1080x600")
    _auto_window.resizable(True, True)

    left_frame = tk.Frame(_auto_window, bg="#f0f0f0", width=756, height=600)
    left_frame.grid(row=0, column=0, sticky="nsew")

    right_frame = tk.Frame(_auto_window, bg="#ffffff", width=324, height=600)
    right_frame.grid(row=0, column=1, sticky="nsew")

    _auto_window.grid_rowconfigure(0, weight=1)
    _auto_window.grid_columnconfigure(0, weight=1)
    _auto_window.grid_columnconfigure(1, weight=1)

    # Input controls
    font_settings = ("Helvetica", 14, "bold")
    tk.Label(left_frame, text="Automatic Controls", font=font_settings, bg="#f0f0f0").pack(pady=30)

    tk.Label(left_frame, text="Position z₁ (mm):", font=("Helvetica", 12), bg="#f0f0f0").pack()
    entry_z1 = tk.Entry(left_frame)
    entry_z1.pack(pady=5)

    tk.Label(left_frame, text="Position z₂ (mm):", font=("Helvetica", 12), bg="#f0f0f0").pack()
    entry_z2 = tk.Entry(left_frame)
    entry_z2.pack(pady=5)

    # Dictionary to store measurement data
    measurement_data = {
        "results": {},
        "images_z1": [],
        "images_z2": [],
        "tables": {},
        "path_base": ""
    }

    # Display results
    def show_results(local_results):
        result_text.configure(state='normal')
        result_text.delete(1.0, tk.END)

        for flt in ['w', 'r', 'g', 'b']:
            result_text.insert(tk.END, f"Filter {flt.upper()}:\n")
            data = local_results.get(flt)

            if not isinstance(data, dict):
                result_text.insert(tk.END, "  ⚠️ Data not available.\n\n")
                continue

            focal = data.get('focal_efectiva', 0)
            err_focal = data.get('error_focal_efectiva', 0)
            delta_f = data.get('delta_f', 0)

            result_text.insert(tk.END, f"   Effective focal length: {focal:.2f} ± {err_focal:.2f} mm\n")
            result_text.insert(tk.END, f"   Δf: {delta_f:.2f} mm\n\n")

        result_text.configure(state='disabled')

    # Start automatic measurement
    def start_measurement():
        try:
            z1 = float(entry_z1.get())
            z2 = float(entry_z2.get())

            def task():
                mode = mode_var.get()  # 1, 2, or 3
                r, iz1, iz2, t, pb = automatic_measurement(z1, z2, mode)
                measurement_data["results"] = r
                measurement_data["images_z1"] = iz1
                measurement_data["images_z2"] = iz2
                measurement_data["tables"] = t
                measurement_data["path_base"] = pb
                _auto_window.after(0, lambda: show_results(r))

            threading.Thread(target=task, daemon=True).start()

        except ValueError:
            result_text.configure(state='normal')
            result_text.delete(1.0, tk.END)
            result_text.insert(tk.END, "⚠️ Invalid input.\n")
            result_text.configure(state='disabled')

    # Save measurement data
    def save_data():
        if (
            measurement_data["results"]
            and measurement_data["tables"]
            and measurement_data["path_base"]
            and measurement_data["images_z1"] is not None
            and measurement_data["images_z2"] is not None
    ):
            folder_name = simpledialog.askstring(
                "Save as...", "Enter folder name (optional):", parent=_auto_window
            )

            try:
                path_base = Path(measurement_data["path_base"])

                if folder_name and folder_name.strip():
                    new_path = path_base.parent / folder_name.strip()
                    new_path.mkdir(parents=True, exist_ok=True)
                    measurement_data["path_base"] = new_path
                else:
                    measurement_data["path_base"] = path_base

                z1 = float(entry_z1.get())
                z2 = float(entry_z2.get())
                
                save_measurement_data(
                    measurement_data["images_z1"],
                    measurement_data["images_z2"],
                    measurement_data["tables"],
                    measurement_data["path_base"],
                    z1,
                    z2
                )
                
                result_text.configure(state='normal')
                result_text.insert(tk.END, "\n Data folder saved successfully.\n")
                result_text.configure(state='disabled')
            except Exception as e:
                result_text.configure(state='normal')
                result_text.insert(tk.END, f"\n Error saving data: {e}\n")
                result_text.configure(state='disabled')
        else:
            result_text.configure(state='normal')
            result_text.insert(tk.END, "\n No data to save yet.\n")
            result_text.configure(state='disabled')

    # Button container
    button_frame = tk.Frame(left_frame, bg="#f0f0f0")
    button_frame.pack(pady=30)

    def capture_with_preview():
        def reference_task():
            try:
                do_reference()
            except Exception as e:
                result_text.configure(state='normal')
                result_text.insert(tk.END, f"\n Error capturing reference: {e}\n")
                result_text.configure(state='disabled')

        threading.Thread(target=reference_task, daemon=True).start()

    # Capture Reference button
    tk.Button(
        button_frame,
        text="Capture Reference",
        font=("Helvetica", 10, "bold"),
        command=capture_with_preview
    ).pack(side="left", padx=10)

    # Measurement mode selection
    mode_var = tk.IntVar(value=1)  # default: mode 1

    frame_mode = tk.Frame(left_frame, bg="#f0f0f0")
    frame_mode.pack(pady=10)

    tk.Label(
        frame_mode, text="Calculation Mode:", bg="#f0f0f0", font=("Helvetica", 12, "bold")
    ).pack(anchor="w")

    # --- Helper to create a mode option with help icon ---
    def add_mode_option(parent, text, tooltip_text, value):
        row = tk.Frame(parent, bg="#f0f0f0")
        row.pack(anchor="w", pady=2)

        rb = tk.Radiobutton(row, text=text, variable=mode_var, value=value, bg="#f0f0f0")
        rb.pack(side="left")

        help_icon = tk.Label(
            row,
            text="❓",
            fg="white",
            bg="#ff7f50",
            font=("Arial", 8, "bold"),
            width=2,
            height=1,
            cursor="question_arrow",
            relief="ridge",
            borderwidth=1
        )
        help_icon.pack(side="left", padx=6)

        ToolTip(help_icon, tooltip_text)

    # Add the 3 modes
    add_mode_option(
        frame_mode,
        "Mode 1",
        "Use this mode when both planes z1 and z2 are between the principal planes "
        "and the focal point. Note: this configuration is also used for negative lenses.",
        1
    )

    add_mode_option(
        frame_mode,
        "Mode 2",
        "Use this mode when plane z1 is between the principal planes and the focal point, "
        "and z2 is located after the focal point.",
        2
    )

    add_mode_option(
        frame_mode,
        "Mode 3",
        "Use this mode when both planes z1 and z2 are located after the focal point.",
        3
    )

    # Start Automatic Measurement button
    tk.Button(
        button_frame,
        text="Start Automatic Measurement",
        font=("Helvetica", 10, "bold"),
        command=start_measurement
    ).pack(side="left", padx=10)

    # Save Data button
    tk.Button(
        button_frame,
        text="Save Data",
        font=("Helvetica", 10, "bold"),
        command=save_data
    ).pack(side="left", padx=10)

    # Results area
    result_text = tk.Text(left_frame, height=18, width=60, font=("Courier", 10))
    result_text.pack(pady=10)
    result_text.configure(state='disabled')

    # Close button
    tk.Button(
        left_frame,
        text="Close",
        font=font_settings,
        command=lambda: (_auto_window.destroy(), _reset(), turn_off_camera_auto())
    ).pack(pady=10)

    # Live camera view
    camera_label = tk.Label(right_frame, bg="black")
    camera_label.place(relx=0.5, rely=0.5, anchor="center")
    start_live_view(camera_label)

    _auto_window.protocol("WM_DELETE_WINDOW", lambda: (_auto_window.destroy(), _reset(), turn_off_camera_auto()))


def _reset():
    global _auto_window
    _auto_window = None
