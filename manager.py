# Matthew Bulger
# CSE 434
# Dr. Syrotiuk
# Socket Project

import string
from socket import *
import logging

from utils import log_request
from game import Game
from player import Player

# Global Variables for Manager
managerPort = 4500  # manager has first 5 ports of range reserved
manager_socket = None  # socket used for incoming/outgoing messages

players = []  # list of all registered clients
games = []  # list of all ongoing games

logger = logging.getLogger()  # get logger with currently defined logging level (from main)


# Entry point for Manager process - Starts the manager process.
# Binds the current process to the server port, and indefinitely responds
# to any requests that are written to that socket
def start_manager() -> None:
    global manager_socket

    # Open the socket
    logger.info("The manager is starting...")
    manager_socket = socket(AF_INET, SOCK_DGRAM)
    manager_socket.bind(("", managerPort))
    logger.info(f"The manager is listening at port {str(managerPort)}.")
    logger.info("To shut down the manager, press \'^C\' (Control + C).")

    # Listen for requests and respond to them
    try:
        while True:  # Keep getting incoming request and respond to each of them
            handle_next_request()
    except KeyboardInterrupt:
        logger.info("Shutting down the manager...")

    manager_socket.close()


# Get an incoming message from the socket and handle the request
def handle_next_request():
    global manager_socket

    # Get the next incoming message from the socket
    request, client_addr = manager_socket.recvfrom(2048)
    message = request.decode()  # bytes -> string

    # Parse command from the request and execute the corresponding function
    response = ""
    tokens = message.split(" ")
    if len(tokens) == 3 and tokens[0] == "register":
        response = register(tokens[1], client_addr[0], tokens[2])
    elif len(tokens) == 2 and f"{tokens[0]} {tokens[1]}" == "query players":
        response = query_players()
    elif len(tokens) == 4 and f"{tokens[0]} {tokens[1]}" == "start game":
        response = start_game(tokens[2], tokens[3])
    elif len(tokens) == 2 and f"{tokens[0]} {tokens[1]}" == "query games":
        response = query_games()
    elif len(tokens) == 3 and tokens[0] == "end":
        response = end(tokens[1], tokens[2])
    elif len(tokens) == 2 and tokens[0] == "de-register" or tokens[0] == "deregister":
        response = deregister(tokens[1])
    else:  # the command was unrecognized, return an error as the response
        response = "SYNTAX_ERROR"

    log_request(client_addr, message, response)  # log the request/response to the console
    manager_socket.sendto(response.encode(), client_addr)  # send the response back to the client


# Register a client into the player database.
# Attempts to associate a given username with their IP address and port
# Both username and port must be unique.
def register(username, address, port):
    new_player = Player(username, address, port)

    # Validate that the username and port are unique (not already registered by another user)
    # If the username is invalid, the client should retry the registration with a different username.
    # If the port is taken, the client should automatically retry with the same username but different port block.
    for player in players:
        if player.port == new_player.port:
            return "FAILURE PORT"
        elif player.name == new_player.name:
            return "FAILURE USERNAME"

    # Username and port were valid, register user in the database
    players.append(new_player)

    return "SUCCESS"


# Returns the number of registered players, along with each of their usernames, IP addresses, and ports.
def query_players() -> string:
    response = f"{len(players)}"
    if len(players) > 0:
        for player in players:
            response += f"\n{player.to_string()}"

    return response


# Invoked by the dealer player to start a new game with 1 <= k <= 3 additional players.
# If there are enough players ready, creates a new game and returns a list of the other players back to the dealer.
# If there are not enough players ready, or the dealer specified an invalid number of additional players, request fails.
def start_game(user, k_str) -> string:
    # Check to see if k is within the valid domain of [1, 3]
    k = int(k_str)
    if k < 1 or k > 3 or len(players) < k:  # additional users out of range
        return "FAILURE"

    # Matchmaking: Randomly assign k of the players who are not currently in a game to the game
    # todo: randomly assign players to the new game - currently sequential
    viable_players = []
    for p in players:
        player_in_game = False
        for game in games:
            for player in game.players:
                if player.name == p.name:
                    player_in_game = True
        if not player_in_game and p.name != user:
            viable_players.append(p)

    if len(viable_players) < k:
        return "FAILURE"

    game_players = viable_players[0:k]

    # Add dealer to list of players
    for player in players:
        if player.name == user:
            game_players.append(player)

    # Register the new game in the database
    new_game_id = len(games)
    new_game = Game(new_game_id, user, game_players)
    games.append(new_game)

    # Form the response to return to the dealer (which includes each of the users that we assigned to the game)
    response = f"SUCCESS\n{new_game_id}"
    for i in range(len(game_players)):
        response += f"\n({game_players[i].to_string()})"

    return response


# Returns a list of all ongoing games (as well as how many games are ongoing).
def query_games() -> string:
    response = f"{str(len(games))}"
    if len(games) > 0:
        for game in games:
            response += f"\n{game.to_string()}"
    return response


# Invoked by the dealer of a game when it is completed.
# Removes the game from the list of ongoing games, and frees the users of the game to join a new game.
def end(game_id_str, user) -> string:
    # Find the game in the db where the invoking user is the dealer and the game id matches
    game_id = int(game_id_str)
    game = -1
    for i in range(len(games)):
        if games[i].gameId == game_id and games[i].dealer == user:
            game = i

    # If there was a matching game, end it
    if game != -1:
        del games[game]
        return "SUCCESS"

    # There was not a matching game, either the wrong user invoked the command or the game id was not found
    return "FAILURE"


# Invoked by a client to remove themselves from the player list, and allow them to safely exit.
# If a client exits without de-registering, they could be assigned to a new game, causing the peers to
# be unable to communicate with them and unable to make progress.
# Can only be invoked by a client who is not currently in an ongoing game.
def deregister(username):
    # Get the index of the user with the specified username
    idx = -1
    for i in range(len(players)):
        if players[i].name == username:
            idx = i
            break

    # Delete the user so they cannot join any more games
    if idx != -1:
        del players[idx]
        return "SUCCESS"

    return "FAILURE"  # could not find user
