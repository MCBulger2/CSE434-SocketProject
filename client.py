from socket import *
import threading
import copy

from player import Player
from card import Card

# Constants
values = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]  # all possible card values
suits = ["S", "C", "D", "H"]  # all possible card suits (Spades, Clubs, Diamonds, Hearts)

# Global Variables for Client
serverName = 'localhost'  # static, permanent IP of the manager process
serverPort = 4500  # static, permanent port of the manager process
clientPort = 4505  # by default a client has port 4505. as ports are allocated each client will get a higher port
portsPerClient = 5  # the number of ports a client is allocated. i.e., the size of port blocks being allocated

manager_socket = None  # socket for communicating with manager (server)
peer_socket = None  # socket for communicating with peers
dealer_socket = None  # socket for communicating with dealer
game_state_socket = None  # socket for getting/sending game state requests to/from dealer (i.e. is game over or not)

dealer_address = None  # the ip address and port of the dealer of the current game

username = ""  # username of the current client
players = []  # list of all other players in the current game (including this client's player interface)
cards = {}  # the game board, keys are player usernames, values are array of cards that user has
stacks = {  # game board continued, stores cards for the stock stack and discard stack
    "stock": [],
    "discard": []
}
currentTurn = None  # which username's turn it is to make a move
held_card = None  # the card being "held" by the current user (card involved with current move while in progress)
round_num = 1  # the current round of the game
gameId = -1  # the game id assigned by the manager. This value is only used by the dealer to end the game


# Entry point for a Client Process - Starts the client.
# Contacts the manager/server to register itself and either:
#   - Joins matchmaking, and waits to be assigned to a game
#   - Starts a new game, and contacts the other peers assigned to the new game
def start_client() -> None:
    global manager_socket, peer_socket, dealer_socket, game_state_socket, clientPort, username

    # Open a socket on a random dynamic port to communicate with the manager
    manager_socket = socket(AF_INET, SOCK_DGRAM)
    register_with_manager()  # ask user for a username, and register with a client (reserves a port group as well)

    # Now that we're registered with the server, open a socket on the port(s) we were assigned to communicate with peers
    # When we register with the manager, we get assigned clientPort and the next 4 ports
    peer_socket = socket(AF_INET, SOCK_DGRAM)
    peer_socket.bind(("", clientPort))

    dealer_socket = socket(AF_INET, SOCK_DGRAM)
    dealer_socket.bind(("", clientPort + 1))

    game_state_socket = socket(AF_INET, SOCK_DGRAM)
    game_state_socket.bind(("", clientPort + 2))

    print(f"The client is listening at port {str(clientPort)}.")

    # Main menu, user will be dumped here at the start and after each game
    while True:
        print("------------------------------------------")
        print("Options:")
        print("1: Start a new game")
        print("2: Join matchmaking (normal rules)")
        print("3: Join matchmaking (special rules)")
        print("4: Query Manager")
        print("5: De-register and Exit")
        selection = int_input("Choose an option: ", lambda x: x in [1, 2, 3, 4, 5])

        if selection == 1:  # Start game
            num_players = int_input("Input the number of additional players (between 1-3 inclusive): ",
                                    lambda x: x >= 1 and x <= 3)
            request_start_game(num_players)
        elif selection == 2:  # normal matchmaking
            print("Waiting to be contacted by a dealer...")
            matchmaking(0)
        elif selection == 3:  # special matchmaking
            print("Not implemented yet")
        elif selection == 4:  # query manager console (for sending raw queries to the manager)
            query_manager()
        elif selection == 5:  # de-register and exit
            response = send_message_manager(f"de-register {username}")
            print(response)
            exit(0)


