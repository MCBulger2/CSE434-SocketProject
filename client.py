from socket import *
import threading

from player import Player

# Global Variables for Client
serverName = 'localhost'  # static, permanent IP of the manager process
serverPort = 4500  # static, permanent port of the manager process
clientPort = 4505  # by default a client has port 4505. as ports are allocated each client will get a higher port
portsPerClient = 5  # the number of ports a client is allocated. i.e., the size of port blocks being allocated

manager_socket = None  # socket for communicating with manager
peer_socket = None  # socket for communicating with peers


# Entry point for a Client Process - Starts the client.
# Contacts the manager/server to register itself and either:
#   - Joins matchmaking, and waits to be assigned to a game
#   - Starts a new game, and contacts the other peers assigned to the new game
def start_client() -> None:
    global manager_socket, peer_socket, clientPort

    # Open a socket on a random dynamic port to communicate with the manager
    manager_socket = socket(AF_INET, SOCK_DGRAM)

    # Wait until the user inputs a username
    username = input("Username: ")

    # Attempt to register with the manager
    is_registered = False
    while not is_registered:
        response = send_message_manager(f"register {username} {clientPort}") # Send a registration request
        if response == "SUCCESS":  # registration successful
            is_registered = True
        elif response == "FAILURE PORT":  # the port block was already taken, try again with next port block
            clientPort += portsPerClient
        elif response == "FAILURE USERNAME":  # the username was already taken, try again with a new username
            print(f"Username \'{username}\' is already taken.")
            username = input("Username: ")

    # Now that we're registered with the server, open a socket on the port(s) we were assigned to communicate with peers
    peer_socket = socket(AF_INET, SOCK_DGRAM)
    peer_socket.bind(("", clientPort))

    # Start a thread that is responsible for listening to incoming requests
    # Without a second thread, the client UI would be unresponsive whenever we're waiting for a response
    x = threading.Thread(target=listener, args=(1, ))
    x.start()

    print(f"The client is listening at port {str(clientPort)}.")

    while True:
        # message = input("Message: ")
        # response = send_message_server(message)
        # print(response)

        request_start_game(username, 1)

    manager_socket.close()


# Executed on a thread separate from the main thread.
# Listens for any incoming requests from other peers and responds to them
def listener(id):
    while True:
        request, client_addr = peer_socket.recvfrom(2048)
        print(f"Request from {client_addr}: {request.decode()}")
        peer_socket.sendto("response".decode(), client_addr)


# Attempts to start a new game as the dealer.
# If the server successfully finds other players to play with, contacts them in order to start playing the game
def request_start_game(username, num_players):
    request = f"start game {username} {num_players}"
    response = send_message_manager(request)
    tokens = response.split("\n")
    if tokens[0] == "SUCCESS":
        num_players = int(tokens[1])
        tokens = tokens[2:]
        players = []
        for player in tokens:
            players.append(Player.from_string(player))

        assign_players(players)
        deal_cards(players)


# Generates a deck of cards, and shuffles them into a random order.
# Invoked by the dealer at the start of every game.
def shuffle_cards():
    #  todo shuffle the deck of cards
    return


# Called by the dealer to notify the other players of the game that they have been assigned to a new game
def assign_players(players):
    #  todo notify all players that they have been assigned to a game with which players
    return


# Notifies all other players that the player is being dealt a card of value 'card'.
def deal_card(player, card, players):
    #  todo notify all players that a specific card is being dealt to a specific player
    return


# Distributes the appropriate number of random cards in a deck to each player of the current game.
def deal_cards(players):
    #  todo shuffle the deck of cards and distribute them to each player

    cards = shuffle_cards()
    cardsDealt = 0
    while cardsDealt < len(players) * 6:
        player = players[cardsDealt % len(players)]
        card = cards.pop()
        deal_card(player, card, players)
        cardsDealt += 1

    return


# Notifies all other players that this client is moving a card from src to dest.
def move_card(src, dest, players):
    #  notify all other players that this client is rearranging their card
    return


# Notifies all other players that this client is turning over a card in their stack.
def reveal_card(src, card, players):
    #  notify all other players that this client is revealing a certain card
    return


# Notifies all other players that this client is swapping the card in their hand with one of their six cards.
def swap_card(src, oldCard, newCard, players):
    #  notify other players that this client is discarding the card at src and replacing it with the card in their hand
    return


# Notifies other players that this client is drawing a card from the stock, and holding it in their hand (not swapping)
def draw_card(drawFromDiscard, players):
    #  notify all other players that this client is drawing a card from either the stock or discard
    return


# Sends a message to another peer, and waits for their response/acknowledgment.
def ping(peer: Player):
    print(peer.to_string() + " ping ")
    peer_socket.sendto("PING".encode(), (peer.address, int(peer.port)))
    #print(response)


# Sends a message to the manager/server and returns its response as a string.
def send_message_manager(message) -> string:
    global manager_socket

    manager_socket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = manager_socket.recvfrom(2048)
    return response.decode()
