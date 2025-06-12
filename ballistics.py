import math

def convert_temperature(value, to_celsius):
    if to_celsius:
        return (value - 32) * 5/9 if not isinstance(value, str) else value
    return value * 9/5 + 32 if not isinstance(value, str) else value

def convert_distance(value, to_meters, is_height=False):
    if isinstance(value, str):
        return value
    if is_height:
        return value * 2.54 if to_meters else value / 2.54
    return value * 0.9144 if to_meters else value / 0.9144

def atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft):
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
    bullet_mass_kg = bullet_weight_grains / 7000 * 0.453592
    twist_rate = 1 / barrel_twist_in
    spin_velocity = velocity_ms * twist_rate * 0.0254
    drift_m = 1.25 * (bullet_mass_kg / 0.01) * (range_m / 1000) ** 2 / (velocity_ms / 300) * (twist_rate / 0.1)
    return drift_m

def calculate_wind_drift(wind_speed_ms, wind_direction_deg, time_of_flight, range_m, velocity_ms, bc):
    crosswind = wind_speed_ms * math.sin(math.radians(wind_direction_deg))
    drift_m = crosswind * time_of_flight * (1 - bc / 2) / (bc * 1.5)
    if abs(drift_m) > 100:
        drift_m = 0.0
    return drift_m

def calculate_trajectory(
    velocity_fps, bc, bullet_weight_grains, range_yards, zero_range_yards, scope_height_in,
    temp_c, humidity, pressure_inhg, altitude_ft, target_angle_deg, drag_model,
    wind_speed_mph, wind_direction_deg, barrel_twist_in, use_meters, use_celsius,
    zero_env=None):
    if zero_env is not None:
        tol = 0.5
        if (
            abs(range_yards - zero_range_yards) < 1e-3 and
            abs(temp_c - zero_env.get("temp", temp_c)) < tol and
            abs(humidity - zero_env.get("humidity", humidity)) < tol and
            abs(pressure_inhg - zero_env.get("pressure", pressure_inhg)) < tol and
            abs(altitude_ft - zero_env.get("altitude", altitude_ft)) < tol and
            abs(wind_speed_mph - zero_env.get("wind_speed", wind_speed_mph)) < tol and
            abs(wind_direction_deg - zero_env.get("wind_direction", wind_direction_deg)) < tol
        ):
            return 0.0, velocity_fps, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0

    velocity_ms = velocity_fps * 0.3048
    range_m = convert_distance(range_yards, True) if not use_meters else range_yards
    zero_range_m = convert_distance(zero_range_yards, True) if not use_meters else zero_range_yards
    scope_height_m = convert_distance(scope_height_in, True, is_height=True) / 100
    temp_c = convert_temperature(temp_c, True) if not use_celsius else temp_c
    wind_speed_ms = wind_speed_mph * 0.44704
    bullet_mass = bullet_weight_grains / 7000 * 0.453592
    bullet_area = 0.000506707
    target_angle_rad = math.radians(target_angle_deg)

    corrected_bc, adjusted_pressure = atmosphere_correction(bc, temp_c, humidity, pressure_inhg, altitude_ft)
    drag_coeff = 0.5 if drag_model == "G1" else 0.25
    air_density = (adjusted_pressure * 3386.39) / (287.05 * (temp_c + 273.15))

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
    drop_unit = adjusted_drop_m * 100 if use_meters else adjusted_drop_m * 39.3701

    moa_adjustment = (drop_unit / (range_yards / 100)) / 1.047 if range_yards > 0 and not use_meters else (drop_unit / (range_m / 100)) / 1.047
    mrad_adjustment = (drop_unit / (range_yards / 100)) / 3.6 if range_yards > 0 and not use_meters else (drop_unit / (range_m / 100)) / 3.6

    wind_drift_m = calculate_wind_drift(wind_speed_ms, wind_direction_deg, time_of_flight, range_m, velocity_ms, corrected_bc)
    spin_drift_m = calculate_spin_drift(bullet_weight_grains, barrel_twist_in, range_m, velocity_ms)
    total_lateral_drift_m = wind_drift_m + spin_drift_m
    total_lateral_drift_unit = total_lateral_drift_m * 100 if use_meters else total_lateral_drift_m * 39.3701

    total_lateral_moa = (total_lateral_drift_unit / (range_yards / 100)) / 1.047 if range_yards > 0 and not use_meters else (total_lateral_drift_unit / (range_m / 100)) / 1.047
    total_lateral_mrad = (total_lateral_drift_unit / (range_yards / 100)) / 3.6 if range_yards > 0 and not use_meters else (total_lateral_drift_unit / (range_m / 100)) / 3.6

    return drop_unit, velocity_at_range_fps, energy_ftlbs, moa_adjustment, mrad_adjustment, total_lateral_drift_unit, total_lateral_moa, total_lateral_mrad
