from socket import *
import threading
import time

from player import Player

serverName = 'localhost'
serverPort = 4500
clientPort = 4505  # by default a client has port 4505. as ports are allocated each client will get a higher port
portsPerClient = 5

clientSocket = None
clientSocket2 = None

def start_client() -> None:
    global clientSocket, clientSocket2, clientPort

    clientSocket = socket(AF_INET, SOCK_DGRAM)
    #  clientSocket.bind(("", serverPort))


    username = input("Username: ")

    isRegistered = False
    while not isRegistered:
        response = send_message(f"register {username} {clientPort}")
        if response == "SUCCESS":
            isRegistered = True
        elif response == "FAILURE PORT":
            clientPort += portsPerClient
        elif response == "FAILURE USERNAME":
            print(f"Username \'{username}\' is already taken.")
            username = input("Username: ")

    clientSocket2 = socket(AF_INET, SOCK_DGRAM)
    clientSocket2.bind(("", clientPort))
    x = threading.Thread(target=listener, args=(1, ))
    x.start()
    print(f"The client is listening at port {str(clientPort)}.")

    while True:
        message = input("Message: ")
        ##response = send_message(message)
        request_start_game(username, 1)
        print(response)

    clientSocket.close()


def listener(id):
    print(str(id))
    while True:
        print("here")
        request, client_addr = clientSocket2.recvfrom(2048)
        print(f"Request from {client_addr}: {request.decode()}")
        # clientSocket2.sendto(request, client_addr)


def request_start_game(username, num_players):
    request = f"start game {username} {num_players}"
    response = send_message(request)
    tokens = response.split("\n")
    if tokens[0] == "SUCCESS":
        num_players = int(tokens[1])
        tokens = tokens[2:]
        players = []
        for player in tokens:
            players.append(Player.from_string(player))
        ping(players[0])


def ping(peer: Player):
    print(peer.to_string() + " ping ")
    clientSocket2.sendto("PING".encode(), (peer.address, int(peer.port)))
    #print(response)


def send_message(message):
    global clientSocket

    clientSocket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = clientSocket.recvfrom(2048)
    return response.decode()