# Ask the user for a username, and attempt to register it with the manager.
# If the port we try to use is already allocated to another client, try again with the next set of ports
# If the username we try to user is already taken, ask the user to input a new username
# Port and username must be unique across clients.
def register_with_manager():
    global username, clientPort

    # Wait until the user inputs a username (must not be empty, can't be longer than 15 characters)
    username = input_validator("Enter your Username (between 1-15 characters long): ", lambda x: 1 <= len(x) <= 15)
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
            username = input_validator("Enter your Username (between 1-15 characters long): ",
                                       lambda x: 1 <= len(x) <= 15)


# Opens the Query Console for sending raw requests directly to the manager.
def query_manager():
    global manager_socket

    # if we started the console via the -q console command, make sure the socket is open
    if manager_socket is None:
        manager_socket = socket(AF_INET, SOCK_DGRAM)
        print("Six Card Golf Client - Query Manager ")

    print("Type \'q\' to stop querying the manager.")
    query = input_validator(">>", lambda x: len(x) > 0)
    while query != "q":  # go back to the main menu when the user inputs "q"
        response = send_message_manager(query)  # send the inputted query to the manager and wait for the response
        print(response)
        query = input_validator(">>", lambda x: len(x) > 0)  # get next query and repeat


# Broadcast a message to all other players in the current game via the specified socket.
# message_bytes - the message to send, usually a string encoded in utf-8.
# soc - the message through which to send the requests and receive the responses.
# callback - the action to take when we received acknowledgment of a broadcast by a client.
#       This is called with the request bytes, and the client's address/port.
# notify_self - Default true. If false, the message will not be sent to our own username/ports.
# This is useful because we do not always have a second thread open listening for the reply,
# so if we try to communicate with ourselves, we'll be blocked waiting for a reply that will never come.
def broadcast(message_bytes, soc, callback=lambda x, y: x, notify_self=True, port_offset=0):
    players_copy = copy.deepcopy(players)
    for player in players_copy:  # send to all players in the game
        if notify_self or player.name != username:  # skip ourselves if the parameter is false
            soc.sendto(message_bytes, (player.address, player.port + port_offset))  # broadcast message
            request, client_addr = soc.recvfrom(2048)  # wait for acknowledgement
            callback(request, client_addr)  # take action on response


# Listens to the specified socket for a command of a particular name.
# When this command is received, acknowledge it, and parse the parameters out from the command.
# These tokens (and the sender) are returned to the caller to take action on the command.
def wait_for_command(command, soc):
    while True:
        request, sender = soc.recvfrom(2048)  # wait for command to come in
        message = request.decode()
        tokens = message.split("\n")  # split the message by newline; parameters will be on separate lines
        if tokens[0] == command:  # is the command we got the one we were expecting
            soc.sendto(f"ack {message}".encode(), sender)  # send acknowledgement of receipt
            tokens = tokens[1:]  # remove the command token, which is a given, leaving only the parameters array
            return tokens, sender


# Attempts to start a new game as the dealer.
# If the server successfully finds other players to play with, contacts them in order to start playing the game
def request_start_game(num_players):
    global players, dealer_socket, gameId

    # Send a message to the manager indicating we're ready to start a new game
    request = f"start game {username} {num_players}"
    response = send_message_manager(request)
    tokens = response.split("\n")
    if tokens[0] == "SUCCESS":  # notify the other players the game is starting
        gameId = int(tokens[1])
        tokens = tokens[2:]

        # Convert the list of players to Player objects for convenience
        players = []
        for player in tokens:
            new_player = Player.from_string(player)
            players.append(new_player)
            cards[new_player.name] = []  # all players start the game with no cards

        # spawn thread that will play the game on behalf of the dealer so the dealer main thread can do other stuff
        dealer_player_thread = threading.Thread(target=matchmaking, args=(1,))
        dealer_player_thread.start()

        assign_players()  # notify all the other players that the game is starting
        deal_cards()  # shuffle the deck, and distribute the cards to all players
        announce_initial_reveal()  # once all players have gotten their cards, everyone needs to reveal 2 cards

        # spawn thread that will check the state of the game at the end of each round to see if there was a winner
        game_state_thread = threading.Thread(target=wait_for_game_completion, args=(1,))
        game_state_thread.start()

        wait_for_initial_reveal_completion()  # wait for all players to reveal 2 cards before kicking off round 1

        # game setup is complete, wait for the threads to end, indicating the game is over
        game_state_thread.join()
        dealer_player_thread.join()

        # once the game is over, notify the manager so each player can join another game
        send_message_manager(f"end {gameId} {username}")
    else:
        print("There are not enough players in matchmaking right now, try again later.")


