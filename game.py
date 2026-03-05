import pygame
import csv
import time
import pandas as pd
from PIL import Image
import os
import datetime
import ctypes
import threading
import re
from pylsl import StreamInfo, StreamOutlet, StreamInlet, local_clock, resolve_byprop, proc_ALL
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
parser.add_argument(
    "--player_id",
    type=int,
    choices=[1, 2],
    required=True,
    help="Player id for sync (use 1 on one PC and 2 on the other)"
)

args = parser.parse_args()
IMAGE_FOLDER = args.image_folder
PLAYER_ID = args.player_id

# MODE SWITCH:
# - Coop_Images  -> show/merge remote found circles + remote-driven level completion
# - Solo_Images  -> DO NOT listen to remote markers (no circles, no remote completion)
FOLDER_BASE = os.path.basename(os.path.normpath(IMAGE_FOLDER)).lower()
COOP_MODE = (FOLDER_BASE == "coop_images")

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

# Thread sync primitives
found_lock = threading.Lock()
remote_ready_event = threading.Event()
stop_sync_thread = threading.Event()
stop_remote_thread = threading.Event()
sync_thread = None
remote_thread = None
level_complete_event = threading.Event()


# --- Marker outlet (unique per player so other device can subscribe in COOP_MODE) ---
def create_lsl_marker_stream():
    marker_name = "GameMarkers"
    marker_source_id = f"game_markers_p{PLAYER_ID}"
    info = StreamInfo(marker_name, "Markers", 1, 0, "string", marker_source_id)
    outlet = StreamOutlet(info)
    print(f"LSL marker stream created: name={marker_name} source_id={marker_source_id}")
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

# (optional debug) Check marker stream discovery on this machine
print("Looking for marker streams on the network...")
streams = resolve_byprop("name", "GameMarkers", timeout=2)
print("Found:", len(streams))
for s in streams:
    print(" -", s.name(), s.type(), s.source_id(), s.hostname())

if not wait_for_labrecorder_connection(outlet=market_outlet, timeout=120):
    print("Recorder not connected → exiting.")
    pygame.quit()
    exit()

# --- monitor logic unchanged ---
monitor_offsets = [(0, 0)]
if monitor_index > 0:
    monitor_offsets.append((screen_width_primary, 0))
x_offset, y_offset = monitor_offsets[monitor_index]
os.environ["SDL_VIDEO_WINDOW_POS"] = f"{x_offset},{y_offset}"

screen = pygame.display.set_mode(
    (2560, 1440),
    pygame.FULLSCREEN | pygame.SHOWN,
    display=0
)
pygame.display.set_caption("Find The Differences")

# -----------------------------------------------------------------------
# 2-PLAYER START SYNC (GameSync stream)
# -----------------------------------------------------------------------
SYNC_NAME = "GameSync"
SYNC_SOURCE_ID = f"game_sync_p{PLAYER_ID}"
sync_info = StreamInfo(SYNC_NAME, "Markers", 1, 0, "string", SYNC_SOURCE_ID)
sync_outlet = StreamOutlet(sync_info)
sync_inlet = None

sync_outlet.push_sample([f"SYNC_ONLINE:{PLAYER_ID}"], local_clock())
print(f"LSL sync stream created: name={SYNC_NAME} source_id={SYNC_SOURCE_ID}")

# -------------------- Threads --------------------

def sync_listener_thread(other_source_id: str, other_ready_msg: str):
    """
    Background thread: listens for READY from the other device on GameSync.
    Sets remote_ready_event when received.
    """
    inlet = None
    while not stop_sync_thread.is_set():
        try:
            if inlet is None:
                st = resolve_byprop("source_id", other_source_id, timeout=1)
                if st:
                    inlet = StreamInlet(st[0], processing_flags=proc_ALL)
                    inlet.open_stream(timeout=2)
                    print(f"[SYNC-THREAD] Connected to remote sync: source_id={st[0].source_id()} host={st[0].hostname()}")
                else:
                    continue

            sample, _ts = inlet.pull_sample(timeout=0.1)
            if sample is None:
                continue
            if sample[0] == other_ready_msg:
                print(f"[SYNC-THREAD] Remote ready received: {sample[0]}")
                remote_ready_event.set()

        except Exception as e:
            print("[SYNC-THREAD] Error:", repr(e))
            inlet = None
            time.sleep(0.2)


