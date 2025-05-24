const TelegramBot = require('node-telegram-bot-api');
const express = require('express');

const token = process.env.TELEGRAM_BOT_TOKEN || 'YOUR_TELEGRAM_BOT_TOKEN';
const port = process.env.PORT || 3000;

const app = express();
const bot = new TelegramBot(token, { polling: true });

app.get('/', (req, res) => res.send('Tic Tac Toe Bot is running!'));
app.listen(port, () => console.log(`Server running on port ${port}`));

// Game data storage
const games = {};
const playerGames = {};
const waitingPlayers = []; // Players waiting for a match

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
function initGame(player1Id, player2Id) {
    const gameId = generateGameId();
    
    games[gameId] = {
        board: Array(9).fill(null),
        players: {
            X: player1Id,
            O: player2Id
        },
        currentPlayer: 'X',
        isGameActive: true
    };
    
    playerGames[player1Id] = gameId;
    playerGames[player2Id] = gameId;
    
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

// Generate game board keyboard
function generateBoard(board, gameId) {
    const keyboard = {
        inline_keyboard: []
    };

    // Create 3x3 grid
    for (let row = 0; row < 3; row++) {
        const rowButtons = [];
        for (let col = 0; col < 3; col++) {
            const index = row * 3 + col;
            rowButtons.push({
                text: board[index] || ' ',
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
    const data = callbackQuery.data;
    const messageId = callbackQuery.message.message_id;
    
    try {
        // Handle game mode selection
        if (data === 'single_player') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            const gameId = initGame(chatId, 'AI');
            const game = games[gameId];
            const keyboard = generateBoard(game.board, gameId);
            
            await bot.editMessageText(`Your turn (X)`, {
                chat_id: chatId,
                message_id: messageId,
                reply_markup: keyboard
            });
            return;
        }
        
        if (data === 'multiplayer') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            // Check if there's a waiting player
            if (waitingPlayers.length > 0 && waitingPlayers[0] !== chatId) {
                const player2Id = waitingPlayers.shift();
                const gameId = initGame(chatId, player2Id);
                const game = games[gameId];
                const keyboard = generateBoard(game.board, gameId);
                
                // Notify both players
                await bot.sendMessage(chatId, `Game started! Your turn (X)`, {
                    reply_markup: keyboard
                });
                
                await bot.sendMessage(player2Id, `Game started! Your turn (O)`, {
                    reply_markup: keyboard
                });
                
                await bot.deleteMessage(chatId, messageId);
                await bot.deleteMessage(player2Id, messageId);
            } else {
                // No waiting player - add to queue
                if (!waitingPlayers.includes(chatId)) {
                    waitingPlayers.push(chatId);
                    
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
                } else {
                    await bot.answerCallbackQuery(callbackQuery.id, { text: 'Already waiting for a player!' });
                }
            }
            return;
        }
        
        if (data === 'join_game') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            // Check if there's a waiting player
            if (waitingPlayers.length > 0 && waitingPlayers[0] !== chatId) {
                const player1Id = waitingPlayers.shift();
                const gameId = initGame(player1Id, chatId);
                const game = games[gameId];
                const keyboard = generateBoard(game.board, gameId);
                
                // Notify both players
                await bot.sendMessage(player1Id, `Game started! Your turn (X)`, {
                    reply_markup: keyboard
                });
                
                await bot.sendMessage(chatId, `Game started! Your turn (O)`, {
                    reply_markup: keyboard
                });
                
                await bot.deleteMessage(chatId, messageId);
                await bot.deleteMessage(player1Id, messageId);
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
            if (currentPlayerId !== chatId && currentPlayerId !== 'AI') {
                return bot.answerCallbackQuery(callbackQuery.id, { text: "It's not your turn!" });
            }
            
            // Handle restart
            if (action === 'restart') {
                game.board = Array(9).fill(null);
                game.currentPlayer = 'X';
                game.isGameActive = true;
                
                const keyboard = generateBoard(game.board, gameId);
                const playerX = game.players.X;
                const playerO = game.players.O;
                
                await bot.editMessageText(`Game restarted! Your turn (X)`, {
                    chat_id: playerX,
                    message_id: messageId,
                    reply_markup: keyboard
                });
                
                if (playerO !== 'AI') {
                    await bot.editMessageText(`Game restarted! Opponent's turn (X)`, {
                        chat_id: playerO,
                        message_id: messageId,
                        reply_markup: keyboard
                    });
                }
                
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
                let resultText;
                
                if (winner === 'draw') {
                    resultText = 'Game ended in a draw!';
                } else {
                    const winnerId = game.players[winner];
                    const winnerName = winnerId === 'AI' ? 'AI' : 'You';
                    resultText = `${winnerName} (${winner}) wins!`;
                }
                
                const keyboard = generateBoard(game.board, gameId);
                
                // Update both players' boards
                await bot.editMessageText(resultText, {
                    chat_id: game.players.X,
                    message_id: messageId,
                    reply_markup: keyboard
                });
                
                if (game.players.O !== 'AI') {
                    await bot.editMessageText(resultText, {
                        chat_id: game.players.O,
                        message_id: messageId,
                        reply_markup: keyboard
                    });
                }
                
                return;
            }
            
            // Switch player
            game.currentPlayer = game.currentPlayer === 'X' ? 'O' : 'X';
            
            // Update board
            const keyboard = generateBoard(game.board, gameId);
            const nextPlayerId = game.players[game.currentPlayer];
            
            await bot.editMessageText(`Your turn (${game.currentPlayer})`, {
                chat_id: nextPlayerId,
                message_id: messageId,
                reply_markup: keyboard
            });
            
            // Update other player's board
            const otherPlayerId = game.currentPlayer === 'X' ? game.players.O : game.players.X;
            if (otherPlayerId !== 'AI') {
                await bot.editMessageText(`Opponent's turn (${game.currentPlayer})`, {
                    chat_id: otherPlayerId,
                    message_id: messageId,
                    reply_markup: keyboard
                });
            }
        }
    } catch (error) {
        console.error('Error handling callback:', error);
        bot.answerCallbackQuery(callbackQuery.id, { text: 'An error occurred!' });
    }
});

console.log('Tic Tac Toe bot is running...');
