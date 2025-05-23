import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    filters,
)
from typing import Dict, List, Tuple
import random

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Game states
EMPTY = " "
X = "X"
O = "O"

# Store active games: {(chat_id, game_id): game_data}
games = {}
# Store game invitations: {chat_id: {'message_id': int, 'host': int, 'game_id': str}}
invitations = {}
# Store player active games: {user_id: (chat_id, game_id)}
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
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "Hi! I'm a Tic Tac Toe bot. Use /play to start a game in this group!",
        parse_mode='HTML'
    )

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a game invitation."""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    # Check if user is already in a game
    if user_id in player_games:
        chat_id_existing, game_id = player_games[user_id]
        if (chat_id_existing, game_id) in games:
            await update.message.reply_text(
                "<b>⚠️ You're already in a game!</b>\n\nUse the surrender button below the game to exit.",
                parse_mode='HTML'
            )
            return

    # Generate unique game ID
    game_id = generate_game_id()
    
    # Create invitation
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
    """Escape HTML special characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks with proper HTML formatted alerts."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data

    # Handle game invitations
    if data.startswith("join_"):
        parts = data.split("_")
        if len(parts) != 3:
            return
            
        host_id = int(parts[1])
        game_id = parts[2]
        
        if chat_id not in invitations or invitations[chat_id]['game_id'] != game_id:
            await query.answer(
                text="<b>⚠️ Game Not Found!</b>\nThis invitation is no longer valid.",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        if user_id == host_id:
            await query.answer(
                text="<b>🤦 You can't play against yourself!</b>",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        if user_id in player_games:
            await query.answer(
                text="<b>⚠️ You're already in another game!</b>",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        # Remove invitation
        del invitations[chat_id]
        
        # Create game
        game_key = (chat_id, game_id)
        games[game_key] = TicTacToeGame(host_id, user_id, game_id)
        
        # Track player games
        player_games[host_id] = (chat_id, game_id)
        player_games[user_id] = (chat_id, game_id)
        
        # Get player names
        host_name = escape_html((await context.bot.get_chat_member(chat_id, host_id)).user.first_name)
        player_name = escape_html((await context.bot.get_chat_member(chat_id, user_id)).user.first_name)
        
        # Edit original message to show game started
        await query.edit_message_text(
            text=f"<b>Game {game_id} started!</b>\n\n<b>{X}:</b> {host_name}\n<b>{O}:</b> {player_name}\n\nIt's <b>{X}'s</b> turn!",
            reply_markup=create_game_markup(games[game_key].board, game_id),
            parse_mode='HTML'
        )
        
        games[game_key].message_id = query.message.message_id
        return
    
    elif data.startswith("cancel_"):
        parts = data.split("_")
        if len(parts) != 3:
            return
            
        host_id = int(parts[1])
        game_id = parts[2]
        
        if (chat_id in invitations and 
            invitations[chat_id]['host'] == host_id and 
            user_id == host_id and
            invitations[chat_id]['game_id'] == game_id):
            
            del invitations[chat_id]
            await query.edit_message_text(
                "<b>❌ Game invitation cancelled.</b>",
                parse_mode='HTML'
            )
            return
    
    # Handle game moves
    if data.startswith("move_"):
        parts = data.split("_")
        if len(parts) != 3:
            return
            
        game_id = parts[2]
        game_key = (chat_id, game_id)
        
        if game_key not in games:
            await query.answer(
                text="<b>⚠️ Game Not Found!</b>\nThis game has already ended.",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        game = games[game_key]
        
        # Check if it's the user's turn with HTML formatted alert
        if user_id != game.players[game.current_player]:
            current_player_name = escape_html((await context.bot.get_chat_member(chat_id, game.players[game.current_player])).user.first_name)
            await query.answer(
                text=f"<b>⏳ Not Your Turn!</b>\n\nIt's <i>{current_player_name}'s</i> turn right now.",
                show_alert=True,
                parse_mode='HTML'
            )
            return
        
        # Make move
        try:
            position = int(parts[1])
            if not game.make_move(position):
                await query.answer(
                    text="<b>❌ Invalid Move!</b>\n\nPlease select an empty square.",
                    show_alert=True,
                    parse_mode='HTML'
                )
                return
        except (IndexError, ValueError):
            logger.error(f"Invalid callback data: {data}")
            return
        
        # Update game message
        await update_game_message(chat_id, game_id, query, context)
        return
    
    # Handle surrender
    elif data.startswith("surrender_"):
        game_id = data.split("_")[1]
        game_key = (chat_id, game_id)
        
        if game_key not in games:
            await query.answer(
                text="<b>⚠️ Game Not Found!</b>\nThis game has already ended.",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        game = games[game_key]
        
        if user_id not in game.players.values():
            await query.answer(
                text="<b>🚫 Access Denied!</b>\n\nYou're not part of this game.",
                show_alert=True,
                parse_mode='HTML'
            )
            return
            
        # Determine winner
        winner_id = game.players[O] if user_id == game.players[X] else game.players[X]
        winner_name = escape_html((await context.bot.get_chat_member(chat_id, winner_id)).user.first_name)
        
        # Clean up
        del games[game_key]
        if user_id in player_games:
            del player_games[user_id]
        if winner_id in player_games:
            del player_games[winner_id]
        
        await query.edit_message_text(
            text=f"<b>🏳️ Game {game_id} surrendered!</b>\n\n<b>🎉 Winner:</b> {winner_name}",
            reply_markup=None,
            parse_mode='HTML'
        )

async def update_game_message(chat_id: int, game_id: str, query, context):
    """Update the game message after a move."""
    game_key = (chat_id, game_id)
    if game_key not in games:
        return
        
    game = games[game_key]
    
    # Get player names
    player1_name = escape_html((await context.bot.get_chat_member(chat_id, game.players[X])).user.first_name)
    player2_name = escape_html((await context.bot.get_chat_member(chat_id, game.players[O])).user.first_name)
    
    if game.winner:
        winner_name = player1_name if game.winner == X else player2_name
        text = (f"<b>🏆 Game {game_id} over!</b>\n\n"
               f"<b>{X}:</b> {player1_name}\n<b>{O}:</b> {player2_name}\n\n"
               f"<b>🎉 Winner:</b> {winner_name}!")
        
        # Clean up
        del games[game_key]
        if game.players[X] in player_games:
            del player_games[game.players[X]]
        if game.players[O] in player_games:
            del player_games[game.players[O]]
            
        markup = None
    elif game.draw:
        text = (f"<b>🤝 Game {game_id} over!</b>\n\n"
               f"<b>{X}:</b> {player1_name}\n<b>{O}:</b> {player2_name}\n\n"
               f"<b>It's a draw!</b>")
        
        # Clean up
        del games[game_key]
        if game.players[X] in player_games:
            del player_games[game.players[X]]
        if game.players[O] in player_games:
            del player_games[game.players[O]]
            
        markup = None
    else:
        current_player_name = player1_name if game.current_player == X else player2_name
        text = (f"<b>🎮 Game {game_id} in progress!</b>\n\n"
               f"<b>{X}:</b> {player1_name}\n<b>{O}:</b> {player2_name}\n\n"
               f"It's <b>{game.current_player}'s</b> turn (<i>{current_player_name}</i>)!")
        markup = create_game_markup(game.board, game_id)
    
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=markup,
            parse_mode='HTML'
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")

def create_game_markup(board: List[str], game_id: str) -> InlineKeyboardMarkup:
    """Create an inline keyboard markup for the current board state with surrender button."""
    keyboard = []
    
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            position = i + j
            row.append(InlineKeyboardButton(board[position], callback_data=f"move_{position}_{game_id}"))
        keyboard.append(row)
    
    # Add surrender button row
    keyboard.append([InlineKeyboardButton("🚩 Surrender", callback_data=f"surrender_{game_id}")])
    
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
<b>🎮 Tic Tac Toe Bot Commands:</b>

<code>/play</code> - Create a game invitation
<code>/help</code> - Show this help message

<b>How to play:</b>
1. Use <code>/play</code> to create a game invitation
2. Another player clicks "Join Game" on your invitation
3. Players take turns clicking the board
4. First to get 3 in a row wins!
5. Click 🚩 <b>Surrender</b> to quit the game

Each game has a unique ID to handle multiple games.
"""
    await update.message.reply_text(help_text, parse_mode='HTML')

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors."""
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

def main() -> None:
    """Run the bot."""
    # Create the Application
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
    
    application = Application.builder().token(token).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("play", play))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CallbackQueryHandler(button_click))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Determine run mode
    if os.getenv("DOCKER_MODE") == "1":
        # Webhook mode for Docker deployment
        port = int(os.environ.get("PORT", 8443))
        webhook_url = os.getenv("WEBHOOK_URL")
        if not webhook_url:
            raise ValueError("WEBHOOK_URL environment variable not set for Docker mode")
            
        # Set up webhook with error handling
        try:
            application.run_webhook(
                listen="0.0.0.0",
                port=port,
                url_path=token,
                webhook_url=f"{webhook_url}/{token}",
                drop_pending_updates=True
            )
        except Exception as e:
            logger.error(f"Webhook setup failed: {e}")
            # Fallback to polling if webhook fails
            application.run_polling()
    else:
        # Polling mode for local development
        application.run_polling()

if __name__ == "__main__":
    main()
