#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os

# Ensure output directories exist
os.makedirs('res/mipmap-mdpi', exist_ok=True)
os.makedirs('assets', exist_ok=True)

# Cell size for boats (we'll use 40x40 as base unit)
CELL_SIZE = 40

# 1. Create app icon (64x64) - Harbor with rowing boat
img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Water background
draw.rectangle([(0, 0), (64, 64)], fill='#4A90E2')

# Dock/pier on right side
draw.rectangle([(50, 0), (64, 64)], fill='#8B4513', outline='#654321', width=2)

# Player rowing boat (red)
draw.ellipse([(16, 24), (40, 36)], fill='#E74C3C', outline='#C0392B', width=2)
# Oars
draw.line([(20, 30), (12, 26)], fill='#8B4513', width=2)
draw.line([(36, 30), (44, 26)], fill='#8B4513', width=2)

# Small yacht in background (white)
draw.ellipse([(8, 12), (20, 18)], fill='#FFFFFF', outline='#BDC3C7', width=1)

img.save('res/mipmap-mdpi/icon_64x64.png', 'PNG', optimize=True)
print("Icon saved: res/mipmap-mdpi/icon_64x64.png")

# 2. Create water tile (40x40) - animated later in code
water = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(water)

# Base water color with slight gradient
for y in range(CELL_SIZE):
    intensity = int(74 + (y / CELL_SIZE) * 20)  # Gradient from lighter to darker
    color = f'#{intensity:02x}90E2'
    draw.line([(0, y), (CELL_SIZE, y)], fill=color, width=1)

# Add some wave details
draw.arc([(5, 5), (15, 15)], 0, 180, fill='#5FA3E8', width=1)
draw.arc([(25, 15), (35, 25)], 0, 180, fill='#5FA3E8', width=1)
draw.arc([(10, 25), (20, 35)], 0, 180, fill='#3D7CB8', width=1)

water.save('assets/water.png', 'PNG', optimize=True)
print(f"Water tile saved: assets/water.png ({CELL_SIZE}x{CELL_SIZE})")

# 3. Create exit/dock area (40x40)
exit_tile = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(exit_tile)

# Wooden dock/pier
draw.rectangle([(0, 0), (CELL_SIZE, CELL_SIZE)], fill='#8B4513', outline='#654321', width=2)

# Wood planks (horizontal lines)
for y in range(0, CELL_SIZE, 8):
    draw.line([(0, y), (CELL_SIZE, y)], fill='#654321', width=1)

# Arrow pointing out (exit indicator)
arrow_color = '#FFD700'
draw.polygon([(10, 20), (30, 20), (30, 15), (35, 20), (30, 25), (30, 20)], 
             fill=arrow_color, outline='#FFA500', width=1)

exit_tile.save('assets/exit.png', 'PNG', optimize=True)
print(f"Exit tile saved: assets/exit.png ({CELL_SIZE}x{CELL_SIZE})")

