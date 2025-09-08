import streamlit as st
import math
import random
import time
from PIL import Image, ImageDraw

# --- CONFIG ---
WIDTH, HEIGHT = 700, 400
BALL_RADIUS = 8
HOLE_RADIUS = 12
FRICTION = 0.98  # slows the ball until it stops

st.set_page_config(page_title="2D Golf Game", layout="centered")

# --- SESSION STATE ---
if "level" not in st.session_state:
    st.session_state.level = 1
    st.session_state.ball_x = 60
    st.session_state.ball_y = HEIGHT - 40
    st.session_state.hole_x = WIDTH - 100
    st.session_state.hole_y = HEIGHT // 2
    st.session_state.vx = 0
    st.session_state.vy = 0
    st.session_state.in_motion = False
    st.session_state.shot_taken = False
    st.session_state.message = "Aim and take your shot!"

def reset_level():
    st.session_state.ball_x = 60
    st.session_state.ball_y = HEIGHT - 40
    st.session_state.vx = 0
    st.session_state.vy = 0
    st.session_state.in_motion = False
    st.session_state.shot_taken = False
    st.session_state.message = f"Retry Level {st.session_state.level}"

def next_level():
    st.session_state.level += 1
    st.session_state.ball_x = 60
    st.session_state.ball_y = HEIGHT - 40
    st.session_state.vx = 0
    st.session_state.vy = 0
    # Hole appears between 100–150px from the right wall
    st.session_state.hole_x = WIDTH - random.randint(100, 150)
    st.session_state.hole_y = random.randint(80, HEIGHT - 80)
    st.session_state.in_motion = False
    st.session_state.shot_taken = False
    st.session_state.message = f"🏆 Level {st.session_state.level - 1} complete! Now Level {st.session_state.level}"

def draw_scene(angle=0, power=0, show_arrow=True):
    """Draw current scene"""
    img = Image.new("RGB", (WIDTH, HEIGHT), (90, 180, 90))
    draw = ImageDraw.Draw(img)

    # Draw hole
    draw.ellipse(
        (st.session_state.hole_x - HOLE_RADIUS, st.session_state.hole_y - HOLE_RADIUS,
         st.session_state.hole_x + HOLE_RADIUS, st.session_state.hole_y + HOLE_RADIUS),
        fill=(50, 50, 50)
    )

    # Draw ball
    draw.ellipse(
        (st.session_state.ball_x - BALL_RADIUS, st.session_state.ball_y - BALL_RADIUS,
         st.session_state.ball_x + BALL_RADIUS, st.session_state.ball_y + BALL_RADIUS),
        fill=(255, 255, 255), outline=(0, 0, 0)
    )

    # Draw aiming arrow if ball hasn’t been shot
    if show_arrow and not st.session_state.shot_taken:
        rad = math.radians(angle)
        arrow_length = 25 + power * 2
        end_x = st.session_state.ball_x + arrow_length * math.cos(rad)
        end_y = st.session_state.ball_y - arrow_length * math.sin(rad)
        draw.line((st.session_state.ball_x, st.session_state.ball_y, end_x, end_y),
                  fill=(255, 0, 0), width=2)

    # HUD
    draw.text((10, 10), f"Level {st.session_state.level}", fill=(0, 0, 0))
    draw.text((10, 30), st.session_state.message, fill=(0, 0, 0))

    return img

# --- UI ---
st.title("⛳ One-Shot Golf")

power = st.slider("Power", 1, 20, 10)
angle = st.slider("Angle", 0, 90, 45)

col1, col2 = st.columns(2)
with col1:
    if st.button("Hit Ball!"):
        if not st.session_state.shot_taken:
            st.session_state.shot_taken = True
            st.session_state.in_motion = True
            st.session_state.vx = power * math.cos(math.radians(angle))
            st.session_state.vy = -power * math.sin(math.radians(angle))
            st.session_state.message = "Ball in motion..."

with col2:
    if st.button("🔄 Reset Level"):
        reset_level()

# --- Ball Animation ---
ph = st.empty()

if st.session_state.in_motion:
    for _ in range(200):  # simulate frames
        # Update physics (straight-line with friction only)
        st.session_state.ball_x += st.session_state.vx
        st.session_state.ball_y += st.session_state.vy
        st.session_state.vx *= FRICTION
        st.session_state.vy *= FRICTION

        # Draw frame
        img = draw_scene(show_arrow=False)
        ph.image(img, use_container_width=True)

        time.sleep(0.03)

        # Check win
        if math.hypot(st.session_state.ball_x - st.session_state.hole_x,
                      st.session_state.ball_y - st.session_state.hole_y) < HOLE_RADIUS:
            st.session_state.in_motion = False
            next_level()
            break

        # Stop if ball slows down completely
        if abs(st.session_state.vx) < 0.2 and abs(st.session_state.vy) < 0.2:
            st.session_state.in_motion = False
            reset_level()
            break

# --- Static render if not moving ---
if not st.session_state.in_motion:
    img = draw_scene(angle=angle, power=power, show_arrow=True)
    st.image(img, use_container_width=True)
