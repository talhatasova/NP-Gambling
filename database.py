from datetime import datetime, timezone
import random
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Table, Double, DateTime
from sqlalchemy import event, func, case

from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from sqlalchemy import select

from settings import Constant, BetPlaceLines, Emoji

Base = declarative_base()

# Association Table for many-to-many relationship
gambler_bet_table = Table(
    'gambler_bet', Base.metadata,
    Column('gambler_id', Integer, ForeignKey('gamblers.id'), primary_key=True),
    Column('bet_id', Integer, ForeignKey('bets.id'), primary_key=True),
    Column('bet_on', Integer)
)

class Gambler(Base):
    __tablename__ = 'gamblers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    correct = Column(Integer, default=0)
    wrong = Column(Integer, default=0)
    total = Column(Integer, default=0)
    payoff = Column(Double, default=0.00)
    bets = relationship('Bet', secondary=gambler_bet_table, back_populates='gamblers')

    def __repr__(self):
        return (
            f"**{self.name}**\n\n"
            f"**Bets Placed:** {self.total}\n"
            f"**Correct Bets:** {self.correct}\n"
            f"**Wrong Bets:** {self.wrong}\n"
            f"**Total Payoff:** {self.payoff:.2f}$"
        )
    def __eq__(self,other):
        return self.payoff == other.payoff

    def __lt__(self,other):
        return self.payoff < other.payoff

    def __le__(self, other):
        return self.payoff <= other.payoff

class Bet(Base):
    __tablename__ = 'bets'

    id:Integer = Column(Integer, primary_key=True)
    field:String = Column(String, nullable=False)
    home_team:String = Column(String, nullable=False)
    away_team:String = Column(String, nullable=False)
    odd_1:Double = Column(Double, nullable=False)
    odd_0:Double = Column(Double, nullable=False)
    odd_2:Double = Column(Double, nullable=False)
    deadline:DateTime = Column(DateTime, nullable=False)
    week:Integer = Column(Integer, nullable=False)
    winning_odd:Integer = Column(Integer, nullable=True)
    gamblers = relationship('Gambler', secondary=gambler_bet_table, back_populates='bets')

    def __repr__(self):
        return (
            f"{self.home_team} - {self.away_team} | Odds: (1: {self.odd_1:.2f}, 0: {self.odd_0:.2f}, 2: {self.odd_2:.2f}), "
            f"Match Date: {self.deadline} (Week {self.week})"
        )
    
    def __eq__(self,other):
        return self.deadline == other.deadline

    def __lt__(self,other):
        return self.deadline < other.deadline

    def __le__(self, other):
        return self.deadline <= other.deadline

class WeeklyStatistics(Base):
    __tablename__ = 'weekly_statistics'

    id = Column(Integer, primary_key=True, autoincrement=True)  # Unique ID for each record
    week_num = Column(Integer, nullable=False)  # The week number
    gambler_id = Column(Integer, ForeignKey('gamblers.id'), nullable=False)  # The gambler's ID
    name = Column(String, nullable=False)  # The gambler's name for reference
    rank = Column(Integer, nullable=True)
    payoff = Column(Double, default=0.0, nullable=False)  # The total payoff for the week
    correct = Column(Integer, default=0, nullable=False)  # Correct bets during the week
    wrong = Column(Integer, default=0, nullable=False)  # Wrong bets during the week
    total = Column(Integer, default=0, nullable=False)  # Total bets placed during the week

    def __repr__(self):
        return (
            f"Week {self.week_num} - {self.name}: "
            f"Payoff: {self.payoff:.2f}, Correct: {self.correct}, Wrong: {self.wrong}, Total: {self.total}"
        )

# Function to generate an 8-digit random number
def generate_unique_bet_id():
    while True:
        random_id = random.randint(10_000_000, 99_999_999)
        if not session.query(Bet).filter_by(id=random_id).first():
            return random_id
        
@event.listens_for(Bet, "before_insert")
def set_bet_id(mapper, connection, target):
    if not target.id:
        target.id = generate_unique_bet_id()

