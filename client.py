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
game_state_socket = None  # socket for communicating with dealer

dealer_address = None

values = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
suits = ["S", "C", "D", "H"]

username = ""
players = []
cards = {}
stacks = {
    "stock": [],
    "discard": []
}
currentTurn = None
held_card = None
round = 1


# Entry point for a Client Process - Starts the client.
# Contacts the manager/server to register itself and either:
#   - Joins matchmaking, and waits to be assigned to a game
#   - Starts a new game, and contacts the other peers assigned to the new game
def start_client() -> None:
    global manager_socket, peer_socket, dealer_socket, game_state_socket, clientPort, username

    # Open a socket on a random dynamic port to communicate with the manager
    manager_socket = socket(AF_INET, SOCK_DGRAM)

    # Wait until the user inputs a username
    username = input("Username: ")

    # Attempt to register with the manager
    is_registered = False
    while not is_registered:
        response = send_message_manager(f"register {username} {clientPort}")  # Send a registration request
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

    game_state_socket = socket(AF_INET, SOCK_DGRAM)
    game_state_socket.bind(("", clientPort + 2))

    # Start a thread that is responsible for listening to incoming requests
    # Without a second thread, the client UI would be unresponsive whenever we're waiting for a response
    # x = threading.Thread(target=listener, args=(1, ))
    # x.start()

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


def broadcast(bytes, soc, callback, notify_self=True):
    for player in players:
        if notify_self or player.name != username:
            soc.sendto(bytes, (player.address, player.port))
            request, client_addr = soc.recvfrom(2048)
            callback(request, client_addr)


def wait_for_command(command, soc):
    while True:
        request, sender = soc.recvfrom(2048)
        message = request.decode()
        tokens = message.split("\n")
        if tokens[0] == command:
            soc.sendto(f"ack {message}".encode(), sender)
            tokens = tokens[1:]
            return tokens, sender


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
            players.append(newPlayer)
            cards[newPlayer.name] = []

        # spawn thread that will play the game on behalf of the dealer so the dealer main thread can do other stuff
        dealer_player_thread = threading.Thread(target=matchmaking, args=(1,))
        dealer_player_thread.start()

        assign_players()

        deal_cards()

        announce_initial_reveal()

        game_state_thread = threading.Thread(target=wait_for_game_completion, args=(1,))
        game_state_thread.start()

        wait_for_initial_reveal_completion()


def matchmaking(id):
    global players, cards, dealer_address

    tokens, sender = wait_for_command("assign player", peer_socket)
    tokens = tokens[1:]
    players = []
    for player in tokens:
        new_player = Player.from_string(player)
        players.append(new_player)
        cards[new_player.name] = []
    dealer_address = sender

    wait_for_cards(0)


def wait_for_cards(id):
    i = 0
    while i < len(players) * 6:
        tokens, sender = wait_for_command("deal card", peer_socket)
        card = Card.from_string(tokens[0])
        cards[tokens[1]].append(card)
        i += 1

    stacks["stock"] = []
    stacks["discard"] = []
    tokens, sender = wait_for_command("stack", peer_socket)
    stack_type = tokens[0]
    tokens = tokens[1:]
    for card in tokens:
        new_card = Card.from_string(card)
        stacks[stack_type].append(new_card)

    print_cards()
    wait_for_reveal_announcement(0)


def play_round():
    global currentTurn

    print("#################################")
    print(f"     Round {round}")
    print("#################################")

    tokens, sender = wait_for_command("game state", peer_socket)
    if tokens[0] == "end":
        print(f"The winner is {tokens[1]}")
        return

    tokens, sender = wait_for_command("pass stick", peer_socket)
    nextPlayer = players[0]
    currentTurn = nextPlayer
    del players[0]
    players.append(nextPlayer)

    print_cards()
    if nextPlayer.name == username:
        print(f"It's my turn")
        pop_card()
        replace_card()

        dealer_socket.sendto("query game state".encode(), (dealer_address[0], dealer_address[1] + 1))
        request, client_addr = dealer_socket.recvfrom(2048)

        pass_talking_stick()
    else:
        print(f"Waiting for {nextPlayer.name} to complete their turn.")
        listen_for_move()