def remote_marker_listener(other_player_id: int):
    """
    COOP MODE ONLY:
    Listen to the other player's GameMarkers stream and update found[] + level completion.
    """
    other_marker_source_id = f"game_markers_p{other_player_id}"
    inlet = None

    # Matches: CorrectDifference-Level{lvl}-ID{idx}-PID{pid}
    pattern = re.compile(r"^CorrectDifference-Level(\d+)-ID(\d+)-PID(\d+)$")

    while not stop_remote_thread.is_set():
        try:
            if inlet is None:
                st = resolve_byprop("source_id", other_marker_source_id, timeout=1)
                if st:
                    inlet = StreamInlet(st[0], processing_flags=proc_ALL)
                    inlet.open_stream(timeout=2)
                    print(f"[REMOTE] Connected to other markers: source_id={st[0].source_id()} host={st[0].hostname()}")
                else:
                    continue

            sample, _ts = inlet.pull_sample(timeout=0.1)
            if sample is None:
                continue

            msg = sample[0]
            m = pattern.match(msg)
            if not m:
                continue

            lvl = int(m.group(1))
            idx = int(m.group(2))
            # pid = int(m.group(3))  # not needed, but parsed

            # Only apply to current local level
            if lvl != current_level:
                continue

            with found_lock:
                if 0 <= idx < len(found) and not found[idx]:
                    found[idx] = True
                    all_done = all(found)
                else:
                    all_done = False

            print(f"[REMOTE] Applied remote found: level={lvl} id={idx}")

            if all_done:
                print(f"[REMOTE] Level complete detected from remote on level {lvl}")
                level_complete_event.set()

        except Exception as e:
            print("[REMOTE] Error:", repr(e))
            inlet = None
            time.sleep(0.2)

# -------------------- Game logic --------------------

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
        send_marker(outlet, "GameFinished")
        pygame.quit()
        exit()

    orig_img = Image.open(left_path)
    W_orig, H_orig = orig_img.size

    screen_width, screen_height = pygame.display.get_surface().get_size()
    IMAGE_SIZE = (int(screen_width * 0.4), int(screen_height * 0.8))
    LEFT_POS = (int(screen_width * 0.05), int(screen_height * 0.1))
    RIGHT_POS = (int(screen_width * 0.55), int(screen_height * 0.1))

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
        r_new = int(row["radius"] * ((scale_x + scale_y) / 2))
        difference_regions.append((x_new, y_new, r_new))

    with found_lock:
        found = [False] * len(difference_regions)

    return difference_regions


def get_timestamp():
    ts = time.time()
    return datetime.datetime.fromtimestamp(ts)


def draw_game():
    screen.fill((220, 220, 220))
    screen.blit(left_img, LEFT_POS)
    screen.blit(right_img, RIGHT_POS)

    with found_lock:
        found_snapshot = found[:]

    for i, (cx, cy, r) in enumerate(difference_regions):
        if i < len(found_snapshot) and found_snapshot[i]:
            pygame.draw.circle(screen, (0, 255, 0), (LEFT_POS[0] + cx, LEFT_POS[1] + cy), r, 3)
            pygame.draw.circle(screen, (0, 255, 0), (RIGHT_POS[0] + cx, RIGHT_POS[1] + cy), r, 3)

    text = font.render(
        f"Level {current_level}   Found: {sum(found_snapshot)}/{len(difference_regions)}",
        True,
        (0, 0, 0)
    )
    screen.blit(text, (50, screen.get_height() - 50))
    pygame.display.flip()


