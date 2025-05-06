import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")  # Set this in Render environment variables
PORT = int(os.environ.get("PORT", 8443))

games = {}  # key = (chat_id, game_id), value = game state
game_id_counter = 0

# Start game with /tictactoe
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global game_id_counter
    chat_id = update.effective_chat.id
    user = update.effective_user

    game_id_counter += 1
    game_key = (chat_id, game_id_counter)
    games[game_key] = {
        "players": [user.id],
        "board": [" "] * 9,
        "turn": None,
        "message_id": None
    }

    join_button = InlineKeyboardMarkup([[InlineKeyboardButton("Join", callback_data=f"join_{chat_id}_{game_id_counter}")]])
    message = await update.message.reply_text(
        f"{user.first_name} started a new Tic Tac Toe game!\nClick 'Join' to play.",
        reply_markup=join_button
    )
    games[game_key]["message_id"] = message.message_id

# Join button handler
async def handle_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, chat_id, game_id = query.data.split("_")
    chat_id = int(chat_id)
    game_id = int(game_id)
    game_key = (chat_id, game_id)
    user = query.from_user

    game = games.get(game_key)
    if not game or len(game["players"]) >= 2:
        await query.edit_message_text("This game is full or no longer exists.")
        return

    if user.id in game["players"]:
        await query.answer("You already joined.")
        return

    game["players"].append(user.id)
    game["turn"] = game["players"][0]

    await query.edit_message_text(f"{user.first_name} joined the game!\n\nLet's begin:")
    await send_board(context.bot, chat_id, game_id)

# Board sender
async def send_board(bot, chat_id, game_id):
    game_key = (chat_id, game_id)
    game = games[game_key]
    board = game["board"]
    turn = game["turn"]

    def symbol(i):
        return board[i] if board[i] != " " else str(i + 1)

    keyboard = [
        [InlineKeyboardButton(symbol(i), callback_data=f"move_{chat_id}_{game_id}_{i}") for i in row]
        for row in [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
    ]

    await bot.send_message(
        chat_id=chat_id,
        text=f"Player {turn}'s turn",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Move handler
async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, chat_id, game_id, cell = query.data.split("_")
    chat_id = int(chat_id)
    game_id = int(game_id)
    cell = int(cell)
    user = query.from_user

    game_key = (chat_id, game_id)
    game = games.get(game_key)

    if not game or len(game["players"]) != 2:
        return

    if user.id != game["turn"]:
        await query.answer("Not your turn!")
        return

    if game["board"][cell] != " ":
        await query.answer("Cell already taken!")
        return

    symbol = "X" if user.id == game["players"][0] else "O"
    game["board"][cell] = symbol
    game["turn"] = game["players"][1] if game["turn"] == game["players"][0] else game["players"][0]

    # Check for win
    b = game["board"]
    wins = [(0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6)]
    for a, b_, c in wins:
        if game["board"][a] == game["board"][b_] == game["board"][c] != " ":
            await query.edit_message_text(f"{user.first_name} wins!")
            del games[game_key]
            return

    if " " not in game["board"]:
        await query.edit_message_text("It's a draw!")
        del games[game_key]
        return

    await send_board(context.bot, chat_id, game_id)

# MAIN
async def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("tictactoe", start_game))
    app.add_handler(CallbackQueryHandler(handle_join, pattern="^join_"))
    app.add_handler(CallbackQueryHandler(handle_move, pattern="^move_"))

    # Webhook setup
    await app.bot.set_webhook("https://your-app-name.onrender.com")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url="https://your-app-name.onrender.com"
    )

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
