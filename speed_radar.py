#!/usr/bin/env python3
"""
speed_radar.py — Mini Speed Radar Sign
Raspberry Pi 4 + HC-SR04 + 16x2 I2C LCD

Measures the speed of objects (toy cars!) moving toward or away
from the ultrasonic sensor and displays the result on an LCD.

Hardware:
    - HC-SR04 ultrasonic sensor (TRIG → GPIO 23, ECHO → GPIO 24 via level shifter)
    - 16x2 LCD with PCF8574 I2C backpack (SDA → GPIO 2, SCL → GPIO 3)

Usage:
    python3 speed_radar.py

Author:  Jeremy & Copilot
Date:    2026-06-07
"""

import time
import signal
import sys
from collections import deque

import RPi.GPIO as GPIO
from RPLCD.i2c import CharLCD


# ──────────────────────────────────────────────
# CONFIGURATION — tweak these to taste
# ──────────────────────────────────────────────

# GPIO pins (BCM numbering)
TRIG_PIN = 23
ECHO_PIN = 24

# I2C LCD settings
LCD_I2C_ADDR   = 0x27      # Run `i2cdetect -y 1` if unsure; common: 0x27 or 0x3F
LCD_PORT       = 1          # I2C bus 1 on Pi 4
LCD_COLS       = 16
LCD_ROWS       = 2

# Sensor / measurement settings
SAMPLE_INTERVAL  = 0.06    # seconds between distance samples (~60 ms → ~16 Hz)
ROLLING_WINDOW   = 3       # number of speed readings to average (smoothing)
MAX_RANGE_CM     = 400     # HC-SR04 max rated range
MIN_RANGE_CM     = 2       # HC-SR04 min rated range
ECHO_TIMEOUT     = 0.04    # seconds to wait for echo before giving up (~6.8 m round-trip)
SPEED_OF_SOUND   = 34300   # cm/s at ~20 °C

# Display
IDLE_THRESHOLD   = 0.5     # in/s — below this we show 0.0 (noise floor)


# ──────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────

def setup_gpio():
    """Configure GPIO pins for the HC-SR04 sensor."""
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
    GPIO.output(TRIG_PIN, False)
    # Let the sensor settle
    print("[INIT] Letting HC-SR04 settle...")
    time.sleep(1.0)


def setup_lcd():
    """Initialize the I2C LCD and return the lcd object."""
    lcd = CharLCD(
        i2c_expander='PCF8574',
        address=LCD_I2C_ADDR,
        port=LCD_PORT,
        cols=LCD_COLS,
        rows=LCD_ROWS,
        dotsize=8,
        auto_linebreaks=True,
    )
    lcd.clear()
    lcd.cursor_pos = (0, 0)
    lcd.write_string("Speed Radar")
    lcd.cursor_pos = (1, 0)
    lcd.write_string("Initializing...")
    time.sleep(1.5)
    lcd.clear()
    return lcd


# ──────────────────────────────────────────────
# SENSOR READING
# ──────────────────────────────────────────────

def get_distance_cm():
    """
    Trigger the HC-SR04 and return the measured distance in cm.
    Returns None if the reading times out or is out of range.
    """
    # Send a 10 µs trigger pulse
    GPIO.output(TRIG_PIN, True)
    time.sleep(0.00001)  # 10 µs
    GPIO.output(TRIG_PIN, False)

    # Wait for ECHO to go HIGH (start of return pulse)
    pulse_start = None
    timeout_start = time.time()
    while GPIO.input(ECHO_PIN) == 0:
        pulse_start = time.time()
        if pulse_start - timeout_start > ECHO_TIMEOUT:
            return None  # timed out waiting for echo start

    # Wait for ECHO to go LOW (end of return pulse)
    pulse_end = None
    while GPIO.input(ECHO_PIN) == 1:
        pulse_end = time.time()
        if pulse_end - timeout_start > ECHO_TIMEOUT:
            return None  # timed out waiting for echo end

    if pulse_start is None or pulse_end is None:
        return None

    # Calculate distance from pulse duration
    pulse_duration = pulse_end - pulse_start
    distance_cm = (pulse_duration * SPEED_OF_SOUND) / 2.0

    # Reject out-of-range readings
    if distance_cm < MIN_RANGE_CM or distance_cm > MAX_RANGE_CM:
        return None

    return distance_cm


