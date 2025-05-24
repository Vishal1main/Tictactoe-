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
const availableGames = {}; // Games waiting for players

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
function initGame(creatorId) {
    const gameId = generateGameId();
    
    availableGames[gameId] = {
        creatorId,
        creatorName: `🎲 ${creatorId}` // Will be updated with username
    };
    
    return gameId;
}

// Start the actual game when second player joins
function startGame(gameId, joinerId) {
    const creatorId = availableGames[gameId].creatorId;
    const creatorName = availableGames[gameId].creatorName;
    
    games[gameId] = {
        board: Array(9).fill(null),
        players: {
            X: creatorId,
            O: joinerId,
            names: {
                [creatorId]: creatorName,
                [joinerId]: `🎲 ${joinerId}` // Will be updated with username
            }
        },
        currentPlayer: 'X',
        isGameActive: true
    };
    
    playerGames[creatorId] = gameId;
    playerGames[joinerId] = gameId;
    delete availableGames[gameId];
    
    return games[gameId];
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

    // Add surrender button
    keyboard.inline_keyboard.push([{
        text: '🏳️ Surrender',
        callback_data: `${gameId}_surrender`
    }]);

    return keyboard;
}

// End game with surrender
async function handleSurrender(gameId, surrenderingPlayerId) {
    const game = games[gameId];
    if (!game) return;

    game.isGameActive = false;
    
    // Determine winner (opposite player)
    const winnerSymbol = game.players.X === surrenderingPlayerId ? 'O' : 'X';
    const winnerId = game.players[winnerSymbol];
    
    // Get player names
    const winnerName = game.players.names[winnerId] || 'Opponent';
    const loserName = game.players.names[surrenderingPlayerId] || 'You';
    
    const resultText = `${loserName} surrendered! ${winnerName} (${winnerSymbol}) wins!`;
    const keyboard = generateBoard(game.board, gameId);

    // Notify both players
    await bot.sendMessage(game.players.X, resultText, { reply_markup: keyboard });
    await bot.sendMessage(game.players.O, resultText, { reply_markup: keyboard });
    
    // Clean up
    delete playerGames[game.players.X];
    delete playerGames[game.players.O];
    delete games[gameId];
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
    const username = callbackQuery.from.username || 'Player';
    
    try {
        // Handle game mode selection
        if (data === 'single_player') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            const gameId = generateGameId();
            games[gameId] = {
                board: Array(9).fill(null),
                players: {
                    X: chatId,
                    O: 'AI',
                    names: {
                        [chatId]: `🎲 ${username}`
                    }
                },
                currentPlayer: 'X',
                isGameActive: true
            };
            
            playerGames[chatId] = gameId;
            const keyboard = generateBoard(games[gameId].board, gameId);
            
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
            
            const gameId = initGame(chatId);
            availableGames[gameId].creatorName = `🎲 ${username}`;
            
            const joinKeyboard = {
                inline_keyboard: [
                    [{ 
                        text: 'Join Game', 
                        callback_data: `join_${gameId}` 
                    }]
                ]
            };
            
            await bot.editMessageText(
                `${availableGames[gameId].creatorName} wants to play Tic Tac Toe! (Game ID: ${gameId})\n\nClick Join Game to play against them!`, 
                {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: joinKeyboard
                }
            );
            return;
        }
        
        // Handle join game
        if (data.startsWith('join_')) {
            const gameId = data.split('_')[1];
            
            if (!availableGames[gameId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not available!' });
            }
            
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }
            
            if (availableGames[gameId].creatorId === chatId) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: "You can't join your own game!" });
            }
            
            const game = startGame(gameId, chatId);
            game.players.names[chatId] = `🎲 ${username}`;
            
            const keyboard = generateBoard(game.board, gameId);
            
            // Notify both players
            await bot.sendMessage(
                game.players.X, 
                `Game started against ${game.players.names[game.players.O]}! Your turn (X)`, 
                { reply_markup: keyboard }
            );
            
            await bot.sendMessage(
                game.players.O, 
                `Game started against ${game.players.names[game.players.X]}! Waiting for their move (X)`, 
                { reply_markup: keyboard }
            );
            
            return;
        }
        
        // Handle game moves
        if (data.includes('_')) {
            const [gameId, action] = data.split('_');
            
            // Handle surrender
            if (action === 'surrender') {
                if (!games[gameId]) {
                    return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not found!' });
                }
                
                await handleSurrender(gameId, chatId);
                return;
            }
            
            const game = games[gameId];
            
            if (!game || !game.isGameActive) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not found or ended!' });
            }
            
            // Check if it's the player's turn
            const currentPlayerId = game.players[game.currentPlayer];
            if (currentPlayerId !== chatId && currentPlayerId !== 'AI') {
                return bot.answerCallbackQuery(callbackQuery.id, { text: "It's not your turn!" });
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
                    const winnerName = game.players.names[winnerId] || 'Opponent';
                    resultText = `${winnerName} (${winner}) wins!`;
                }
                
                const keyboard = generateBoard(game.board, gameId);
                
                // Update both players' boards
                await bot.sendMessage(game.players.X, resultText, { reply_markup: keyboard });
                if (game.players.O !== 'AI') {
                    await bot.sendMessage(game.players.O, resultText, { reply_markup: keyboard });
                }
                
                // Clean up
                delete playerGames[game.players.X];
                if (game.players.O !== 'AI') delete playerGames[game.players.O];
                delete games[gameId];
                
                return;
            }
            
            // Switch player
            game.currentPlayer = game.currentPlayer === 'X' ? 'O' : 'X';
            
            // Update board
            const keyboard = generateBoard(game.board, gameId);
            const nextPlayerId = game.players[game.currentPlayer];
            
            if (nextPlayerId === 'AI') {
                // AI move
                await bot.sendMessage(game.players.X, `AI is thinking...`, { reply_markup: keyboard });
                
                setTimeout(async () => {
                    // Simple AI move - find first empty spot
                    const emptyIndex = game.board.findIndex(cell => cell === null);
                    if (emptyIndex !== -1) {
                        game.board[emptyIndex] = 'O';
                        
                        // Check if AI won
                        const winner = checkWinner(game.board);
                        if (winner) {
                            game.isGameActive = false;
                            let resultText = winner === 'draw' ? 'Game ended in a draw!' : 'AI wins!';
                            await bot.sendMessage(game.players.X, resultText, { 
                                reply_markup: generateBoard(game.board, gameId) 
                            });
                            
                            delete playerGames[game.players.X];
                            delete games[gameId];
                            return;
                        }
                        
                        game.currentPlayer = 'X';
                        await bot.sendMessage(game.players.X, `Your turn (X)`, { 
                            reply_markup: generateBoard(game.board, gameId) 
                        });
                    }
                }, 1000);
            } else {
                // Human player's turn
                const currentPlayerName = game.players.names[nextPlayerId] || 'You';
                const otherPlayerId = game.currentPlayer === 'X' ? game.players.O : game.players.X;
                
                await bot.sendMessage(nextPlayerId, `${currentPlayerName}'s turn (${game.currentPlayer})`, {
                    reply_markup: keyboard
                });
                
                await bot.sendMessage(otherPlayerId, `Waiting for ${currentPlayerName}'s move (${game.currentPlayer})`, {
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
