

## Confirmed Plan

**Units:** inches/second (in/s) — perfect for toy car scale.

### Wiring

```
HC-SR04         Level Shifter         Raspberry Pi 4
────────        ─────────────         ──────────────
VCC  ──────────────────────────────── 5V (Pin 2)
GND  ──────────────────────────────── GND (Pin 6)
TRIG ──────────────────────────────── GPIO 23 (Pin 16)  ← direct, no shifter needed
ECHO ────────── H1
                L1 ────────────────── GPIO 24 (Pin 18)
                HV ────────────────── 5V (Pin 4)
                LV ────────────────── 3.3V (Pin 1)
                GND ───────────────── GND (Pin 9)

I2C LCD (16x2)
──────────
VCC  ──────────────────────────────── 5V (Pin 2)
GND  ──────────────────────────────── GND (Pin 6)
SDA  ──────────────────────────────── GPIO 2 / SDA1 (Pin 3)
SCL  ──────────────────────────────── GPIO 3 / SCL1 (Pin 5)
```

> **Note on the LCD:** Most I2C LCD backpacks with the PCF8574 chip work fine at 3.3V logic from the Pi even though they're powered at 5V — the I2C bus has pull-ups to 3.3V and the chip reads it fine. No shifter needed for the LCD.

### Software

```
1. Enable I2C:        sudo raspi-config → Interface Options → I2C → Enable
2. Install packages:  sudo apt install python3-pip i2c-tools
                      pip3 install RPLCD smbus2 RPi.GPIO
3. Verify LCD:        i2cdetect -y 1   (should show address 0x27 or 0x3F)
4. Run script
```

### Script Logic

* Sample HC-SR04 distance every **60ms** (\~16 samples/sec)
* Speed = `|distance_prev - distance_now| / time_delta`
* Convert cm/s → in/s (÷ 2.54)
* Rolling average of last 3 readings to smooth noise
* Display on LCD Line 1: `Speed: XX.X in/s`
* LCD Line 2: blank for now (could add peak speed later)

***

### Concerns / Gotchas

* **Toy car speed range:** A Hot Wheels off a 3-foot ramp might hit \~60–100 in/s. HC-SR04 can sample fast enough for this, but it'll be tight. If readings are noisy, we can bump to a 5-reading average.
* **Sensor placement:** Point the HC-SR04 **down the track** so the car moves toward or away from it. Side-on won't work — ultrasonic measures distance on-axis only.
* **Min distance:** HC-SR04 can't measure below \~2cm. Don't let the car slam into it.

---
---

Here's your script: [speed\_radar.py](blob:https://www.microsoft365.com/9e936b16-8135-4ee4-b1ae-b43eb58465e4)

## What's In It

### Config Block (top of file — all the knobs)

| Variable                | Default       | What It Does                                               |
| ----------------------- | ------------- | ---------------------------------------------------------- |
| `TRIG_PIN` / `ECHO_PIN` | 23 / 24       | GPIO pins for HC-SR04                                      |
| `LCD_I2C_ADDR`          | `0x27`        | Change to `0x3F` if your LCD doesn't show up               |
| `SAMPLE_INTERVAL`       | `0.06` (60ms) | Time between distance readings                             |
| `ROLLING_WINDOW`        | `3`           | Number of readings to average for smoothing                |
| `IDLE_THRESHOLD`        | `0.5 in/s`    | Below this = show 0.0 (kills noise when nothing's moving)  |
| `ECHO_TIMEOUT`          | `0.04s`       | Prevents the script from hanging if sensor misses a return |

### LCD Output

```
Line 1: Speed: XX.X in/s
Line 2: Peak:  XX.X in/s    ← tracks the fastest reading since start
```

Threw in peak speed on line 2 since you'll want to know which car/ramp angle wins.

### Terminal Debug Output

Every reading also prints to the console so you can watch raw vs. averaged values while tuning:

```
Dist:  45.3 cm | Raw:  32.1 in/s | Avg:  28.7 in/s | Peak:  42.3 in/s
```

### Safety

* Echo timeout so the script never hangs
* Out-of-range readings are silently dropped
* Ctrl+C / SIGTERM both clean up GPIO and show "Radar OFF" on the LCD
* Bogus/None readings don't pollute the speed buffer

## To Run

```bash
# Install deps (if you haven't)
pip3 install RPLCD smbus2 RPi.GPIO

# Run it (needs root for GPIO)
sudo python3 speed_radar.py
```

## First Tuning Tips

* If readings are **jumpy**, bump `ROLLING_WINDOW` to `5`
* If it's **missing fast cars**, drop `SAMPLE_INTERVAL` to `0.04` (40ms)
* If it shows speed when nothing's moving, raise `IDLE_THRESHOLD` to `1.0`

Get it wired up and let me know what you see. We can tune from there.
