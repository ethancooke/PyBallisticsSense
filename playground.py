# This file is now split into modules:
# - ballistics.py: all calculation and conversion functions
# - sensehat_io.py: all Sense HAT reading/writing
# - gui.py: the GUI application
#
# To run the application, use gui.py as your entry point.

#!/usr/bin/python3
# Ballistic Calculator for Raspberry Pi with Sense HAT
# ---------------------------------------------------
# This application provides a GUI for ballistic calculations, using real-time environmental data from the Sense HAT sensors.
# It displays results both on the GUI and the Sense HAT LED grid.
#
# Features:
# - Reads temperature, humidity, and pressure from Sense HAT
# - Calculates bullet drop, wind drift, spin drift, and scope adjustments
# - Supports unit switching (metric/imperial)
# - Visualizes elevation and windage adjustments on the Sense HAT grid
# - Warns if drop or drift exceeds target size
#
# Author: [Your Name]
# Date: [Update as needed]

import tkinter as tk
from tkinter import ttk, messagebox
from sense_hat import SenseHat
import threading
import time
import math
import json

# Initialize Sense HAT
sense = SenseHat()
sense.clear()

# Ballistic calculation functions

def convert_temperature(value, to_celsius):
    """Convert temperature between °C and °F."""
    if to_celsius:
        return (value - 32) * 5/9 if not isinstance(value, str) else value
    return value * 9/5 + 32 if not isinstance(value, str) else value

def convert_distance(value, to_meters, is_height=False):
    """Convert distance between yards/meters or inches/cm."""
    if isinstance(value, str):
        return value
    if is_height:
        return value * 2.54 if to_meters else value / 2.54  # inches to cm
    return value * 0.9144 if to_meters else value / 0.9144  # yards to meters

def atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft):
    """Adjust ballistic coefficient for environmental conditions.
    - Adjusts for temperature, humidity, pressure, and altitude.
    - Returns corrected BC and adjusted pressure.
    """
    temp_k = temp_c + 273.15
    std_temp_k = 15 + 273.15
    if pressure_inhg == 29.92 and altitude_ft != 0:
        pressure_inhg = 29.92 * math.exp(-altitude_ft / 30000)
    pressure_pa = pressure_inhg * 3386.39
    air_density = (pressure_pa / (287.05 * temp_k)) * (1 - 0.0065 * temp_c / 288.15) ** 4.255
    std_air_density = (101325 / (287.05 * std_temp_k)) * (1 - 0.0065 * 15 / 288.15) ** 4.255
    density_factor = std_air_density / air_density
    humidity_factor = 1 - (humidity / 100) * 0.02
    corrected_bc = bc * density_factor * humidity_factor
    return corrected_bc, pressure_inhg

def calculate_spin_drift(bullet_weight_grains, barrel_twist_in, range_m, velocity_ms):
    """Calculate spin drift (lateral drift due to bullet spin).
    - Returns drift in meters.
    """
    bullet_mass_kg = bullet_weight_grains / 7000 * 0.453592
    twist_rate = 1 / barrel_twist_in
    spin_velocity = velocity_ms * twist_rate * 0.0254
    drift_m = 1.25 * (bullet_mass_kg / 0.01) * (range_m / 1000) ** 2 / (velocity_ms / 300) * (twist_rate / 0.1)
    return drift_m

def calculate_wind_drift(wind_speed_ms, wind_direction_deg, time_of_flight, range_m, velocity_ms, bc):
    """Calculate lateral drift due to wind.
    - Returns drift in meters.
    """
    crosswind = wind_speed_ms * math.sin(math.radians(wind_direction_deg))
    # Litz-based model: drift adjusted for BC and velocity decay
    drift_m = crosswind * time_of_flight * (1 - bc / 2) / (bc * 1.5)
    if abs(drift_m) > 100:  # Cap at ~100 meters
        drift_m = 0.0
    return drift_m

