#!/usr/bin/python

# ~~~~~==============   HOW TO RUN   ==============~~~~~
# 1) Configure things in CONFIGURATION section
# 2) Change permissions: chmod +x bot.py
# 3) Run in loop: while true; do ./bot.py; sleep 1; done

from __future__ import print_function

import sys
import socket
import json

# ~~~~~============== CONFIGURATION  ==============~~~~~
# replace REPLACEME with your team name!
team_name="CRISPY"
# This variable dictates whether or not the bot is connecting to the prod
# or test exchange. Be careful with this switch!
test_mode = True

# This setting changes which test exchange is connected to.
# 0 is prod-like
# 1 is slower
# 2 is empty
test_exchange_index=1
prod_exchange_hostname="production"

port=25000 + (test_exchange_index if test_mode else 0)
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
    print ('READ EXCHANGE: ', line)
    return line

# ~~~~~============== DATA STRUCTURE ==============~~~~~
LIMITS = {
    "BOND": 100,
    "AAPL": 100,
    "MSFT": 100,
    "GOOG": 100,
    "XLK" : 100,
    "BABZ": 10,
    "BABA": 10
}
OUR_STATEMENT = [
]

OUR_BOOK = {
    "BUY": {
    },

    "SELL": {
    }
}

for sym, limit in LIMITS.iteritems():
    OUR_STATEMENT.append({sym: []})
    OUR_BOOK["BUY"][sym] = \
        (0, {"size": None,
               "price": None,
               "id": None
         })
    OUR_BOOK["SELL"][sym] = \
        (0, {"size": None,
         "price": None,
         "id": None
         })


def parse_exchange(line):
    if line['type'] == 'ack':
        OUR_BOOK[line['dir']][line['symbol']][line['ID']] = {'price': line['price'], 'size': line['size']}

    elif line['type'] == 'out':
        del OUR_BOOK[line['dir']][line['symbol']][line['ID']]

    elif line['type'] == 'fill':
        mult_dir = 1
        if line['dir'] == 'SELL':
            mult_dir = -1
        OUR_BOOK[line['dir']][line['symbol']][line['ID']]['size'] += line['size']


# ~~~~~============== BOND EXCHANGE ==============~~~~~
def exchange_bonds(price):
    if price is None:
        return None
    if (price < 1000):
        return ('BUY', price, 10)
    if (price > 1000):
        return ('SELL', price, 10)
    else:
        return None


def read_buy_sell_BOND(json_data):
    if json_data['type'] == "Trade":
        if json_data['symbol'] == "Bond":
            return json_data['price']
    return None


def simple_bond(exchange):
    count = 0
    while True:
        if OUR_BOOK['BUY']['BONDS'][] is not None:
            if (val != 'reject'):
                write_to_exchange(exchange,
                                  {"type": "add", "order_id": count, "symbol": "BOND", "dir": "BUY", "price": 999,
                                   "size": 1})
                print('buy')
                write_to_exchange(exchange,
                                  {"type": "add", "order_id": count + 1, "symbol": "BOND", "dir": "SELL", "price": 1000,
                                   "size": 1})
                print('sell')
                count += 2

# ~~~~~============== MAIN LOOP ==============~~~~~

def main():
    exchange = connect()
    write_to_exchange(exchange, {"type": "hello", "team": team_name.upper()})
    hello_from_exchange = read_from_exchange(exchange)
    print("The exchange replied:", hello_from_exchange, file=sys.stderr)

    simple_bond(exchange)

if __name__ == "__main__":
    main()