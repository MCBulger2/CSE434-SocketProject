from socket import *
import threading

from player import Player
from card import Card

# Global Variables for Client
serverName = 'localhost'  # static, permanent IP of the manager process
serverPort = 4500  # static, permanent port of the manager process
clientPort = 4505  # by default a client has port 4505. as ports are allocated each client will get a higher port
portsPerClient = 5  # the number of ports a client is allocated. i.e., the size of port blocks being allocated

manager_socket = None  # socket for communicating with manager
peer_socket = None  # socket for communicating with peers
dealer_socket = None  # socket for communicating with dealer

values = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
suits = ["S", "C", "D", "H"]

username = ""
players = []
cards = {}


# Entry point for a Client Process - Starts the client.
# Contacts the manager/server to register itself and either:
#   - Joins matchmaking, and waits to be assigned to a game
#   - Starts a new game, and contacts the other peers assigned to the new game
def start_client() -> None:
    global manager_socket, peer_socket, dealer_socket, clientPort, username

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

    dealer_socket = socket(AF_INET, SOCK_DGRAM)
    dealer_socket.bind(("", clientPort + 1))

    # Start a thread that is responsible for listening to incoming requests
    # Without a second thread, the client UI would be unresponsive whenever we're waiting for a response
    #x = threading.Thread(target=listener, args=(1, ))
    #x.start()

    print(f"The client is listening at port {str(clientPort)}.")

    print("Options:")
    print("1: Start a new game")
    print("2: Join matchmaking (normal rules)")
    print("3: Join matchmaking (special rules)")
    selection = int(input("Choose an option: "))

    if selection == 1:
        num_players = int(input("Input the number of additional players: "))
        request_start_game(num_players)
    elif selection == 2:
        print("Waiting to be contacted by a dealer...")
        matchmaking(0)
    elif selection == 3:
        print("Not implemented yet")

    manager_socket.close()


def matchmaking(id):
    global players, cards

    request, client_addr = peer_socket.recvfrom(2048)
    message = request.decode()
    if message.startswith("assign player"):
        peer_socket.sendto(f"ack {message}".encode(), client_addr)
        tokens = message.split("\n")
        tokens = tokens[2:]
        players = []
        for player in tokens:
            newPlayer = Player.from_string(player)
            players.append(newPlayer)
            cards[newPlayer.name] = []

    wait_for_cards(0)


def wait_for_cards(id):
    i = 0
    while i < len(players) * 6:
        request, client_addr = peer_socket.recvfrom(2048)
        message = request.decode()
        if message.startswith("deal card"):
            peer_socket.sendto(f"ack {message}".encode(), client_addr)
            tokens = message.split("\n")
            tokens = tokens[1:]
            card = Card.from_string(tokens[0])
            cards[tokens[1]].append(card)
            print('got card ' + card.to_string())
            i += 1
    print_cards()
    #wait_for_stick_pass()
    wait_for_reveal_announcement(0)


def wait_for_stick_pass():
    request, client_addr = peer_socket.recvfrom(2048)
    message = request.decode()
    if message.startswith("pass stick"):
        peer_socket.sendto(f"ack {message}".encode(), client_addr)
        nextPlayer = players[0]
        del players[0]
        players.append(nextPlayer)
        if nextPlayer.name == username:
            x = threading.Thread(target=wait_for_player, args=(1, ))
            x.start()
            make_move()
            # x.join()
            pass_talking_stick()
        else:
            wait_for_player(0)

def wait_for_reveal_announcement(id):
    print("waiting for reveal announcement")
    request, client_addr = peer_socket.recvfrom(2048)
    message = request.decode()
    if message.startswith("announce initial reveal"):
        peer_socket.sendto(f"ack {message}".encode(), client_addr)

        x = threading.Thread(target=listen_for_revelations, args=(1,))
        x.start()

        card1 = int(input("Card 1: "))
        reveal_card(card1)
        card2 = int(input("Card 2: "))
        reveal_card(card2)
    wait_for_player(0)

def listen_for_revelations(id):
    while True:
        request, client_addr = peer_socket.recvfrom(2048)
        message = request.decode()
        if message.startswith("reveal card"):
            peer_socket.sendto(f"ack {message}".encode(), client_addr)
            tokens = message.split("\n")
            tokens = tokens[1:]
            cards[tokens[1]][int(tokens[0])].hidden = False
            print_cards()

def wait_for_player(id):
    print("waiting for player")

    wait_for_stick_pass()
    return


def make_move():
    input("Selection: (currently will flip)")
    reveal_card(0)
    return


def print_cards():
    for player in cards:
        print(f"{player}:")
        for card in cards[player]:
            if (card.hidden):
                print(f"***")
            else:
                print(f"{card.to_string()} ")


# Executed on a thread separate from the main thread.
# Listens for any incoming requests from other peers and responds to them
#def listener(id):
#    while True:
#        request, client_addr = peer_socket.recvfrom(2048)
#        message = request.decode()
#        if not message.startswith("ack"):
#            print(f"Request from {client_addr}: {request.decode()}")
#            peer_socket.sendto(f"ack {message}".encode(), client_addr)


