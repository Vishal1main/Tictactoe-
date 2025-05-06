import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import os

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Bot token from @BotFather
TOKEN = os.getenv("BOT_TOKEN", "7666132298:AAGKkh3e9j1dcGniY_0tiOiiUtRYJi10fQg")  # replace with your token or set in environment

# Game state storage
games = {}  # key = chat_id + player1_id + player2_id (tuple), value = game dict

# Emoji mapping
symbols = {"X": "❌", "O": "⭕", "": "⬜"}

def render_board(board):
    keyboard = []
    for i in range(3):
        row = []
        for j in range(3):
            cell = board[i][j]
            callback_data = f"move_{i}_{j}"
            row.append(InlineKeyboardButton(symbols[cell], callback_data=callback_data))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def create_game(player1_id):
    return {
        "board": [["" for _ in range(3)] for _ in range(3)],
        "turn": "X",
        "players": {"X": player1_id, "O": None},
    }

async def tictactoe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    key = (chat_id, user_id)

    for k in games:
        if k[0] == chat_id and user_id in k:
            await update.message.reply_text("You're already in a game!")
            return

    game = create_game(user_id)
    games[key] = game

    join_button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Game", callback_data=f"join_{user_id}")]
    ])
    await update.message.reply_text("Tic Tac Toe game started! Waiting for opponent...", reply_markup=join_button)

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, host_id = data.split("_")
    host_id = int(host_id)
    joiner_id = query.from_user.id
    chat_id = query.message.chat.id
    key = (chat_id, host_id)

    if key not in games:
        await query.edit_message_text("Game not found or already started.")
        return

    if games[key]["players"]["O"]:
        await query.edit_message_text("Game already has two players.")
        return

    if joiner_id == host_id:
        await query.answer("You can't join your own game.")
        return

    games[key]["players"]["O"] = joiner_id
    await query.edit_message_text("Game started!")

    board_markup = render_board(games[key]["board"])
    await context.bot.send_message(chat_id, f"Game started between X (ID: {host_id}) and O (ID: {joiner_id}). X's turn!", reply_markup=board_markup)

def check_winner(board):
    for row in board:
        if row[0] != "" and row[0] == row[1] == row[2]:
            return row[0]
    for col in range(3):
        if board[0][col] != "" and board[0][col] == board[1][col] == board[2][col]:
            return board[0][col]
    if board[0][0] != "" and board[0][0] == board[1][1] == board[2][2]:
        return board[0][0]
    if board[0][2] != "" and board[0][2] == board[1][1] == board[2][0]:
        return board[0][2]
    return None

def is_draw(board):
    return all(cell != "" for row in board for cell in row)

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _, i, j = data.split("_")
    i, j = int(i), int(j)

    chat_id = query.message.chat.id
    user_id = query.from_user.id

    # Find the game this user belongs to in this chat
    for key, game in games.items():
        if key[0] == chat_id and user_id in key:
            break
    else:
        await query.answer("No game found.")
        return

    board = game["board"]
    turn = game["turn"]
    players = game["players"]

    if players[turn] != user_id:
        await query.answer("It's not your turn.")
        return

    if board[i][j] != "":
        await query.answer("This cell is already taken.")
        return

    board[i][j] = turn
    winner = check_winner(board)

    if winner:
        markup = render_board(board)
        await query.edit_message_text(f"Player {turn} wins!", reply_markup=markup)
        del games[key]
    elif is_draw(board):
        markup = render_board(board)
        await query.edit_message_text("It's a draw!", reply_markup=markup)
        del games[key]
    else:
        game["turn"] = "O" if turn == "X" else "X"
        markup = render_board(board)
        await query.edit_message_text(f"{game['turn']}'s turn", reply_markup=markup)

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("tictactoe", tictactoe))
    app.add_handler(CallbackQueryHandler(join_game, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(handle_move, pattern="^move_"))
    app.run_polling()
