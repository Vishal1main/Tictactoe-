import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("7666132298:AAGKkh3e9j1dcGniY_0tiOiiUtRYJi10fQg")

games = {}  # Stores ongoing games: {(chat_id, player1_id, player2_id): board}

def create_keyboard(board, chat_id, player1, player2):
    keyboard = []
    for i in range(0, 9, 3):
        row = [
            InlineKeyboardButton(board[i+j] or ' ', callback_data=f"{chat_id}:{player1}:{player2}:move_{i+j}")
            for j in range(3)
        ]
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def check_winner(board):
    wins = [(0,1,2), (3,4,5), (6,7,8),
            (0,3,6), (1,4,7), (2,5,8),
            (0,4,8), (2,4,6)]
    for a,b,c in wins:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if all(board):
        return "Draw"
    return None

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    message = await update.message.reply_text("Waiting for second player to join... (Click the button below)",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Game", callback_data=f"{chat_id}:{user_id}:join")]
        ])
    )

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    chat_id, player1 = int(data[0]), int(data[1])
    player2 = query.from_user.id

    if player1 == player2:
        await query.edit_message_text("You can't play with yourself.")
        return

    board = [None] * 9
    games[(chat_id, player1, player2)] = {"board": board, "turn": player1}
    keyboard = create_keyboard(board, chat_id, player1, player2)
    await query.edit_message_text(f"Game started!\nPlayer 1: {player1}\nPlayer 2: {player2}\nPlayer {player1}'s turn (X)",
                                  reply_markup=keyboard)

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    chat_id = int(data[0])
    player1 = int(data[1])
    player2 = int(data[2])
    move_index = int(data[3].split("_")[1])

    key = (chat_id, player1, player2)
    reverse_key = (chat_id, player2, player1)
    game = games.get(key) or games.get(reverse_key)

    if not game:
        await query.edit_message_text("Game not found or expired.")
        return

    user_id = query.from_user.id
    if user_id != game["turn"]:
        await query.answer("Not your turn!", show_alert=True)
        return

    if game["board"][move_index] is not None:
        await query.answer("Invalid move!", show_alert=True)
        return

    symbol = 'X' if user_id == player1 else 'O'
    game["board"][move_index] = symbol
    game["turn"] = player2 if user_id == player1 else player1

    winner = check_winner(game["board"])
    if winner:
        text = f"Game Over! Winner: {winner}" if winner != "Draw" else "Game Draw!"
        await query.edit_message_text(text)
        games.pop(key, None)
        games.pop(reverse_key, None)
    else:
        keyboard = create_keyboard(game["board"], chat_id, player1, player2)
        await query.edit_message_text(f"Player {game['turn']}'s turn ({'X' if game['turn']==player1 else 'O'})",
                                      reply_markup=keyboard)

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("tictactoe", start_game))
    app.add_handler(CallbackQueryHandler(join_game, pattern=r"^\d+:\d+:join$"))
    app.add_handler(CallbackQueryHandler(handle_move, pattern=r"^\d+:\d+:\d+:move_\d$"))

    app.run_polling()
