import string
from socket import *
import ports
from game import Game
from player import Player

managerPort = 4500

players = []
games = []


def start_manager() -> None:
    print("The manager is starting...")
    manager_socket = socket(AF_INET, SOCK_DGRAM)
    manager_socket.bind(("", managerPort))
    print(f"The manager is listening at port {str(managerPort)}.")

    while True:
        request, client_addr = manager_socket.recvfrom(2048)
        print(f"Received a request from {client_addr}")
        message = request.decode()

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
        elif len(tokens) == 2 and tokens[0] == "de-register":
            response = deregister(tokens[1])
        else:
            response = "SYNTAX_ERROR"

        manager_socket.sendto(response.encode(), client_addr)

    manager_socket.close()


def register(user, address, port) -> string:
    newPlayer = Player(user, address, port)

    for player in players:
        if player.port == newPlayer.port:
            return "FAILURE PORT"
        elif player.name == newPlayer.name:
            return "FAILURE USERNAME"

    players.append(newPlayer)

    return "SUCCESS"


def query_players() -> string:
    response = f"{len(players)}"
    if len(players) > 0:
        for player in players:
            response += f"\n{player.to_string()}"
    print(response)
    return response


def start_game(user, k_str) -> string:
    k = int(k_str)
    if k < 1 or k > 3 or len(players) < k:  # additional users out of range
        return "FAILURE"

    gamePlayers = []
    for i in range(k):
        gamePlayers.append(players[i])
    newGameId = len(games)
    newGame = Game(newGameId, user, gamePlayers)
    games.append(newGame)

    response = f"SUCCESS\n{newGameId}"
    for i in range(k):
        response += f"\n({gamePlayers[i].to_string()})"

    return response


def query_games() -> string:
    response = f"{str(len(games))}"
    if len(games) > 0:
        for game in games:
            response += f"\n{game.to_string()}"
    return response


def end(gameId_str, user) -> string:
    gameId = int(gameId_str)
    game = -1
    for i in range(len(games)):
        if games[i].gameId == gameId and games[i].dealer == user:
            game = i

    if game != -1:
        del games[game]
        return "SUCCESS"

    return "FAILURE"


def deregister(username) -> string:
    idx = -1
    for i in range(len(players)):
        if players[i].name == username:
            idx = i
            break

    if idx != -1:
        del players[idx]
        return "SUCCESS"

    return "FAILURE"