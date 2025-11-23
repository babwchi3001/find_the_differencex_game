import pygame
import sys
import math

pygame.init()

# Window
screen = pygame.display.set_mode(
    (0, 0),
    pygame.FULLSCREEN | pygame.DOUBLEBUF
)
WIDTH, HEIGHT = screen.get_size()
pygame.display.set_caption("Advanced Dot Movement")

clock = pygame.time.Clock()

# Dot parameters
start_x = WIDTH // 2
start_y = HEIGHT // 2
x = float(start_x)
y = float(start_y)
radius = 15
speed = 5.0   # high speed now okay

# Directions: straight + diagonal
directions = [
    (1, 0),
    (-1, 0),
    (0, 1),
    (0, -1),
    (1, 1),
    (-1, 1),
    (1, -1),
    (-1, -1),
]

direction_index = 0
dx, dy = directions[direction_index]

mode = "MOVING"
target = None

# Bulletproof movement (never overshoots)
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

# -------------------- MAIN LOOP --------------------
while True:
    dt = clock.tick(240)   # HIGH FPS for smooth motion

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()

    screen.fill((0, 0, 0))

    # MOVEMENT LOGIC (unchanged)
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
                pygame.quit()
                sys.exit()

            direction_index += 1
            dx, dy = directions[direction_index]
            mode = "MOVING"

    # -------------------- NEW DRAWING CODE (no blur!) --------------------
    dot_surf = pygame.Surface((radius*2, radius*2), pygame.SRCALPHA)
    pygame.draw.circle(dot_surf, (255, 0, 0), (radius, radius), radius)
    screen.blit(dot_surf, (x - radius, y - radius))

    pygame.display.flip()
