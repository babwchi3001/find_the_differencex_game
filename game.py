import pygame
import csv
import time
import pandas as pd
from PIL import Image
import os
import datetime
import ctypes
from pylsl import StreamInfo, StreamOutlet, local_clock, resolve_byprop
import argparse

pygame.init()
pygame.font.init()

last_lsl_ts = 0
MIN_SPACING = 0.0001


def send_marker(outlet, message):
    global last_lsl_ts
    ts = local_clock()
    if ts <= last_lsl_ts:
        ts = last_lsl_ts + MIN_SPACING
    last_lsl_ts = ts
    outlet.push_sample([message], ts)
    print(f"[LSL] {message} at {ts:.4f}")


parser = argparse.ArgumentParser(description="Find-the-differences experiment")
parser.add_argument(
        "--image_folder",
        type=str,
        default="Simple Images",
        help="Folder containing experiment images"
    )

IMAGE_FOLDER = parser.parse_args().image_folder
left_img = right_img = None
difference_regions = []
found = []

LEFT_POS = (50, 50)
RIGHT_POS = (750, 50)
IMAGE_SIZE = (600, 600)

font = pygame.font.SysFont(None, 50)
clock = pygame.time.Clock()

current_level = 1
screen = None
running = True
logfile = None
writer = None

monitor_index = 1
user32 = ctypes.windll.user32
user32.SetProcessDPIAware()

screen_width_primary = user32.GetSystemMetrics(0)
screen_height_primary = user32.GetSystemMetrics(1)

# --- START LOGIC FIX: Create LSL outlet FIRST (before display/fullscreen) ---
def create_lsl_marker_stream():
    info = StreamInfo('GameMarkers', 'Markers', 1, 0, 'string', 'game_marker_stream')
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

market_outlet = create_lsl_marker_stream()

# (optional debug) Now the stream exists, so resolve_byprop makes sense:
print("Looking for my own stream on the network...")
streams = resolve_byprop('name', 'GameMarkers', timeout=2)
print("Found:", len(streams))
for s in streams:
    print(" -", s.name(), s.type(), s.source_id())

if not wait_for_labrecorder_connection(outlet=market_outlet, timeout=120):
    print("Recorder not connected → exiting.")
    pygame.quit()
    exit()

# --- START LOGIC FIX: set window pos BEFORE set_mode ---
monitor_offsets = [(0, 0)]
if monitor_index > 0:
    monitor_offsets.append((screen_width_primary, 0))
x_offset, y_offset = monitor_offsets[monitor_index]
os.environ['SDL_VIDEO_WINDOW_POS'] = f"{x_offset},{y_offset}"

# now create the window (unchanged otherwise)
screen = pygame.display.set_mode(
    (2560, 1440),
    pygame.FULLSCREEN | pygame.SHOWN, display=0
)
pygame.display.set_caption("Find The Differences")

# --- everything below unchanged ---

def load_level(outlet, level):
    global left_img, right_img, difference_regions, found
    global LEFT_POS, RIGHT_POS, IMAGE_SIZE

    print(f"\n--- Loading level {level} ---")
    send_marker(outlet, f"LevelStart-{level}")

    left_path = f"{IMAGE_FOLDER}/{level} Left.png"
    right_path = f"{IMAGE_FOLDER}/{level} Right.png"
    csv_path = f"{IMAGE_FOLDER}/{level} diff_map.csv"

    if not os.path.exists(left_path):
        print("No more levels. Game finished.")
        send_marker(outlet,"GameFinished")
        pygame.quit()
        exit()

    orig_img = Image.open(left_path)
    W_orig, H_orig = orig_img.size

    screen_width, screen_height = pygame.display.get_surface().get_size()
    IMAGE_SIZE = (int(screen_width*0.4), int(screen_height*0.8))
    LEFT_POS = (int(screen_width*0.05), int(screen_height*0.1))
    RIGHT_POS = (int(screen_width*0.55), int(screen_height*0.1))

    left_img_temp = pygame.image.load(left_path)
    right_img_temp = pygame.image.load(right_path)
    left_img = pygame.transform.scale(left_img_temp, IMAGE_SIZE)
    right_img = pygame.transform.scale(right_img_temp, IMAGE_SIZE)

    df = pd.read_csv(csv_path)
    scale_x = IMAGE_SIZE[0] / int(W_orig)
    scale_y = IMAGE_SIZE[1] / int(H_orig)

    difference_regions = []
    for _, row in df.iterrows():
        x_new = int(row["x_coordinate"] * scale_x)
        y_new = int(row["y_coordinate"] * scale_y)
        r_new = int(row["radius"] * ((scale_x + scale_y)/2))
        difference_regions.append((x_new, y_new, r_new))

    found = [False] * len(difference_regions)
    return difference_regions

