#!/usr/bin/python3
import tkinter as tk
from tkinter import ttk, messagebox
from sense_hat import SenseHat
import threading
import time
import math

# Initialize Sense HAT
sense = SenseHat()
sense.clear()

# Ballistic calculation functions
def atmosphere_correction(bc, temp_c, humidity, pressure_inhg):
    """Adjust ballistic coefficient for environmental conditions."""
    # Standard conditions: 59°F (15°C), 0% humidity, 29.92 inHg
    temp_k = temp_c + 273.15
    std_temp_k = 15 + 273.15
    # Air density calculation
    pressure_pa = pressure_inhg * 3386.39  # Convert inHg to Pa
    air_density = (pressure_pa / (287.05 * temp_k)) * (1 - 0.0065 * temp_c / 288.15) ** 4.255
    std_air_density = (101325 / (287.05 * std_temp_k)) * (1 - 0.0065 * 15 / 288.15) ** 4.255
    density_factor = std_air_density / air_density
    humidity_factor = 1 - (humidity / 100) * 0.02  # Humidity reduces air density slightly
    corrected_bc = bc * density_factor * humidity_factor
    return corrected_bc

def calculate_cant_adjustment(cant_deg, range_yards):
    """Calculate bullet impact shift due to rifle cant."""
    range_m = range_yards * 0.9144
    g = 9.81
    # Simplified cant effect: lateral and vertical shift
    cant_rad = math.radians(cant_deg)
    vertical_shift_m = range_m * math.sin(cant_rad) * math.cos(cant_rad) * g / 9.81
    lateral_shift_m = range_m * math.sin(cant_rad) ** 2
    return vertical_shift_m * 39.3701, lateral_shift_m * 39.3701  # Convert to inches

def calculate_trajectory(velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, temp_c, humidity, pressure_inhg, target_angle_deg, drag_model, cant_deg):
    """Calculate bullet drop, velocity, and scope adjustments at range."""
    # Convert inputs
    velocity = velocity_fps * 0.3048  # Convert fps to m/s
    range_m = range_yards * 0.9144  # Convert yards to meters
    zero_range_m = zero_range_yards * 0.9144
    bullet_mass = bullet_weight_grains / 7000 * 0.453592  # Convert grains to kg
    bullet_area = 0.000506707  # Approx. cross-sectional area for .308 bullet (m^2)
    target_angle_rad = math.radians(target_angle_deg)

    # Adjust BC for environment
    corrected_bc = atmosphere_correction(bc, temp_c, pressure_inhg)

    # Drag model coefficients
    drag_coeff = 0.5 if drag_model == "G1" else 0.25  # G7 has lower drag
    air_density = (pressure_inhg * 3386.39) / (287.05 * (temp_c + 273.15))

    # Time of flight (simplified, iterative for drag)
    time_of_flight = range_m / velocity
    for _ in range(3):  # Iterative refinement
        avg_velocity = velocity * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
        time_of_flight = range_m / (velocity + avg_velocity) * 2

    # Velocity at range
    velocity_at_range = velocity * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
    velocity_at_range_fps = velocity_at_range / 0.3048

    # Bullet drop with angle adjustment
    g = 9.81
    drop_m = (0.5 * g * time_of_flight ** 2) * math.cos(target_angle_rad)  # Adjust for angle
    zero_angle = math.atan2(drop_m, zero_range_m)
    adjusted_drop_m = drop_m - range_m * math.tan(zero_angle)
    drop_in = adjusted_drop_m * 39.3701

    # Cant adjustment
    cant_vertical_in, cant_lateral_in = calculate_cant_adjustment(cant_deg, range_yards)
    total_drop_in = drop_in + cant_vertical_in

    # Scope adjustments
    moa_adjustment = (total_drop_in / (range_yards / 100)) / 1.047  # MOA per 100 yards
    mrad_adjustment = (total_drop_in / (range_yards / 100)) / 3.6  # MRAD per 100 yards
    lateral_moa = (cant_lateral_in / (range_yards / 100)) / 1.047
    lateral_mrad = (cant_lateral_in / (range_yards / 100)) / 3.6

    return drop_in, velocity_at_range_fps, moa_adjustment, mrad_adjustment, cant_lateral_in, lateral_moa, lateral_mrad

