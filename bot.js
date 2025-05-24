const TelegramBot = require('node-telegram-bot-api');
const express = require('express');

const token = process.env.TELEGRAM_BOT_TOKEN || 'YOUR_BOT_TOKEN';
const port = process.env.PORT || 3000;

const app = express();
const bot = new TelegramBot(token, { polling: true });

app.get('/', (req, res) => res.send('Tic Tac Toe Bot is running!'));
app.listen(port, () => console.log(`Server running on port ${port}`));

// Game storage
const activeGames = {};
const waitingGames = {};
const playerGames = {};

// Generate random game ID
function generateGameId() {
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    return Array(6).fill(0).map(() => chars[Math.floor(Math.random() * chars.length)]).join('');
}

// Create new game board
function createNewBoard() {
    return Array(9).fill(null);
}

// Check for winner
function checkWinner(board) {
    const winPatterns = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], // rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], // columns
        [0, 4, 8], [2, 4, 6]             // diagonals
    ];

    for (const [a, b, c] of winPatterns) {
        if (board[a] && board[a] === board[b] && board[a] === board[c]) {
            return board[a];
        }
    }
    return board.includes(null) ? null : 'draw';
}

// Generate game keyboard
function generateKeyboard(board, gameId) {
    const keyboard = {
        inline_keyboard: []
    };

    // Create 3x3 grid
    for (let i = 0; i < 9; i += 3) {
        const row = board.slice(i, i + 3).map((cell, index) => ({
            text: cell || ' ',
            callback_data: `${gameId}_${i + index}`
        }));
        keyboard.inline_keyboard.push(row);
    }

    // Add surrender button
    keyboard.inline_keyboard.push([{
        text: '🏳️ Surrender',
        callback_data: `${gameId}_surrender`
    }]);

    return keyboard;
}

// Handle /start and /play
bot.onText(/\/start|\/play/, (msg) => {
    const chatId = msg.chat.id;
    const username = msg.from.username || 'Player';
    
    const menu = {
        inline_keyboard: [
            [{ text: '🤖 Single Player', callback_data: 'single' }],
            [{ text: '👥 Multiplayer', callback_data: 'multiplayer' }]
        ]
    };
    
    bot.sendMessage(chatId, `👋 Hello ${username}! Choose game mode:`, {
        reply_markup: menu
    });
});

