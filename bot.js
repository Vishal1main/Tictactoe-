const TelegramBot = require('node-telegram-bot-api');
const express = require('express');

const token = process.env.TELEGRAM_BOT_TOKEN || 'YOUR_TELEGRAM_BOT_TOKEN';
const port = process.env.PORT || 3000;

const app = express();
const bot = new TelegramBot(token, { polling: true });

app.get('/', (req, res) => res.send('Tic Tac Toe Bot is running!'));
app.listen(port, () => console.log(`Server running on port ${port}`));

// Game data storage
const games = {};          // { gameId: gameData }
const playerGames = {};    // { playerId: gameId }
const waitingPlayers = {}; // { chatId: playerId }

// Generate a random game ID
function generateGameId() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let result = '';
    for (let i = 0; i < 6; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

// Initialize a new game
function initGame(chatId, player1Id, player2Id = null) {
    const gameId = generateGameId();
    const isSinglePlayer = player2Id === null;
    
    games[gameId] = {
        chatId,
        board: Array(9).fill(null),
        players: {
            X: player1Id,
            O: isSinglePlayer ? 'AI' : player2Id
        },
        currentPlayer: 'X',
        isGameActive: true,
        isSinglePlayer,
        messageId: null
    };
    
    playerGames[player1Id] = gameId;
    if (!isSinglePlayer) playerGames[player2Id] = gameId;
    
    return gameId;
}

// Check for winner or draw
function checkWinner(board) {
    const winPatterns = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], // rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], // columns
        [0, 4, 8], [2, 4, 6]             // diagonals
    ];

    for (const pattern of winPatterns) {
        const [a, b, c] = pattern;
        if (board[a] && board[a] === board[b] && board[a] === board[c]) {
            return board[a];
        }
    }

    return board.includes(null) ? null : 'draw';
}

// Generate game board keyboard with game info
function generateBoard(gameId) {
    const game = games[gameId];
    const keyboard = {
        inline_keyboard: []
    };

    // Create 3x3 grid
    for (let row = 0; row < 3; row++) {
        const rowButtons = [];
        for (let col = 0; col < 3; col++) {
            const index = row * 3 + col;
            rowButtons.push({
                text: game.board[index] || ' ',
                callback_data: `${gameId}_${index}`
            });
        }
        keyboard.inline_keyboard.push(rowButtons);
    }

    // Add restart button
    keyboard.inline_keyboard.push([{
        text: 'Restart Game',
        callback_data: `${gameId}_restart`
    }]);

    return keyboard;
}

// Get player display name
async function getPlayerName(playerId) {
    try {
        if (playerId === 'AI') return 'AI';
        const user = await bot.getChatMember(playerId, playerId);
        return user.user.first_name + (user.user.last_name ? ' ' + user.user.last_name : '');
    } catch {
        return 'Player';
    }
}

// Update game message with current status
async function updateGameMessage(gameId) {
    const game = games[gameId];
    if (!game || !game.messageId) return;

    const playerXName = await getPlayerName(game.players.X);
    const playerOName = await getPlayerName(game.players.O);
    const currentPlayerName = game.currentPlayer === 'X' ? playerXName : playerOName;

    const gameInfo = `🎮 Game ${gameId}\n\nX: ${playerXName}\nO: ${playerOName}\n\nIt's ${game.currentPlayer}'s turn (${currentPlayerName})`;

    const keyboard = generateBoard(gameId);

    try {
        await bot.editMessageText(gameInfo, {
            chat_id: game.chatId,
            message_id: game.messageId,
            reply_markup: keyboard
        });
    } catch (error) {
        console.error('Error updating game message:', error);
    }
}

// Handle /start command
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    const menu = {
        inline_keyboard: [
            [{ text: 'Single Player', callback_data: 'single_player' }],
            [{ text: 'Multiplayer', callback_data: 'multiplayer' }]
        ]
    };
    
    bot.sendMessage(chatId, 'Welcome to Tic Tac Toe! Choose game mode:', {
        reply_markup: menu
    });
});

// Handle /play command
bot.onText(/\/play/, (msg) => {
    const chatId = msg.chat.id;
    const menu = {
        inline_keyboard: [
            [{ text: 'Single Player', callback_data: 'single_player' }],
            [{ text: 'Multiplayer', callback_data: 'multiplayer' }]
        ]
    };
    
    bot.sendMessage(chatId, 'Choose game mode:', {
        reply_markup: menu
    });
});