# Wait to be contacted by the dealer of a new game. The manager will provide the dealer our address and port.
def matchmaking(id):
    global players, cards, dealer_address

    tokens, sender = wait_for_command("assign player", peer_socket)
    tokens = tokens[1:]
    # Now that we have been assigned to a game, load all the other players from the message
    players = []
    for player in tokens:
        new_player = Player.from_string(player)
        players.append(new_player)
        cards[new_player.name] = []

    # keep track of the client who assigned us, since this indicates they are the dealer
    # this is needed to be able to initiate request to the dealer instead of just receiving them
    dealer_address = sender

    # wait for the dealer to shuffle the deck and start sending us cards
    wait_for_cards(0)


# Wait for the dealer to shuffle the deck and start sending us cards.
# This also keeps track of cards dealt to the other players, so that we can print out their game boards on our end.
def wait_for_cards(id):
    # Expect 6 cards for each player in the game
    i = 0
    while i < len(players) * 6:
        tokens, sender = wait_for_command("deal card", peer_socket)
        card = Card.from_string(tokens[0])
        cards[tokens[1]].append(card)  # deal the card to the player it was assigned to
        i += 1

    # Expect the stockpile and discard pile
    stacks["stock"] = []
    stacks["discard"] = []
    tokens, sender = wait_for_command("stack", peer_socket)
    stack_type = tokens[0]
    tokens = tokens[1:]
    for card in tokens:
        new_card = Card.from_string(card)
        stacks[stack_type].append(new_card)

    # Now that we have all the cards for all the players, we can print the game board
    print_cards()
    wait_for_reveal_announcement(0)


def play_round():
    global currentTurn, round_num

    print("#################################")
    print(f"     Round {round_num}")
    print("#################################")

    tokens, sender = wait_for_command("game state", dealer_socket)
    if tokens[0] == "end":
        print(f"The winner is {tokens[1]}")
        return True

    # tokens, sender = wait_for_command("pass stick", peer_socket)
    nextPlayer = players[0]
    currentTurn = nextPlayer
    del players[0]
    players.append(nextPlayer)

    print_cards()
    if nextPlayer.name == username:
        print(f"It's my turn")
        skip_replace = pop_card()
        if not skip_replace:
            replace_card()

        dealer_socket.sendto("query game state".encode(), (dealer_address[0], dealer_address[1] + 1))
        # request, client_addr = dealer_socket.recvfrom(2048)
    else:
        print(f"Waiting for {nextPlayer.name} to complete their turn.")
        listen_for_move()

    round_num += 1
    return False


def listen_for_move():
    global held_card

    tokens, sender = wait_for_command("pop", peer_socket)
    stack_type = tokens[0]

    if stack_type == "steal":
        temp_card = cards[tokens[1]][int(tokens[2])]
        cards[tokens[3]][int(tokens[4])].hidden = False
        cards[tokens[1]][int(tokens[2])] = cards[tokens[3]][int(tokens[4])]
        temp_card.hidden = False
        cards[tokens[3]][int(tokens[4])] = temp_card
        return
    else:
        held_card = stacks[stack_type].pop()

    print_cards()

    tokens, sender = wait_for_command("replace", peer_socket)
    if tokens[0] == "discard" or tokens[0] == "d":
        held_card.hidden = False
        stacks["discard"].append(held_card)
    else:
        swapped_card_index = int(tokens[0])
        user = tokens[1]
        swapped_card = cards[user][swapped_card_index]
        swapped_card.hidden = False
        cards[user][swapped_card_index] = held_card
        cards[user][swapped_card_index].hidden = False
        stacks["discard"].append(swapped_card)
    held_card = None


