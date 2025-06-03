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

def calculate_wind_drift(wind_speed_mph, wind_direction_deg, time_of_flight, range_yards):
    """Calculate lateral drift due to wind."""
    wind_speed_ms = wind_speed_mph * 0.44704  # Convert mph to m/s
    crosswind = wind_speed_ms * math.sin(math.radians(wind_direction_deg))
    drift_m = crosswind * time_of_flight
    drift_in = drift_m * 39.3701  # Convert to inches
    moa = (drift_in / (range_yards / 100)) / 1.047
    mrad = (drift_in / (range_yards / 100)) / 3.6
    return drift_in, moa, mrad

def calculate_trajectory(velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, scope_height_in, temp_c, humidity, pressure_inhg, target_angle_deg, drag_model, wind_speed_mph, wind_direction_deg):
    """Calculate bullet drop, velocity, and scope adjustments at range."""
    # Convert inputs
    velocity = velocity_fps * 0.3048  # Convert fps to m/s
    range_m = range_yards * 0.9144  # Convert yards to meters
    zero_range_m = zero_range_yards * 0.9144
    scope_height_m = scope_height_in * 0.0254  # Convert inches to meters
    bullet_mass = bullet_weight_grains / 7000 * 0.453592  # Convert grains to kg
    bullet_area = 0.000506707  # Approx. cross-sectional area for .308 bullet (m^2)
    target_angle_rad = math.radians(target_angle_deg)

    # Adjust BC for environment
    corrected_bc = atmosphere_correction(bc, temp_c, pressure_inhg)

    # Drag model coefficients
    drag_coeff = 0.5 if drag_model == "G1" else 0.25  # G7 has lower drag
    air_density = (pressure_inhg * 3386.39) / (287.05 * (temp_c + 273.15))

    # Time of flight (simplified)
    time_of_flight = range_m / velocity  # Initial estimate
    velocity_at_range = velocity * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
    time_of_flight = range_m / ((velocity + velocity_at_range) / 2)  # Refine with average velocity

    # Velocity at range
    velocity_at_range_fps = velocity_at_range / 0.3048

    # Bullet drop with angle and scope height adjustment
    g = 9.81
    drop_m = (0.5 * g * time_of_flight ** 2) * math.cos(target_angle_rad)
    zero_angle = math.atan2(drop_m + scope_height_m, zero_range_m)
    adjusted_drop_m = drop_m - range_m * math.tan(zero_angle) + scope_height_m
    drop_in = adjusted_drop_m * 39.3701

    # Scope adjustments
    moa_adjustment = (drop_in / (range_yards / 100)) / 1.047
    mrad_adjustment = (drop_in / (range_yards / 100)) / 3.6

    # Wind drift
    wind_drift_in, wind_moa, wind_mrad = calculate_wind_drift(wind_speed_mph, wind_direction_deg, time_of_flight, range_yards)

    return drop_in, velocity_at_range_fps, moa_adjustment, mrad_adjustment, wind_drift_in, wind_moa, wind_mrad

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
        self.scope_height_var = tk.StringVar(value="1.5")
        self.wind_speed_var = tk.StringVar(value="10")
        self.wind_direction_var = tk.StringVar(value="90")
        self.barrel_twist_var = tk.StringVar(value="10")
        self.target_size_var = tk.StringVar(value="10")
        self.target_angle_var = tk.StringVar(value="0")
        self.temp_var = tk.StringVar(value="N/A")
        self.humidity_var = tk.StringVar(value="N/A")
        self.pressure_var = tk.StringVar(value="N/A")
        self.drop_var = tk.StringVar(value="0.00")
        self.velocity_at_range_var = tk.StringVar(value="0.00")
        self.moa_var = tk.StringVar(value="0.00")
        self.mrad_var = tk.StringVar(value="0.00")
        self.wind_moa_var = tk.StringVar(value="0.00")
        self.wind_mrad_var = tk.StringVar(value="0.00")
        self.wind_drift_var = tk.StringVar(value="0.00")
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

        ttk.Label(main_frame, text="Scope Height (inches):").grid(row=5, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.scope_height_var).grid(row=5, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Wind Speed (mph):").grid(row=6, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.wind_speed_var).grid(row=6, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Wind Direction (deg):").grid(row=7, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.wind_direction_var).grid(row=7, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Barrel Twist (in/turn):").grid(row=8, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.barrel_twist_var).grid(row=8, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Target Size (inches):").grid(row=9, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.target_size_var).grid(row=9, column=1, sticky=(tk.W, tk.E))

        ttk.Label(main_frame, text="Target Angle (deg):").grid(row=10, column=0, sticky=tk.W)
        ttk.Entry(main_frame, textvariable=self.target_angle_var).grid(row=10, column=1, sticky=(tk.W, tk.E))

        # Drag model toggle
        ttk.Label(main_frame, text="Drag Model:").grid(row=11, column=0, sticky=tk.W)
        ttk.Radiobutton(main_frame, text="G1", variable=self.drag_model_var, value="G1").grid(row=11, column=1, sticky=tk.W)
        ttk.Radiobutton(main_frame, text="G7", variable=self.drag_model_var, value="G7").grid(row=11, column=1, sticky=tk.E)

        # Sensor fields (read-only)
        ttk.Label(main_frame, text="Temperature (°C):").grid(row=12, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.temp_var).grid(row=12, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Humidity (%):").grid(row=13, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.humidity_var).grid(row=13, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Pressure (inHg):").grid(row=14, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.pressure_var).grid(row=14, column=1, sticky=tk.W)

        # Output fields
        ttk.Label(main_frame, text="Bullet Drop (inches):").grid(row=15, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.drop_var).grid(row=15, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Velocity at Range (fps):").grid(row=16, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.velocity_at_range_var).grid(row=16, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Elevation Adjustment (MOA):").grid(row=17, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.moa_var).grid(row=17, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Elevation Adjustment (MRAD):").grid(row=18, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.mrad_var).grid(row=18, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Wind Drift (inches):").grid(row=19, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.wind_drift_var).grid(row=19, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Windage Adjustment (MOA):").grid(row=20, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.wind_moa_var).grid(row=20, column=1, sticky=tk.W)

        ttk.Label(main_frame, text="Windage Adjustment (MRAD):").grid(row=21, column=0, sticky=tk.W)
        ttk.Label(main_frame, textvariable=self.wind_mrad_var).grid(row=21, column=1, sticky=tk.W)

        # Calculate button
        ttk.Button(main_frame, text="Calculate", command=self.calculate).grid(row=22, column=0, columnspan=2, pady=10)

        # Configure grid weights
        main_frame.columnconfigure(1, weight=1)
        for i in range(23):
            main_frame.rowconfigure(i, weight=1)

    def poll_sensors(self):
        """Continuously poll Sense HAT sensors and update GUI."""
        while self.running:
            try:
                temp_c = self.sense.get_temperature()
                humidity = self.sense.get_humidity()
                pressure_mb = self.sense.get_pressure()
                pressure_inhg = pressure_mb * 0.02953
                self.temp_var.set(f"{temp_c:.1f}")
                self.humidity_var.set(f"{humidity:.1f}")
                self.pressure_var.set(f"{pressure_inhg:.2f}")
            except Exception as e:
                self.temp_var.set("Error")
                self.humidity_var.set("Error")
                self.pressure_var.set("Error")
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
            scope_height = float(self.scope_height_var.get())
            wind_speed = float(self.wind_speed_var.get())
            wind_direction = float(self.wind_direction_var.get())
            barrel_twist = float(self.barrel_twist_var.get())
            target_size = float(self.target_size_var.get())
            target_angle = float(self.target_angle_var.get())
            temp_c = float(self.temp_var.get()) if self.temp_var.get() != "Error" else 15.0
            humidity = float(self.humidity_var.get()) if self.humidity_var.get() != "Error" else 0.0
            pressure_inhg = float(self.pressure_var.get()) if self.pressure_var.get() != "Error" else 29.92
            drag_model = self.drag_model_var.get()

            if any(x <= 0 for x in [velocity, bc, bullet_weight, zero_range_yards, scope_height, barrel_twist, target_size]):
                raise ValueError("Inputs must be positive (except range, angles, wind).")
            if not 0 <= wind_direction <= 360:
                raise ValueError("Wind direction must be between 0 and 360 degrees.")

            drop, velocity_at_range, moa, mrad, wind_drift, wind_moa, wind_mrad = calculate_trajectory(
                velocity, bc, bullet_weight, range_yards, zero_range_yards, scope_height, temp_c, humidity, pressure_inhg, target_angle, drag_model, wind_speed, wind_direction
            )
            self.drop_var.set(f"{drop:.2f}")
            self.velocity_at_range_var.set(f"{velocity_at_range:.2f}")
            self.moa_var.set(f"{moa:.2f}")
            self.mrad_var.set(f"{mrad:.2f}")
            self.wind_drift_var.set(f"{wind_drift:.2f}")
            self.wind_moa_var.set(f"{wind_moa:.2f}")
            self.wind_mrad_var.set(f"{wind_mrad:.2f}")

            # Validate target size
            if abs(drop) > target_size:
                messagebox.showwarning("Target Warning", f"Bullet drop ({abs(drop):.2f} in) exceeds target size ({target_size:.2f} in).")
            if abs(wind_drift) > target_size:
                messagebox.showwarning("Target Warning", f"Wind drift ({abs(wind_drift):.2f} in) exceeds target size ({target_size:.2f} in).")
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