# GUI Application
class BallisticCalculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Ballistic Calculator")
        self.geometry("800x480")
        self.attributes("-fullscreen", False)
        self.sense = sense
        self.running = True

        # Variables
        self.velocity_var = tk.StringVar(value="3000")
        self.bc_var = tk.StringVar(value="0.45")
        self.bullet_weight_var = tk.StringVar(value="150")
        self.range_var = tk.StringVar(value="100")
        self.zero_range_var = tk.StringVar(value="100")
        self.target_size_var = tk.StringVar(value="10")
        self.target_angle_var = tk.StringVar(value="0")
        self.temp_var = tk.StringVar(value="N/A")
        self.humidity_var = tk.StringVar(value="N/A")
        self.pressure_var = tk.StringVar(value="N/A")
        self.cant_var = tk.StringVar(value="N/A")
        self.drop_var = tk.StringVar(value="0.00")
        self.velocity_at_range_var = tk.StringVar(value="0.00")
        self.moa_var = tk.StringVar(value="0.00")
        self.mrad_var = tk.StringVar(value="0.00")
        self.lateral_moa_var = tk.StringVar(value="0.00")
        self.lateral_mrad_var = tk.StringVar(value="0.00")
        self.drag_model_var = tk.StringVar(value="G1")

        # GUI Layout
        self.create_widgets()

        # Start sensor polling thread
        self.sensor_thread = threading.Thread(target=self.poll_sensors, daemon=True)
        self.sensor_thread.start()

    def create_widgets(self):
        main_frame = ttk.Frame(self, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Input fields
        ttk.Label(main_frame, text="Muzzle Velocity (fps):").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.velocity_var).grid(row=0, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Ballistic Coefficient:").grid(row=1, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.bc_var).grid(row=1, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Bullet Weight (grains):").grid(row=2, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.bullet_weight_var).grid(row=2, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Range (yards):").grid(row=3, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.range_var).grid(row=3, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Zero Range (yards):").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.zero_range_var).grid(row=4, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Target Size (inches):").grid(row=5, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.target_size_var).grid(row=5, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Target Angle (deg):").grid(row=6, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.target_angle_var).grid(row=6, column=1, sticky=(tk.W, tk.E))

        # Drag model toggle
        ttk.Label(main_frame, text="Drag Model:").grid(row=7, column=0, sticky=tk.W)
        ttk.Radiobutton(main_frame, text="G1", variable=self.drag_model_var, value="G1").grid(row=7, column=1, sticky=tk.W)
        ttk.Radiobutton(main_frame, text="G7", variable=self.drag_model_var, value="G7").grid(row=7, column=1, sticky=tk.E)

        # Sensor fields (read-only)
        ttk.Label(main_frame, text="Temperature (°C):").grid(row=8, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.temp_var).grid(row=8, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Humidity (%):").grid(row=9, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.humidity_var).grid(row=9, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Pressure (inHg):").grid(row=10, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.pressure_var).grid(row=10, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Rifle Cant (deg):").grid(row=11, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.cant_var).grid(row=11, column=1, sticky=tk.W)

        # Output fields
        ttk.Label(main_frame, text="Bullet Drop (inches):").grid(row=12, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.drop_var).grid(row=12, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Velocity at Range (fps):").grid(row=13, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.velocity_at_range_var).grid(row=13, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Elevation Adjustment (MOA):").grid(row=14, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.moa_var).grid(row=14, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Elevation Adjustment (MRAD):").grid(row=15, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.mrad_var).grid(row=15, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Windage Adjustment (MOA):").grid(row=16, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.lateral_moa_var).grid(row=16, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Windage Adjustment (MRAD):").grid(row=17, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.lateral_mrad_var).grid(row=17, column=1, sticky=tk.W)

        # Calculate button
        ttk.Button(main_frame, text="Calculate", command=self.calculate).grid(row=18, column=0, columnspan=2, pady=10)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        for i in range(19):
            main_frame.rowconfigure(i, weight=1)

    def poll_sensors(self):
        """Continuously poll Sense HAT sensors and update GUI."""
        while self.running:
            try:
                temp_c = self.sense.get_temperature()
                humidity = self.sense.get_humidity()
                pressure_mb = self.sense.get_pressure()
                pressure_inhg = pressure_mb * 0.02953  # Convert mbar to inHg
                # Get gyroscope data (pitch for cant)
                gyro = self.sense.get_gyroscope()
                cant_deg = gyro['pitch'] if abs(gyro['pitch']) < 45 else 0  # Limit to reasonable cant
                self.temp_var.set(f"{temp_c:.1f}")
                self.humidity_var.set(f"{humidity:.1f}")
                self.pressure_var.set(f"{pressure_inhg:.2f}")
                self.cant_var.set(f"{cant_deg:.1f}")
            except Exception as e:
                self.temp_var.set("Error")
                self.humidity_var.set("Error")
                self.pressure_var.set("Error")
                self.cant_var.set("Error")
                print(f"Sensor error: {e}")
            time.sleep(2)

    def calculate(self):
        """Perform ballistic calculation based on inputs."""
        try:
            velocity = float(self.velocity_var.get())
            bc = float(self.bc_var.get())
            bullet_weight = float(self.bullet_weight_var.get())
            range_yards = float(self.range_var.get())
            zero_range_yards = float(self.zero_range_var.get())
            target_size = float(self.target_size_var.get())
            target_angle = float(self.target_angle_var.get())
            temp_c = float(self.temp_var.get()) if self.temp_var.get() != "Error" else 15.0
            humidity = float(self.humidity_var.get()) if self.humidity_var.get() != "Error" else 0.0
            pressure_inhg = float(self.pressure_var.get()) if self.pressure_var.get() != "Error" else 29.92
            cant_deg = float(self.cant_var.get()) if self.cant_var.get() != "Error" else 0.0
            drag_model = self.drag_model_var.get()

            if velocity <= 0 or bc <= 0 or bullet_weight <= 0 or range_yards < 0 or zero_range_yards <= 0 or target_size <= 0:
                raise ValueError("Inputs must be positive numbers (except range and angles).")

            drop, velocity_at_range, moa, mrad, cant_lateral, lateral_moa, lateral_mrad = calculate_trajectory(
                velocity, bc, bullet_weight, range_yards, zero_range_yards, temp_c, humidity, pressure_inhg, target_angle, drag_model, cant_deg
            )
            self.drop_var.set(f"{drop:.2f}")
            self.velocity_at_range_var.set(f"{velocity_at_range:.2f}")
            self.moa_var.set(f"{moa:.2f}")
            self.mrad_var.set(f"{mrad:.2f}")
            self.lateral_moa_var.set(f"{lateral_moa:.2f}")
            self.lateral_mrad_var.set(f"{lateral_mrad:.2f}")

            # Validate target size
            if abs(drop) > target_size:
                messagebox.showwarning("Target Warning", f"Bullet drop ({abs(drop):.2f} in) exceeds target size ({target_size:.2f} in).")
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))

    def destroy(self):
        """Clean up on exit."""
        self.running = False
        self.sense.clear()
        super().destroy()

# Run the application
if __name__ == "__main__":
    try:
        app = BallisticCalculator()
        app.mainloop()
    except KeyboardInterrupt:
        app.destroy()