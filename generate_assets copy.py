#!/usr/bin/env python3
from PIL import Image, ImageDraw, ImageFont
import os
import math

# Ensure output directories exist
os.makedirs('res/mipmap-mdpi', exist_ok=True)
os.makedirs('assets', exist_ok=True)

# 1. Create app icon (64x64)
img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Draw bird body (yellow circle)
draw.ellipse([(12, 18), (48, 54)], fill='#FFD700', outline='#FFA500', width=3)

# Draw wing
draw.ellipse([(32, 28), (52, 44)], fill='#FFA500', outline='#FF8C00', width=2)

# Draw eye
draw.ellipse([(20, 24), (30, 34)], fill='#FFFFFF', outline='#000000', width=2)
draw.ellipse([(23, 27), (27, 31)], fill='#000000')

# Draw beak
beak = [(32, 36), (46, 36), (39, 42)]
draw.polygon(beak, fill='#FF6B35', outline='#D84315', width=1)

img.save('res/mipmap-mdpi/icon_64x64.png', 'PNG', optimize=True)
print("Icon saved: res/mipmap-mdpi/icon_64x64.png")

# 2. Create bird sprite (32x32)
bird = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
draw = ImageDraw.Draw(bird)

# Draw bird body
draw.ellipse([(4, 6), (28, 30)], fill='#FFD700', outline='#FFA500', width=2)

# Draw wing
draw.ellipse([(16, 12), (28, 22)], fill='#FFA500', outline='#FF8C00', width=1)

# Draw eye
draw.ellipse([(8, 10), (14, 16)], fill='#FFFFFF', outline='#000000', width=1)
draw.ellipse([(10, 12), (12, 14)], fill='#000000')

# Draw beak
beak = [(18, 18), (26, 18), (22, 22)]
draw.polygon(beak, fill='#FF6B35', outline='#D84315', width=1)

bird.save('assets/bird.png', 'PNG', optimize=True)
print("Bird sprite saved: assets/bird.png")

# 2b. Create fire bird sprite (32x32) - for beating highscore
fire_bird = Image.new('RGBA', (32, 32), (0, 0, 0, 0))
draw = ImageDraw.Draw(fire_bird)

# Draw bird body
draw.ellipse([(4, 6), (28, 30)], fill="#FFD700", outline="#FFA500", width=2)

# Draw wing
draw.ellipse([(16, 12), (28, 22)], fill="#FFA500", outline="#FF8C00", width=1)

# Draw eye
draw.ellipse([(8, 10), (14, 16)], fill="#FFFFFF", outline="#000000", width=1)
draw.ellipse([(10, 12), (12, 14)], fill="#000000")

# Draw beak
beak = [(18, 18), (26, 18), (22, 22)]
draw.polygon(beak, fill="#FF6B35", outline="#D84315", width=1)


# Draw crown (3 points on top of head)
crown_color = '#FFD700'  # Gold

# Middle crown point (tallest)
crown_mid = [(15, 2), (13, 8), (17, 8)]
draw.polygon(crown_mid, fill=crown_color, outline='#FF8C00', width=1)

# Left crown point
crown_left = [(11, 4), (9, 8), (13, 8)]
draw.polygon(crown_left, fill=crown_color, outline='#FF8C00', width=1)

# Right crown point
crown_right = [(19, 4), (17, 8), (21, 8)]
draw.polygon(crown_right, fill=crown_color, outline='#FF8C00', width=1)

fire_bird.save('assets/fire_bird.png', 'PNG', optimize=True)
print("Fire bird sprite saved: assets/fire_bird.png (with crown!)")

# 3. Create pipe sprite (40x200)
pipe = Image.new('RGBA', (40, 200), (0, 0, 0, 0))
draw = ImageDraw.Draw(pipe)

# Pipe body
draw.rectangle([(4, 10), (36, 200)], fill='#5CB85C', outline='#449D44', width=2)

# Pipe cap
draw.rectangle([(0, 0), (40, 12)], fill='#5CB85C', outline='#449D44', width=2)

# Add some shading/detail
draw.rectangle([(8, 12), (10, 200)], fill='#78C878')
draw.rectangle([(30, 12), (32, 200)], fill='#449D44')

pipe.save('assets/pipe.png', 'PNG', optimize=True)
print("Pipe sprite saved: assets/pipe.png")

# Create flipped pipe for top pipes
pipe_flipped = pipe.transpose(Image.FLIP_TOP_BOTTOM)
pipe_flipped.save('assets/pipe_top.png', 'PNG', optimize=True)
print("Flipped pipe sprite saved: assets/pipe_top.png")

# 4. Create wave sprite (tileable pattern)
def create_wave_tile(
    width=32,
    height=32,
    water_color='#1E90FF',  # DodgerBlue
    crest_color='#FFFFFF'
):
    """
    Create a tileable water wave pattern.
    """
    wave = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(wave)

    # Path for the wave crest
    crest_path = []
    for x in range(width + 1):
        # Sine wave for the crest
        y = height / 2 + (height / 5) * math.sin(2 * math.pi * x / width)
        crest_path.append((x, y))

    # Polygon for the filled wave body
    wave_poly = crest_path + [(width, height), (0, height)]

    # Draw the water body
    draw.polygon(wave_poly, fill=water_color)

    # Draw the wave crest line on top for highlight
    draw.line(crest_path, fill=crest_color, width=2)
    
    return wave

# Generate wave with default settings
wave = create_wave_tile(
    width=64,
    height=32,
)

wave.save('assets/wave.png', 'PNG', optimize=True)
print(f"Wave sprite saved: assets/wave.png ({wave.width}x{wave.height} tileable)")

# 5. Create cloud sprite (for parallax scrolling)
def create_cloud(width=50, height=25):
    """Create a simple cloud shape"""
    cloud = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cloud)

    # Draw overlapping circles to create cloud shape
    center_y = height // 2

    # Left puff
    draw.ellipse([(0, center_y - 8), (20, center_y + 12)], fill='#FFFFFF')
    # Middle puff (larger)
    draw.ellipse([(12, center_y - 12), (38, center_y + 16)], fill='#FFFFFF')
    # Right puff
    draw.ellipse([(30, center_y - 8), (width, center_y + 12)], fill='#FFFFFF')

    return cloud

cloud = create_cloud(width=50, height=25)
cloud.save('assets/cloud.png', 'PNG', optimize=True)
print(f"Cloud sprite saved: assets/cloud.png ({cloud.width}x{cloud.height})")

# # 6. Create background (320x240)
# bg = Image.new('RGB', (320, 240), '#87CEEB')  # Sky blue
# draw = ImageDraw.Draw(bg)

# # Add some clouds
# for x, y in [(40, 30), (120, 50), (200, 35), (280, 45)]:
#     draw.ellipse([(x-20, y-10), (x+20, y+10)], fill='#FFFFFF')
#     draw.ellipse([(x-15, y-5), (x+15, y+15)], fill='#FFFFFF')
#     draw.ellipse([(x-10, y-8), (x+25, y+12)], fill='#FFFFFF')

# bg.save('assets/background.png', 'PNG', optimize=True)
# print("Background saved: assets/background.png")

print("\nAll assets generated successfully!")
