from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

import json

@dataclass
class Bet():
    ID: str
    FIELD: str
    HOME_TEAM: str
    AWAY_TEAM: str
    ODD_1: float
    ODD_0: float
    ODD_2: float
    WINNING_ODD: Optional[int]
    DEADLINE: Optional[date]
    GAMBLERS: Dict[str, str]
    
    def __post_init__(self):
        if isinstance(self.GAMBLERS, str):
            self.GAMBLERS = json.loads(self.GAMBLERS)

    def set_winning_odd(self, winning_odd:int):
        if not isinstance(winning_odd, int):
            raise TypeError("Odd must be an integer.")
        if winning_odd not in {0, 1, 2}:
            raise ValueError("Result must be one of: 0, 1, or 2.")
        if self.WINNING_ODD:
            raise ValueError(f"{self.HOME_TEAM}-{self.AWAY_TEAM} has already resulted: {self.WINNING_ODD}")

        self.WINNING_ODD = winning_odd

    def __repr__(self):
        return (
            f"{self.HOME_TEAM} - {self.AWAY_TEAM} | Odds: (1: {self.ODD_1:.2f}, 0: {self.ODD_0:.2f}, 2: {self.ODD_2:.2f}), "
            f"Winning Odd: {self.WINNING_ODD}"
        )
    