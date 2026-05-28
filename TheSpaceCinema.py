import requests
import json

OKCYAN = '\033[96m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BLUE = '\033[94m'
UNDERLINE = '\033[4;38;5;129m'
GREEN = '\033[92m'
ORANGE = '\033[38;5;208m'


class TheSpaceCinema:
    BASE = "https://www.thespacecinema.it"
    API_CINEMAS = BASE + "/api/microservice/showings/cinemas"
    API_FILMS = BASE + "/api/microservice/showings/films"
    API_SHOWINGDATES = BASE + "/api/microservice/showings/showingDates"
    API_ORDER = BASE + "/api/microservice/booking/order"
    def getCinemas(self):
        r = requests.get(self.API_CINEMAS).json()
        cinemas = [cinema for item in r["result"] for cinema in item["cinemas"]]
        return cinemas

    def getFilms(self, cinema=None):
        api = self.API_FILMS
        if cinema is not None:
            api = api + "?cinemaId=" + cinema["cinemaId"]
        films = requests.get(api).json()["result"]
        return films

    def getShowingGroups(self, cinema, film):
        api = f"{self.API_CINEMAS}/{cinema['cinemaId']}/films/{film['filmId']}/showingGroups?minEmbargoLevel=3"
        s = requests.Session()
        s.get(self.BASE)
        r = s.get(api)
        if r.status_code != 200:
            print(r.content)
            print(api)
            exit(1)
        else:
            r = r.json()["result"]
        return r

    def getSeats(self, cinema, showing):
        s = requests.Session()
        s.get(self.BASE + showing["bookingUrl"])
        r = s.get(self.BASE + f"/api/microservice/booking/Session/{cinema['cinemaId']}/{showing['sessionId']}/seats")
        return r.json()["result"]

    def selectSeats(self, seats, selected_seats):
        ret_seats = []
        for row in seats["seatRows"]:
            for seat in row["columns"]:
                if seat["name"].lower() in selected_seats:
                    ret_seats.append(seat)
        return ret_seats

    def __getTickets(self, cinema, showing):
        s = requests.Session()
        s.get(self.BASE + showing["bookingUrl"])
        r = s.get(self.BASE + f"/api/microservice/booking/Session/{cinema['cinemaId']}/{showing['sessionId']}/tickets").json()
        return r["result"][0]

    def __GetTicketsCode(self, tickets, areaCategoryCode):
        for ticket in tickets["tickets"]:
            if ticket["areaCategoryCode"] == areaCategoryCode:
                return ticket["code"]

    def postOrder(self, cinema, showing, seats):
        tickets = self.__getTickets(cinema, showing)
        tickets_payload = {}

        for seat in seats:
            if seat["areaCategoryCode"] not in tickets_payload:
                tickets_payload[seat["areaCategoryCode"]] = {
                    "areaCategoryCode": seat["areaCategoryCode"],
                    "code": self.__GetTicketsCode(tickets, seat["areaCategoryCode"]),
                    "seats": []
                }
            tickets_payload[seat["areaCategoryCode"]]["seats"].append({
                "areaNumber": seat["areaNumber"],
                "rowIndex": seat["rowIndex"],
                "columnIndex": seat["columnIndex"]
            })

        body = {
            "cinemaId": cinema["cinemaId"],
            "sessionId": showing["sessionId"],
            "customer": {
                "email": "info@example.com"
            },
            "tickets": list(tickets_payload.values()),
        }

        headers = {"content-type": "application/json"}
        s = requests.Session()
        s.get(self.BASE + showing["bookingUrl"])
        s.post(self.API_ORDER, data=json.dumps(body), headers=headers)

    def printSeats(self, seats):
        rows = seats["seatRows"]
        row_i = 0

        while row_i < len(rows):
            if all(v is None for v in rows[row_i]["columns"]):
                rows.pop(row_i)
                continue

            print(rows[row_i]["rowLabel"], end=" ")
            seat_i = 0
            row_seats = rows[row_i]["columns"]

            while seat_i < len(rows[row_i]["columns"]):
                if row_seats[seat_i] is None:
                    rows[row_i]["columns"].pop(seat_i)
                    continue

                seat = row_seats[seat_i]
                if seat["seatStatus"] != 0:
                    print(UNDERLINE, end=" ")
                elif seat["areaCategoryCode"] == "0000000005":
                    print(GREEN, end=" ")
                elif seat["areaCategoryCode"] == "0000000002":
                    print(ORANGE, end=" ")
                elif seat["areaCategoryCode"] == "0000000003":
                    print(FAIL, end=" ")
                elif seat["areaCategoryCode"] == "0000000004":
                    print(BLUE, end=" ")

                print(seat["name"], end=ENDC + " ")
                seat_i += 1

            print()
            row_i += 1

