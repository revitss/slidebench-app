# SlideBench
 
**SlideBench** is an open-source device and software application for measuring the focal length of lenses and lens systems. It was developed as a Bachelor of Science in Physics degree project at the **Physics Department of the National University of Colombia**, within the **Applied Optics Group** led by Professor **Yobani Mejía Barbosa**.
 
The measurement method is based on the scientific article:
 
> Y. Mejía, *"Improvement in the measurement of focal length using spot patterns and spherical aberration"*, Applied Optics, vol. 52, no. 23, pp. 5577–5584, 2013.
> [https://opg.optica.org/ao/abstract.cfm?uri=ao-52-23-5577](https://opg.optica.org/ao/abstract.cfm?uri=ao-52-23-5577)
 
---
 
## What does SlideBench do?
 
SlideBench measures the **effective focal length** of a lens or system of lenses using a novel optical method based on spot patterns. It can also determine whether a lens is **achromatic** by computing the focal length independently for red, green and blue light using optical filters.
 
The device consists of a motorized screen that moves along an optical axis, a USB camera that captures images of the spot pattern at different positions, and an Arduino that controls the motor and LED light source. The SlideBench software controls the entire measurement process automatically, processes the captured images, and computes the focal length with its associated uncertainty.
 
---
 
## Hardware Requirements
 
To use SlideBench you will need the following hardware:
 
- **Laptop or desktop computer** running Windows (Mac and Linux support coming soon)
- **Arduino Uno** — microcontroller that controls the motor and LED
- **Stepper motor NEMA 17** — moves the screen along the optical axis
- **Motor driver DRV8825** — drives the stepper motor from the Arduino
- **Servomotor** — controls the optical filter wheel
- **LED light source** — illuminates the spot pattern screen
- **USB camera** — captures images of the spot pattern
- A circuit diagram of the device is available in the repository in the `stepper/` folder
 
---

## Arduino Code

The Arduino sketch that controls the motor, LED and filter wheel is available 
in the `stepper/` folder of this repository. You will need to flash it to your 
Arduino Uno before using the device.

To flash the sketch:
1. Download and install the [Arduino IDE](https://www.arduino.cc/en/software)
2. Open the sketch file from the `stepper/` folder
3. Connect your Arduino Uno via USB
4. Select the correct port in the Arduino IDE
5. Click **Upload**

---
 
## How to Install and Run
 
### Option 1 — Run the executable (recommended for most users)
 
> No Python installation required.
 
1. Download `SlideBench.exe` from the [Releases](https://github.com/revitss/slidebench-app/releases/tag/v1.0.0) page
2. Place it in a folder of your choice
3. Connect the Arduino and camera to your computer
4. Double click `SlideBench.exe` to launch the application
5. The `media/` and `data/` folders will be created automatically next to the exe on first run
 
> **Note:** Windows may show a SmartScreen warning the first time you run the exe. Click **"More info" → "Run anyway"** to proceed. This is normal for unsigned executables.
 
---
 
### Option 2 — Run from source code (recommended for developers)
 
If you want to explore, modify or contribute to the code, follow these steps:
 
**1. Clone the repository**
```bash
git clone https://github.com/revitss/slidebench.git
cd slidebench
```
 
**2. Create and activate a virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # Mac/Linux
```
 
**3. Install dependencies**
```bash
pip install -r requirements.txt
```
 
**4. Run the application**
```bash
cd program
python main.py
```
 
---
 
## How to Use the GUI
 
SlideBench has two main interfaces:
 
### Main Interface
The main window is divided into three sections:
 
- **Device Control (left)** — controls for manual motor movement, absolute positioning, speed, LED intensity and optical filter selection. Also contains the button to open the Automatic Mode window.
- **Camera Controls (center)** — buttons to activate the live camera feed, capture images, record video, select a save folder, and run a quick distance measurement on the spot pattern.
- **Live Camera View (right)** — displays the live camera feed and the last captured photo.
 
> Screenshots coming soon.
 
### Automatic Measurement Mode
The automatic measurement window allows you to run a full focal length measurement automatically. You enter the two screen positions (z₁ and z₂ in mm), select the calculation mode that matches your optical setup, capture a reference image, and start the measurement. Results are displayed for each filter (white, red, green, blue) and can be saved to an Excel file.
 
> Screenshots coming soon.
 
---
 
## How the Code is Organized
 
The application is divided into the following modules inside the `program/` folder:
 
| File | Description |
|------|-------------|
| `main.py` | Entry point — launches the application |
| `main_gui.py` | Main GUI window — connection dialog and main interface |
| `automatic_gui.py` | Automatic measurement window |
| `camera_functions.py` | Camera control, image capture, video recording |
| `controller.py` | Motor, LED and filter control commands |
| `communication.py` | Arduino serial communication |
| `focal_measurements.py` | Image processing and focal length computation |
| `utils.py` | Path utilities and mm/steps conversion |
 
The `program/resources/` folder contains images and configuration files used by the GUI.
 
---
 
## How to Cite
 
If you use SlideBench in your research or academic work, please cite both the original method and this software:
 
**Original method:**
> Y. Mejía, *"Improvement in the measurement of focal length using spot patterns and spherical aberration"*, Applied Optics, vol. 52, no. 23, pp. 5577–5584, 2013.
> DOI: [10.1364/AO.52.005577](https://doi.org/10.1364/AO.52.005577)
 
**This software:**
> Kevin Perez and Y. Mejía Barbosa, *SlideBench — Focal Length Measurement Software*, National University of Colombia, Physics Department, Applied Optics Group, 2025.
> Available at: https://github.com/revitss/slidebench-app
 
---
 
## Credits
 
- **Yobani Mejía Barbosa** — Professor and researcher, Applied Optics Group, Physics Department, National University of Colombia. Author of the focal length measurement method.
- **Kevin Perez** — Developer of the SlideBench device and software, as part of a Bachelor of Science in Physics degree project at the National University of Colombia.
 
---
 
## License
 
This project does not currently have a license. Please contact the authors before using this software for commercial purposes.
 
---
 
## Contact
 
For questions or collaborations, please contact the Applied Optics Group at the Physics Department of the National University of Colombia.

- **Yobani Mejía Barbosa** — ymejiab@unal.edu.co
- **Kevin Perez** — keperez@unal.edu.co