# Database Setup
engine = create_engine('sqlite:///gamblers_bets.db')  # Use SQLite for simplicity
Base.metadata.create_all(engine)

# Session
Session = sessionmaker(bind=engine)
session = Session()

# Functions for CRUD Operations
def add_gambler(discord_id: int, name: str):
    gambler = session.query(Gambler).filter_by(id=discord_id).first()
    if gambler:
        raise ValueError(f"{gambler.name} is already registered.")

    # Create a new gambler if not found
    gambler = Gambler(id=discord_id, name=name)
    session.add(gambler)
    session.commit()
    return gambler

def get_gambler(gambler_dc_id: int):
    gambler = session.get(Gambler, gambler_dc_id)
    if gambler:
        return session.get(Gambler, gambler_dc_id)
    else:
        raise KeyError(f"No gambler with the given ID: {gambler_dc_id}")

def get_gambler_bet_details(gambler_dc_id: int):
    stmt = (
        select(
            Gambler.name,
            Bet.field,
            Bet.home_team,
            Bet.odd_1,
            Bet.away_team,
            Bet.odd_2,
            Bet.odd_0,
            Bet.deadline,
            gambler_bet_table.c.bet_on
        )
        .join(gambler_bet_table, Gambler.id == gambler_bet_table.c.gambler_id)
        .join(Bet, Bet.id == gambler_bet_table.c.bet_id)
        .where(Gambler.id == gambler_dc_id)
    )

    results = session.execute(stmt).fetchall()
    if not results:
        return None
    
    bets = [
        Bet(
            field=field,
            home_team=home_team,
            away_team=away_team,
            odd_1=odd1,
            odd_0=odd0,
            odd_2=odd2,
            deadline=deadline,
            week=0  # Use 0 if week is not part of the query; adjust as necessary
        )
        for _, field, home_team, odd1, away_team, odd2, odd0, deadline, _ in results
    ]
    sorted_bets = sorted(bets)

    # Format the sorted results
    bets_details = []
    for bet in sorted_bets:
        bet_on = next(result[-1] for result in results if result[2] == bet.home_team and result[4] == bet.away_team)
        bet_placed = f"{Emoji.ZERO} Draw ({bet.odd_0})" if bet_on == 0 else f"{Emoji.ONE} {bet.home_team} ({bet.odd_1})" if bet_on == 1 else f"{Emoji.TWO} {bet.away_team} ({bet.odd_2})"
        bet_description = f"{bet.home_team} vs {bet.away_team} | {bet_placed}"
        bets_details.append(bet_description)

    return bets_details

def add_bet(description: dict) -> Bet:
    try:
        bet = Bet(**description)
        session.add(bet)
        session.commit()
        return bet
    except Exception as e:
        session.rollback()
        print(e)