// Handle callback queries
bot.on('callback_query', async (callbackQuery) => {
    const chatId = callbackQuery.message.chat.id;
    const userId = callbackQuery.from.id;
    const data = callbackQuery.data;
    const messageId = callbackQuery.message.message_id;
    
    try {
        // Handle game mode selection
        if (data === 'single_player') {
            if (playerGames[userId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            const gameId = initGame(chatId, userId);
            games[gameId].messageId = messageId;
            
            await updateGameMessage(gameId);
            return;
        }
        
        if (data === 'multiplayer') {
            if (playerGames[userId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            // Check if there's a waiting player in this chat
            if (waitingPlayers[chatId] && waitingPlayers[chatId] !== userId) {
                const player2Id = waitingPlayers[chatId];
                delete waitingPlayers[chatId];
                
                const gameId = initGame(chatId, userId, player2Id);
                games[gameId].messageId = messageId;
                
                await updateGameMessage(gameId);
                await bot.deleteMessage(chatId, messageId);
            } else {
                // No waiting player - add to queue
                waitingPlayers[chatId] = userId;
                
                const joinKeyboard = {
                    inline_keyboard: [
                        [{ text: 'Join Game', callback_data: 'join_game' }]
                    ]
                };
                
                await bot.editMessageText('Waiting for another player to join...', {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: joinKeyboard
                });
            }
            return;
        }
        
        if (data === 'join_game') {
            if (playerGames[userId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            // Check if there's a waiting player in this chat
            if (waitingPlayers[chatId] && waitingPlayers[chatId] !== userId) {
                const player1Id = waitingPlayers[chatId];
                delete waitingPlayers[chatId];
                
                const gameId = initGame(chatId, player1Id, userId);
                games[gameId].messageId = messageId;
                
                await updateGameMessage(gameId);
                await bot.deleteMessage(chatId, messageId);
            } else {
                await bot.answerCallbackQuery(callbackQuery.id, { text: 'No games available to join!' });
            }
            return;
        }
        
        // Handle game moves
        if (data.includes('_')) {
            const [gameId, action] = data.split('_');
            const game = games[gameId];
            
            if (!game || !game.isGameActive) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not found or ended!' });
            }
            
            // Check if it's the player's turn
            const currentPlayerId = game.players[game.currentPlayer];
            if (currentPlayerId !== userId && currentPlayerId !== 'AI') {
                return bot.answerCallbackQuery(callbackQuery.id, { text: "It's not your turn!" });
            }
            
            // Handle restart
            if (action === 'restart') {
                game.board = Array(9).fill(null);
                game.currentPlayer = 'X';
                game.isGameActive = true;
                
                await updateGameMessage(gameId);
                return;
            }
            
            // Handle moves
            const position = parseInt(action);
            if (isNaN(position) || position < 0 || position > 8 || game.board[position]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Invalid move!' });
            }
            
            // Make the move
            game.board[position] = game.currentPlayer;
            
            // Check for winner
            const winner = checkWinner(game.board);
            if (winner) {
                game.isGameActive = false;
                
                const playerXName = await getPlayerName(game.players.X);
                const playerOName = await getPlayerName(game.players.O);
                
                let resultText;
                if (winner === 'draw') {
                    resultText = `🎮 Game ${gameId}\n\nX: ${playerXName}\nO: ${playerOName}\n\nGame ended in a draw!`;
                } else {
                    const winnerName = winner === 'X' ? playerXName : playerOName;
                    resultText = `🎮 Game ${gameId}\n\nX: ${playerXName}\nO: ${playerOName}\n\n${winnerName} (${winner}) wins!`;
                }
                
                const keyboard = generateBoard(gameId);
                
                await bot.editMessageText(resultText, {
                    chat_id: game.chatId,
                    message_id: game.messageId,
                    reply_markup: keyboard
                });
                
                return;
            }
            
            // Switch player
            game.currentPlayer = game.currentPlayer === 'X' ? 'O' : 'X';
            await updateGameMessage(gameId);
            
            // If single player and AI's turn
            if (game.isSinglePlayer && game.currentPlayer === 'O') {
                setTimeout(() => makeAiMove(gameId), 1000);
            }
        }
    } catch (error) {
        console.error('Error handling callback:', error);
        bot.answerCallbackQuery(callbackQuery.id, { text: 'An error occurred!' });
    }
});

// Simple AI move for single player
async function makeAiMove(gameId) {
    const game = games[gameId];
    if (!game || !game.isGameActive || game.currentPlayer !== 'O') return;
    
    // Find empty positions
    const emptyPositions = game.board
        .map((val, idx) => val === null ? idx : null)
        .filter(val => val !== null);
    
    if (emptyPositions.length === 0) return;
    
    // Random move
    const randomIndex = Math.floor(Math.random() * emptyPositions.length);
    const position = emptyPositions[randomIndex];
    
    // Make the move
    game.board[position] = 'O';
    
    // Check for winner
    const winner = checkWinner(game.board);
    if (winner) {
        game.isGameActive = false;
        
        const playerXName = await getPlayerName(game.players.X);
        
        let resultText;
        if (winner === 'draw') {
            resultText = `🎮 Game ${gameId}\n\nX: ${playerXName}\nO: AI\n\nGame ended in a draw!`;
        } else {
            const winnerName = winner === 'X' ? playerXName : 'AI';
            resultText = `🎮 Game ${gameId}\n\nX: ${playerXName}\nO: AI\n\n${winnerName} (${winner}) wins!`;
        }
        
        const keyboard = generateBoard(gameId);
        
        await bot.editMessageText(resultText, {
            chat_id: game.chatId,
            message_id: game.messageId,
            reply_markup: keyboard
        });
        
        return;
    }
    
    // Switch back to player
    game.currentPlayer = 'X';
    await updateGameMessage(gameId);
}

console.log('Tic Tac Toe bot is running...');