# Wait for all the cards to be dealt out to everyone, and allow the user to reveal 2 cards at that point.
def wait_for_reveal_announcement(id):
    # Since other users are revealing at the same time we're typing (which a blocking function call), start a second
    # thread to listen for which cards were turned over by the other users
    revelation_listener = threading.Thread(target=listen_for_revelations, args=(1,))

    request, client_addr = peer_socket.recvfrom(2048)  # wait until we're told we can start revealing cards
    message = request.decode()
    if message.startswith("announce initial reveal"):
        peer_socket.sendto(f"ack {message}".encode(), client_addr)

        revelation_listener.start()

        # Allow user to reveal 2 cards
        card1 = int_input("Choose the first card to reveal (between 0-5 inclusive): ", lambda x: 0 <= x <= 5)
        reveal_card(card1)

        card2 = int_input("Choose the second card to reveal (between 0-5 inclusive): ", lambda x: 0 <= x <= 5)
        while card2 == card1:  # check that the user isn't trying to reveal the same card twice
            print("That card is already revealed, choose a different card to reveal.")
            card2 = int_input("Choose the second card to reveal (between 0-5 inclusive): ", lambda x: 0 <= x <= 5)
        reveal_card(card2)

    print_cards()
    revelation_listener.join()

    # Start actually playing the game, taking turns making moves until someone wins
    game_complete = False
    while not game_complete:
        game_complete = play_round()


# Listen for broadcasts made by other players that indicate which cards they are revealing
# This is for revealing the first two cards at the start of the game.
def listen_for_revelations(id):
    # Expect two cards to be revealed by each player before terminating the thread
    cards_received = 0
    while cards_received < 2 * len(players):
        tokens, sender = wait_for_command("reveal card", peer_socket)
        cards[tokens[1]][int(tokens[0])].hidden = False  # reveal the card that was specified
        cards_received += 1


# Allows the user to selection what move they want to make.
# Broadcast to all other players that we have popped a card from the stock or discard,
# or we have stolen a card from another player.
def pop_card():
    global held_card
    valid_stacks = [1, 3]
    print("------------Get Net Card---------------")
    print("Where do you want to draw a card from?")
    print("1. Stock")
    if len(stacks["discard"]) > 0:  # disable discard option if the discard stack is empty
        valid_stacks.append(2)
        print("2. Discard")
    else:
        print("2. (You cannot draw from the discard because it is empty.)")
    print("3. Steal from another player")

    selection = int_input("Selection: ", lambda x: x in valid_stacks)
    stack_type = "stock"
    if selection == 2:
        stack_type = "discard"

    if selection == 3:  # Steal a card from another player
        steal_username = input_validator("From which user do you want to steal? ",
                                         lambda x: x in map(lambda p: p.name, players) and x != username)
        steal_card_index = int_input("Which card do you want to steal (must be revealed)? ",
                                     lambda x: not cards[steal_username][x].hidden)
        temp_card = cards[steal_username][steal_card_index]
        replace_card_index = int_input("Which card do you want to replace the stolen card with (must be hidden)? ",
                                       lambda x: cards[username][x].hidden)

        # Swap the stolen card with the card of our own we selected
        cards[username][replace_card_index].hidden = False
        cards[steal_username][steal_card_index] = cards[username][replace_card_index]
        temp_card.hidden = False
        cards[username][replace_card_index] = temp_card

        # Let everyone know which card we stole and which one we replaced it with
        broadcast(f"pop\nsteal\n{steal_username}\n{steal_card_index}\n{username}\n{replace_card_index}".encode(),
                  peer_socket,
                  notify_self=False)
        print_cards()
        return True  # by returning true we skip the second stage of the turn that would normally occur

    # If execution gets here, we're popping a card from one of the stacks (discard or stock)
    held_card = stacks[stack_type].pop()
    broadcast(f"pop\n{stack_type}".encode(), peer_socket,
              notify_self=False)

    print_cards()
    return False  # by returning false we make sure to do the second stage of our turn (replace_card)


