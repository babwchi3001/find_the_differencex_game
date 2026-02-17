import pygame
import sys
import time
import ctypes
import os
from pylsl import StreamInfo, StreamOutlet, local_clock

# --------------------------
# LSL Marker Stream
# --------------------------
last_ts = 0.0
MIN_SPACING = 0.0001

def send_marker(outlet, message):
    global last_ts
    ts = local_clock()
    if ts <= last_ts:
        ts = last_ts + MIN_SPACING
    last_ts = ts
    outlet.push_sample([message], ts)
    print(f"Sent marker: {message} at {ts:.6f}")

def create_lsl_marker_stream():
    info = StreamInfo(
        'EyeTrackerMarkers', 'Markers',
        1, 0, 'string',
        'eyetracker_marker_stream'
    )
    outlet = StreamOutlet(info)
    print("LSL marker stream created.")
    return outlet

def wait_for_labrecorder_connection(outlet, timeout=60):
    print("Waiting for LabRecorder to start recording...")
    start_time = time.time()
    while True:
        if outlet.have_consumers():
            print("LabRecorder connected and recording!")
            return True
        if time.time() - start_time > timeout:
            print("Timeout: LabRecorder did not connect.")
            return False
        time.sleep(0.2)

# --------------------------
# Parameters
# --------------------------
RADIUS = 50
BLINK_INTERVAL = 2.0          # seconds between blinks
BLINK_FLASH_DURATION = 0.50   # white dot duration
NUM_BLINKS = 10               # <<< EXACTLY 10 BLINKS
DOT_BASE_COLOR = (0, 0, 0)

# --------------------------
# Monitor geometry (Windows)
# --------------------------
def get_monitor_geometry(monitor_index=0):
    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long)]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_ulong),
                    ("rcMonitor", RECT),
                    ("rcWork", RECT),
                    ("dwFlags", ctypes.c_ulong)]

    monitors = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(RECT),
        ctypes.c_double
    )

    def callback(hMonitor, hdc, rect, data):
        monitors.append(hMonitor)
        return 1

    ctypes.windll.user32.EnumDisplayMonitors(
        0, 0, MonitorEnumProc(callback), 0
    )

    if monitor_index >= len(monitors):
        monitor_index = 0

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    ctypes.windll.user32.GetMonitorInfoW(monitors[monitor_index], ctypes.byref(mi))

    x = mi.rcMonitor.left
    y = mi.rcMonitor.top
    w = mi.rcMonitor.right - mi.rcMonitor.left
    h = mi.rcMonitor.bottom - mi.rcMonitor.top
    return x, y, w, h

# --------------------------
# Bring pygame window to foreground
# --------------------------
def bring_pygame_to_foreground():
    try:
        hwnd = pygame.display.get_wm_info().get("window")
        if hwnd:
            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
            user32.SetFocus(hwnd)
    except Exception as e:
        print("Foreground focus failed:", e)

# --------------------------
# Start button
# --------------------------
def wait_for_start_click(screen, font):
    screen.fill((0, 0, 0))
    button = pygame.Rect(0, 0, 300, 100)
    button.center = screen.get_rect().center

    pygame.draw.rect(screen, (0, 200, 0), button)
    text = font.render("START", True, (255, 255, 255))
    screen.blit(
        text,
        (button.centerx - text.get_width() // 2,
         button.centery - text.get_height() // 2)
    )
    pygame.display.flip()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if button.collidepoint(event.pos):
                    return

# --------------------------
# Drawing helper
# --------------------------
def draw_dot(screen, x, y, radius, color):
    screen.fill((0, 0, 0))
    pygame.draw.circle(screen, color, (int(x), int(y)), radius)
    pygame.display.flip()

# --------------------------
# Blink-dot routine (10 blinks)
# --------------------------
def run_blink_dot_10x(screen, clock, outlet, cx, cy):
    start = time.time()

    draw_dot(screen, cx, cy, RADIUS, DOT_BASE_COLOR)

    for i in range(1, NUM_BLINKS + 1):
        target_time = start + i * BLINK_INTERVAL

        # wait until scheduled blink time
        while time.time() < target_time:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            clock.tick(240)

        # WHITE DOT + MARKER
        send_marker(outlet, "BlinkDot-ON")
        draw_dot(screen, cx, cy, RADIUS, (255, 255, 255))

        flash_start = time.time()
        while time.time() - flash_start < BLINK_FLASH_DURATION:
            clock.tick(240)

        # BACK TO BASE DOT
        send_marker(outlet, "BlinkDot-OFF")
        draw_dot(screen, cx, cy, RADIUS, DOT_BASE_COLOR)

# --------------------------
# Main experiment
# --------------------------
def run_blink_experiment(monitor_index=1):
    outlet = create_lsl_marker_stream()
    if not wait_for_labrecorder_connection(outlet, 120):
        return

    x, y, W, H = get_monitor_geometry(monitor_index)
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x},{y}"

    pygame.init()
    screen = pygame.display.set_mode((W, H), pygame.NOFRAME | pygame.DOUBLEBUF)
    pygame.display.set_caption("Blink Dot Experiment")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 60)

    bring_pygame_to_foreground()
    wait_for_start_click(screen, font)
    bring_pygame_to_foreground()

    cx, cy = W // 2, H // 2

    send_marker(outlet, "BlinkDotBlock-Start")
    run_blink_dot_10x(screen, clock, outlet, cx, cy)
    send_marker(outlet, "BlinkDotBlock-End")

    send_marker(outlet, "ExperimentEnd")
    pygame.quit()
    sys.exit()

# --------------------------
# Entry point
# --------------------------
if __name__ == "__main__":
    run_blink_experiment(monitor_index=1)
