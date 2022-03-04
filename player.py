# Matthew Bulger
# CSE 434
# Dr. Syrotiuk
# Socket Project

# Represent a single player/client
class Player:
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port

    # convert a player to a string representation for transmission
    def to_string(self):
        return f"({self.name}, {self.address}, {self.port})"

    # convert a string to a player (string likely output from to_string above and transmitted as a message)
    @staticmethod
    def from_string(player_str):
        player_str1 = player_str.replace("(",  "").replace(")", "").replace("\n", "").replace("\t", "").replace(" ", "")
        tokens = player_str1.split(",")
        new_player = Player(tokens[0], tokens[1], int(tokens[2]))
        return new_player
