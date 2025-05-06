from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from collections import defaultdict

# Store games as (chat_id, user_id) => game data
games = {}

# Start a personal game
async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    key = (chat_id, user_id)

    if key in games:
        await update.message.reply_text("Aapka ek game already chal raha hai. Pehle usse complete karein.")
        return

    games[key] = {
        "board": [" "] * 9,
        "turn": "X",
    }
    await update.message.reply_text(
        f"{update.effective_user.first_name}, aapka Tic Tac Toe game start ho gaya hai!",
    )
    await send_board(chat_id, user_id, context)

# Show board to user
async def send_board(chat_id, user_id, context):
    game = games[(chat_id, user_id)]
    board = game["board"]
    keyboard = []

    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            idx = i + j
            mark = board[idx] if board[idx] != " " else str(idx + 1)
            row.append(InlineKeyboardButton(mark, callback_data=f"{chat_id}:{user_id}:move_{idx}"))
        keyboard.append(row)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"Player {game['turn']} ki baari (Only for you):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Handle moves
async def handle_move(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        chat_id, user_id, move_str = query.data.split(":")
        chat_id = int(chat_id)
        user_id = int(user_id)
        move_index = int(move_str.split("_")[1])
    except:
        return

    if query.from_user.id != user_id:
        await query.answer("Yeh aapka game nahi hai.")
        return

    key = (chat_id, user_id)
    if key not in games:
        await query.answer("Koi active game nahi mila.")
        return

    game = games[key]

    if game["board"][move_index] != " ":
        await query.answer("Yeh jagah already bhari hai.")
        return

    game["board"][move_index] = game["turn"]

    winner = check_winner(game["board"])
    if winner:
        await query.edit_message_text(f"Player {winner} jeet gaya! Game over.")
        del games[key]
    elif " " not in game["board"]:
        await query.edit_message_text("Game draw ho gaya!")
        del games[key]
    else:
        game["turn"] = "O" if game["turn"] == "X" else "X"
        await query.delete_message()
        await send_board(chat_id, user_id, context)

# Check win
def check_winner(board):
    win_positions = [(0,1,2), (3,4,5), (6,7,8),
                     (0,3,6), (1,4,7), (2,5,8),
                     (0,4,8), (2,4,6)]
    for i, j, k in win_positions:
        if board[i] == board[j] == board[k] and board[i] != " ":
            return board[i]
    return None

# Main
async def main():
    app = Application.builder().token("7666132298:AAGKkh3e9j1dcGniY_0tiOiiUtRYJi10fQg").build()

    app.add_handler(CommandHandler("tictactoe", start_game))
    app.add_handler(CallbackQueryHandler(handle_move, pattern=r"^\d+:\d+:move_\d$"))

    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