# ──────────────────────────────────────────────
# SPEED CALCULATION
# ──────────────────────────────────────────────

def cm_per_s_to_in_per_s(speed_cm_s):
    """Convert speed from cm/s to in/s."""
    return speed_cm_s / 2.54


# ──────────────────────────────────────────────
# LCD DISPLAY
# ──────────────────────────────────────────────

def update_lcd(lcd, speed_in_s, peak_in_s):
    """
    Update the 16x2 LCD:
        Line 1: Speed: XX.X in/s
        Line 2: Peak:  XX.X in/s
    """
    line1 = f"Speed:{speed_in_s:6.1f} in/s"
    line2 = f"Peak: {peak_in_s:6.1f} in/s"

    # Pad/truncate to exactly 16 chars
    line1 = line1[:LCD_COLS].ljust(LCD_COLS)
    line2 = line2[:LCD_COLS].ljust(LCD_COLS)

    lcd.cursor_pos = (0, 0)
    lcd.write_string(line1)
    lcd.cursor_pos = (1, 0)
    lcd.write_string(line2)


# ──────────────────────────────────────────────
# CLEANUP
# ──────────────────────────────────────────────

def cleanup(lcd):
    """Clean up GPIO and LCD on exit."""
    print("\n[EXIT] Cleaning up...")
    try:
        lcd.clear()
        lcd.cursor_pos = (0, 0)
        lcd.write_string("Radar OFF")
        lcd.close(clear=False)
    except Exception:
        pass
    GPIO.cleanup()
    print("[EXIT] Done. Goodbye!")


# ──────────────────────────────────────────────
# MAIN LOOP
# ──────────────────────────────────────────────

def main():
    # Setup hardware
    setup_gpio()
    lcd = setup_lcd()

    # Handle Ctrl+C and SIGTERM gracefully
    def signal_handler(sig, frame):
        cleanup(lcd)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # State variables
    speed_buffer = deque(maxlen=ROLLING_WINDOW)  # rolling window of speed readings
    prev_distance = None
    prev_time = None
    peak_speed = 0.0

    print("[RUNNING] Speed radar active. Ctrl+C to quit.")
    print(f"[CONFIG] Sample interval: {SAMPLE_INTERVAL*1000:.0f}ms | "
          f"Rolling avg window: {ROLLING_WINDOW} | "
          f"Idle threshold: {IDLE_THRESHOLD} in/s")
    print("-" * 50)

    try:
        while True:
            # Take a distance reading
            distance = get_distance_cm()
            now = time.time()

            if distance is not None and prev_distance is not None and prev_time is not None:
                # Calculate time delta
                dt = now - prev_time

                if dt > 0:
                    # Raw speed in cm/s (absolute value — we don't care about direction)
                    speed_cm_s = abs(distance - prev_distance) / dt

                    # Convert to in/s
                    speed_in_s = cm_per_s_to_in_per_s(speed_cm_s)

                    # Add to rolling buffer
                    speed_buffer.append(speed_in_s)

                    # Calculate smoothed average speed
                    avg_speed = sum(speed_buffer) / len(speed_buffer)

                    # Apply idle threshold (suppress sensor noise when nothing is moving)
                    if avg_speed < IDLE_THRESHOLD:
                        avg_speed = 0.0

                    # Update peak speed
                    if avg_speed > peak_speed:
                        peak_speed = avg_speed

                    # Update LCD
                    update_lcd(lcd, avg_speed, peak_speed)

                    # Debug output to terminal
                    print(f"  Dist: {distance:6.1f} cm | "
                          f"Raw: {speed_in_s:6.1f} in/s | "
                          f"Avg: {avg_speed:6.1f} in/s | "
                          f"Peak: {peak_speed:6.1f} in/s")

            # Store current reading for next iteration
            if distance is not None:
                prev_distance = distance
                prev_time = now

            # Wait before next sample
            time.sleep(SAMPLE_INTERVAL)

    except KeyboardInterrupt:
        pass
    finally:
        cleanup(lcd)


if __name__ == "__main__":
    main()
