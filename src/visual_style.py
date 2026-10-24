"""Cosmetic settings only. Block, spike and menu settings are independent.

Background settings stay in background.py. Gameplay values stay in config.py.
"""

# Shared reinforced steel: a dim face gradient, broad wear and scattered grain.
METAL_PALETTE = ((57, 68, 79), (64, 75, 86), (69, 80, 90), (60, 70, 81))
METAL_EDGE = (91, 104, 116)
METAL_SHADOW = (25, 32, 40)
METAL_SEAM = (33, 41, 50)
METAL_RIVET = (112, 124, 134)
METAL_SHADE_VARIATION = 7
BLOCK_BORDER = 2
PANEL_SPACING = 64
METAL_WEAR_SCALE = 24
METAL_WEAR_OPACITY = 12
GRAIN_AREA = 35  # One short, randomly placed grain mark per this many pixels.
GRAIN_SHADE_VARIATION = 4
SCRATCH_AREA = 900
RIVET_RADIUS = 1

# Destructible cover uses the same steel beneath patchy, dark red-brown corrosion.
RUST_PALETTE = ((76, 42, 32), (88, 48, 35), (99, 53, 36),
                (66, 38, 31), (104, 60, 41))
RUST_PATCH_SCALE = 20
RUST_TEXTURE_SCALE = 2  # Paint corrosion at half resolution, then enlarge once.
RUST_THRESHOLD = 140
RUST_ALPHA_SCALE = 5
RUST_MAX_ALPHA = 235
RUST_SEAM_WIDTH = 8
RUST_SEAM_BOOST = 30
RUST_PIT_CHANCE = 0.015
CRACK_COLOR = (15, 17, 19)
CRACK_EDGE = (123, 87, 64)
EXPOSED_INTERIOR = (27, 29, 32)

# Spikes: steel teeth, red tips and a recessed red mounting bed.
SPIKE_BED = (68, 20, 28)
SPIKE_MOUNT = (38, 43, 50)
SPIKE_STEEL = (142, 151, 160)
SPIKE_SHADOW = (73, 82, 94)
SPIKE_RED = (237, 65, 76)
SPIKE_HIGHLIGHT = (255, 143, 143)
SPIKE_SPACING = 16
SPIKE_MOUNT_HEIGHT = 5
SPIKE_EDGE_WIDTH = 1

# Menu: static panels and typography, separate from gameplay HUD settings.
MENU_FONT = 'consolas'
MENU_TITLE_SIZE = 96
MENU_OPTION_SIZE = 30
MENU_TEXT_SIZE = 20
MENU_PANEL = (23, 29, 37)
MENU_PANEL_SELECTED = (38, 49, 60)
MENU_BORDER = (65, 77, 89)
MENU_TEXT = (207, 215, 221)
MENU_MUTED = (132, 146, 160)
MENU_ACCENT = (207, 156, 70)
MENU_SHADOW = (9, 13, 19)
MENU_PLAYER1 = (80, 160, 255)
MENU_PLAYER2 = (255, 90, 90)
