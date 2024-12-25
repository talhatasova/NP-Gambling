import json
import sqlite3
import uuid

from rich import print
from bet import Bet
from gambler import Gambler
from settings import Paths, Classes, Constant
from typing import List

db_path = Paths.DATABASE

def generateID(key_type:str) -> str:
    match key_type:
        case Classes.BET:
            unique_id = f"{Classes.BET}_{uuid.uuid4().hex[:Constant.ID_LENGTH].upper()}"
        case Classes.GAMBLER:
            unique_id = f"{Classes.GAMBLER}_{uuid.uuid4().hex[:Constant.ID_LENGTH].upper()}"
        case _:
            raise KeyError(f"{key_type} does not exist in key types.")
    return unique_id

# BET METHODS #
def createBetsSQL():
    query = f'''
    CREATE TABLE IF NOT EXISTS bets_new (
        id CHAR({Constant.ID_LENGTH}) PRIMARY KEY,
        field TINYTEXT DEFAULT NULL,
        home_team TINYTEXT DEFAULT NULL,
        away_team TINYTEXT DEFAULT NULL,
        odd_1 NUMERIC DEFAULT 1.00,
        odd_0 NUMERIC DEFAULT 1.00,
        odd_2 NUMERIC DEFAULT 1.00,
        winning_bet TINYINT DEFAULT NULL,
        deadline DATETIME,
        gamblers JSON DEFAULT NULL,
    )
    '''
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        conn.commit()

def create_bet(bet: tuple) -> tuple:
    values = [generateID(key_type=Classes.BET), *bet]
    query = '''
        INSERT OR IGNORE INTO bets (id, field, home_team, away_team, odd_1, odd_0, odd_2, deadline, gamblers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id, field, home_team, away_team, odd_1, odd_0, odd_2, deadline
    '''
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, values)
        created_bet = cursor.fetchone()
        conn.commit()

    return created_bet

def get_all_bets() -> List[Bet]:
    query = "SELECT id, field, home_team, away_team, odd_1, odd_0, odd_2 FROM bets"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [Bet(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows]

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()

def get_bet(bet:int) -> Bet:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if isinstance(bet, int):
        cursor.execute('SELECT * FROM bets WHERE id = ?', (bet,))
        result = cursor.fetchone()
        if not result:
            raise KeyError("No bet with the given ID.")
    else:
        raise KeyError("Make sure that you provide the bet's ID number.")

    conn.close()
    return Bet(*result)

def set_bet_result(bet_ref:int, result:int):
    bet:Bet = get_bet(bet=bet_ref)
    try:
        bet.set_winning_odd(winning_odd=result)
    except (TypeError, ValueError) as e:
        raise e
    
    query = '''
        UPDATE bets
        SET winning_bet = ?
        WHERE id = ?
    '''
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (bet.WINNING_ODD, bet.ID))
        conn.commit()
    
    print(f"[BET-RESULT] {bet.HOME_TEAM}-{bet.AWAY_TEAM}: {result}")


# GAMBLER METHODS #
def createGamblersSQL():
    query = '''
    CREATE TABLE IF NOT EXISTS gamblers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE DEFAULT NULL,
        bets JSON DEFAULT NULL,
        correct_guess NUMERIC DEFAULT 0.0,
        wrong_guess NUMERIC DEFAULT 0.0,
        number_guess NUMERIC DEFAULT 0.0,
        total_payoff NUMERIC DEFAULT 0.0
    )
    '''
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(query)
    conn.commit()
    conn.close()

def create_gambler(identifier:int, name:str):
    try:
        existing_gambler = get_gambler(gambler=identifier)
        raise ValueError(f"You are already registered as {existing_gambler.NAME}")
    except KeyError:
        query = '''
            INSERT OR IGNORE INTO gamblers (id, name, bets, correct_guess, wrong_guess, number_guess, total_payoff) VALUES (?, ?, ?, ?, ?, ?, ?)
        '''
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (identifier, name, json.dumps({}), 0, 0, 0, 0))
            conn.commit()

