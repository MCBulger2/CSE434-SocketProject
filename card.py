
class Card:
    def __init__(self, value):
        self.value = value
        self.hidden = True

    def to_string(self):
        return f"({self.value}, {self.hidden})"

    @staticmethod
    def from_string(card_str):
        card_str1 = card_str.replace("(", "").replace(")", "").replace("\n", "").replace("\t", "").replace(" ", "")
        tokens = card_str1.split(",")
        new_card = Card(tokens[0])
        if tokens[1] == "False:":
            new_card.hidden = False

        return new_card