# Replace the card in our hand (which we drew from one of the stacks) with another card from our deck.
# You can also discard the card that you're holding.
def replace_card():
    global held_card

    print("------------Swap Card---------------")
    print("Which of your cards do you want to replace?")
    print("Your selection should be between 0-5 (inclusive) or \'d\' for \'discard\'.")
    card_index_str = input_validator("Selection: ", lambda x: x in ["d", "discard", "0", "1", "2", "3", "4", "5"])
    if (card_index_str == "discard" or card_index_str == "d"):  # discard the card we are holding
        card_index = 6
        held_card.hidden = False
        stacks["discard"].append(held_card)
    else:  # replace the card we're holding with one of the six cards in our deck
        card_index = int(card_index_str)
        swapped_card = cards[username][card_index]
        swapped_card.hidden = False
        cards[username][card_index] = held_card
        cards[username][card_index].hidden = False
        stacks["discard"].append(swapped_card)

    held_card = None  # at the end of the turn, we shouldn't be holding anything
    broadcast(f"replace\n{card_index_str}\n{username}".encode(), peer_socket, notify_self=False)


# Print out the cards each user has, as well as the top card of the discard, and other elements of the GUI.
def print_cards():
    print("##############################")
    print("----Stacks----")
    for stack in stacks: # print the top card of each stack
        print(f"{stack}:")

        if len(stacks[stack]) > 0:
            top_card = stacks[stack][-1].player_card_to_string()
            print(top_card)
        else:
            print(
                f"""┌─ ─ ─ ┐
  No   
│Cards │
        
└ ─ ─ ─┘""")

    print("----Players----")
    for player in cards: # print out every card that a player has
        print(f"{player}:")
        if currentTurn is not None and currentTurn.name == player:
            print("It's this player's turn. They are holding:")
            if held_card is not None:
                held_card.hidden = False
                print(f"{held_card.player_card_to_string()}")
            else:
                print(f"{Card.empty_card_to_string()}")
        print(Card.player_deck_to_string(cards[player]))
    print("##############################")


# Run by the dealer to wait for all players to finish revealing 2 cards at the beginning of the game.
def wait_for_initial_reveal_completion():
    # busy wait, checking if the proper number of cards have been revealed by each player
    waiting_for_revelations = True
    while waiting_for_revelations:
        cards_revealed = 0
        for player_cards in cards:
            for card in cards[player_cards]:
                if not card.hidden:
                    cards_revealed += 1
        if cards_revealed == 2 * len(players):  # expect 2 cards from each player to be revealed
            waiting_for_revelations = False

    # Querying the game state (listener runs on another socket and thread in the dealer) kicks off a round
    # Normally this is done by the player whose turn it is, but since its no one's turn yet, the dealer must do it
    dealer_socket.sendto("query game state".encode(), (dealer_address[0], dealer_address[1] + 1))


