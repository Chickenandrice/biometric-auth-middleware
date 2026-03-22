import matplotlib
matplotlib.use('TkAgg')

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import max30102
from collections import deque

# --- Sensor Init ---
m = max30102.MAX30102()

# --- Data Buffers ---
WINDOW = 500
red_data = deque([0] * WINDOW, maxlen=WINDOW)
ir_data  = deque([0] * WINDOW, maxlen=WINDOW)

# --- Plot Setup ---
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))
line1, = ax1.plot(list(red_data), color='red')
line2, = ax2.plot(list(ir_data),  color='darkblue')

ax1.set_title("Red LED — Heart Rate")
ax2.set_title("IR LED — SpO2")
ax1.set_ylim(0, 300000)
ax2.set_ylim(0, 300000)
ax1.set_ylabel("Raw ADC Value")
ax2.set_ylabel("Raw ADC Value")
ax2.set_xlabel("Samples")

# --- Animation ---
def animate(i):
    red, ir = m.read_sequential()
    red_data.extend(red)
    ir_data.extend(ir)
    line1.set_ydata(list(red_data))
    line2.set_ydata(list(ir_data))
    return line1, line2

ani = animation.FuncAnimation(fig, animate, interval=10, blit=True)
plt.tight_layout()
plt.show()
