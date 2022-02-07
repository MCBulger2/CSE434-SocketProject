
class Player:
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port

    def to_string(self):
        return f"({self.name}, {self.address}, {self.port})"

    @staticmethod
    def from_string(player_str):
        player_str1 = player_str.replace("(",  "").replace(")", "").replace("\n", "").replace("\t", "").replace(" ", "")
        tokens = player_str1.split(",")
        print(tokens[1])
        print(tokens[2])
        new_player = Player(tokens[0], tokens[1], int(tokens[2]))
        return new_player
