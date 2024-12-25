from dataclasses import dataclass
import json
from typing import Dict

@dataclass
class Gambler():
    ID: str
    NAME: str
    CORRECT: int
    WRONG: int
    TOTAL: int
    PAYOFF: float
    BETS: Dict[str, str]

    def __post_init__(self):
        if isinstance(self.BETS, str):
            self.BETS = json.loads(self.BETS)

    def place_bet(self, game_to_bet:str, bet_on:int):
        if not isinstance(bet_on, int):
            raise TypeError("Odd must be an integer.")
        if bet_on not in {0, 1, 2}:
            raise ValueError("Bet must be made on one of: 0, 1, or 2.")
        
        if game_to_bet not in self.BETS:
            self.BETS.update({game_to_bet:bet_on})
        else:
            raise KeyError("You have already made your guess on this bet.")
    
    def __repr__(self):
        return (
            f"**{self.NAME}**\n"
            f"**Bets Placed:** {self.TOTAL}\n"
            f"**Correct Bets:** {self.CORRECT}\n"
            f"**Wrong Bets:** {self.WRONG}\n"
            f"**Total Payoff:** {self.PAYOFF:.2f}"
        )