def listen_for_move():
    global held_card

    tokens, sender = wait_for_command("pop", peer_socket)
    stack_type = tokens[0]
    held_card = stacks[stack_type].pop()

    print_cards()

    tokens, sender = wait_for_command("replace", peer_socket)
    swapped_card_index = int(tokens[0])
    user = tokens[1]
    swapped_card = cards[user][swapped_card_index]
    swapped_card.hidden = False
    cards[user][swapped_card_index] = held_card
    cards[user][swapped_card_index].hidden = False
    stacks["discard"].append(swapped_card)
    held_card = None


def wait_for_reveal_announcement(id):
    print("waiting for reveal announcement")
    x2 = threading.Thread(target=listen_for_revelations, args=(1,))
    request, client_addr = peer_socket.recvfrom(2048)
    message = request.decode()
    if message.startswith("announce initial reveal"):
        peer_socket.sendto(f"ack {message}".encode(), client_addr)

        x2.start()

        card1 = int(input("Card 1: "))
        reveal_card(card1)
        card2 = int(input("Card 2: "))
        reveal_card(card2)

    print_cards()

    x2.join()

    wait_for_player(0)


def listen_for_revelations(id):
    cardReceived = 0
    while cardReceived < 2 * len(players):
        tokens, sender = wait_for_command("reveal card", peer_socket)
        cards[tokens[1]][int(tokens[0])].hidden = False
        cardReceived += 1


def wait_for_player(id):
    while True:
        play_round()


def pop_card():
    global held_card
    print("------------Get Net Card---------------")
    print("Where do you want to draw a card from?")
    print("1. Stock")
    print("2. Discard")
    selection = int(input("Selection: "))
    stack_type = "stock"
    if selection == 2:
        stack_type = "discard"
    held_card = stacks[stack_type].pop()
    broadcast(f"pop\n{stack_type}".encode(), peer_socket, lambda response, sender: print(f"{response}"),
              notify_self=False)

    print_cards()


def replace_card():
    global held_card
    print("------------Swap Card---------------")
    print("Which of your cards do you want to replace?")
    print("Your selection should be between 0-5 (inclusive).")
    card_index = int(input("Selection: "))

    swappedCard = cards[username][card_index]
    swappedCard.hidden = False
    cards[username][card_index] = held_card
    cards[username][card_index].hidden = False
    stacks["discard"].append(swappedCard)
    held_card = None
    broadcast(f"replace\n{card_index}\n{username}".encode(), peer_socket, lambda response, sender: print(f"{response}"),
              notify_self=False)


def print_cards():
    print("##############################")
    print("----Stacks----")
    for stack in stacks:
        print(f"{stack}:")

        if len(stacks[stack]) > 0:
            topCard = stacks[stack][-1].player_card_to_string()
            print(topCard)
        else:
            print(
                f"""┌──────┐
│ No   │
│Cards │
│      │
└──────┘""")

    print("----Players----")
    for player in cards:
        print(f"{player}:")
        if currentTurn is not None and currentTurn.name == player:
            if held_card is not None:
                print(f"This player is holding {held_card.to_string()}")
            else:
                print(f"It's this player's turn, but they are holding no cards.")
        print(Card.player_deck_to_string(cards[player]))
        # for card in cards[player]:
        #    if (card.hidden):
        #        print(f"***")
        #    else:
        #        print(f"{card.to_string()} ")
    print("##############################")


def wait_for_initial_reveal_completion():
    # todo after this method, pass the talking stick to the next player so they can make a move

    waitingForRevelations = True
    while waitingForRevelations:
        cards_revealed = 0
        for player_cards in cards:
            for card in cards[player_cards]:
                if not card.hidden:
                    cards_revealed += 1
        if cards_revealed == 2 * len(players):
            waitingForRevelations = False

    print("All players have revealed their cards")

    dealer_socket.sendto("query game state".encode(), (dealer_address[0], dealer_address[1] + 1))
    request, client_addr = dealer_socket.recvfrom(2048)

    print("Passing the talking stick")
    pass_talking_stick()