# Attempts to start a new game as the dealer.
# If the server successfully finds other players to play with, contacts them in order to start playing the game
def request_start_game(num_players):
    global players, dealer_socket

    request = f"start game {username} {num_players}"
    response = send_message_manager(request)
    tokens = response.split("\n")
    if tokens[0] == "SUCCESS":
        num_players = int(tokens[1])
        tokens = tokens[2:]
        players = []
        for player in tokens:
            newPlayer = Player.from_string(player)
            #if newPlayer.name == username:
            #    newPlayer.port += 1
            players.append(newPlayer)
            cards[newPlayer.name] = []

        # spawn thread that will play the game on behalf of the dealer so the dealer main thread can do other stuff
        x = threading.Thread(target=matchmaking, args=(1,))
        x.start()

        assign_players()
        #print("done assigning")

        deal_cards()
        #print("done dealing")

        #print("pass stick")
        #pass_talking_stick()

        #print("announce initial reveal")
        announce_initial_reveal()
        wait_for_initial_reveal_completion()


def wait_for_initial_reveal_completion():
    # todo after this method, pass the talking stick to the next player so they can make a move
    revealedCards = 0
    while revealedCards < len(players) * 2:
        request, client_addr = peer_socket.recvfrom(2048)
        message = request.decode()
        if message.startswith("reveal card"):
            peer_socket.sendto(f"ack {message}".encode(), client_addr)
            revealedCards += 1


def sendToAll(bytes, soc, callback):
    for player in players:
        soc.sendto(bytes, (player.address, int(player.port)))
        response, server_addr = soc.recvfrom(2048)
        callback(response)


def announce_initial_reveal():
    for player in players:
        dealer_socket.sendto("announce initial reveal".encode(), (player.address, int(player.port)))
        response, server_addr = dealer_socket.recvfrom(2048)


def pass_talking_stick():
    nextPlayer = players[0]
    print("passing the talking stick now")
    for player in players:
        #if (player.name != username):
        dealer_socket.sendto(f"pass stick {nextPlayer.name}".encode(), (player.address, int(player.port)))
        response, server_addr = dealer_socket.recvfrom(2048)

    #del player[0]
    #players.append(nextPlayer)


# Generates a deck of cards, and shuffles them into a random order.
# Invoked by the dealer at the start of every game.
def shuffle_cards():
    #  todo shuffle the deck of cards
    all_cards = []
    for suit in suits:
        for value in values:
            all_cards.append(Card(suit + value))

    return all_cards


# Called by the dealer to notify the other players of the game that they have been assigned to a new game
def assign_players():
    #  todo notify all players that they have been assigned to a game with which players
    players_str = ""
    for player in players:
        players_str += f"\n{player.to_string()}"

    for player in players:
        message = f"assign player\n{len(players)}{players_str}"
        dealer_socket.sendto(message.encode(), (player.address, int(player.port)))
        response, server_addr = dealer_socket.recvfrom(2048)
        #print(response.decode())
    return


# Notifies all other players that the player is being dealt a card of value 'card'.
def deal_card(player, card):
    #  todo notify all players that a specific card is being dealt to a specific player
    print("deal card " + card.to_string() + player.name + str(player.port))
    for p in players:
        dealer_socket.sendto(f"deal card\n{card.to_string()}\n{player.name}".encode(), (p.address, p.port))
        response, server_addr = dealer_socket.recvfrom(2048)
    return


# Distributes the appropriate number of random cards in a deck to each player of the current game.
def deal_cards():
    #  todo shuffle the deck of cards and distribute them to each player

    all_cards = shuffle_cards()
    cards_dealt = 0
    while cards_dealt < len(players) * 6:
        player = players[cards_dealt % len(players)]
        card = all_cards.pop()
        deal_card(player, card)
        cards_dealt += 1

    return


# Notifies all other players that this client is moving a card from src to dest.
def move_card(src, dest, players):
    #  notify all other players that this client is rearranging their card
    return


# Notifies all other players that this client is turning over a card in their stack.
def reveal_card(src):
    #  notify all other players that this client is revealing a certain card
    cards[username][src].hidden = False

    for player in players:
        print("reveal" + str(src))
        dealer_socket.sendto(f"reveal card\n{src}\n{username}".encode(), (player.address, int(player.port)))
        response, server_addr = dealer_socket.recvfrom(2048)


# Notifies all other players that this client is swapping the card in their hand with one of their six cards.
def swap_card(src, oldCard, newCard, players):
    #  notify other players that this client is discarding the card at src and replacing it with the card in their hand
    return


# Notifies other players that this client is drawing a card from the stock, and holding it in their hand (not swapping)
def draw_card(drawFromDiscard, players):
    #  notify all other players that this client is drawing a card from either the stock or discard
    return


# Sends a message to another peer, and waits for their response/acknowledgment.
#def ping(peer: Player):
#    print(peer.to_string() + " ping ")
#    peer_socket.sendto("PING".encode(), (peer.address, int(peer.port)))
#    #print(response)


# Sends a message to the manager/server and returns its response as a string.
def send_message_manager(message):
    global manager_socket

    manager_socket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = manager_socket.recvfrom(2048)
    return response.decode()
