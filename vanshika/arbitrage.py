from __future__ import print_function

import sys
import socket
import json

# ~~~~~============== CONFIGURATION  ==============~~~~~
# replace REPLACEME with your team name!
team_name = "CRISPY"
# This variable dictates whether or not the bot is connecting to the prod
# or test exchange. Be careful with this switch!
test_mode = True

# This setting changes which test exchange is connected to.
# 0 is prod-like
# 1 is slower
# 2 is empty
test_exchange_index = 1
prod_exchange_hostname = "production"

port = 25000 + (test_exchange_index if test_mode else 0)
exchange_hostname = "test-exch-" + team_name if test_mode else prod_exchange_hostname


# ~~~~~============== NETWORKING CODE ==============~~~~~
def connect():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((exchange_hostname, port))
    return s.makefile('rw', 1)


def write_to_exchange(exchange, obj):
    json.dump(obj, exchange)
    exchange.write("\n")


def read_from_exchange(exchange):
    line = json.loads(exchange.readline())
    return line


# ~~~~============== DATA STRUCTURE ==============~~~~
CURRENT_STATUS, OID = {}, {}

LIMITS = {
    "BOND": 100,
    "AAPL": 100,
    "MSFT": 100,
    "GOOG": 100,
    "XLK": 100,
    "BABZ": 10,
    "BABA": 10,
    "USD": 10000000
}

for stock in LIMITS.keys():
    CURRENT_STATUS[stock] = {
        "best_sell": None,
        "best_buy": None,
        "fair_value": None,
        "size": 0,
        "our_sell": None,
        "our_buy": None
    }

CURRENT_STATUS['USD']['size'] = 0

UNACKNOWLEDGED_OID = {}
CURRENT_OID = {}
COMPLETE_OID = {}
BABZ_OID = []
BABA_OID = []


def process_signals(exchange):
    line = read_from_exchange(exchange)
    type = line['type']

    def do_fill(line):
        oid = line['order_id']
        buyorsell = 1
        if line['dir'] == 'SELL':
            buyorsell = -1
        CURRENT_OID[oid]['price'] = line['price']
        CURRENT_OID[oid]['size'] += line['size'] * buyorsell
        CURRENT_STATUS[line['symbol']]['size'] += CURRENT_OID[oid]['size'] * buyorsell
        CURRENT_STATUS['USD']['size'] += CURRENT_OID[oid]['price'] * CURRENT_OID[oid]['size'] * buyorsell * -1

    if type == 'error':
        print(line['error'], file=sys.stderr)
    elif type == 'book':
        if line['symbol'] == 'BABA' or line['symbol'] == 'BABZ':
            calculate_fair_value(line)
            return True
    elif type == 'ack':
        oid = line['order_id']
        try:
            CURRENT_OID[oid] = UNACKNOWLEDGED_OID[oid]
            del UNACKNOWLEDGED_OID[oid]
        except:
            return False
    elif type == 'reject':
        oid = line['order_id']
        try:
            COMPLETE_OID[oid] = UNACKNOWLEDGED_OID[oid]
            del UNACKNOWLEDGED_OID[oid]
        except (KeyError):
            return False
    elif type == 'out':
        oid = line['order_id']
        try:
            COMPLETE_OID[oid] = CURRENT_OID[oid]
            del CURRENT_OID[oid]
        except (KeyError):
            return False
    elif type == 'fill':
        do_fill(line)
    return False


# ~~~~~============== ARBITRAGE CODE ==============~~~~~
def calculate_fair_value(line):
    print("calculate_fair_value")
    max_buy = None
    min_sell = None
    for buys in line['buy']:
        if max_buy == None:
            max_buy = buys[0]
        elif buys[0] > max_buy:
            max_buy = buys[0]
    for sells in line['sell']:
        if min_sell == None:
            min_sell = sells[0]
        elif sells[0] < min_sell:
            min_sell = sells[0]

    print("MIN_SELL: ", min_sell, " MAX_BUY: ", max_buy)
    if min_sell is not None:
        CURRENT_STATUS[line['symbol']]['best_sell'] = min_sell
    if max_buy is not None:
        CURRENT_STATUS[line['symbol']]['best_buy'] = max_buy
    if max_buy is not None and min_sell is not None:
        CURRENT_STATUS[line['symbol']]['fair_value'] = (CURRENT_STATUS[line['symbol']]['best_sell'] + CURRENT_STATUS[line['symbol']]['best_buy']) / 2


