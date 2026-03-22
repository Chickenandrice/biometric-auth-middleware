import matplotlib
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import board
import busio
from adafruit_ads1x15.ads1115 import ADS1115
from adafruit_ads1x15.analog_in import AnalogIn
from gpiozero import DigitalInputDevice
from collections import deque

LO_PLUS = DigitalInputDevice(17)
LO_MINUS = DigitalInputDevice(27)

i2c = busio.I2C(board.SCL, board.SDA)
ads = ADS1115(i2c)
ads.gain = 1
ads.data_rate = 860
chan = AnalogIn(ads, 0)

WINDOW = 800
ecg_data = deque([0.0] * WINDOW, maxlen=WINDOW)
time_axis = list(range(WINDOW))

fig, ax = plt.subplots(figsize=(12, 4))
line, = ax.plot(time_axis, list(ecg_data), color='lime', linewidth=0.8)
status_txt = ax.text(0.01, 0.95, '', transform=ax.transAxes,
                     color='red', fontsize=11, va='top')

ax.set_facecolor('black')
fig.patch.set_facecolor('black')
ax.tick_params(colors='white')
for spine in ax.spines.values():
    spine.set_color('white')
ax.set_title("ECG — AD8232", color='white', fontsize=13)
ax.set_ylabel("Voltage (V)", color='white')
ax.set_xlabel("Samples", color='white')
ax.set_ylim(0, 3.3)
ax.set_xlim(0, WINDOW)

def animate(i):
    if LO_PLUS.value or LO_MINUS.value:
        ecg_data.append(0.0)
        status_txt.set_text("⚠ Lead-off — check electrodes")
    else:
        ecg_data.append(chan.voltage)
        status_txt.set_text("")

    line.set_ydata(list(ecg_data))
    return line, status_txt

ani = animation.FuncAnimation(
    fig,
    animate,
    interval=5,
    blit=True,
    cache_frame_data=False
)

plt.tight_layout()

try:
    plt.show()
finally:
    print("Done.")
