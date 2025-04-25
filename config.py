import numpy as np

"""
Configuration for Swim Lap Counter:
Defines WebSocket parameters, detection thresholds, and pool zones.
"""
WEBSOCKET_URL = "ws://homeassistant.local:3000"
DEVICE_SERIAL_NUMBER = "T8113T7223242231"
CONFIDENCE_THRESHOLD = 0.15
PROCESS_EVERY_N_FRAMES = 1

START_ZONE = np.array([
    [644, 726],
    [726, 682],
    [918, 735],
    [829, 791],
], dtype=np.int32)

END_ZONE = np.array([
    [905, 597],
    [972, 559],
    [1127, 590],
    [1060, 635],
], dtype=np.int32)