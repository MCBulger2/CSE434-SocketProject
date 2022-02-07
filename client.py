from socket import *

serverName = 'localhost'
serverPort = 4500
clientPort = 4505  # by default a client has port 4505. as ports are allocated each client will get a higher port

clientSocket = None


def start_client() -> None:
    global clientSocket, clientPort

    clientSocket = socket(AF_INET, SOCK_DGRAM)

    username = input("Username: ")

    isRegistered = False
    while not isRegistered:
        response = send_message(f"register {username} {clientPort}").decode()
        if response == "SUCCESS":
            isRegistered = True
        elif response == "FAILURE PORT":
            clientPort += 1
        elif response == "FAILURE USERNAME":
            print(f"Username \'{username}\' is already taken.")
            username = input("Username: ")

    while True:
        message = input("Message: ")
        response = send_message(message)
        print(response)

    clientSocket.close()


def send_message(message):
    global clientSocket

    clientSocket.sendto(message.encode(), (serverName, serverPort))
    response, server_addr = clientSocket.recvfrom(2048)
    return response
