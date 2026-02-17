import pygame
import sys
import math
import time
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


# ---------------------------------------------------------
def create_lsl_marker_stream():
    info = StreamInfo(
        'EyeTrackerMarkers', 'Markers', 1, 0,
        'string', 'eyetracker_marker_stream'
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

        if (time.time() - start_time) > timeout:
            print("Timeout: LabRecorder did not connect.")
            return False

        time.sleep(0.2)

# ---------------------------------------------------------
def run_experiment():

    marker_outlet = create_lsl_marker_stream()

    if not wait_for_labrecorder_connection(marker_outlet, 120):
        print("Experiment NOT started because LabRecorder is not recording.")
        return
    pygame.init()
    info = pygame.display.Info()
    WIDTH, HEIGHT = info.current_w, info.current_h

    screen = pygame.display.set_mode(
        (WIDTH, HEIGHT),
        pygame.NOFRAME | pygame.DOUBLEBUF
    )

    clock = pygame.time.Clock()

    start_x = WIDTH // 2
    start_y = HEIGHT // 2
    x = float(start_x)
    y = float(start_y)

    radius = 15
    speed = 2.0

    directions = [(1, 0), (-1, 0)]
    direction_index = 0
    dx, dy = directions[direction_index]

    experiment_start = local_clock()
    send_marker(marker_outlet, "ExperimentStart")

    running = True
    duration = 60.0 
    mode = "MOVING"

    while running:

        dt = clock.tick(240)

        if (local_clock() - experiment_start) >= duration:
            running = False
            break

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((0, 0, 0))

        if mode == "MOVING":
            x += dx * speed

            if x - radius <= 0 or x + radius >= WIDTH:
                move_name = "Horizontal-Right" if dx == 1 else "Horizontal-Left"
                send_marker(marker_outlet, move_name)

                mode = "RETURN_TO_CENTER"
                target = (start_x, start_y)

        elif mode == "RETURN_TO_CENTER":
            dx_c = target[0] - x
            dy_c = target[1] - y

            dist = math.sqrt(dx_c ** 2 + dy_c ** 2)
            if dist <= speed:
                x = float(start_x)
                y = float(start_y)
                send_marker(marker_outlet, "ReturnedToCenter")

                direction_index = 1 - direction_index
                dx, dy = directions[direction_index]
                mode = "MOVING"
            else:
                x += (dx_c / dist) * speed
                y += (dy_c / dist) * speed

        dot = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(dot, (255, 0, 0), (radius, radius), radius)
        screen.blit(dot, (x - radius, y - radius))

        pygame.display.flip()

    pygame.quit()

    send_marker(marker_outlet, "ExperimentEnd")
    print("Experiment finished.")
    sys.exit()


if __name__ == "__main__":
    run_experiment()