def wait_for_game_completion(id):
    while True:
        tokens, sender = wait_for_command("query game state", game_state_socket)
        waitingForCompletion = True
        cards_revealed = 0
        player = ""
        for player_cards in cards:
            for card in cards[player_cards]:
                if not card.hidden:
                    cards_revealed += 1
        if cards_revealed == 6 * len(players):
            waitingForCompletion = False

        scores = {}
        winner = ""
        winnerScore = 0
        for player in cards:
            player_sum = 0
            for card in cards[player]:
                value = card.value[1:]
                if value == "A":
                    value = 1
                elif value == "J":
                    value = 11
                elif value == "Q":
                    value = 12
                elif value == "K":
                    value = 13
                else:
                    value = int(value)
                player_sum += value
            scores[player] = player_sum
            if player_sum > winnerScore:
                winnerScore = player_sum
                winner = player

        response = "continue"
        if not waitingForCompletion:
            response = f"end\n{winner}"

        broadcast(f"game state\n{response}".encode(), game_state_socket, lambda response, client_addr: print(response))


def announce_initial_reveal():
    broadcast("announce initial reveal".encode(), dealer_socket,
              lambda response, sender: print(f"{sender[1]}: {response}"))


def pass_talking_stick_thread(id):
    broadcast(f"pass stick".encode(), dealer_socket, lambda response, client_addr: print(response))


def pass_talking_stick():
    t = threading.Thread(target=pass_talking_stick_thread, args=(1,))
    t.start()
    t.join()


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

    message = f"assign player\n{len(players)}{players_str}".encode()
    broadcast(message, dealer_socket, lambda response, client_addr: print(response))


# Notifies all other players that the player is being dealt a card of value 'card'.
def deal_card(player, card):
    #  todo notify all players that a specific card is being dealt to a specific player
    print("deal card " + card.to_string() + player.name + str(player.port))
    broadcast(f"deal card\n{card.to_string()}\n{player.name}".encode(), dealer_socket,
              lambda response, sender: print(f"{response}"))
    # for p in players:
    #    dealer_socket.sendto(f"deal card\n{card.to_string()}\n{player.name}".encode(), (p.address, p.port))
    #    response, server_addr = dealer_socket.recvfrom(2048)
    # return


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

    broadcast_stack("stock", all_cards)


def broadcast_stack(stack_type, stack_cards):
    cardStr = ""
    for card in stack_cards:
        cardStr += f"\n{card.to_string()}"
    broadcast(f"stack\n{stack_type}{cardStr}".encode(), dealer_socket, lambda response, sender: print(f"{response}"))


# Notifies all other players that this client is moving a card from src to dest.
def move_card(src, dest, players):
    #  notify all other players that this client is rearranging their card
    return


# Notifies all other players that this client is turning over a card in their stack.
def reveal_card(src):
    #  notify all other players that this client is revealing a certain card
    # cards[username][src].hidden = False

    broadcast(f"reveal card\n{src}\n{username}".encode(), dealer_socket,
              lambda response, sender: print(f"{sender[1]}: {response}"))

    # for player in players:
    #    print("reveal " + str(src) + " to " + player.name)
    #    dealer_socket.sendto(f"reveal card\n{src}\n{username}".encode(), (player.address, int(player.port)))
    #    response, server_addr = dealer_socket.recvfrom(2048)


# Notifies all other players that this client is swapping the card in their hand with one of their six cards.
def swap_card(src, oldCard, newCard, players):
    #  notify other players that this client is discarding the card at src and replacing it with the card in their hand
    return


# Notifies other players that this client is drawing a card from the stock, and holding it in their hand (not swapping)
def draw_card(drawFromDiscard, players):
    #  notify all other players that this client is drawing a card from either the stock or discard
    return


# Sends a message to another peer, and waits for their response/acknowledgment.
# def ping(peer: Player):
#    print(peer.to_string() + " ping ")
#    peer_socket.sendto("PING".encode(), (peer.address, int(peer.port)))
#    #print(response)


# Sends a message to the manager/server and returns its response as a string.
def send_message_manager(message):
    global manager_socket

    manager_socket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = manager_socket.recvfrom(2048)
    return response.decode()
