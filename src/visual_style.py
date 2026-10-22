"""Cosmetic settings only. Block, spike and menu settings are independent.

Background settings stay in background.py. Gameplay values stay in config.py.
"""

# Reinforced steel: patches and grain vary these shades, keeping one metal hue.
METAL_PALETTE = ((61, 72, 82), (69, 80, 90), (76, 87, 97), (55, 66, 76))
METAL_EDGE = (96, 108, 119)
METAL_SHADOW = (28, 35, 43)
METAL_SEAM = (35, 43, 52)
METAL_RIVET = (125, 135, 142)
BLOCK_BORDER = 2
PANEL_SPACING = 48
PATCH_SIZE = (7, 19)
PATCH_SHADE_VARIATION = 12
GRAIN_SPACING = 3
GRAIN_SHADE_VARIATION = 7
SCRATCH_AREA = 450  # One short wear mark per this many square pixels.
RIVET_RADIUS = 1

# Weaker copper cover: recognizable before the first hit.
COVER_PALETTE = ((108, 73, 44), (124, 86, 49), (116, 78, 44), (98, 65, 39))
COVER_EDGE = (157, 113, 66)
COVER_SHADOW = (49, 33, 24)
COVER_SEAM = (65, 43, 29)
COVER_RIVET = (176, 133, 80)
WARNING_AMBER = (188, 139, 54)
WARNING_DARK = (44, 33, 22)
WARNING_HEIGHT = 6
WARNING_SPACING = 12
CRACK_COLOR = (19, 16, 14)
CRACK_EDGE = (179, 126, 70)
EXPOSED_INTERIOR = (35, 29, 25)

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