def link_gambler_to_bet(gambler_id: int, bet_id: int, bet_on: int, skip_timecheck: bool=False):
    gambler = session.get(Gambler, gambler_id)
    bet = session.get(Bet, bet_id)

    if not gambler:
        raise ValueError(f"No gambler found with ID: {gambler_id}")
    if not bet:
        raise ValueError(f"No bet found with ID: {bet_id}")
    if not skip_timecheck:
        if datetime.now(timezone.utc) > bet.deadline.astimezone(timezone.utc):
            raise ValueError("You are too late to place a bet on this match. Try another one.")

    # Query the existing `bet_on` value
    stmt = select(gambler_bet_table.c.bet_on).where(
        (gambler_bet_table.c.gambler_id == gambler_id) &
        (gambler_bet_table.c.bet_id == bet_id)
    )
    result = session.execute(stmt).scalar()  # Fetch the `bet_on` value if it exists

    # Determine old and new bets for messaging
    old_bet = bet.home_team if result == 1 else bet.away_team if result == 2 else "beraberlik" if result == 0 else "kararsiz"
    new_bet = bet.home_team if bet_on == 1 else bet.away_team if bet_on == 2 else "beraberlik" if bet_on == 0 else "kararsiz"

    if old_bet == new_bet:
        raise ValueError(f"You have already made your bet as {old_bet}.")
    
    if bet_on == 3:
        stmt = gambler_bet_table.delete().where(
            (gambler_bet_table.c.gambler_id == gambler_id) &
            (gambler_bet_table.c.bet_id == bet_id)
            )
        session.execute(stmt)
        session.commit()
        return f"{old_bet} olan iddiamı geri çekiyorum çünkü gayım."
    
    if result is not None:
        # If a previous bet exists, update the `bet_on` value
        stmt = gambler_bet_table.update().where(
            (gambler_bet_table.c.gambler_id == gambler_id) &
            (gambler_bet_table.c.bet_id == bet_id)
        ).values(bet_on=bet_on)
        session.execute(stmt)
        session.commit()
        iam = BetPlaceLines.getRandomNPProperty()
        return f"{old_bet} olan iddiamı {new_bet} olarak değiştiriyorum çünkü {iam}."

    else:
        # If no previous bet exists, insert a new record explicitly
        stmt = gambler_bet_table.insert().values(
            gambler_id=gambler_id,
            bet_id=bet_id,
            bet_on=bet_on
        )
        session.execute(stmt)

        # Add the ORM relationship for the gambler and bet
        #gambler.bets.append(bet)
        session.commit()

        line = (
            f"{bet.home_team} {BetPlaceLines.getRandomWinClaim()}"
            if bet_on == 1
            else f"{bet.away_team} {BetPlaceLines.getRandomWinClaim()}"
            if bet_on == 2
            else f"{BetPlaceLines.getRandomDrawClaim()}"
        )
        return line

def get_gambler_bets(gambler_id: int):
    gambler = session.get(Gambler, gambler_id)
    return gambler.bets if gambler else None

def get_all_gamblers():
    out = session.query(Gambler).all()
    out.sort(reverse=True)
    return out

def get_all_bets():
    out = session.query(Bet).all()
    out.sort()
    return out

def get_bet(bet_id: int):
    bet = session.get(Bet, bet_id)
    if bet:
        return bet
    else:
        raise KeyError(f"No bet with the given ID: {bet_id}")

def set_bet_result(bet_id: int, result: int):
    bet = session.get(Bet, bet_id)
    if not bet:
        raise KeyError(f"No bet with the given ID: {bet_id}")
    
    if bet.winning_odd:
        raise ValueError(f"This bet ({bet}) has already resulted: {bet.winning_odd}")
    
    if bet.deadline.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError(f"You cannot set the result before the match ends.")
    
    # Validate the result
    if result not in Constant.BET_OUTCOMES:
        raise ValueError("Invalid result. Result must be one of: 1 (home team wins), 0 (draw), or 2 (away team wins).")

    bet.winning_odd = result
    session.commit()  # Persist the changes in the database
    return bet

def update_gamblers_on_bet_result(bet_id: int):
    try:
        bet = get_bet(bet_id=bet_id)
    except KeyError as e:
        raise e
    
    result = bet.winning_odd

    # Get all gamblers who bet on this bet
    stmt = (
        select(gambler_bet_table.c.gambler_id, gambler_bet_table.c.bet_on)
        .where(gambler_bet_table.c.bet_id == bet_id)
    )
    gambler_bets = session.execute(stmt).fetchall()

    output: list[str] = []
    if not gambler_bets:
        print(f"No gamblers placed a bet on: {bet}")
        return

    # Update each gambler based on their bet outcome
    for gambler_id, bet_on in gambler_bets:
        gambler = get_gambler(gambler_dc_id=gambler_id)
        if not gambler:
            print(f"Skipping invalid gambler ID: {gambler_id}")
            continue
        
        old_payoff = round(gambler.payoff,2)
        # Check if the gambler's bet was correct
        if bet_on == result:
            result_str = Emoji.CHECK
            gambler.correct += 1
            gambler.payoff += bet.odd_1 if result == 1 else bet.odd_0 if result == 0 else bet.odd_2
        else:
            result_str = Emoji.X
            gambler.wrong += 1

        # Subtract participation fee
        gambler.payoff -= 1
        # Update total bets
        gambler.total += 1

        new_payoff = round(gambler.payoff,2)
        bet_placed = f"{Emoji.ZERO}: Draw ({bet.odd_0})" if bet_on == 0 else f"{Emoji.ONE}: {bet.home_team} ({bet.odd_1})" if bet_on == 1 else f"{Emoji.TWO}: {bet.away_team} ({bet.odd_2})"
        payoff_status_text = "⤴" if new_payoff > old_payoff else "⤵" if new_payoff < old_payoff else "↔"
        output.append(f"""
            **{gambler.name}** {result_str}
        Bet: {bet_placed}
        Payoff: {old_payoff} {payoff_status_text} {new_payoff}
        """)
    # Commit updates to gamblers
    session.commit()
    return output