BAB_BUFFER = 2
BUY_SELL_SPREAD = 1


def arbitrage_bab(exchange, order_number, count):
    print("in arbitrage")
    baba_fair = CURRENT_STATUS['BABA']['fair_value']
    baba_sell = CURRENT_STATUS['BABA']['best_sell']
    baba_buy = CURRENT_STATUS['BABA']['best_buy']
    babz_fair = CURRENT_STATUS['BABZ']['fair_value']
    babz_sell = CURRENT_STATUS['BABZ']['best_sell']
    babz_buy = CURRENT_STATUS['BABZ']['best_buy']
    print("BABA_FAIR: ", baba_fair, " BABZ_FAIR: ", babz_fair)

    if baba_fair is not None and babz_fair is not None:
        print("in not none")
        if baba_fair + BAB_BUFFER < babz_fair:
            print("HERE")
            add_oid_baba = {"type": "add", "order_id": count, "symbol": "BABA", "dir": "BUY",
                            "price": baba_buy + BUY_SELL_SPREAD,
                            "size": order_number}
            write_to_exchange(exchange, add_oid_baba)
            add_oid_babz = {"type": "add", "order_id": count + 1, "symbol": "BABZ", "dir": "SELL",
                            "price": babz_sell - BUY_SELL_SPREAD,
                            "size": order_number}
            write_to_exchange(exchange, add_oid_babz)

            CURRENT_STATUS['BABA']['our_buy'] = baba_buy + BUY_SELL_SPREAD
            UNACKNOWLEDGED_OID[count] = add_oid_baba
            add_to_baba(count, exchange)
            UNACKNOWLEDGED_OID[count + 1] = add_oid_babz
            add_to_babz(count + 1, exchange)

        elif baba_fair - BAB_BUFFER > babz_fair:
            add_oid_baba = {"type": "add", "order_id": count, "symbol": "BABA", "dir": "SELL",
                            "price": baba_sell - BUY_SELL_SPREAD,
                            "size": order_number}
            write_to_exchange(exchange, add_oid_baba)
            add_oid_babz = {"type": "add", "order_id": count + 1, "symbol": "BABZ", "dir": "BUY",
                            "price": babz_buy + BUY_SELL_SPREAD,
                            "size": order_number}
            write_to_exchange(exchange, add_oid_babz)

            CURRENT_STATUS['BABA']['our_sell'] = baba_sell - BUY_SELL_SPREAD
            UNACKNOWLEDGED_OID[count] = add_oid_baba
            add_to_baba(count, exchange)
            UNACKNOWLEDGED_OID[count + 1] = add_oid_babz
            add_to_babz(count + 1, exchange)


def add_to_baba(id, exchange):
    if len(BABA_OID) == 2:
        torem = min(BABA_OID)
        cancel(torem, exchange)
        BABA_OID.remove(torem)
    BABA_OID.append(id)


def add_to_babz(id, exchange):
    if len(BABZ_OID) == 2:
        torem = min(BABZ_OID)
        cancel(torem, exchange)
        BABZ_OID.remove(torem)
    BABZ_OID.append(id)


def cancel(id, exchange):
    write_to_exchange(exchange, {"type": "cancel", "order_id": id})


# ~~~~~============== MAIN LOOP ==============~~~~~

def main():
    exchange = connect()
    write_to_exchange(exchange, {"type": "hello", "team": team_name.upper()})
    hello_from_exchange = read_from_exchange(exchange)
    print("The exchange replied:", hello_from_exchange, file=sys.stderr)

    count = 0
    while True:
        boolean = process_signals(exchange)
        if (abs(CURRENT_STATUS['BABA']['size']) < 10 or abs(CURRENT_STATUS['BABA']['size']) < 10) and boolean:
            arbitrage_bab(exchange, 1, count)
            count += 2

if __name__ == "__main__":
    main()