def get_all_gamblers() -> List[Gambler]:
    query = "SELECT id, name, bets, correct_guess, wrong_guess, number_guess, total_payoff FROM gamblers"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        return [Gambler(row[0], row[1], row[2], row[3], row[4], row[5], row[6]) for row in rows]

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return []
    finally:
        conn.close()

def get_gambler(gambler:int|str) -> Gambler:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    if isinstance(gambler, int):
        cursor.execute('SELECT * FROM gamblers WHERE id = ?', (gambler,))
        result = cursor.fetchone()
        if not result:
            raise KeyError("No gambler with the given ID.")
    elif isinstance(gambler, str):
        cursor.execute('SELECT * FROM gamblers WHERE name = ?', (gambler,))
        result = cursor.fetchone()
        if not result:
            raise KeyError("No gambler with the given name.")
    else:
        raise KeyError("Make sure that you provide either the gambler's ID number or the gambler's name.")
    
    conn.close()
    return Gambler(*result)
    
def gambler_place_bet(gambler_ref:int|str, bet_ref:int, bet_on:int):
    gambler:Gambler = get_gambler(gambler_ref)
    bet:Bet = get_bet(bet_ref)
    try:
        gambler.place_bet(game_to_bet=bet.ID, bet_on=bet_on)
    except KeyError:
        bet_played = gambler.BETS.get(str(bet.ID))
        raise KeyError(f"{gambler.NAME} has already gambled on ({bet.HOME_TEAM}-{bet.AWAY_TEAM}): {bet_played}")
    
    try:
        bets_json = json.dumps(gambler.BETS)
    except TypeError:
        raise ValueError("Failed to serialize BETS to JSON.")
    
    query = '''
        UPDATE gamblers
        SET bets = ?
        WHERE id = ?
    '''
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query, (bets_json, gambler.ID))
        conn.commit()
    
    print(f"[BET-MADE] {gambler.NAME}: {bet.ID} ({bet.HOME_TEAM}-{bet.AWAY_TEAM}) -> {bet_on}")

def get_gambler_count() -> int:
    query = "SELECT COUNT(*) FROM gamblers"
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        count = cursor.fetchone()[0]
    return count

def declare_results(bet_ref:int|str) -> List[str]:
    output = []
    bet:Bet = get_bet(bet_ref)
    bet_id = str(bet.ID)

    all_gamblers:List[Gambler] = get_all_gamblers()
    for gambler in all_gamblers:
        bet_placed = gambler.BETS.get(bet_id)
        if not bet_placed:
            continue
        
        if bet_placed == bet.WINNING_ODD:
            # Bet won
            gambler.CORRECT += 1
            payout = getattr(bet, f"ODD_{bet_placed}") - 1 # winnings - bet placing fee
            gambler.PAYOFF += payout
            output.append(f"Gambler {gambler.NAME} won bet on '{bet.HOME_TEAM}-{bet.AWAY_TEAM}'. Payoff updated by +{payout:.2f}$.")
        else:
            # Bet lost
            gambler.WRONG += 1
            payout = -1
            output.append(f"Gambler {gambler.NAME} lost bet on '{bet.HOME_TEAM}-{bet.AWAY_TEAM}'. Payoff updated by -1.00$.")

        # Update total stats
        gambler.TOTAL += 1

        # Save the updated stats to the database
        query = '''
            UPDATE gamblers
            SET bets = ?, correct_guess = ?, wrong_guess = ?, number_guess = ?, total_payoff = ?
            WHERE id = ?
        '''
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                query,
                (
                    json.dumps(gambler.BETS),
                    gambler.CORRECT,
                    gambler.WRONG,
                    gambler.TOTAL,
                    gambler.PAYOFF,
                    gambler.ID
                )
            )
            conn.commit()
    return output