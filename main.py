import database

def main():
    database.createBetsSQL()
    database.createGamblersSQL()
    database.gambler_place_bet("Deneme", 3, 2)
    database.set_bet_result(bet_ref=3, result=2)
    #database.update_gambler_stats()


if __name__ == "__main__":
    main()