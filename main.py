import time
import os
from TheSpaceCinema import TheSpaceCinema
from datetime import datetime

def main():
    debug = True

    space = TheSpaceCinema()
    cinemas = space.getCinemas()

    ic = 0
    for cinema in cinemas:
        print(f"{ic}) {cinema["cinemaName"]}")
        ic+=1

    if not debug:
        selected_cinema = cinemas[int(input("pick a cinema: "))]
    else:
        selected_cinema = cinemas[32]

    films = space.getFilms(selected_cinema)
    print("---------------------------------------------")

    fc = 0
    for film in films:
        print(f"{fc}) {film["filmTitle"]}")
        fc += 1

    if not debug:
        selected_film = films[int(input("pick a film: "))]
    else:
        selected_film = films[0]

    showingGroups = space.getShowingGroups(selected_cinema, selected_film)
    print("---------------------------------------------")

    dc = 0
    for day in showingGroups:
        print(f"{dc}) {day["date"]}")
        dc += 1

    if not debug:
        selected_day = showingGroups[int(input("pick a day: "))]
    else:
        selected_day = showingGroups[0]
    print("---------------------------------------------")

    tc = 0
    for timec in selected_day["sessions"]:
        print(f"{tc}) {timec["startTime"]}")
        tc += 1

    if not debug:
        selected_showing = selected_day["sessions"][int(input("pick a time: "))]
    else:
        selected_showing = selected_day["sessions"][-1]
    print("---------------------------------------------")

    seats = space.getSeats(selected_cinema, selected_showing)
    space.printSeats(seats)

    if not debug:
        selected_seats = input("select wanted seats, use this format 'j1 j2 h11 h12: ").split(" ")
    else:
        selected_seats = "g4 g5"
    selected_seats = space.selectSeats(seats, selected_seats)
    while True:
        print(datetime.now())
        if datetime.now().hour >= 21:
            exit(0)
        space.postOrder(selected_cinema, selected_showing, selected_seats)

        time.sleep(60)

main()