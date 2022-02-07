
class Player:
    def __init__(self, name, address, port):
        self.name = name
        self.address = address
        self.port = port

    def to_string(self):
        return f"({self.name}, {self.address}, {self.port})"