// Handle callback queries
bot.on('callback_query', async (callbackQuery) => {
    const chatId = callbackQuery.message.chat.id;
    const messageId = callbackQuery.message.message_id;
    const data = callbackQuery.data;
    const username = callbackQuery.from.username || 'Player';

    try {
        // Single player mode
        if (data === 'single') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }

            const gameId = generateGameId();
            activeGames[gameId] = {
                board: createNewBoard(),
                players: { X: chatId, O: 'AI' },
                currentPlayer: 'X',
                isActive: true
            };
            playerGames[chatId] = gameId;

            const keyboard = generateKeyboard(activeGames[gameId].board, gameId);
            await bot.editMessageText('Your turn (X)', {
                chat_id: chatId,
                message_id: messageId,
                reply_markup: keyboard
            });
            return;
        }

        // Multiplayer mode
        if (data === 'multiplayer') {
            if (playerGames[chatId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'You are already in a game!' });
            }

            const gameId = generateGameId();
            waitingGames[gameId] = {
                creatorId: chatId,
                creatorName: username,
                messageId: messageId
            };

            const joinKeyboard = {
                inline_keyboard: [
                    [{ text: '🎮 Join Game', callback_data: `join_${gameId}` }]
                ]
            };

            await bot.editMessageText(
                `🎲 ${username} wants to play! (Game ID: ${gameId})\n\nClick JOIN to play against them!`,
                {
                    chat_id: chatId,
                    message_id: messageId,
                    reply_markup: joinKeyboard
                }
            );
            return;
        }

        // Join multiplayer game
        if (data.startsWith('join_')) {
            const gameId = data.split('_')[1];
            const waitingGame = waitingGames[gameId];

            if (!waitingGame || waitingGame.creatorId === chatId) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Cannot join this game!' });
            }

            if (playerGames[chatId] || playerGames[waitingGame.creatorId]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'One of you is already in a game!' });
            }

            // Start the game
            activeGames[gameId] = {
                board: createNewBoard(),
                players: { X: waitingGame.creatorId, O: chatId },
                currentPlayer: 'X',
                isActive: true
            };
            playerGames[chatId] = gameId;
            playerGames[waitingGame.creatorId] = gameId;
            delete waitingGames[gameId];

            const keyboard = generateKeyboard(activeGames[gameId].board, gameId);

            // Notify both players
            await bot.sendMessage(
                waitingGame.creatorId,
                `Game started with @${username}! Your turn (X)`,
                { reply_markup: keyboard }
            );

            await bot.sendMessage(
                chatId,
                `Game started with @${waitingGame.creatorName}! Their turn (X)`,
                { reply_markup: keyboard }
            );

            // Delete waiting message
            await bot.deleteMessage(waitingGame.creatorId, waitingGame.messageId);
            return;
        }

        // Handle game moves
        if (data.includes('_')) {
            const [gameId, action] = data.split('_');
            const game = activeGames[gameId];

            // Handle surrender
            if (action === 'surrender') {
                if (!game || !game.isActive) {
                    return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not found!' });
                }

                const winner = game.players.X === chatId ? 'O' : 'X';
                const winnerId = game.players[winner];
                const winnerName = winnerId === 'AI' ? 'AI' : (winnerId === chatId ? 'You' : 'Opponent');

                await bot.sendMessage(
                    game.players.X,
                    `🏳️ Game over! ${winnerName} (${winner}) wins by surrender!`
                );
                
                if (game.players.O !== 'AI') {
                    await bot.sendMessage(
                        game.players.O,
                        `🏳️ Game over! ${winnerName} (${winner}) wins by surrender!`
                    );
                }

                // Cleanup
                delete playerGames[game.players.X];
                if (game.players.O !== 'AI') delete playerGames[game.players.O];
                delete activeGames[gameId];
                return;
            }

            if (!game || !game.isActive) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Game not found or ended!' });
            }

            // Check if it's player's turn
            if (game.players[game.currentPlayer] !== chatId) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: "It's not your turn!" });
            }

            // Make move
            const position = parseInt(action);
            if (isNaN(position) || position < 0 || position > 8 || game.board[position]) {
                return bot.answerCallbackQuery(callbackQuery.id, { text: 'Invalid move!' });
            }

            game.board[position] = game.currentPlayer;

            // Check for winner
            const winner = checkWinner(game.board);
            if (winner) {
                game.isActive = false;
                let resultText = '';
                
                if (winner === 'draw') {
                    resultText = 'Game ended in a draw!';
                } else {
                    const winnerId = game.players[winner];
                    const winnerName = winnerId === 'AI' ? 'AI' : (winnerId === chatId ? 'You' : 'Opponent');
                    resultText = `${winnerName} (${winner}) wins!`;
                }

                const keyboard = generateKeyboard(game.board, gameId);
                
                await bot.sendMessage(game.players.X, resultText, { reply_markup: keyboard });
                if (game.players.O !== 'AI') {
                    await bot.sendMessage(game.players.O, resultText, { reply_markup: keyboard });
                }

                // Cleanup
                delete playerGames[game.players.X];
                if (game.players.O !== 'AI') delete playerGames[game.players.O];
                delete activeGames[gameId];
                return;
            }

            // Switch turns
            game.currentPlayer = game.currentPlayer === 'X' ? 'O' : 'X';
            const keyboard = generateKeyboard(game.board, gameId);

            // Handle AI move in single player
            if (game.players.O === 'AI' && game.currentPlayer === 'O') {
                // Simple AI - find first empty spot
                const emptyIndex = game.board.findIndex(cell => cell === null);
                if (emptyIndex !== -1) {
                    game.board[emptyIndex] = 'O';
                    
                    // Check if AI won
                    const winner = checkWinner(game.board);
                    if (winner) {
                        game.isActive = false;
                        let resultText = winner === 'draw' ? 'Game ended in a draw!' : 'AI wins!';
                        
                        await bot.sendMessage(
                            game.players.X, 
                            resultText, 
                            { reply_markup: generateKeyboard(game.board, gameId) }
                        );
                        
                        delete playerGames[game.players.X];
                        delete activeGames[gameId];
                        return;
                    }
                    
                    game.currentPlayer = 'X';
                    await bot.sendMessage(
                        game.players.X,
                        'Your turn (X)',
                        { reply_markup: generateKeyboard(game.board, gameId) }
                    );
                }
            } else {
                // Human player's turn
                const currentPlayerId = game.players[game.currentPlayer];
                const currentPlayerName = currentPlayerId === chatId ? 'Your' : 'Opponent\'s';
                
                await bot.sendMessage(
                    currentPlayerId,
                    `${currentPlayerName} turn (${game.currentPlayer})`,
                    { reply_markup: keyboard }
                );
                
                // Notify other player
                const otherPlayerId = game.currentPlayer === 'X' ? game.players.O : game.players.X;
                if (otherPlayerId !== 'AI') {
                    await bot.sendMessage(
                        otherPlayerId,
                        `Waiting for ${currentPlayerName.toLowerCase()} move (${game.currentPlayer})`,
                        { reply_markup: keyboard }
                    );
                }
            }
        }
    } catch (error) {
        console.error('Error:', error);
        bot.answerCallbackQuery(callbackQuery.id, { text: 'An error occurred!' });
    }
});

console.log('Tic Tac Toe bot is running...');