# 4. Create player rowing boat (40x40 for 1-cell, 40x80 for 2-cell horizontal)
def create_rowing_boat(width_cells=2, vertical=False):
    """Create the player's rowing boat"""
    if vertical:
        w, h = CELL_SIZE, CELL_SIZE * width_cells
    else:
        w, h = CELL_SIZE * width_cells, CELL_SIZE
    
    boat = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(boat)
    
    # Boat body (red/orange)
    padding = 4
    draw.ellipse([(padding, padding), (w-padding, h-padding)], 
                 fill='#E74C3C', outline='#C0392B', width=2)
    
    # Add rowing oars on sides (if horizontal and 2 cells)
    if not vertical and width_cells == 2:
        # Left oar
        draw.line([(15, h//2), (5, h//2-8)], fill='#8B4513', width=3)
        draw.ellipse([(2, h//2-12), (8, h//2-4)], fill='#D2691E', outline='#8B4513', width=1)
        
        # Right oar
        draw.line([(w-15, h//2), (w-5, h//2-8)], fill='#8B4513', width=3)
        draw.ellipse([(w-8, h//2-12), (w-2, h//2-4)], fill='#D2691E', outline='#8B4513', width=1)
    
    # Add person silhouette in center
    center_x, center_y = w//2, h//2
    draw.ellipse([(center_x-4, center_y-6), (center_x+4, center_y+2)], fill='#2C3E50')
    draw.ellipse([(center_x-3, center_y-10), (center_x+3, center_y-4)], fill='#34495E')
    
    return boat

# Generate player boat variations
player_boat_h2 = create_rowing_boat(2, False)
player_boat_h2.save('assets/player_h2.png', 'PNG', optimize=True)
print(f"Player boat (horizontal 2) saved: assets/player_h2.png ({player_boat_h2.width}x{player_boat_h2.height})")

player_boat_v2 = create_rowing_boat(2, True)
player_boat_v2.save('assets/player_v2.png', 'PNG', optimize=True)
print(f"Player boat (vertical 2) saved: assets/player_v2.png ({player_boat_v2.width}x{player_boat_v2.height})")

player_boat_h3 = create_rowing_boat(3, False)
player_boat_h3.save('assets/player_h3.png', 'PNG', optimize=True)
print(f"Player boat (horizontal 3) saved: assets/player_h3.png ({player_boat_h3.width}x{player_boat_h3.height})")

player_boat_v3 = create_rowing_boat(3, True)
player_boat_v3.save('assets/player_v3.png', 'PNG', optimize=True)
print(f"Player boat (vertical 3) saved: assets/player_v3.png ({player_boat_v3.width}x{player_boat_v3.height})")

# 5. Create yacht sprites (obstacles)
def create_yacht(length_cells=2, vertical=False, color='#FFFFFF', accent='#3498DB'):
    """Create a yacht/sailboat obstacle"""
    if vertical:
        w, h = CELL_SIZE, CELL_SIZE * length_cells
    else:
        w, h = CELL_SIZE * length_cells, CELL_SIZE
    
    yacht = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(yacht)
    
    padding = 4
    
    # Yacht hull
    draw.ellipse([(padding, padding), (w-padding, h-padding)], 
                 fill=color, outline='#BDC3C7', width=2)
    
    # Add colored stripe
    if vertical:
        stripe_y = h // 2 - 3
        draw.rectangle([(padding+2, stripe_y), (w-padding-2, stripe_y+6)], fill=accent)
    else:
        stripe_x = w // 2 - 3
        draw.rectangle([(stripe_x, padding+2), (stripe_x+6, h-padding-2)], fill=accent)
    
    # Add sail/mast indicator (small triangle)
    center_x, center_y = w//2, h//2
    if vertical:
        draw.polygon([(center_x, center_y-8), (center_x-4, center_y), (center_x+4, center_y)], 
                     fill=accent, outline='#2C3E50', width=1)
    else:
        draw.polygon([(center_x-8, center_y), (center_x, center_y-4), (center_x, center_y+4)], 
                     fill=accent, outline='#2C3E50', width=1)
    
    return yacht

# Generate yacht variations (different colors and sizes)
yacht_colors = [
    ('white', '#FFFFFF', '#3498DB'),
    ('blue', '#5DADE2', '#2874A6'),
    ('yellow', '#F9E79F', '#F39C12'),
    ('green', '#82E0AA', '#27AE60'),
    ('pink', '#F8B4D9', '#E91E63'),
]

for size in [2, 3, 4]:
    for name, color, accent in yacht_colors:
        # Horizontal
        yacht_h = create_yacht(size, False, color, accent)
        yacht_h.save(f'assets/yacht_{name}_h{size}.png', 'PNG', optimize=True)
        print(f"Yacht {name} h{size} saved: assets/yacht_{name}_h{size}.png")
        
        # Vertical
        yacht_v = create_yacht(size, True, color, accent)
        yacht_v.save(f'assets/yacht_{name}_v{size}.png', 'PNG', optimize=True)
        print(f"Yacht {name} v{size} saved: assets/yacht_{name}_v{size}.png")

# 6. Create grid border/frame pieces (optional decorative elements)
border = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(border)

# Simple wooden border
draw.rectangle([(0, 0), (CELL_SIZE, CELL_SIZE)], fill='#6F4E37', outline='#4A3320', width=3)

border.save('assets/border.png', 'PNG', optimize=True)
print(f"Border tile saved: assets/border.png ({CELL_SIZE}x{CELL_SIZE})")

# 7. Create button/UI assets
def create_button_icon(icon_type, size=32):
    """Create UI button icons"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    center = size // 2
    
    if icon_type == 'reset':
        # Circular arrow
        draw.arc([(4, 4), (size-4, size-4)], 45, 315, fill='#3498DB', width=3)
        # Arrow head
        draw.polygon([(size-8, 8), (size-4, 4), (size-4, 12)], fill='#3498DB')
    
    elif icon_type == 'new':
        # Plus sign
        draw.rectangle([(center-2, 6), (center+2, size-6)], fill='#27AE60')
        draw.rectangle([(6, center-2), (size-6, center+2)], fill='#27AE60')
    
    elif icon_type == 'settings':
        # Gear icon simplified
        draw.ellipse([(8, 8), (size-8, size-8)], outline='#95A5A6', width=3)
        draw.ellipse([(12, 12), (size-12, size-12)], fill='#95A5A6')
    
    return img

reset_icon = create_button_icon('reset')
reset_icon.save('assets/icon_reset.png', 'PNG', optimize=True)
print("Reset icon saved: assets/icon_reset.png")

new_icon = create_button_icon('new')
new_icon.save('assets/icon_new.png', 'PNG', optimize=True)
print("New game icon saved: assets/icon_new.png")

settings_icon = create_button_icon('settings')
settings_icon.save('assets/icon_settings.png', 'PNG', optimize=True)
print("Settings icon saved: assets/icon_settings.png")

# 8. Create wave animation frames (for animated water)
def create_wave_frame(frame_num, total_frames=4):
    """Create a frame of wave animation"""
    wave = Image.new('RGBA', (CELL_SIZE, CELL_SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wave)
    
    # Transparent - we'll overlay this on water
    offset = int((frame_num / total_frames) * CELL_SIZE)
    
    # Draw wavy line
    for x in range(0, CELL_SIZE, 2):
        y = int(CELL_SIZE // 2 + 3 * math.sin((x + offset) * 0.3))
        if 0 <= y < CELL_SIZE:
            draw.point((x, y), fill='#FFFFFF80')  # Semi-transparent white
    
    return wave

import math

for i in range(4):
    wave = create_wave_frame(i, 4)
    wave.save(f'assets/wave_{i}.png', 'PNG', optimize=True)
    print(f"Wave frame {i} saved: assets/wave_{i}.png")

print("\n" + "="*50)
print("All QuasiBoats assets generated successfully!")
print("="*50)
print("\nGenerated assets:")
print("  - App icon (64x64)")
print("  - Water tile (40x40)")
print("  - Exit/dock tile (40x40)")
print("  - Player rowing boats (2-3 cells, h/v)")
print("  - Yachts in 5 colors (2-4 cells, h/v)")
print("  - Border tile (40x40)")
print("  - UI icons (reset, new, settings)")
print("  - Wave animation frames (4 frames)")
