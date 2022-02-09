
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

    def player_card_to_string(self):
        suit = self.value[0]
        num_value = self.value[1:]
        spacing = ""
        if len(str(num_value)) == 1 or self.hidden:
            spacing = " "
        if self.hidden:
            suit = "*"
            num_value = "*"

        return \
            f"""┌──────┐
│ {suit}    │
│      │
│  {spacing}{num_value}  │
└──────┘"""

    @staticmethod
    def empty_card_to_string():
        return \
            f"""┌─ ─ ─ ┐
        
│      │       
       
└ ─ ─ ─┘"""

    @staticmethod
    def merge_lines(l1, l2):
        res = ""
        l1a = list(filter(lambda x: x != "", l1.split("\n")))
        l2a = list(filter(lambda x: x != "", l2.split("\n")))
        for i in range(len(l1a)):
            res += f"{l1a[i]}{l2a[i]}\n"
        return res

    @staticmethod
    def player_deck_to_string(deck):
        result = ""
        for i in range(len(deck)):
            new_card_str = deck[i].player_card_to_string()
            if (len(result) > 0):
                result = Card.merge_lines(result, new_card_str)
            else:
                result = new_card_str
        return result.replace(";n;", "\n")

