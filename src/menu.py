"""A small keyboard menu, separate from the game's round and upgrade state."""

import pygame

from src.background import generate_background
from src.player import Player1, Player2
from src import visual_style as style


# Add a label/action pair here, then handle the action in main.run_application.
MENU_OPTIONS = (('Local Multiplayer', 'multiplayer'), ('Controls', 'controls'), ('Quit', 'quit'))


class MainMenu:
    def __init__(self, size, seed=0):
        self.size = size
        self.selected_index = 0
        self.screen_name = 'main'
        self.background, _ = generate_background(seed, size)
        self.title_font = pygame.font.SysFont(style.MENU_FONT, style.MENU_TITLE_SIZE, bold=True)
        self.option_font = pygame.font.SysFont(style.MENU_FONT, style.MENU_OPTION_SIZE, bold=True)
        self.text_font = pygame.font.SysFont(style.MENU_FONT, style.MENU_TEXT_SIZE)
        # Read the real bindings rather than maintaining a second set of controls.
        players = (Player1(0, 0), Player2(0, 0))
        self.control_rows = []
        for label, action in (('Rotate left', 'left'), ('Rotate right', 'right'),
                              ('Thrust', 'up'), ('Shoot', 'shoot')):
            keys = []
            for player in players:
                key = player.controls[action]
                name = pygame.key.name(key).title()
                if key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
                    name += ' Arrow'
                keys.append(name)
            self.control_rows.append((label, *keys))

    def handle_event(self, event):
        """Return a launch/quit action; keep help navigation inside the menu."""
        if event.type == pygame.QUIT:
            return 'quit'
        if event.type != pygame.KEYDOWN:
            return None
        if self.screen_name == 'controls':
            if event.key == pygame.K_ESCAPE:
                self.screen_name = 'main'
            return None
        if event.key == pygame.K_UP:
            self.selected_index = (self.selected_index - 1) % len(MENU_OPTIONS)
        elif event.key == pygame.K_DOWN:
            self.selected_index = (self.selected_index + 1) % len(MENU_OPTIONS)
        elif event.key == pygame.K_RETURN:
            action = MENU_OPTIONS[self.selected_index][1]
            if action == 'controls':
                self.screen_name = 'controls'
            else:
                return action
        return None

    def draw(self, screen):
        screen.fill('black')
        screen.blit(self.background, (0, 0))
        width, height = self.size
        # Static industrial framing leaves the existing space scenery visible.
        pygame.draw.rect(screen, style.MENU_BORDER, (28, 28, width - 56, height - 56), 1)
        for x in (28, width - 70):
            for y in (28, height - 30):
                pygame.draw.line(screen, style.MENU_ACCENT, (x, y), (x + 42, y), 3)
        if self.screen_name == 'controls':
            self._draw_controls(screen)
        else:
            self._draw_main(screen)

    def _label(self, screen, text, center, color=None, font=None):
        font = self.text_font if font is None else font
        color = style.MENU_TEXT if color is None else color
        label = font.render(text, True, color)
        screen.blit(label, label.get_rect(center=center))

    def _draw_main(self, screen):
        width, height = self.size
        self._label(screen, 'MAYHAM', (width // 2 + 3, 135), style.MENU_SHADOW, self.title_font)
        self._label(screen, 'MAYHAM', (width // 2, 132), font=self.title_font)
        self._label(screen, 'LOCAL TWO-PLAYER ROCKET COMBAT', (width // 2, 208), style.MENU_MUTED)
        pygame.draw.line(screen, style.MENU_BORDER, (width // 2 - 230, 244), (width // 2 + 230, 244))
        gap = 14
        available_height = height - 285 - 120
        button_height = min(64, (available_height - gap * (len(MENU_OPTIONS) - 1)) // len(MENU_OPTIONS))
        for index, (label, _) in enumerate(MENU_OPTIONS):
            rect = pygame.Rect(width // 2 - 240, 285 + index * (button_height + gap), 480, button_height)
            selected = index == self.selected_index
            pygame.draw.rect(screen, style.MENU_PANEL_SELECTED if selected else style.MENU_PANEL, rect)
            pygame.draw.rect(screen, style.MENU_ACCENT if selected else style.MENU_BORDER, rect, 1)
            if selected:
                pygame.draw.rect(screen, style.MENU_ACCENT, (rect.x, rect.y, 5, rect.height))
            self._label(screen, label.upper(), rect.center,
                        style.MENU_ACCENT if selected else style.MENU_TEXT, self.option_font)
        self._label(screen, 'UP / DOWN  select     ENTER  confirm', (width // 2, height - 72), style.MENU_MUTED)

    def _draw_controls(self, screen):
        width, height = self.size
        self._label(screen, 'CONTROLS', (width // 2, 118), font=self.title_font)
        panel = pygame.Rect(80, 200, width - 160, 420)
        pygame.draw.rect(screen, style.MENU_PANEL, panel)
        pygame.draw.rect(screen, style.MENU_BORDER, panel, 1)
        columns = (width // 2 - 280, width // 2, width // 2 + 280)
        self._label(screen, 'ACTION', (columns[0], 230), style.MENU_MUTED)
        self._label(screen, 'PLAYER 1', (columns[1], 230), style.MENU_PLAYER1, self.option_font)
        self._label(screen, 'PLAYER 2', (columns[2], 230), style.MENU_PLAYER2, self.option_font)
        for index, row in enumerate(self.control_rows):
            for column, text in zip(columns, row):
                self._label(screen, text, (column, 278 + index * 34))
        pygame.draw.line(screen, style.MENU_BORDER, (110, 412), (width - 110, 412))
        rules = (
            'Destroy the other rocket to win the round.',
            'Hold thrust to accelerate. Thrust uses fuel; orange cans refill it.',
            'Hold shoot to fire; the weapon has a short cooldown.',
            'Rusty panels break after 3 hits. Red spikes kill on contact.',
            'After a loss, press 1 / 2 / 3 to choose an upgrade.',
            'Upgrades last for this match; each round brings a new arena.',
        )
        for index, text in enumerate(rules):
            self._label(screen, text, (width // 2, 445 + index * 28))
        self._label(screen, 'ESC  return to main menu', (width // 2, height - 56), style.MENU_ACCENT)