def set_all_gamblers_global_stats():
    # Fetch all gamblers
    gamblers = session.query(Gambler).all()

    for gambler in gamblers:
        # Initialize stats
        total_bets = 0
        correct_bets = 0
        wrong_bets = 0
        total_payoff = 0.0

        # Fetch all bets placed by this gambler
        stmt = (
            select(gambler_bet_table.c.bet_id, gambler_bet_table.c.bet_on)
            .join(Bet, Bet.id == gambler_bet_table.c.bet_id)
            .where(gambler_bet_table.c.gambler_id == gambler.id)
        )
        gambler_bets = session.execute(stmt).fetchall()

        for bet_id, bet_on in gambler_bets:
            bet = session.get(Bet, bet_id)

            if not bet or bet.winning_odd is None:
                continue  # Skip bets without results

            total_bets += 1

            if bet_on == bet.winning_odd:
                correct_bets += 1
                total_payoff += (
                    bet.odd_1 if bet_on == 1 else bet.odd_0 if bet_on == 0 else bet.odd_2
                )
            else:
                wrong_bets += 1

            # Subtract participation fee
            total_payoff -= 1

        # Update gambler's stats
        gambler.correct = correct_bets
        gambler.wrong = wrong_bets
        gambler.total = total_bets
        gambler.payoff = round(total_payoff, 2)

    # Commit updates
    session.commit()
    print("Global stats updated for all gamblers.")

def get_weekly_stats(week_number: int):
    return (
        session.query(WeeklyStatistics)
        .filter(WeeklyStatistics.week_num == week_number)
        .order_by(WeeklyStatistics.payoff.desc())
        .all()
    )

def update_weekly_stats(week_number: int):
    all_gamblers = get_all_gamblers()
    session.query(WeeklyStatistics).filter(WeeklyStatistics.week_num == week_number).delete()

    for gambler in all_gamblers:
        total, correct, wrong, payoff = 0, 0, 0, 0.0

        stmt = (
            select(gambler_bet_table.c.bet_id, gambler_bet_table.c.bet_on)
            .join(Bet, Bet.id == gambler_bet_table.c.bet_id)
            .where(gambler_bet_table.c.gambler_id == gambler.id, Bet.week == week_number)
        )
        gambler_bets = session.execute(stmt).fetchall()
        
        for bet_id, bet_on in gambler_bets:
            bet = get_bet(bet_id)

            if bet.winning_odd is None:  # Skip if the bet result is not set
                continue

            if bet_on == bet.winning_odd:
                correct += 1
                payoff += bet.odd_1 if bet_on == 1 else bet.odd_0 if bet_on == 0 else bet.odd_2
            else:
                wrong += 1

            payoff -= 1  # Subtract participation fee
            total += 1

        weekly_stat = WeeklyStatistics(
            week_num=week_number,
            gambler_id=gambler.id,
            name=gambler.name,
            rank=None,
            payoff=round(payoff, 2),
            correct=correct,
            wrong=wrong,
            total=total
        )
        session.add(weekly_stat)
    session.commit()

    weekly_stats = (
        session.query(WeeklyStatistics)
        .filter(WeeklyStatistics.week_num == week_number)
        .order_by(WeeklyStatistics.payoff.desc())
        .all()
    )
    for rank, stat in enumerate(weekly_stats, start=1):
        stat.rank = rank
    session.commit()

if __name__ == "__main__":
    set_all_gamblers_global_stats()