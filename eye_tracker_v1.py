import pygame
import sys
import math
import time
import ctypes
import os
from pylsl import StreamInfo, StreamOutlet, local_clock

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
    info = StreamInfo('EyeTrackerMarkers', 'Markers', 1, 0, 'string', 'eyetracker_marker_stream')
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
        if (time.time() - start_time) > timeout:
            print("Timeout: LabRecorder did not connect.")
            return False
        time.sleep(0.2)

CONSTANT_SPEED = 700
CENTER_HOLD = 3.0
RADIUS = 25
REPEAT_CYCLES = 5

INITIAL_WAIT = True
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

    monitor_handles = []
    MonitorEnumProc = ctypes.WINFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_double)
    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        monitor_handles.append(hMonitor)
        return 1
    ctypes.windll.user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(callback), 0)

    if monitor_index >= len(monitor_handles):
        print(f"Monitor index {monitor_index} out of range, using primary monitor")
        monitor_index = 0

    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    ctypes.windll.user32.GetMonitorInfoW(monitor_handles[monitor_index], ctypes.byref(mi))
    x_offset = mi.rcMonitor.left
    y_offset = mi.rcMonitor.top
    width = mi.rcMonitor.right - mi.rcMonitor.left
    height = mi.rcMonitor.bottom - mi.rcMonitor.top

    return x_offset, y_offset, width, height

def wait_for_start_click(screen, font):
    screen.fill((0, 0, 0))
    button_rect = pygame.Rect(0, 0, 300, 100)
    button_rect.center = screen.get_rect().center
    pygame.draw.rect(screen, (0, 200, 0), button_rect)
    text = font.render("START", True, (255, 255, 255))
    screen.blit(text, (button_rect.centerx - text.get_width()//2,
                       button_rect.centery - text.get_height()//2))
    pygame.display.flip()

    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if button_rect.collidepoint(event.pos):
                    waiting = False

def move_to_position(screen, clock, marker_outlet, current_x, current_y, target_x, target_y, radius, speed, marker_name):
    send_marker(marker_outlet, marker_name)
    
    global INITIAL_WAIT
    if INITIAL_WAIT:
        wait_start = time.time()
        while time.time() - wait_start < 2.0:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()

            screen.fill((0, 0, 0))
            pygame.draw.circle(screen, (38, 120, 228), (int(current_x), int(current_y)), radius)
            pygame.display.flip()
            clock.tick(240)

        INITIAL_WAIT = False
    distance = math.hypot(target_x - current_x, target_y - current_y)
    if distance == 0:
        return target_x, target_y
    move_duration = distance / speed
    move_start = time.time()
    start_pos_x, start_pos_y = current_x, current_y
    while True:
        elapsed = time.time() - move_start
        progress = min(elapsed / move_duration, 1.0)
        x = start_pos_x + (target_x - start_pos_x) * progress
        y = start_pos_y + (target_y - start_pos_y) * progress

        for event in pygame.event.get():
            if event.type == pygame.QUIT: pygame.quit(); sys.exit()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit(); sys.exit()
        
        screen.fill((0, 0, 0))
        pygame.draw.circle(screen, (38, 120, 228), (int(x), int(y)), radius)
        pygame.display.flip()
        clock.tick(240)

        if progress >= 1.0:
            return target_x, target_y

def run_experiment(monitor_index=0):
    marker_outlet = create_lsl_marker_stream()
    if not wait_for_labrecorder_connection(marker_outlet, 120):
        print("Experiment NOT started because LabRecorder is not recording.")
        return

    x_offset, y_offset, WIDTH, HEIGHT = get_monitor_geometry(monitor_index)
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x_offset},{y_offset}"

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.NOFRAME | pygame.DOUBLEBUF)
    pygame.display.set_caption("Eye Movement Experiment")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 60)

    wait_for_start_click(screen, font)

    start_x = WIDTH // 2
    start_y = HEIGHT // 2
    current_x = start_x
    current_y = start_y


    for repeat in range(REPEAT_CYCLES):

        horizontal_positions = [
            ("Left", (RADIUS*2, start_y)),
            ("Right", (WIDTH - RADIUS*2, start_y)),
            ("Left", (RADIUS*2, start_y)),
            ("Right", (WIDTH - RADIUS*2, start_y)),
        ]
        for dir_name, (tx, ty) in horizontal_positions:
            current_x, current_y = move_to_position(screen, clock, marker_outlet, current_x, current_y, tx, ty, RADIUS, CONSTANT_SPEED, f"Move-{dir_name}")

        current_x, current_y = move_to_position(screen, clock, marker_outlet, current_x, current_y, start_x, start_y, RADIUS, CONSTANT_SPEED, "ReturnToCenter-Horizontal")
        hold_start = time.time()
        send_marker(marker_outlet, "HoldCenter-AfterHorizontal")
        while time.time() - hold_start < CENTER_HOLD:
            for event in pygame.event.get():
                if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    pygame.quit(); sys.exit()
            screen.fill((0, 0, 0))
            pygame.draw.circle(screen, (38, 120, 228), (start_x, start_y), RADIUS)
            pygame.display.flip()
            clock.tick(240)

        vertical_positions = [
            ("Up", (start_x, RADIUS*2)),
            ("Down", (start_x, HEIGHT - RADIUS*2)),
            ("Up", (start_x, RADIUS*2)),
            ("Down", (start_x, HEIGHT - RADIUS*2)),
        ]
        for dir_name, (tx, ty) in vertical_positions:
            current_x, current_y = move_to_position(screen, clock, marker_outlet, current_x, current_y, tx, ty, RADIUS, CONSTANT_SPEED, f"Move-{dir_name}")

        current_x, current_y = move_to_position(screen, clock, marker_outlet, current_x, current_y, start_x, start_y, RADIUS, CONSTANT_SPEED, "ReturnToCenter-Vertical")
        if repeat < REPEAT_CYCLES - 1:
            hold_start = time.time()
            send_marker(marker_outlet, "HoldCenter-BeforeNextRepeat")
            while time.time() - hold_start < CENTER_HOLD:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: pygame.quit(); sys.exit()
                    if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                        pygame.quit(); sys.exit()
                screen.fill((0, 0, 0))
                pygame.draw.circle(screen, (38, 120, 228), (start_x, start_y), RADIUS)
                pygame.display.flip()
                clock.tick(240)

    send_marker(marker_outlet, "ExperimentEnd")
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    run_experiment(monitor_index=1)
