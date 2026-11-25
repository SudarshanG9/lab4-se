import random
import pygame

WIDTH, HEIGHT, CUBE_W, CUBE_H = 720, 560, 72, 42
SIDE = 21
ROWS, TARGET = 7, 2
HOP_TIME, HOP_HEIGHT = 0.28, 26
CELLS = {(r, c) for r in range(ROWS) for c in range(r + 1)}
DEFAULT_PALETTE = [(90, 160, 220), (190, 120, 70), (100, 210, 140)]
LEVEL_PALETTES = (
    ((60, 10, 10), (200, 80, 20), (255, 200, 50)),  # Fire
    ((10, 30, 60), (30, 120, 200), (180, 230, 255)),  # Ice
    ((20, 10, 40), (140, 20, 200), (230, 80, 255)),  # Neon
    ((40, 25, 10), (120, 80, 30), (210, 175, 90)),  # Earth
    ((80, 10, 40), (220, 60, 120), (255, 180, 210)),  # Candy
    ((5, 40, 60), (10, 140, 160), (80, 230, 220)),  # Ocean
    ((60, 20, 10), (210, 100, 40), (255, 160, 80)),  # Sunset
    ((10, 40, 10), (50, 180, 50), (160, 255, 80)),  # Toxic
)
FLASH_DURATION = 0.5
_flashes = {}  # Maps a completed cell to its remaining flash time.
KEY_HOPS = {pygame.K_LEFT: (-1, -1), pygame.K_UP: (-1, 0), pygame.K_DOWN: (1, 0), pygame.K_RIGHT: (1, 1)}


def cube_palette(level):
    """Return one RGB colour per paint stage, cycling the palettes by level."""
    return list(LEVEL_PALETTES[(level - 1) % len(LEVEL_PALETTES)])


def on_cube_completed(cell):
    """Start a short flash when a cube first reaches its target colour."""
    _flashes[cell] = FLASH_DURATION


def bonus_life_threshold():
    """Award an extra life for each 1,000 points earned."""
    return 1000


def cube_center(row, col):
    return pygame.Vector2(WIDTH / 2 + (col - row / 2) * CUBE_W, 90 + row * CUBE_H)


def neighbors(row, col):
    return [(row - 1, col - 1), (row - 1, col), (row + 1, col), (row + 1, col + 1)]


def shade(color, factor):
    return tuple(int(v * factor) for v in color)


class Hopper:
    def __init__(self, cell):
        self.cell, self.target, self.t, self.fall = cell, None, 0.0, None

    @property
    def busy(self):
        return self.target is not None or self.fall is not None

    def start(self, target):
        self.target, self.t = target, 0.0

    def update(self, dt):
        """Advance the hop; return the landing cell when a hop finishes on the pyramid."""
        if self.fall is not None:
            self.fall += 420 * dt
            return None
        if self.target is None:
            return None
        self.t += dt / HOP_TIME
        if self.t < 1:
            return None
        self.cell, self.target = self.target, None
        if self.cell not in CELLS:
            self.fall = 0.0
            return None
        return self.cell

    def pos(self):
        if self.target is None:
            base = cube_center(*self.cell)
            if self.fall is not None:
                base.y += self.fall
            return base
        start, end = cube_center(*self.cell), cube_center(*self.target)
        point = start.lerp(end, self.t)
        point.y -= HOP_HEIGHT * 4 * self.t * (1 - self.t)
        return point


