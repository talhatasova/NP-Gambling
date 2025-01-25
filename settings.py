import random

class Paths():
    DATABASE = "database.db"

class Constant():
    ID_LENGTH = 8
    BET_OUTCOMES = [1,0,2]

class Fields():
    FOOTBALL = "Football"
    BASKETBALL = "Basketball"
    VOLLEYBALL = "Volleyball"
    CS2 = "CS2"
    DOTA2 = "DOTA2"
    LOL = "League of Legends"
    ROCKET_LEAGUE = "Rocket League"
    CHESS = "Chess"
    ALL_FIELDS = [FOOTBALL, BASKETBALL, VOLLEYBALL, CS2, DOTA2, LOL, ROCKET_LEAGUE, CHESS]

class ID():
    class Roles():
        ADMIN = 330595330494169090
        GAMBLER = 1317238552886775869

    class Channels():
        ADMIN = 1317240924585201714
        MAC_SONUC = 1317239926202564608
        MAC_BILDIRIM = 1317239684493213757
        KAYIT = 1317239294242455602
        LEADERBOARD = 1317239426203783239
        DEBUG = 1328002864919875635

class Emoji():
    X = "❌"
    CHECK = "✅"
    ZERO = "0️⃣"
    ONE = "1️⃣"
    TWO = "2️⃣"
    GAY_KISS = "👨🏿‍❤️‍💋‍👨🏿"
    GAY_FLAG = "🏳️‍🌈"
    HOME = "🏠"
    AWAY  = "✈️"
    DRAW = "🤝"
    WITHDRAW = "🏳️"
    DATE = "📅"
    
    REACTION_ROLES = {
    "🎲": ID.Roles.GAMBLER
    }
        
class Classes():
    BET = "bet"
    GAMBLER = "gmb"

class BetPlaceLines():
    @classmethod
    def getRandomWinClaim(cls) -> str:
        return random.choice([
            "bu maçı zükertir.",
            "yenmezse götümü açıyorum.",
            "ez win gg.",
            "alacak ve gerçek gurmeler ortaya çıkacak."
        ])
    @classmethod
    def getRandomDrawClaim(cls) -> str:
        return random.choice([
            "Bu maçı züksen kimse yenemez.",
            "Sabaha kadar oynasalar yenişemezler.",
            "Nicksizim54'ün çük boyu > bu maçı birinin kazanma ihtimali",
            "Güçlü takıma oynamak kolaydır, asıl gurmeler beraberlik bilerek kendini gösterir, iyi akşamlar."
        ])
    @classmethod
    def getRandomNPProperty(cls) -> str:
        return random.choice([
            "GAYIM.",
            "döneğim.",
            "ibonun amk."
        ])