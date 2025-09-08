import streamlit as st
import numpy as np
import random
import time
from dataclasses import dataclass
import streamlit.components.v1 as components

@dataclass
class Point:
    r: int
    c: int

def new_food(grid_h, grid_w, occupied):
    candidates = [(r, c) for r in range(grid_h) for c in range(grid_w) if (r, c) not in occupied]
    if not candidates:
        return None
    r, c = random.choice(candidates)
    return Point(r, c)

def draw_board(grid_h, grid_w, snake, food):
    BG = np.array([240, 248, 255], dtype=np.uint8)
    GRID = np.array([220, 230, 240], dtype=np.uint8)
    SNAKE_HEAD = np.array([0, 150, 0], dtype=np.uint8)
    SNAKE_BODY = np.array([40, 200, 40], dtype=np.uint8)
    FOOD = np.array([220, 50, 32], dtype=np.uint8)

    cell_px = st.session_state.cell_px
    img = np.tile(BG, (grid_h * cell_px, grid_w * cell_px, 1))

    for r in range(grid_h):
        img[r * cell_px:(r * cell_px) + 1, :, :] = GRID
    for c in range(grid_w):
        img[:, c * cell_px:(c * cell_px) + 1, :] = GRID

    for i, p in enumerate(snake):
        r0, c0 = p.r * cell_px, p.c * cell_px
        color = SNAKE_HEAD if i == 0 else SNAKE_BODY
        img[r0 + 1:r0 + cell_px - 1, c0 + 1:c0 + cell_px - 1, :] = color

    if food is not None:
        r0, c0 = food.r * cell_px, food.c * cell_px
        img[r0 + 1:r0 + cell_px - 1, c0 + 1:c0 + cell_px - 1, :] = FOOD

    return img

def step(state):
    dir_map = {
        'UP': Point(-1, 0),
        'DOWN': Point(1, 0),
        'LEFT': Point(0, -1),
        'RIGHT': Point(0, 1)
    }
    drc = dir_map[state['direction']]
    head = state['snake'][0]
    new_head = Point(head.r + drc.r, head.c + drc.c)

    if not (0 <= new_head.r < state['grid_h'] and 0 <= new_head.c < state['grid_w']):
        state['running'] = False
        state['game_over'] = True
        return state

    if (new_head.r, new_head.c) in {(p.r, p.c) for p in state['snake']}:
        state['running'] = False
        state['game_over'] = True
        return state

    state['snake'].insert(0, new_head)

    if state['food'] and new_head.r == state['food'].r and new_head.c == state['food'].c:
        state['score'] += 1
        occupied = {(p.r, p.c) for p in state['snake']}
        state['food'] = new_food(state['grid_h'], state['grid_w'], occupied)
    else:
        state['snake'].pop()

    return state

# -------------------------
# Initialize state
# -------------------------
if 'initialized' not in st.session_state:
    st.session_state.initialized = True
    st.session_state.grid_h = 20
    st.session_state.grid_w = 20
    st.session_state.cell_px = 22
    st.session_state.speed_ms = 150
    st.session_state.direction = 'RIGHT'
    st.session_state.running = False
    st.session_state.game_over = False
    st.session_state.score = 0
    mid = Point(st.session_state.grid_h // 2, st.session_state.grid_w // 4)
    st.session_state.snake = [mid, Point(mid.r, mid.c - 1), Point(mid.r, mid.c - 2)]
    occupied = {(p.r, p.c) for p in st.session_state.snake}
    st.session_state.food = new_food(st.session_state.grid_h, st.session_state.grid_w, occupied)

# -------------------------
# Keyboard → hidden input
# -------------------------
components.html(
    """
    <script>
    const streamlitDoc = window.parent.document;
    streamlitDoc.addEventListener("keydown", function(e) {
        let keyMap = {
          "ArrowUp": "UP", "w": "UP",
          "ArrowDown": "DOWN", "s": "DOWN",
          "ArrowLeft": "LEFT", "a": "LEFT",
          "ArrowRight": "RIGHT", "d": "RIGHT"
        };
        let dir = keyMap[e.key];
        if (dir) {
            const input = streamlitDoc.querySelector('input[id="keyboard_input"]');
            if (input) {
                input.value = dir;
                input.dispatchEvent(new Event("input", { bubbles: true }));
            }
        }
    });
    </script>
    """,
    height=0,
)

# Hidden input where JS writes
key_pressed = st.text_input("keyboard", key="keyboard_input", label_visibility="hidden")

# Update direction safely
if key_pressed:
    if key_pressed == "UP" and st.session_state.direction != "DOWN":
        st.session_state.direction = "UP"
    elif key_pressed == "DOWN" and st.session_state.direction != "UP":
        st.session_state.direction = "DOWN"
    elif key_pressed == "LEFT" and st.session_state.direction != "RIGHT":
        st.session_state.direction = "LEFT"
    elif key_pressed == "RIGHT" and st.session_state.direction != "LEFT":
        st.session_state.direction = "RIGHT"

# -------------------------
# UI
# -------------------------
st.title("🐍 Snake with Keyboard Controls")
st.metric("Score", st.session_state.score)

img = draw_board(
    st.session_state.grid_h,
    st.session_state.grid_w,
    st.session_state.snake,
    st.session_state.food,
)
board = st.image(img, clamp=True, use_column_width=True)

if not st.session_state.running and not st.session_state.game_over:
    if st.button("▶️ Start"):
        st.session_state.running = True

if st.session_state.running and not st.session_state.game_over:
    st.session_state = step(st.session_state)
    img = draw_board(
        st.session_state.grid_h,
        st.session_state.grid_w,
        st.session_state.snake,
        st.session_state.food,
    )
    board.image(img, clamp=True, use_column_width=True)
    time.sleep(st.session_state.speed_ms / 1000.0)
    st.rerun()

if st.session_state.game_over:
    st.error("Game Over! Press Restart.")
    if st.button("🔄 Restart"):
        st.session_state.direction = 'RIGHT'
        st.session_state.running = True
        st.session_state.game_over = False
        st.session_state.score = 0
        mid = Point(st.session_state.grid_h // 2, st.session_state.grid_w // 4)
        st.session_state.snake = [mid, Point(mid.r, mid.c - 1), Point(mid.r, mid.c - 2)]
        occupied = {(p.r, p.c) for p in st.session_state.snake}
        st.session_state.food = new_food(st.session_state.grid_h, st.session_state.grid_w, occupied)
        st.rerun()
