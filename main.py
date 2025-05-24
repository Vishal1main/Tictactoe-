import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)
from typing import Dict, List, Tuple
import random

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Game states
EMPTY = " "
X = "X"
O = "O"

# Game storage
games = {}
invitations = {}
player_games = {}

def generate_game_id() -> str:
    return ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789', k=6))

class TicTacToeGame:
    def __init__(self, player1: int, player2: int, game_id: str):
        self.board = [EMPTY] * 9
        self.players = {X: player1, O: player2}
        self.current_player = X
        self.winner = None
        self.draw = False
        self.message_id = None
        self.game_id = game_id
    
    def make_move(self, position: int) -> bool:
        if position < 0 or position >= 9 or self.board[position] != EMPTY or self.winner is not None:
            return False
        
        self.board[position] = self.current_player
        self.check_winner()
        
        if not self.winner and EMPTY not in self.board:
            self.draw = True
        else:
            self.current_player = O if self.current_player == X else X
        
        return True
    
    def check_winner(self):
        winning_combinations = [
            [0, 1, 2], [3, 4, 5], [6, 7, 8],  # rows
            [0, 3, 6], [1, 4, 7], [2, 5, 8],  # columns
            [0, 4, 8], [2, 4, 6]              # diagonals
        ]
        
        for combo in winning_combinations:
            a, b, c = combo
            if self.board[a] != EMPTY and self.board[a] == self.board[b] == self.board[c]:
                self.winner = self.board[a]
                return

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Hi! I'm a Tic Tac Toe bot. Use /play to start a game in this group!",
        parse_mode='HTML'
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    if user_id in player_games:
        chat_id_existing, game_id = player_games[user_id]
        if (chat_id_existing, game_id) in games:
            await update.message.reply_text(
                "<b>⚠️ You're already in a game!</b>\n\nUse the surrender button below the game to exit.",
                parse_mode='HTML'
            )
            return

    game_id = generate_game_id()
    
    keyboard = [
        [InlineKeyboardButton("🎮 Join Game", callback_data=f"join_{user_id}_{game_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await update.message.reply_text(
        f"<b>🎲 {escape_html(username)} wants to play Tic Tac Toe!</b> (Game ID: <code>{game_id}</code>)\n\n"
        "Click <b>Join Game</b> to play against them!",
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

    invitations[chat_id] = {
        'message_id': message.message_id,
        'host': user_id,
        'game_id': game_id
    }

def escape_html(text: str) -> str:
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data

    if data.startswith("join_"):
        # ... (rest of your existing code remains the same)
        pass
    # ... (keep all other handler functions the same)

def create_game_markup(board: List[str], game_id: str) -> InlineKeyboardMarkup:
    keyboard = []
    
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            position = i + j
            row.append(InlineKeyboardButton(board[position], callback_data=f"move_{position}_{game_id}"))
        keyboard.append(row)
    
    keyboard.append([InlineKeyboardButton("🚩 Surrender", callback_data=f"surrender_{game_id}")])
    
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = """
<b>🎮 Tic Tac Toe Bot Commands:</b>

<code>/play</code> - Create a game invitation
<code>/help</code> - Show this help message

<b>How to play:</b>
1. Use <code>/play</code> to create a game invitation
2. Another player clicks "Join Game" on your invitation
3. Players take turns clicking the board
4. First to get 3 in a row wins!
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

def main() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    
    app = Application.builder().token(token).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("play", play))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_click))
    
    # Koyeb-specific webhook setup
    koyeb_app_name = os.getenv("KOYEB_APP_NAME")
    if koyeb_app_name:
        port = int(os.getenv("PORT", 8000))
        webhook_url = f"https://{koyeb_app_name}.koyeb.app/{token}"
        
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=webhook_url,
            drop_pending_updates=True
        )
    else:
        app.run_polling()

if __name__ == "__main__":
    main()
