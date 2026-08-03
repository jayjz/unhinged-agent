import os
from PIL import Image, ImageDraw

# Hardware constraints
WIDTH = 320
HEIGHT = 240
BG_COLOR = (0, 0, 0)        # Pure Black
FG_COLOR = (0, 255, 0)      # Pure Green
LINE_WIDTH = 6

def create_canvas():
    img = Image.new('RGB', (WIDTH, HEIGHT), color=BG_COLOR)
    return img, ImageDraw.Draw(img)

def save_face(img, filename):
    os.makedirs("assets", exist_ok=True)
    filepath = os.path.join("assets", filename)
    img.save(filepath)
    print(f"Generated: {filepath}")

# 1. IDLE (Neutral, waiting)
# Two horizontal lines for eyes, flat line for mouth
img, draw = create_canvas()
draw.line((80, 80, 120, 80), fill=FG_COLOR, width=LINE_WIDTH)   # Left Eye
draw.line((200, 80, 240, 80), fill=FG_COLOR, width=LINE_WIDTH)  # Right Eye
draw.line((100, 160, 220, 160), fill=FG_COLOR, width=LINE_WIDTH) # Mouth
save_face(img, "face_idle.png")

# 2. LISTENING (Attentive, wide eyes, slight smile)
img, draw = create_canvas()
draw.ellipse((80, 70, 120, 110), outline=FG_COLOR, width=LINE_WIDTH)  # Left Eye
draw.ellipse((200, 70, 240, 110), outline=FG_COLOR, width=LINE_WIDTH) # Right Eye
draw.arc((100, 130, 220, 180), start=30, end=150, fill=FG_COLOR, width=LINE_WIDTH) # Smile
save_face(img, "face_listening.png")

# 3. THINKING (Squinting, processing)
# One eye open, one eye flat, mouth is a small 'o'
img, draw = create_canvas()
draw.ellipse((80, 70, 120, 110), outline=FG_COLOR, width=LINE_WIDTH)  # Left Eye (Open)
draw.line((200, 90, 240, 90), fill=FG_COLOR, width=LINE_WIDTH)        # Right Eye (Squint)
draw.ellipse((145, 160, 175, 180), outline=FG_COLOR, width=LINE_WIDTH) # Mouth (Pondering)
save_face(img, "face_thinking.png")

# 4. SPEAKING (Active output)
# Normal eyes, large open mouth
img, draw = create_canvas()
draw.arc((80, 70, 120, 110), start=180, end=360, fill=FG_COLOR, width=LINE_WIDTH)  # Left Eye (Happy)
draw.arc((200, 70, 240, 110), start=180, end=360, fill=FG_COLOR, width=LINE_WIDTH) # Right Eye (Happy)
draw.ellipse((110, 150, 210, 190), outline=FG_COLOR, width=LINE_WIDTH) # Mouth (Open)
save_face(img, "face_speaking.png")

# 5. ERROR (Pipeline failure or network drop)
# X's for eyes, jagged mouth
img, draw = create_canvas()
# Left Eye (X)
draw.line((80, 70, 120, 110), fill=FG_COLOR, width=LINE_WIDTH)
draw.line((120, 70, 80, 110), fill=FG_COLOR, width=LINE_WIDTH)
# Right Eye (X)
draw.line((200, 70, 240, 110), fill=FG_COLOR, width=LINE_WIDTH)
draw.line((240, 70, 200, 110), fill=FG_COLOR, width=LINE_WIDTH)
# Mouth (Zig-Zag)
draw.line((100, 170, 140, 150), fill=FG_COLOR, width=LINE_WIDTH)
draw.line((140, 150, 180, 170), fill=FG_COLOR, width=LINE_WIDTH)
draw.line((180, 170, 220, 150), fill=FG_COLOR, width=LINE_WIDTH)
save_face(img, "face_error.png")