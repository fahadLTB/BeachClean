import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Snake with Keyboard", layout="centered")
st.title("🐍 Snake Game (Keyboard Controls)")

game_html = """
<!DOCTYPE html>
<html>
<head>
  <style>
    canvas { background: #eef; display: block; margin: auto; }
    #scoreBoard { text-align: center; font-size: 20px; margin: 10px; font-family: Arial, sans-serif; }
    #restartBtn { display: block; margin: auto; padding: 8px 16px; font-size: 16px; cursor: pointer; }
  </style>
</head>
<body>
<div id="scoreBoard">Score: 0</div>
<canvas id="gameCanvas" width="400" height="400"></canvas>
<button id="restartBtn">Restart Game</button>

<script>
const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");
const scoreBoard = document.getElementById("scoreBoard");
const restartBtn = document.getElementById("restartBtn");

const box = 20;
let snake, direction, food, score, game;

function initGame() {
  snake = [{x: 9*box, y: 10*box}];
  direction = "RIGHT";
  food = {
    x: Math.floor(Math.random()*19+1)*box,
    y: Math.floor(Math.random()*19+1)*box
  };
  score = 0;
  scoreBoard.innerText = "Score: " + score;
  if (game) clearInterval(game);
  game = setInterval(draw, 120);
}

document.addEventListener("keydown", dir);
function dir(event){
  if(event.keyCode == 37 && direction != "RIGHT") direction = "LEFT";
  else if(event.keyCode == 38 && direction != "DOWN") direction = "UP";
  else if(event.keyCode == 39 && direction != "LEFT") direction = "RIGHT";
  else if(event.keyCode == 40 && direction != "UP") direction = "DOWN";
}

function draw(){
  ctx.fillStyle = "#eef";
  ctx.fillRect(0, 0, 400, 400);

  for(let i=0; i<snake.length; i++){
    ctx.fillStyle = (i==0)? "green" : "lightgreen";
    ctx.fillRect(snake[i].x, snake[i].y, box, box);
    ctx.strokeStyle = "white";
    ctx.strokeRect(snake[i].x, snake[i].y, box, box);
  }

  ctx.fillStyle = "red";
  ctx.fillRect(food.x, food.y, box, box);

  let snakeX = snake[0].x;
  let snakeY = snake[0].y;

  if(direction == "LEFT") snakeX -= box;
  if(direction == "UP") snakeY -= box;
  if(direction == "RIGHT") snakeX += box;
  if(direction == "DOWN") snakeY += box;

  if(snakeX == food.x && snakeY == food.y){
    score++;
    scoreBoard.innerText = "Score: " + score;
    food = {
      x: Math.floor(Math.random()*19+1)*box,
      y: Math.floor(Math.random()*19+1)*box
    };
  } else {
    snake.pop();
  }

  let newHead = {x: snakeX, y: snakeY};

  if(snakeX < 0 || snakeY < 0 || snakeX >= 400 || snakeY >= 400 ||
     snake.some(s => s.x == newHead.x && s.y == newHead.y)){
    clearInterval(game);
    alert("Game Over! Final Score: " + score);
    return;
  }

  snake.unshift(newHead);

  ctx.fillStyle = "black";
  ctx.font = "20px Arial";
  ctx.fillText("Score: " + score, 300, 20);
}

restartBtn.addEventListener("click", initGame);

// start first game
initGame();
</script>
</body>
</html>
"""

components.html(game_html, height=500)