def calculate_trajectory(
    velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, scope_height_in,
    temp_c, humidity, pressure_inhg, altitude_ft, target_angle_deg, drag_model,
    wind_speed_mph, wind_direction_deg, barrel_twist_in, use_meters, use_celsius,
    zero_env=None):
    """Calculate bullet drop, velocity, energy, and scope adjustments.
    - Converts all inputs to SI or imperial as needed
    - Applies environmental corrections
    - Returns drop, velocity at range, energy, MOA/MRAD adjustments, and lateral drift
    - If at zero range and environment matches zero_env, returns zero adjustments
    """
    # Check for zeroing condition
    if zero_env is not None:
        tol = 0.5  # tolerance for temp, humidity, pressure, altitude, wind
        if (
            abs(range_yards - zero_range_yards) < 1e-3 and
            abs(temp_c - zero_env.get("temp", temp_c)) < tol and
            abs(humidity - zero_env.get("humidity", humidity)) < tol and
            abs(pressure_inhg - zero_env.get("pressure", pressure_inhg)) < tol and
            abs(altitude_ft - zero_env.get("altitude", altitude_ft)) < tol and
            abs(wind_speed_mph - zero_env.get("wind_speed", wind_speed_mph)) < tol and
            abs(wind_direction_deg - zero_env.get("wind_direction", wind_direction_deg)) < tol
        ):
            # At zero, matching environment: all adjustments zero
            return 0.0, velocity_fps, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    # Convert inputs based on units
    velocity_ms = velocity_fps * 0.3048
    range_m = convert_distance(range_yards, True) if not use_meters else range_yards
    zero_range_m = convert_distance(zero_range_yards, True) if not use_meters else zero_range_yards
    scope_height_m = convert_distance(scope_height_in, True, is_height=True) / 100  # cm to m
    temp_c = convert_temperature(temp_c, True) if not use_celsius else temp_c
    wind_speed_ms = wind_speed_mph * 0.44704
    bullet_mass = bullet_weight_grains / 7000 * 0.453592
    bullet_area = 0.000506707  # Approx. for .308 bullet
    target_angle_rad = math.radians(target_angle_deg)

    corrected_bc, adjusted_pressure = atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft)
    drag_coeff = 0.5 if drag_model == "G1" else 0.25
    air_density = (adjusted_pressure * 3386.39) / (287.05 * (temp_c + 273.15))

    # Iterative time of flight
    time_of_flight = range_m / velocity_ms
    velocity_at_range = velocity_ms * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass * corrected_bc))
    for _ in range(3):
        avg_velocity = (velocity_ms + velocity_at_range) / 0.2
        time_of_flight = range_m / avg_velocity
        velocity_at_range = velocity_ms * math.exp(-drag_coeff * air_density * bullet_area * range_m / (2 * bullet_mass / corrected_bc))

    velocity_at_range_fps = velocity_at_range / 0.3048
    energy_joules = 0.5 * bullet_mass * velocity_at_range ** 2
    energy_ftlbs = energy_joules / 1.35582

    g = 9.81
    drop_m = (0.5 * g * time_of_flight ** 2) * math.cos(target_angle_rad)
    zero_angle = math.atan2(drop_m + scope_height_m, zero_range_m) if zero_range_m > 0 else 0.0
    adjusted_drop_m = drop_m - range_m * math.tan(zero_angle) + scope_height_m
    drop_unit = adjusted_drop_m * 100 if use_meters else adjusted_drop_m * 39.3701  # m to cm or inches

    moa_adjustment = (drop_unit / (range_yards / 100)) / 1.047 if range_yards > 0 and not use_meters else (drop_unit / (range_m / 100)) / 1.047
    mrad_adjustment = (drop_unit / (range_yards / 100)) / 3.6 if range_yards > 0 and not use_meters else (drop_unit / (range_m / 100)) / 3.6

    wind_drift_m = calculate_wind_drift(wind_speed_ms, wind_direction_deg, time_of_flight, range_m, velocity_ms, corrected_bc)
    spin_drift_m = calculate_spin_drift(bullet_weight_grains, barrel_twist_in, range_m, velocity_ms)
    total_lateral_drift_m = wind_drift_m + spin_drift_m
    total_lateral_drift_unit = total_lateral_drift_m * 100 if use_meters else total_lateral_drift_m * 39.3701

    total_lateral_moa = (total_lateral_drift_unit / (range_yards / 100)) / 1.047 if range_yards > 0 and not use_meters else (total_lateral_drift_unit / (range_m / 100)) / 1.047
    total_lateral_mrad = (total_lateral_drift_unit / (range_yards / 100)) / 3.6 if range_yards > 0 and not use_meters else (total_lateral_drift_unit / (range_m / 100)) / 3.6

    return drop_unit, velocity_at_range_fps, energy_ftlbs, moa_adjustment, mrad_adjustment, total_lateral_drift_unit, total_lateral_moa, total_lateral_mrad