def get_timestamp():
    ts = time.time()
    return datetime.datetime.fromtimestamp(ts)

def draw_game():
    screen.fill((220, 220, 220))
    screen.blit(left_img, LEFT_POS)
    screen.blit(right_img, RIGHT_POS)

    for i, (cx, cy, r) in enumerate(difference_regions):
        if found[i]:
            pygame.draw.circle(screen, (0, 255, 0), (LEFT_POS[0] + cx, LEFT_POS[1] + cy), r, 3)
            pygame.draw.circle(screen, (0, 255, 0), (RIGHT_POS[0] + cx, RIGHT_POS[1] + cy), r, 3)

    text = font.render(f"Level {current_level}   Found: {sum(found)}/{len(difference_regions)}", True, (0, 0, 0))
    screen.blit(text, (50, screen.get_height()-50))
    pygame.display.flip()

def check_click(outlet, pos):
    global current_level, difference_regions, found

    gx, gy = pos
    timestamp = get_timestamp()

    if LEFT_POS[0] <= gx <= LEFT_POS[0]+IMAGE_SIZE[0] and LEFT_POS[1] <= gy <= LEFT_POS[1]+IMAGE_SIZE[1]:
        img_offset = LEFT_POS
    elif RIGHT_POS[0] <= gx <= RIGHT_POS[0]+IMAGE_SIZE[0] and RIGHT_POS[1] <= gy <= RIGHT_POS[1]+IMAGE_SIZE[1]:
        img_offset = RIGHT_POS
    else:
        writer.writerow([timestamp, current_level, gx, gy, False, "wrong-click"])
        send_marker(outlet, f"WrongClick-Level{current_level}")
        return

    lx = gx - img_offset[0]
    ly = gy - img_offset[1]

    for i, (cx, cy, r) in enumerate(difference_regions):
        if not found[i]:
            dist = ((lx - cx)**2 + (ly - cy)**2)**0.5
            if dist <= r:
                found[i] = True
                writer.writerow([timestamp, current_level, gx, gy, True, i])
                send_marker(outlet,f"CorrectDifference-Level{current_level}-ID{i}")
                if all(found):
                    draw_game()
                    pygame.time.delay(600)
                    current_level += 1
                    load_level(outlet, current_level)
                return

    writer.writerow([timestamp, current_level, gx, gy, False, "wrong"])
    send_marker(outlet, f"WrongClick-Level{current_level}")

def force_foreground():
    hwnd = pygame.display.get_wm_info()["window"]
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)

def wait_for_start_click():
    screen.fill((30, 30, 30))
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
                exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if button_rect.collidepoint(event.pos):
                    waiting = False

force_foreground()
wait_for_start_click()

current_level = 1
difference_regions = load_level(market_outlet, current_level)
logfile = open("click_log.csv", "w", newline="")
writer = csv.writer(logfile)
writer.writerow(["timestamp", "level", "global_x", "global_y", "correct", "difference_id"])

send_marker(market_outlet, "GameStart")

running = True
while running:
    clock.tick(60)
    draw_game()
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            check_click(market_outlet, pygame.mouse.get_pos())

send_marker(market_outlet, "GameStop")
pygame.quit()
logfile.close()