class Game:
    def __init__(self):
        self.font = pygame.font.Font(None, 26)
        self.level, self.score, self.lives = 1, 0, 3
        self.reset()

    def reset(self, full=True):
        if full:
            self.level, self.score, self.lives = 1, 0, 3
            self.bonus_awarded = 0
        self.stages = {cell: 0 for cell in CELLS}
        _flashes.clear()
        self.state = "play"
        self.respawn()

    def respawn(self):
        self.player = Hopper((0, 0))
        self.coily, self.balls = None, []
        self.coily_timer, self.ball_timer, self.enemy_hop = 3.0, 2.0, 0.0

    def paint(self, cell):
        if cell not in self.stages or self.stages[cell] >= TARGET:
            return
        self.stages[cell] += 1
        self.score += 25
        if self.stages[cell] == TARGET:
            on_cube_completed(cell)

    def hop(self, key):
        if self.state != "play" or self.player.busy:
            return
        delta = KEY_HOPS[key]
        candidate = (self.player.cell[0] + delta[0], self.player.cell[1] + delta[1])
        self.player.start(candidate)

    def move_enemies(self):
        if self.coily and not self.coily.busy:
            options = [n for n in neighbors(*self.coily.cell) if n in CELLS]
            goal = cube_center(*self.player.cell)
            self.coily.start(min(options, key=lambda n: cube_center(*n).distance_squared_to(goal)))
        for ball in self.balls:
            if not ball.busy:
                ball.start((ball.cell[0] + 1, ball.cell[1] + random.randint(0, 1)))

    def lose_life(self):
        self.lives -= 1
        if self.lives <= 0:
            self.state = "lose"
        else:
            self.respawn()

    def award_bonus_lives(self):
        threshold = bonus_life_threshold()
        if threshold:
            earned = self.score // threshold
            if earned > self.bonus_awarded:
                self.lives += earned - self.bonus_awarded
                self.bonus_awarded = earned

    def update(self, dt):
        # Keep fading flashes on the level-clear screen.
        for cell in list(_flashes):
            _flashes[cell] -= dt
            if _flashes[cell] <= 0:
                del _flashes[cell]
        if self.state != "play":
            return
        landed = self.player.update(dt)
        if landed:
            self.paint(landed)
        self.award_bonus_lives()
        if self.player.fall is not None and self.player.fall > 260:
            self.lose_life()
            return
        self.coily_timer -= dt
        if self.coily is None and self.coily_timer <= 0:
            self.coily = Hopper((0, 0))
        self.ball_timer -= dt * 0.25
        if self.ball_timer <= 0:
            self.balls.append(Hopper((0, 0)))
            self.ball_timer = 5.0
        self.enemy_hop -= dt * 0.25
        if self.enemy_hop <= 0:
            self.enemy_hop = 0.35
            self.move_enemies()
        enemies = ([self.coily] if self.coily else []) + self.balls
        for enemy in enemies:
            enemy.update(dt)
        self.balls = [b for b in self.balls if b.fall is None or b.fall < 260]
        if self.player.target is None and self.player.fall is None:
            for enemy in enemies:
                if enemy.fall is None and enemy.pos().distance_to(self.player.pos()) < 26:
                    self.lose_life()
                    return
        if all(stage >= TARGET for stage in self.stages.values()):
            self.score += 500
            self.award_bonus_lives()
            self.state = "win"

    def draw_cube(self, screen, cell, colors):
        cx, cy = cube_center(*cell)
        top = [(cx, cy - CUBE_H / 2), (cx + CUBE_W / 2, cy), (cx, cy + CUBE_H / 2), (cx - CUBE_W / 2, cy)]
        color = colors[self.stages[cell]]
        left = [top[3], top[2], (cx, cy + CUBE_H / 2 + SIDE), (cx - CUBE_W / 2, cy + SIDE)]
        right = [top[1], top[2], (cx, cy + CUBE_H / 2 + SIDE), (cx + CUBE_W / 2, cy + SIDE)]
        pygame.draw.polygon(screen, shade(DEFAULT_PALETTE[0], 0.45), left)
        pygame.draw.polygon(screen, shade(DEFAULT_PALETTE[0], 0.3), right)
        pygame.draw.polygon(screen, color, top)
        pygame.draw.polygon(screen, (240, 240, 240), top, 1)
        if cell in _flashes:
            alpha = int(220 * _flashes[cell] / FLASH_DURATION)
            flash_surf = pygame.Surface((CUBE_W + 2, CUBE_H + 2), pygame.SRCALPHA)
            origin = (cx - CUBE_W / 2, cy - CUBE_H / 2)
            local_top = [(x - origin[0], y - origin[1]) for x, y in top]
            pygame.draw.polygon(flash_surf, (255, 255, 255, alpha), local_top)
            screen.blit(flash_surf, origin)

    def draw(self, screen):
        screen.fill((18, 20, 38))
        colors = cube_palette(self.level) or DEFAULT_PALETTE
        for cell in sorted(CELLS):
            self.draw_cube(screen, cell, colors)
        for enemy in self.balls:
            pygame.draw.circle(screen, (230, 60, 60), enemy.pos() - (0, 12), 9)
        if self.coily:
            pos = self.coily.pos() - (0, 14)
            pygame.draw.circle(screen, (170, 80, 220), pos, 11)
            pygame.draw.circle(screen, (255, 255, 255), pos + (0, -2), 3)
        pos = self.player.pos() - (0, 14)
        pygame.draw.circle(screen, (250, 150, 40), pos, 13)
        pygame.draw.circle(screen, (255, 255, 255), pos + (-5, -3), 3)
        pygame.draw.circle(screen, (255, 255, 255), pos + (5, -3), 3)
        pygame.draw.circle(screen, (250, 90, 40), pos + (0, 6), 5)
        hud = self.font.render(f"Score {self.score}  Lives {self.lives}  Level {self.level}  R = reset", True, (240, 240, 240))
        screen.blit(hud, (10, 8))
        if self.state != "play":
            text = "LEVEL CLEAR! Press Space" if self.state == "win" else "GAME OVER - Press R"
            label = self.font.render(text, True, (255, 255, 120))
            screen.blit(label, label.get_rect(center=(WIDTH // 2, HEIGHT - 40)))


def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Q*bert")
    clock = pygame.time.Clock()
    game = Game()
    running = True
    while running:
        dt = min(clock.tick(60) / 1000, 0.05)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in KEY_HOPS:
                    game.hop(event.key)
                elif event.key == pygame.K_r:
                    game.reset()
                elif event.key == pygame.K_SPACE and game.state == "win":
                    game.level += 1
                    game.reset(full=False)
        game.update(dt)
        game.draw(screen)
        pygame.display.flip()
    pygame.quit()


if __name__ == "__main__":
    main()
