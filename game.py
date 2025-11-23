import pygame
import csv
import time
import pandas as pd
from PIL import Image
import os
import datetime

pygame.init()

# --------------------------
# Settings
# --------------------------
SCREEN_WIDTH = 1400
SCREEN_HEIGHT = 700
HIGHLIGHT_RADIUS = 30
IMAGE_SIZE = (600, 600)

LEFT_POS = (50, 50)
RIGHT_POS = (750, 50)

# Folder
IMAGE_FOLDER = "Simple Images"

# --------------------------
# Helper function: load level (images + diff map)
# --------------------------
def load_level(level):
    global left_img, right_img, difference_regions, found
    
    print(f"\n--- Loading level {level} ---")

    left_path = f"{IMAGE_FOLDER}/{level} Left.png"
    right_path = f"{IMAGE_FOLDER}/{level} Right.png"
    csv_path = f"{IMAGE_FOLDER}/{level} diff_map.csv"

    if not os.path.exists(left_path):
        print("No more levels. Game finished.")
        pygame.quit()
        exit()

    # Load original image to get original resolution
    orig_img = Image.open(left_path)
    W_orig, H_orig = orig_img.size

    W_new, H_new = IMAGE_SIZE
    scale_x = W_new / W_orig
    scale_y = H_new / H_orig

    # Load pygame images
    left_img_temp = pygame.image.load(left_path)
    right_img_temp = pygame.image.load(right_path)

    left_img = pygame.transform.scale(left_img_temp, IMAGE_SIZE)
    right_img = pygame.transform.scale(right_img_temp, IMAGE_SIZE)

    # Load CSV
    df = pd.read_csv(csv_path)

    # Scale all coordinates
    difference_regions = []
    for _, row in df.iterrows():
        x_new = int(row["x_coordinate"] * scale_x)
        y_new = int(row["y_coordinate"] * scale_y)
        r_new = int(row["radius"] * scale_x)
        difference_regions.append((x_new, y_new, r_new))

    found = [False] * len(difference_regions)
    print("Loaded differences:", difference_regions)

    return difference_regions


# --------------------------
# Load level 1
# --------------------------
current_level = 1
difference_regions = load_level(current_level)

wrong_clicks = []

# --------------------------
# Logging
# --------------------------
logfile = open("click_log.csv", "w", newline="")
writer = csv.writer(logfile)
writer.writerow(["timestamp", "level", "global_x", "global_y", "correct", "difference_id"])

# --------------------------
# Pygame setup
# --------------------------
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Find The Differences")
font = pygame.font.SysFont(None, 35)

clock = pygame.time.Clock()
running = True

def get_timestamp():
    ts = time.time()
    readable = datetime.datetime.fromtimestamp(ts)
    return readable


def draw_game():
    screen.fill((220, 220, 220))

    screen.blit(left_img, LEFT_POS)
    screen.blit(right_img, RIGHT_POS)

    # Draw found differences using their actual radius
    for i, (cx, cy, r) in enumerate(difference_regions):
        if found[i]:
            # left image
            pygame.draw.circle(
                screen, (0, 255, 0),
                (LEFT_POS[0] + cx, LEFT_POS[1] + cy),
                r, 3
            )

            # right image
            pygame.draw.circle(
                screen, (0, 255, 0),
                (RIGHT_POS[0] + cx, RIGHT_POS[1] + cy),
                r, 3
            )

    text = font.render(f"Level {current_level}   Found: {sum(found)}/{len(difference_regions)}", True, (0, 0, 0))
    screen.blit(text, (50, 660))

    pygame.display.flip()



def check_click(pos):
    global current_level, difference_regions, found

    gx, gy = pos

    # Determine which image was clicked
    if LEFT_POS[0] <= gx <= LEFT_POS[0] + IMAGE_SIZE[0] and LEFT_POS[1] <= gy <= LEFT_POS[1] + IMAGE_SIZE[1]:
        img_offset = LEFT_POS
    elif RIGHT_POS[0] <= gx <= RIGHT_POS[0] + IMAGE_SIZE[0] and RIGHT_POS[1] <= gy <= RIGHT_POS[1] + IMAGE_SIZE[1]:
        img_offset = RIGHT_POS
    else:
        timestamp = get_timestamp()
        writer.writerow([timestamp, current_level, gx, gy, True, i])

        return

    # Convert global -> local image coordinates
    lx = gx - img_offset[0]
    ly = gy - img_offset[1]

    # Check all regions
    for i, (cx, cy, r) in enumerate(difference_regions):
        if not found[i]:
            dist = ((lx - cx)**2 + (ly - cy)**2)**0.5
            if dist <= r:

                found[i] = True
                timestamp = get_timestamp()
                writer.writerow([timestamp, current_level, gx, gy, True, "-"])

                # ---------------------------
                # LAST DIFFERENCE FOUND
                # ---------------------------
                if all(found):
                    draw_game()                  # draw final green circle
                    pygame.display.flip()
                    pygame.time.delay(600)       # small pause

                    current_level += 1
                    load_level(current_level)
                return

    # Wrong click
    timestamp = get_timestamp()
    writer.writerow([timestamp, current_level, gx, gy, False, "-"])




# --------------------------
# MAIN GAME LOOP
# --------------------------
while running:
    clock.tick(60)
    draw_game()

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN:
            check_click(pygame.mouse.get_pos())

pygame.quit()
logfile.close()
