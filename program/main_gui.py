import tkinter as tk
from tkinter import filedialog
from tkinter import ttk, messagebox
from PIL import Image, ImageTk

from controller import (
    move_left, move_right, stop_motor, set_speed, move_motor, move_to_position,
    activate_filter, led_on, led_off, led_intensity
)
from communication import (
    send_command, read_current_position, arduino, refresh_ports, connect_arduino
)
from camara import (
    toggle_camera, take_photo, save_current_photo,
    toggle_recording, update_photo_display, refresh_cameras
)
from auto import open_auto_mode_window
import camara
from utils import resource_path

def abrir_ventana_conexion():
    """
    Opens a small window to select and connect both:
      - Arduino COM port
      - Camera device
    Once connected, it opens the main interface.
    """

    win = tk.Tk()
    win.title("Device Connection")

    # Tamaño de la ventana
    window_width = 350
    window_height = 200

    # Dimensioines de la pantalla
    screen_width = win.winfo_screenwidth()
    screen_height = win.winfo_screenheight()

    # Posicision de la ventana 

    center_x = (screen_width // 2) - (window_width // 2)
    center_y = (screen_height // 2) - (window_height // 2)

    win.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")
    
    # Ventana no redimensionable
    win.resizable(False, False)

    # --- COM Port Selection ---
    tk.Label(win, text="Select COM Port:", font=("Helvetica", 12)).pack(pady=5)
    port_combo = ttk.Combobox(win, width=30, state="readonly")
    port_combo.pack(pady=5)

    # --- Camera Selection ---
    tk.Label(win, text="Select Camera:", font=("Helvetica", 12)).pack(pady=5)
    camera_combo = ttk.Combobox(win, width=30, state="readonly")
    camera_combo.pack(pady=5)

    # --- Refresh available ports ---
    def refresh():
        ports = refresh_ports()
        port_combo['values'] = ports
        port_combo.set("")
            
        # Refresh cameras
        cameras = refresh_cameras()
        camera_combo['values'] = cameras
        camera_combo.set("")

    # --- Connect both Arduino and Camera ---
    def connect():
        selected_port = port_combo.get()
        selected_camera = camera_combo.get()

        if not selected_port:
            messagebox.showwarning("No Port", "Please select a COM port.")
            return
        if not selected_camera:
            messagebox.showwarning("No Camera", "Please select a camera.")
            return


        cameras = refresh_cameras()
        try:
            cam_index = cameras.index(selected_camera)
        except ValueError:
            cam_index = 0 

        camara.set_camera_index(cam_index)

        # Try to connect Arduino
        if connect_arduino(selected_port):
            win.destroy()
            iniciar_interfaz()
        else:
            messagebox.showerror("Connection Error", "Failed to connect to Arduino.")

    # --- Buttons ---
    tk.Button(win, text="Connect", command=connect).pack(pady=5)
    tk.Button(win, text="Refresh", command=refresh).pack(pady=5)

    refresh()  # Load ports when window opens
    win.mainloop()


def seleccionar_filtro(filtro, boton, todos_los_botones):
    color = activate_filter(filtro)
    for b in todos_los_botones:
        b.config(bg="SystemButtonFace")
    boton.config(bg=color)

def iniciar_interfaz():
    
    root = tk.Tk()
    root.title("Slidebench Control")

    window_width = 1200
    window_height = 700
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (window_width // 2)
    y = (screen_height // 2) - (window_height // 2)
    root.geometry(f"{window_width}x{window_height}+{x}+{y}")

    font_settings = ("Helvetica", 12, "bold")
    
    image_default = resource_path("resources\\image.png")
    image1_default = resource_path("resources\\image1.png")

    no_camera_img = Image.open(image_default).resize((400, 400))
    no_photo_img = Image.open(image1_default).resize((400, 400))
    no_camera_tk = ImageTk.PhotoImage(no_camera_img)
    no_photo_tk = ImageTk.PhotoImage(no_photo_img)

    canvas = tk.Canvas(root)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)

    main_frame = tk.Frame(canvas)
    
    def resize_frame(event):
        canvas.itemconfig(main_window, width=event.width)

    main_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")

    canvas.bind("<Configure>", resize_frame)

    def on_configure(event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    main_frame.bind("<Configure>", on_configure)
    canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    main_frame.columnconfigure(0, weight=1)
    main_frame.columnconfigure(1, weight=2)
    main_frame.columnconfigure(2, weight=1)

    # --- [MOTOR CONTROL] ---
    motor_frame = tk.LabelFrame(main_frame, text="Device Control", font=font_settings, padx=10, pady=10)
    motor_frame.grid(row=0, column=0, sticky="n", padx=10, pady=10)

    btn_left = tk.Button(motor_frame, text="◀ Back (Left)", font=("Arial", 14))
    btn_right = tk.Button(motor_frame, text="▶ Forward (Right)", font=("Arial", 14))
    btn_left.bind("<ButtonPress>", move_left)
    btn_left.bind("<ButtonRelease>", stop_motor)
    btn_right.bind("<ButtonPress>", move_right)
    btn_right.bind("<ButtonRelease>", stop_motor)
    btn_left.grid(row=0, column=0, padx=5, pady=5)
    btn_right.grid(row=0, column=1, padx=5, pady=5)

    tk.Label(motor_frame, text="Speed:", font=font_settings).grid(row=1, column=0, columnspan=2)
    speed_slider = tk.Scale(motor_frame, from_=1, to=10, orient=tk.HORIZONTAL, length=300, tickinterval=1, command=set_speed)
    speed_slider.set(5)
    speed_slider.grid(row=2, column=0, columnspan=2, padx=5, pady=5)

    tk.Label(motor_frame, text="Distance to move (mm):", font=font_settings).grid(row=3, column=0, columnspan=2)
    mm_entry = tk.Entry(motor_frame, width=15)
    mm_entry.grid(row=4, column=0, columnspan=2, pady=5)

    direction = tk.StringVar(value="f")
    radio_frame = tk.Frame(motor_frame)
    radio_frame.grid(row=5, column=0, columnspan=2)
    tk.Radiobutton(radio_frame, text="Forward", variable=direction, value="f", font=font_settings).pack(side="left")
    tk.Radiobutton(radio_frame, text="Backward", variable=direction, value="b", font=font_settings).pack(side="left")
    
    mm_entry.bind("<Return>", lambda event: [move_motor(mm_entry.get(), direction.get()), mm_entry.master.focus_set()])
    btn_move = tk.Button(motor_frame, 
                         text="Move", 
                         width=20, 
                         height=2, 
                         command=lambda: [move_motor(mm_entry.get(), direction.get()), mm_entry.master.focus_set()])

    btn_move.grid(row=6, column=0, columnspan=2, pady=10)


    # --- [GO TO ABSOLUTE POSITION] ---
    tk.Label(motor_frame, text="Go to position (mm):", font=font_settings).grid(row=7, column=0, columnspan=2)
    go_entry = tk.Entry(motor_frame, width=15)
    go_entry.grid(row=8, column=0, columnspan=2, pady=5)
    
    go_entry.bind("<Return>", lambda event: [move_to_position(go_entry.get()), go_entry.master.focus_set()])
    btn_go = tk.Button(motor_frame, 
                       text="Go", 
                       width=20, 
                       command=lambda: [move_to_position(go_entry.get()), go_entry.master.focus_set()])
    
    btn_go.grid(row=9, column=0, columnspan=2, pady=5)
    
    # --- [POSICIÓN ACTUAL EN mm: VISOR DIGITAL] ---
    posicion_display = tk.Label(
        motor_frame,
        text="000.00 mm",
        font=("Courier", 20, "bold"),  
        fg="#FF3C3C",     
        bg="#1A1A1A",     
        width=10,
        relief="sunken",
        bd=6
    )
    posicion_display.grid(row=10, column=0, columnspan=2, pady=(10, 5))
    
    # --- [LED CONTROL] ---
    tk.Label(motor_frame, text="Light Source Control", font=font_settings).grid(row=11, column=0, columnspan=2, pady=(10, 0))

    default_btn_color = root.cget("bg")

    def toggle_light(state):
        if state == "on":
            led_on()
            intensidad_actual = led_slider.get()
            led_intensity(intensidad_actual)
            btn_light_on.config(bg="#BCBCBC", fg="black")
            btn_light_off.config(bg=default_btn_color, fg="black")
        elif state == "off":
            led_off()
            btn_light_off.config(bg="#BCBCBC", fg="black")
            btn_light_on.config(bg=default_btn_color, fg="black")


    btn_light_on = tk.Button(motor_frame, text="Turn On", width=15, command=lambda: toggle_light("on"))
    btn_light_off = tk.Button(motor_frame, text="Turn Off", width=15, command=lambda: toggle_light("off"))

    btn_light_on.grid(row=12, column=0, pady=5)
    btn_light_off.grid(row=12, column=1, pady=5)

    tk.Label(motor_frame, text="Intensity:", font=font_settings).grid(row=13, column=0, columnspan=2)
    led_slider = tk.Scale(motor_frame, from_=1, to=10, orient=tk.HORIZONTAL, length=300, tickinterval=1,
                        command=lambda val: send_command(f"led{val}"))
    led_slider.set(5)
    led_slider.grid(row=14, column=0, columnspan=2, padx=5, pady=5)


    # --- [FILTER CONTROL] ---
    tk.Label(motor_frame, text="Filters", font=font_settings).grid(row=15, column=0, columnspan=2, pady=(10, 5))
    filter_frame = tk.Frame(motor_frame)
    filter_frame.grid(row=16, column=0, columnspan=2)
    filtros = [("Red", "r"), ("Green", "g"), ("Blue", "b"), ("White", "w")]
    botones_filtro = []
    for nombre, clave in filtros:
        btn = tk.Button(filter_frame, text=nombre, width=10)
        btn.config(command=lambda c=clave, b=btn: seleccionar_filtro(c, b, botones_filtro))
        btn.pack(side="left", padx=5)
        botones_filtro.append(btn)
        
    # --- [OTHER WINDOW] ---        
    btn_modo_auto = tk.Button(motor_frame, text="Automatic Mode", width=20, height=2, command=lambda: open_auto_mode_window(root))
    btn_modo_auto.grid(row=18, column=0, columnspan=2, pady=10)

    # --- [CAMERA CONTROLS] ---
    btns_frame = tk.LabelFrame(main_frame, text="Camera Controls", font=font_settings, padx=10, pady=10)
    btns_frame.grid(row=0, column=1, sticky="n", padx=10, pady=10)
    btn_toggle_camera = tk.Button(btns_frame, text="Activate Camera", width=20, height=2)
    btn_toggle_camera.grid(row=0, column=0, padx=5, pady=5)
    btn_photo = tk.Button(btns_frame, text="Capture Image", width=20, height=2)
    btn_photo.grid(row=1, column=0, padx=5, pady=5)
    btn_record = tk.Button(btns_frame, text="Start/Stop Recording", width=20, height=2)
    btn_record.grid(row=2, column=0, padx=5, pady=5)
    btn_folder = tk.Button(btns_frame, text="Select Folder", width=20, height=2,
                           command=lambda: filedialog.askdirectory())
    btn_folder.grid(row=3, column=0, padx=5, pady=5)
    btn_show_photo = tk.Button(btns_frame, text="Open Image", width=20, height=2,
                               command=lambda: update_photo_display(last_photo_label, filedialog.askopenfilename(
                                   title='Select Image', filetypes=[('Image files', '*.jpg *.jpeg *.png *.bmp')])))
    btn_show_photo.grid(row=4, column=0, padx=5, pady=5)
    btn_save_photo = tk.Button(btns_frame, text="Save Photo", width=20, height=2,
                               command=lambda: save_current_photo(btn_save_photo))
    btn_save_photo.grid(row=5, column=0, padx=5, pady=5)
    btn_save_photo.grid_remove()

    
    btn_test = tk.Button(btns_frame, text="Test Button", width=20, height=2,
                     command=lambda: print("Test button clicked"))
    btn_test.grid(row=8, column=0, padx=5, pady=(50,0))
    
    # --- Cargar imagen ---
    img_path = resource_path("resources\\points.png")
    img = Image.open(img_path).resize((200, 200))    # Ruta de la imagen Tamaño deseado (ancho, alto) en píxeles
    photo = ImageTk.PhotoImage(img) # Convertir para Tkinter

    # --- Crear Label para mostrarla ---
    img_label = tk.Label(btns_frame, image=photo)
    img_label.grid(row=9, column=0, pady=10)  # Coloca debajo del último botón
    img_label.image = photo  # IMPORTANTE: mantener referencia para que no desaparezca
    
    
    
    
    

    # --- [CAMERA VIEW] ---
    camera_frame = tk.LabelFrame(main_frame, text="Live Camera View", font=font_settings, padx=10, pady=10)
    camera_frame.grid(row=0, column=2, sticky="n", padx=10, pady=10)
    camera_frame.columnconfigure(0, weight=1)
    camera_label = tk.Label(camera_frame, image=no_camera_tk, bd=2, relief="groove", bg="black")
    camera_label.grid(row=0, column=0, padx=1, pady=1)
    last_photo_label = tk.Label(camera_frame, image=no_photo_tk, bd=2, relief="groove", bg="black")
    last_photo_label.grid(row=1, column=0, padx=5, pady=10)

    btn_toggle_camera.config(command=lambda: toggle_camera(camera_label, btn_toggle_camera))
    btn_photo.config(command=lambda: take_photo(camera_label, last_photo_label, btn_save_photo))
    btn_record.config(command=lambda: toggle_recording(btn_record))

    def on_closing():
        led_off()
        
        from camara import cap, recording, video_writer
        if cap: cap.release()
        if recording and video_writer: video_writer.release()
        
        if arduino and arduino.is_open: arduino.close()
        root.destroy()

        
    def actualizar_posicion():
        mm = read_current_position()
        if mm is not None:
            posicion_display.config(text=f"{mm:.2f} mm") 
        root.after(50, actualizar_posicion)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    actualizar_posicion()
    root.mainloop()