# Checks at the end of each round whether all the cards have been revealed (which would indicate the end of the game)
# Also tallies the score and determines a winner.
# Run by the dealer.
def wait_for_game_completion(id):
    global game_state_socket

    waiting_for_completion = True
    while waiting_for_completion:
        # Wait until someone queries this thread from the game state
        tokens, sender = wait_for_command("query game state", game_state_socket)

        # Check if all players have revealed all six cards
        cards_revealed = 0
        player = ""
        for player_cards in cards:
            for card in cards[player_cards]:
                if not card.hidden:
                    cards_revealed += 1
        if cards_revealed == 6 * len(players):
            waiting_for_completion = False

        # Tally the scores and determine who the winner is, or who is currently winning
        scores = {}
        winner = ""
        winner_score = 9999999  # players are competing for lowest score, so start with really high score for comparing
        for player in cards:
            player_sum = 0
            # add up the value of all the player's cards
            for card in cards[player]:
                value = card.value[1:]
                # Map special card values to their real value
                if value == "A":  # Ace
                    value = 1
                elif value == "J":  # Jack
                    value = 11
                elif value == "Q":  # Queen
                    value = 12
                elif value == "K":  # King
                    value = 13
                else:  # If it's not a special card just use the face value
                    value = int(value)
                player_sum += value
            scores[player] = player_sum
            if player_sum < winner_score:  # does this player have a better score than the current winner?
                winner_score = player_sum
                winner = player

        response = "continue"
        if not waiting_for_completion: # if all cards have been revealed, let everyone know the game is over
            response = f"end\n{winner}"

        broadcast(f"game state\n{response}".encode(), game_state_socket, lambda x, y: x, True, 1)


# Announce to all players of the current game that they can start revealing two of their cards
# Occurs at start of the game after cards have been dealt. Run by the dealer.
def announce_initial_reveal():
    broadcast("announce initial reveal".encode(), dealer_socket)


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
    # Generate the string that consists of a list of all the players
    players_str = ""
    for player in players:
        players_str += f"\n{player.to_string()}"

    message = f"assign player\n{len(players)}{players_str}".encode()
    broadcast(message, dealer_socket)


# Notifies all other players that the player is being dealt a card of value 'card'.
# Run by the dealer.
def deal_card(player, card):
    broadcast(f"deal card\n{card.to_string()}\n{player.name}".encode(), dealer_socket)


# Distributes the appropriate number of random cards in a deck to each player of the current game.
def deal_cards():
    all_cards = shuffle_cards()
    cards_dealt = 0
    while cards_dealt < len(players) * 6:
        player = players[cards_dealt % len(players)]
        card = all_cards.pop()
        deal_card(player, card)
        cards_dealt += 1

    broadcast_stack("stock", all_cards)


# Sends an entire stack of cards to every other player in the game.
def broadcast_stack(stack_type, stack_cards):
    # Encode entire stack of cards into single string
    card_str = ""
    for card in stack_cards:
        card_str += f"\n{card.to_string()}"
    broadcast(f"stack\n{stack_type}{card_str}".encode(), dealer_socket)


# Notifies all other players that this client is turning over a card in their stack.
def reveal_card(src):
    broadcast(f"reveal card\n{src}\n{username}".encode(), dealer_socket)


# Requests input from the user, and converts the response to an integer.
# If the input cannot be converted to an integer, or the validation function returns False, it tries again.
def int_input(prompt_str, validator=lambda x: True):
    input_int = None
    input_valid = False
    while not input_valid: # keep trying to collect the input until we get one that is valid
        try:
            input_str = input(prompt_str)  # get the input from the user
            input_int = int(input_str)  # convert to int (may throw ValueError)
            input_valid = True
            if not validator(input_int):  # check the validator function (by default always passes)
                input_valid = False
        except ValueError:  # convert to int was not successful
            # nothing
            input_valid = False
    return input_int


# Requests input from the user, and returns it if it passes the validator function (returns True).
# If validation fails, the function tries again with new input from the user until successful.
def input_validator(prompt_str, validator=lambda x: True):
    input_valid = False
    while not input_valid: # only return when we get a valid input
        input_str = input(prompt_str)  # get input from user
        if validator(input_str):  # check if validation passes
            return input_str


# Sends a message to the manager/server and returns its response as a string.
def send_message_manager(message):
    global manager_socket

    manager_socket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = manager_socket.recvfrom(2048)
    return response.decode()
