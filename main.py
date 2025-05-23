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
from typing import Dict, List

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Game states
EMPTY = " "
X = "X"
O = "O"

# Store active games: {chat_id: game_data}
games = {}
# Store game invitations: {chat_id: {'message_id': int, 'host': int}}
invitations = {}

class TicTacToeGame:
    def __init__(self, player1: int, player2: int):
        self.board = [EMPTY] * 9
        self.players = {X: player1, O: player2}
        self.current_player = X
        self.winner = None
        self.draw = False
        self.message_id = None
    
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
    await update.message.reply_text("Hi! I'm a Tic Tac Toe bot. Use /play to start a game in this group!")

async def play(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Create a game invitation."""
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username or update.message.from_user.first_name

    # Check if user is already in a game
    if chat_id in games and (user_id == games[chat_id].players[X] or user_id == games[chat_id].players[O]):
        await update.message.reply_text("You're already in a game! Use the surrender button below the game to exit.")
        return

    # Create invitation
    keyboard = [
        [InlineKeyboardButton("🎮 Join Game", callback_data=f"join_{user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = await update.message.reply_text(
        f"🎲 {username} wants to play Tic Tac Toe!\n\nClick 'Join Game' to play against them!",
        reply_markup=reply_markup
    )

    invitations[chat_id] = {
        'message_id': message.message_id,
        'host': user_id
    }

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button clicks (join game, cancel, moves, surrender)."""
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    data = query.data

    # Handle game invitations
    if data.startswith("join_"):
        host_id = int(data.split("_")[1])
        
        if chat_id not in invitations or invitations[chat_id]['host'] != host_id:
            await query.answer("This invitation is no longer valid.", show_alert=True)
            return
            
        if user_id == host_id:
            await query.answer("You can't play against yourself!", show_alert=True)
            return
            
        # Remove invitation
        del invitations[chat_id]
        
        # Create game
        games[chat_id] = TicTacToeGame(host_id, user_id)
        
        # Get player names
        host_name = (await context.bot.get_chat_member(chat_id, host_id)).user.mention_html()
        player_name = (await context.bot.get_chat_member(chat_id, user_id)).user.mention_html()
        
        # Edit original message to show game started
        await query.edit_message_text(
            text=f"Game started!\n\n{X}: {host_name}\n{O}: {player_name}\n\nIt's {X}'s turn!",
            reply_markup=create_game_markup(games[chat_id].board)
        )
        
        games[chat_id].message_id = query.message.message_id
        return
    
    elif data.startswith("cancel_"):
        host_id = int(data.split("_")[1])
        
        if chat_id in invitations and invitations[chat_id]['host'] == host_id and user_id == host_id:
            del invitations[chat_id]
            await query.edit_message_text("Game invitation cancelled.")
            return
    
    # Handle game moves if we're not in an invitation
    if chat_id not in games:
        return
    
    game = games[chat_id]
    
    # Handle surrender
    if data == "surrender":
        if user_id not in game.players.values():
            await query.answer("You're not in this game!", show_alert=True)
            return
            
        # Determine winner
        winner_id = game.players[O] if user_id == game.players[X] else game.players[X]
        winner_name = (await context.bot.get_chat_member(chat_id, winner_id)).user.mention_html()
        
        # End game
        del games[chat_id]
        
        await query.edit_message_text(
            text=f"Game surrendered! {winner_name} wins by default!",
            reply_markup=None
        )
        return
    
    # Handle move
    try:
        position = int(data.split("_")[1])
    except (IndexError, ValueError):
        logger.error(f"Invalid callback data: {data}")
        return
    
    # Check if it's the user's turn
    if user_id != game.players[game.current_player]:
        await query.answer("It's not your turn!", show_alert=True)
        return
    
    # Make move
    if not game.make_move(position):
        await query.answer("Invalid move!", show_alert=True)
        return
    
    # Update game message
    player1_name = (await context.bot.get_chat_member(chat_id, game.players[X])).user.mention_html()
    player2_name = (await context.bot.get_chat_member(chat_id, game.players[O])).user.mention_html()
    
    if game.winner:
        winner_name = player1_name if game.winner == X else player2_name
        text = f"Game over!\n\n{X}: {player1_name}\n{O}: {player2_name}\n\nWinner: {winner_name}!"
        del games[chat_id]
        markup = None
    elif game.draw:
        text = f"Game over!\n\n{X}: {player1_name}\n{O}: {player2_name}\n\nIt's a draw!"
        del games[chat_id]
        markup = None
    else:
        current_player_name = player1_name if game.current_player == X else player2_name
        text = f"Game in progress!\n\n{X}: {player1_name}\n{O}: {player2_name}\n\nIt's {game.current_player}'s turn ({current_player_name})!"
        markup = create_game_markup(game.board)
    
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=markup,
        )
    except Exception as e:
        logger.error(f"Error editing message: {e}")

def create_game_markup(board: List[str]) -> InlineKeyboardMarkup:
    """Create an inline keyboard markup for the current board state with surrender button."""
    keyboard = []
    
    for i in range(0, 9, 3):
        row = []
        for j in range(3):
            position = i + j
            row.append(InlineKeyboardButton(board[position], callback_data=f"move_{position}"))
        keyboard.append(row)
    
    # Add surrender button row
    keyboard.append([InlineKeyboardButton("🚩 Surrender", callback_data="surrender")])
    
    return InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    help_text = """
    🎮 Tic Tac Toe Bot Commands:
    
    /play - Create a game invitation
    /help - Show this help message
    
    How to play:
    1. Use /play to create a game invitation
    2. Another player clicks "Join Game" on your invitation
    3. Players take turns clicking the board
    4. First to get 3 in a row wins!
    5. Click 🚩 Surrender to quit the game
    """
    await update.message.reply_text(help_text)

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
            
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=token,
            webhook_url=f"{webhook_url}/{token}"
        )
    else:
        # Polling mode for local development
        application.run_polling()

if __name__ == "__main__":
    main()
