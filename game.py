
class Game:
    def __init__(self, gameId, dealer, players):
        self.gameId = gameId
        self.dealer = dealer
        self.players = players

    def to_string(self):
        players_str = ""
        for player in self.players:
            players_str += f"\n\t\t{player.to_string()}"
        return f"Game {self.gameId}\n\tDealer: {self.dealer}\n\tPlayers: {players_str}"
