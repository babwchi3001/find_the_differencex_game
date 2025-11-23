import pygame
import sys
import math
import asyncio
from idun_guardian_client import GuardianClient, GuardianAPI
from idun_guardian_client.igeb_utils import stop_rec


EXPERIMENT = "EyeTracker"
LED_SLEEP = False
SENDING_TIMEOUT = 2
BI_DIRECTIONAL_TIMEOUT = 20
recording_started_event = asyncio.Event()

async def start_idun_recording():
    bci = GuardianClient(debug=True, cloud_enabled=True)

    print("Searching for IDUN earbuds...")
    bci.address = await bci.search_device()
    print("Device found:", bci.address)

    # Create the recording task
    recording_task = asyncio.create_task(
        bci.start_recording(
            experiment="EyeTracker",
            led_sleep=False,
            sending_timout=2,
            bi_directional_receiving_timeout=20,
        )
    )

    # Wait until BLE actually connects
    while not bci.guardian_ble.connection_established:
        await asyncio.sleep(0.1)

    # Retrieve the recording ID AFTER the internal start
    bci.recording_id = bci.guardian_api.guardian_rec.recordingID
    print("Recording ID:", bci.recording_id)

    return bci, recording_task




async def stop_idun_recording(bci):
    print("Stopping recording...")

    # 1) Stop the recording
    stop_rec(
        device_id=bci.address,
        recording_id=bci.recording_id,
    )

    print("Recording stopped. Downloading data...")

    # 2) Download & extract CSV data
    api = GuardianAPI()
    api.download_recording_by_id(
        device_id=bci.guardian_ble.mac_id,
        recording_id=bci.recording_id,
    )

    print("CSV export complete.")

async def run_experiment():

    # ------------------------------------------------------
    # 1) Start IDUN recording in the BACKGROUND
    # ------------------------------------------------------
    #bci, idun_task = await start_idun_recording()

    # Give BLE 2 seconds to connect before starting pygame

    # ------------------------------------------------------
    # 2) Start Pygame window + dot movement
    # ------------------------------------------------------
    pygame.init()

    info = pygame.display.Info()
    WIDTH, HEIGHT = info.current_w, info.current_h

    # Create borderless fullscreen window
    screen = pygame.display.set_mode(
        (WIDTH, HEIGHT),
        pygame.NOFRAME | pygame.DOUBLEBUF
    )
    pygame.display.set_caption("Advanced Dot Movement")

    clock = pygame.time.Clock()

    # Dot parameters
    start_x = WIDTH // 2
    start_y = HEIGHT // 2
    x = float(start_x)
    y = float(start_y)
    radius = 15
    speed = 5.0

    directions = [
        (1, 0), (-1, 0), (0, 1), (0, -1),
        (1, 1), (-1, 1), (1, -1), (-1, -1),
    ]

    direction_index = 0
    dx, dy = directions[direction_index]

    mode = "MOVING"
    target = None

    def move_towards(px, py, tx, ty, v):
        dx = tx - px
        dy = ty - py
        dist2 = dx*dx + dy*dy
        if dist2 <= v*v:
            return float(tx), float(ty)
        dist = math.sqrt(dist2)
        return px + (dx/dist)*v, py + (dy/dist)*v

    def diagonal_opposite_edge(dx, dy):
        if dx == 1 and dy == 1:  return (0, HEIGHT // 2)
        if dx == -1 and dy == 1: return (WIDTH // 2, 0)
        if dx == 1 and dy == -1: return (WIDTH // 2, HEIGHT)
        if dx == -1 and dy == -1:return (WIDTH, HEIGHT // 2)
        return None

    # ------------------------------------------------------
    # 3) MAIN GAME LOOP
    # ------------------------------------------------------
    running = True
    while running:
        dt = clock.tick(240)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((0, 0, 0))

        if mode == "MOVING":
            x += dx * speed
            y += dy * speed

            if dx == 0 or dy == 0:
                if x-radius <= 0 or x+radius >= WIDTH or y-radius <= 0 or y+radius >= HEIGHT:
                    target = (start_x, start_y)
                    mode = "RETURN_TO_CENTER"
            else:
                if x-radius <= 0 or x+radius >= WIDTH or y-radius <= 0 or y+radius >= HEIGHT:
                    target = diagonal_opposite_edge(dx, dy)
                    mode = "TO_EDGE"

        elif mode == "TO_EDGE":
            x, y = move_towards(x, y, target[0], target[1], speed)
            if (int(x), int(y)) == target:
                target = (start_x, start_y)
                mode = "RETURN_TO_CENTER"

        elif mode == "RETURN_TO_CENTER":
            x, y = move_towards(x, y, start_x, start_y, speed)
            if (int(x), int(y)) == (start_x, start_y):
                if direction_index == len(directions)-1:
                    running = False
                else:
                    direction_index += 1
                    dx, dy = directions[direction_index]
                    mode = "MOVING"

        # Draw dot
        dot_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
        pygame.draw.circle(dot_surf, (255,0,0), (radius, radius), radius)
        screen.blit(dot_surf, (x-radius, y-radius))

        pygame.display.flip()

    pygame.quit()

    # ------------------------------------------------------
    # 4) Pygame ended → Wait for IDUN to finish constructing bci object
    # ------------------------------------------------------
    print("Stopping recording...")


    # ------------------------------------------------------
    # 5) Now stop and download data
    # ------------------------------------------------------
    #stop_idun_recording(bci)
    sys.exit()

if __name__ == "__main__":
    asyncio.run(run_experiment())