# GUI Application
class BallisticCalculator(tk.Tk):
    """
    Main GUI application for the Ballistic Calculator.
    - Organizes input fields for rifle, bullet, and environment
    - Displays results and warnings
    - Polls Sense HAT sensors in a background thread
    - Updates Sense HAT grid with elevation/windage MOA
    """
    def _init_vars(self, defaults):
        """Initialize all StringVars in a single dictionary for easier management."""
        self.vars = {}
        # Define all variable groups and their keys
        var_map = {
            'rifle': ["scope_height", "zero_range", "barrel_twist"],
            'bullet': ["velocity", "bc", "weight", "drag_model"],
            'environment_user': ["range", "target_size", "target_angle", "wind_speed", "wind_direction", "altitude"],
            'environment_sensor': ["temp", "humidity", "pressure"],
            'output': ["drop", "velocity_at_range", "energy", "moa", "mrad", "lateral_drift", "lateral_moa", "lateral_mrad"],
            'units': ["temp_unit", "dist_unit"]
        }
        for section, keys in var_map.items():
            for key in keys:
                value = str(defaults[section][key]) if section in defaults and key in defaults[section] else ""
                self.vars[key] = tk.StringVar(value=value)

    def __init__(self):
        super().__init__()
        self.title("Ballistic Calculator")
        self.geometry("800x480")
        self.attributes("-fullscreen", False)
        self.sense = sense
        self.running = True

        # Load defaults from external JSON file
        with open("defaults.json", "r") as f:
            defaults = json.load(f)

        self._init_vars(defaults)

        # Rifle
        self.rifle_scope_height = self.vars["scope_height"]
        self.rifle_zero_range = self.vars["zero_range"]
        self.rifle_barrel_twist = self.vars["barrel_twist"]
        # Bullet
        self.bullet_velocity = self.vars["velocity"]
        self.bullet_bc = self.vars["bc"]
        self.bullet_weight = self.vars["weight"]
        self.bullet_drag_model = self.vars["drag_model"]
        # Environment (User Input)
        self.env_range = self.vars["range"]
        self.env_target_size = self.vars["target_size"]
        self.env_target_angle = self.vars["target_angle"]
        self.env_wind_speed = self.vars["wind_speed"]
        self.env_wind_direction = self.vars["wind_direction"]
        self.env_altitude = self.vars["altitude"]
        # Environment (Sensors)
        self.env_temp = self.vars["temp"]
        self.env_humidity = self.vars["humidity"]
        self.env_pressure = self.vars["pressure"]
        # Output/Results
        self.result_drop = self.vars["drop"]
        self.result_velocity_at_range = self.vars["velocity_at_range"]
        self.result_energy = self.vars["energy"]
        self.result_moa = self.vars["moa"]
        self.result_mrad = self.vars["mrad"]
        self.result_lateral_drift = self.vars["lateral_drift"]
        self.result_lateral_moa = self.vars["lateral_moa"]
        self.result_lateral_mrad = self.vars["lateral_mrad"]
        # Units
        self.unit_temp = self.vars["temp_unit"]
        self.unit_dist = self.vars["dist_unit"]

        # GUI Layout
        self.create_widgets()

        # Start sensor polling thread
        self.sensor_thread = threading.Thread(target=self.poll_sensors, daemon=True)
        self.sensor_thread.start()

    def create_widgets(self):
        """Create and layout all GUI widgets using grid layout with improved readability and maintainability."""
        main_container = ttk.Frame(self, padding="10")
        main_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        # Use a dictionary to store frames for easier access and future extension
        frames = {
            'rifle': ttk.LabelFrame(main_container, text="Rifle Details", padding="5"),
            'bullet': ttk.LabelFrame(main_container, text="Bullet Details", padding="5"),
            'env': ttk.LabelFrame(main_container, text="Environment Details", padding="5"),
            'result': ttk.LabelFrame(main_container, text="Resulting Calculations", padding="5")
        }
        frames['rifle'].grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        frames['bullet'].grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        frames['env'].grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        frames['result'].grid(row=1, column=1, sticky="nsew", padx=5, pady=5)

        main_container.columnconfigure(0, weight=1)
        main_container.columnconfigure(1, weight=1)
        main_container.rowconfigure(0, weight=1)
        main_container.rowconfigure(1, weight=1)

        # Helper for adding labeled entry
        def add_labeled_entry(frame, label, variable, row, col=0, label_kwargs=None, entry_kwargs=None):
            label_kwargs = label_kwargs or {}
            entry_kwargs = entry_kwargs or {}
            ttk.Label(frame, text=label, **label_kwargs).grid(row=row, column=col, sticky=tk.W)
            ttk.Entry(frame, textvariable=variable, **entry_kwargs).grid(row=row, column=col+1, sticky=(tk.W, tk.E))
            frame.columnconfigure(col+1, weight=1)

        # Rifle Details
        add_labeled_entry(frames['rifle'], "Scope Height:", self.rifle_scope_height, 0)
        add_labeled_entry(frames['rifle'], "Zero Range:", self.rifle_zero_range, 1)
        add_labeled_entry(frames['rifle'], "Barrel Twist (in/turn):", self.rifle_barrel_twist, 2)

        # Bullet Details
        add_labeled_entry(frames['bullet'], "Muzzle Velocity (fps):", self.bullet_velocity, 0)
        add_labeled_entry(frames['bullet'], "Ballistic Coefficient:", self.bullet_bc, 1)
        add_labeled_entry(frames['bullet'], "Bullet Weight (gr):", self.bullet_weight, 2)
        ttk.Label(frames['bullet'], text="Drag Model:").grid(row=3, column=0, sticky=tk.W)
        ttk.Radiobutton(frames['bullet'], text="G1", variable=self.bullet_drag_model, value="G1").grid(row=3, column=1, sticky=tk.W)
        ttk.Radiobutton(frames['bullet'], text="G7", variable=self.bullet_drag_model, value="G7").grid(row=3, column=2, sticky=tk.W)
        frames['bullet'].columnconfigure(1, weight=1)
        frames['bullet'].columnconfigure(2, weight=1)

        # Environment Details
        add_labeled_entry(frames['env'], "Range:", self.env_range, 0)
        add_labeled_entry(frames['env'], "Target Size:", self.env_target_size, 1)
        add_labeled_entry(frames['env'], "Target Angle (deg):", self.env_target_angle, 2)
        add_labeled_entry(frames['env'], "Wind Speed (mph):", self.env_wind_speed, 3)
        add_labeled_entry(frames['env'], "Wind Direction (deg):", self.env_wind_direction, 4)
        add_labeled_entry(frames['env'], "Altitude (ft):", self.env_altitude, 5)
        ttk.Label(frames['env'], text="Temperature:").grid(row=6, column=0, sticky=tk.W)
        ttk.Label(frames['env'], textvariable=self.env_temp).grid(row=6, column=1, sticky=tk.W)
        ttk.Label(frames['env'], text="Humidity (%):").grid(row=7, column=0, sticky=tk.W)
        ttk.Label(frames['env'], textvariable=self.env_humidity).grid(row=7, column=1, sticky=tk.W)
        ttk.Label(frames['env'], text="Pressure (inHg):").grid(row=8, column=0, sticky=tk.W)
        ttk.Label(frames['env'], textvariable=self.env_pressure).grid(row=8, column=1, sticky=tk.W)
        # Unit selection
        ttk.Label(frames['env'], text="Units:").grid(row=9, column=0, sticky=tk.W)
        ttk.Radiobutton(frames['env'], text="°C", variable=self.unit_temp, value="°C", command=self.update_units).grid(row=9, column=1, sticky=tk.W)
        ttk.Radiobutton(frames['env'], text="°F", variable=self.unit_temp, value="°F", command=self.update_units).grid(row=9, column=2, sticky=tk.W)
        ttk.Radiobutton(frames['env'], text="Yards", variable=self.unit_dist, value="Yards", command=self.update_units).grid(row=9, column=3, sticky=tk.W)
        ttk.Radiobutton(frames['env'], text="Meters", variable=self.unit_dist, value="Meters", command=self.update_units).grid(row=9, column=4, sticky=tk.W)
        for i in range(1, 5):
            frames['env'].columnconfigure(i, weight=1)

        # Resulting Calculations
        def add_labeled_result(frame, label, variable, row, col=0):
            ttk.Label(frame, text=label).grid(row=row, column=col, sticky=tk.W)
            ttk.Label(frame, textvariable=variable).grid(row=row, column=col+1, sticky=tk.W)
            frame.columnconfigure(col+1, weight=1)
        add_labeled_result(frames['result'], "Bullet Drop:", self.result_drop, 0)
        add_labeled_result(frames['result'], "Velocity at Range (fps):", self.result_velocity_at_range, 1)
        add_labeled_result(frames['result'], "Energy at Range (ft-lbs):", self.result_energy, 2)
        add_labeled_result(frames['result'], "Elevation Adjustment (MOA):", self.result_moa, 3)
        add_labeled_result(frames['result'], "Elevation Adjustment (MRAD):", self.result_mrad, 4)
        add_labeled_result(frames['result'], "Lateral Drift:", self.result_lateral_drift, 5)
        add_labeled_result(frames['result'], "Windage Adjustment (MOA):", self.result_lateral_moa, 6)
        add_labeled_result(frames['result'], "Windage Adjustment (MRAD):", self.result_lateral_mrad, 7)

        # Calculate button
        ttk.Button(main_container, text="Calculate", command=self.calculate).grid(row=2, column=0, columnspan=2, pady=10)

    def update_units(self):
        """Update displayed values when units change (°C/°F, yards/meters)."""
        use_celsius = self.unit_temp.get() == "°C"
        use_meters = self.unit_dist.get() == "Meters"

        try:
            # Temperature
            if self.env_temp.get() != "N/A" and self.env_temp.get() != "Error":
                temp = float(self.env_temp.get())
                self.env_temp.set(f"{convert_temperature(temp, use_celsius):.1f}")

            # Distance variables (range, zero_range)
            for var in [self.env_range, self.rifle_zero_range]:
                if var.get() and var.get() != "Error":
                    value = float(var.get())
                    new_value = convert_distance(value, use_meters)
                    var.set(f"{new_value:.2f}")

            # Height/size variables (scope_height, target_size, drop, lateral_drift)
            for var in [self.rifle_scope_height, self.env_target_size, self.result_drop, self.result_lateral_drift]:
                if var.get() and var.get() != "Error" and var.get() != "0.00":
                    value = float(var.get())
                    new_value = convert_distance(value, use_meters, is_height=True)
                    var.set(f"{new_value:.2f}")

        except ValueError:
            pass

    def poll_sensors(self):
        """Continuously poll Sense HAT sensors and update GUI.
        - Updates temperature, humidity, and pressure fields
        - Handles sensor errors gracefully
        """
        while self.running:
            try:
                temp_c = self.sense.get_temperature()
                humidity = self.sense.get_humidity()
                pressure_mb = self.sense.get_pressure()
                pressure_inhg = pressure_mb * 0.02953
                use_celsius = self.unit_temp.get() == "°C"
                temp_display = temp_c if use_celsius else convert_temperature(temp_c, False)
                self.env_temp.set(f"{temp_display:.1f}")
                self.env_humidity.set(f"{humidity:.1f}")
                self.env_pressure.set(f"{pressure_inhg:.2f}")
            except Exception as e:
                self.env_temp.set("Error")
                self.env_humidity.set("Error")
                self.env_pressure.set("Error")
                print(f"Sensor error: {e}")
            time.sleep(2)

    def calculate(self):
        """Perform ballistic calculation based on user inputs.
        - Validates inputs
        - Calls calculation functions
        - Updates result fields
        """
        try:
            with open("defaults.json", "r") as f:
                defaults = json.load(f)
            zero_env = defaults.get("zero_environment", None)
            velocity = float(self.bullet_velocity.get())
            bc = float(self.bullet_bc.get())
            bullet_weight = float(self.bullet_weight.get())
            range_ = float(self.env_range.get())
            zero_range = float(self.rifle_zero_range.get())
            scope_height = float(self.rifle_scope_height.get())
            wind_speed = float(self.env_wind_speed.get())
            wind_direction = float(self.env_wind_direction.get())
            barrel_twist = float(self.rifle_barrel_twist.get())
            target_size = float(self.env_target_size.get())
            target_angle = float(self.env_target_angle.get())
            altitude = float(self.env_altitude.get())
            temp = float(self.env_temp.get()) if self.env_temp.get() != "Error" else (15.0 if self.unit_temp.get() == "°C" else 59.0)
            humidity = float(self.env_humidity.get()) if self.env_humidity.get() != "Error" else 0.0
            pressure_inhg = float(self.env_pressure.get()) if self.env_pressure.get() != "Error" else 29.92
            drag_model = self.bullet_drag_model.get()
            use_celsius = self.unit_temp.get() == "°C"
            use_meters = self.unit_dist.get() == "Meters"

            # Input validation
            if any(x <= 0 for x in [velocity, bc, bullet_weight, zero_range, scope_height, barrel_twist, target_size]):
                raise ValueError("Inputs must be positive (except range, angles, wind, altitude).")
            if not 0 <= wind_direction <= 360:
                raise ValueError("Wind direction must be between 0 and 360 degrees.")
            if not 0.05 <= bc <= 1.0:
                raise ValueError("Ballistic coefficient must be between 0.05 and 1.0.")
            if range_ < 0:
                raise ValueError("Range must be non-negative.")
            if abs(target_angle) > 90:
                raise ValueError("Target angle must be between -90 and 90 degrees.")

            drop, velocity_at_range, energy, moa, mrad, lateral_drift, lateral_moa, lateral_mrad = calculate_trajectory(
                velocity, bc, bullet_weight, range_, zero_range, scope_height, temp, humidity, pressure_inhg, altitude, target_angle, drag_model, wind_speed, wind_direction, barrel_twist, use_meters, use_celsius, zero_env
            )
            self.result_drop.set(f"{drop:.2f}")
            self.result_velocity_at_range.set(f"{velocity_at_range:.2f}")
            self.result_energy.set(f"{energy:.2f}")
            self.result_moa.set(f"{moa:.2f}")
            self.result_mrad.set(f"{mrad:.2f}")
            self.result_lateral_drift.set(f"{lateral_drift:.2f}")
            self.result_lateral_moa.set(f"{lateral_moa:.2f}")
            self.result_lateral_mrad.set(f"{lateral_mrad:.2f}")

        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            self.sense.clear()

    def destroy(self):
        """Clean up on exit (stop threads, clear Sense HAT)."""
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