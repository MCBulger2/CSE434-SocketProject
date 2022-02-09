
class Game:
    def __init__(self, gameId, dealer, players):
        self.gameId = gameId
        self.dealer = dealer
        self.players = players

    def to_string(self):
        players_str = "["
        for player in self.players:
            sep = ","
            if len(players_str) == 1:
                sep = ""
            players_str += f"{sep}{player.to_string()}"
        players_str += "]"

        return f"({self.gameId}, {self.dealer}, {players_str})"