def check_click(outlet, pos):
    global current_level

    gx, gy = pos
    timestamp = get_timestamp()

    if LEFT_POS[0] <= gx <= LEFT_POS[0] + IMAGE_SIZE[0] and LEFT_POS[1] <= gy <= LEFT_POS[1] + IMAGE_SIZE[1]:
        img_offset = LEFT_POS
    elif RIGHT_POS[0] <= gx <= RIGHT_POS[0] + IMAGE_SIZE[0] and RIGHT_POS[1] <= gy <= RIGHT_POS[1] + IMAGE_SIZE[1]:
        img_offset = RIGHT_POS
    else:
        writer.writerow([timestamp, current_level, gx, gy, False, "wrong-click"])
        send_marker(outlet, f"WrongClick-Level{current_level}")
        return

    lx = gx - img_offset[0]
    ly = gy - img_offset[1]

    for i, (cx, cy, r) in enumerate(difference_regions):
        with found_lock:
            already = found[i] if i < len(found) else True
        if already:
            continue

        dist = ((lx - cx) ** 2 + (ly - cy) ** 2) ** 0.5
        if dist <= r:
            with found_lock:
                found[i] = True
                all_done = all(found)

            writer.writerow([timestamp, current_level, gx, gy, True, i])

            # Always send local correct marker (remote will only APPLY it in COOP_MODE)
            send_marker(outlet, f"CorrectDifference-Level{current_level}-ID{i}-PID{PLAYER_ID}")

            if all_done:
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
    """
    BOTH devices must press START.
    Local click sends READY:<PLAYER_ID> on GameSync.
    Remote ready is detected by background thread.
    """
    global sync_thread

    button_rect = pygame.Rect(0, 0, 300, 100)
    button_rect.center = screen.get_rect().center
    status_font = pygame.font.SysFont(None, 40)

    local_ready = False

    other_id = 2 if PLAYER_ID == 1 else 1
    other_source_id = f"game_sync_p{other_id}"
    other_ready_msg = f"READY:{other_id}"

    if sync_thread is None or not sync_thread.is_alive():
        remote_ready_event.clear()
        stop_sync_thread.clear()
        sync_thread = threading.Thread(
            target=sync_listener_thread,
            args=(other_source_id, other_ready_msg),
            daemon=True
        )
        sync_thread.start()

    while True:
        remote_ready = remote_ready_event.is_set()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                stop_sync_thread.set()
                pygame.quit()
                exit()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                stop_sync_thread.set()
                pygame.quit()
                exit()
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if button_rect.collidepoint(event.pos) and not local_ready:
                    local_ready = True
                    out_msg = f"READY:{PLAYER_ID}"
                    sync_outlet.push_sample([out_msg], local_clock())
                    print(f"[SYNC] Sent: {out_msg}")

        screen.fill((30, 30, 30))
        pygame.draw.rect(screen, (0, 120, 0) if local_ready else (0, 200, 0), button_rect)

        text = font.render("START", True, (255, 255, 255))
        screen.blit(
            text,
            (button_rect.centerx - text.get_width() // 2,
             button_rect.centery - text.get_height() // 2)
        )

        status = f"You: {'READY' if local_ready else 'WAIT'}   Other: {'READY' if remote_ready else 'WAIT'}"
        screen.blit(status_font.render(status, True, (255, 255, 255)), (50, 50))

        pygame.display.flip()

        if local_ready and remote_ready:
            return

        clock.tick(60)

# -------------------- Run --------------------

print("MODE:", "COOP" if COOP_MODE else "SOLO")

force_foreground()
wait_for_start_click()

# Start remote marker listener ONLY in COOP_MODE
if COOP_MODE:
    other_id = 2 if PLAYER_ID == 1 else 1
    stop_remote_thread.clear()
    remote_thread = threading.Thread(target=remote_marker_listener, args=(other_id,), daemon=True)
    remote_thread.start()

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

    # Remote-driven level completion ONLY in COOP_MODE
    if COOP_MODE and level_complete_event.is_set():
        level_complete_event.clear()
        draw_game()
        pygame.time.delay(600)
        current_level += 1
        load_level(market_outlet, current_level)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            check_click(market_outlet, pygame.mouse.get_pos())

send_marker(market_outlet, "GameStop")

stop_sync_thread.set()
stop_remote_thread.set()

pygame.quit()
logfile.close()