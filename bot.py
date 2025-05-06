import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

TOKEN = os.getenv("YOUR_BOT_TOKEN")
PORT = int(os.environ.get("PORT", "8080"))
WEBHOOK_URL = os.getenv("RENDER_EXTERNAL_URL")

games = {}  # key: (chat_id, player1, player2), value: {board, turn}

def create_keyboard(board, chat_id, player1, player2):
    keyboard = []
    for i in range(0, 9, 3):
        row = [
            InlineKeyboardButton(
                board[i + j] or " ",
                callback_data=f"{chat_id}:{player1}:{player2}:move_{i+j}"
            )
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
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Join Game", callback_data=f"join:{chat_id}:{user_id}")]
    ])
    await update.message.reply_text("Waiting for a second player...", reply_markup=keyboard)

async def join_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, chat_id, player1 = query.data.split(":")
    chat_id = int(chat_id)
    player1 = int(player1)
    player2 = query.from_user.id

    if player1 == player2:
        await query.edit_message_text("You can't play with yourself.")
        return

    key = (chat_id, player1, player2)
    board = [None] * 9
    games[key] = {"board": board, "turn": player1}
    markup = create_keyboard(board, chat_id, player1, player2)
    await query.edit_message_text(
        f"Tic Tac Toe Game Started!\nPlayer 1: {player1}\nPlayer 2: {player2}\nPlayer {player1}'s turn (X)",
        reply_markup=markup
    )

async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data.split(":")
    chat_id, player1, player2 = int(data[0]), int(data[1]), int(data[2])
    move_index = int(data[3].split("_")[1])
    key = (chat_id, player1, player2)
    reverse_key = (chat_id, player2, player1)
    game = games.get(key) or games.get(reverse_key)

    if not game:
        await query.edit_message_text("Game not found.")
        return

    user_id = query.from_user.id
    if user_id != game["turn"]:
        await query.answer("It's not your turn!", show_alert=True)
        return

    if game["board"][move_index] is not None:
        await query.answer("Invalid move!", show_alert=True)
        return

    symbol = 'X' if user_id == player1 else 'O'
    game["board"][move_index] = symbol
    game["turn"] = player2 if user_id == player1 else player1

    winner = check_winner(game["board"])
    if winner:
        result = f"Game Over! Winner: {winner}" if winner != "Draw" else "It's a Draw!"
        await query.edit_message_text(result)
        games.pop(key, None)
        games.pop(reverse_key, None)
    else:
        markup = create_keyboard(game["board"], chat_id, player1, player2)
        await query.edit_message_text(
            f"Player {game['turn']}'s turn ({'X' if game['turn']==player1 else 'O'})",
            reply_markup=markup
        )

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("tictactoe", start_game))
    app.add_handler(CallbackQueryHandler(join_game, pattern=r"^join:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(handle_move, pattern=r"^\d+:\d+:\d+:move_\d$"))

    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook/{TOKEN}"
    )
