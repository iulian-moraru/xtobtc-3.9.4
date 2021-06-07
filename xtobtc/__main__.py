import re
import json
import pkg_resources
from os import environ, path
from pathlib import Path
from decimal import Decimal
from bitfinex import ClientV1, ClientV2
from xtobtc.utils import initlog


LOG = initlog('xtobtc')
btfx_client1 = ClientV1(environ.get('API_KEY'), environ.get('API_SECRET'), 2.0)
btfx_client2 = ClientV2(environ.get('API_KEY'), environ.get('API_SECRET'), 2.0)

VERSION = pkg_resources.require("xtobtc")[0].version
LOG.info(f"Loaded app version {VERSION}")


def do_margin():
    wallet_lst = btfx_client2.wallets_balance()
    margin_lst = [x for x in wallet_lst if x[0] == 'margin']
    for x in margin_lst:
        if x[1]:
            currency_from = x[1]
            currency_to = x[1][0:3]
            if x[2] and Decimal(format(x[2], ".8f")) > 0:
                m_amount = str(Decimal(format(x[2], ".8f")))
                try:
                    result = btfx_client2.transfer_between_wallets("margin",
                                                                   "exchange",
                                                                   currency=currency_from,
                                                                   currency_to=currency_to,
                                                                   amount=m_amount)
                except Exception as e:
                    LOG.error(e)
                    continue
                else:
                    LOG.info(result)
                    pair = currency_from + currency_to
                    write_to_file("Transfer", pair, currency_from, currency_to, Decimal(format(x[2], ".8f")), result)


def remove_symbols(symbols_lst):
    new_lst = [x for x in symbols_lst if "eur" not in x["pair"] if "gbp" not in x["pair"] if "jpy" not in x["pair"]]
    new_lst2 = [x for x in new_lst if "test" not in x["pair"] if "f0" not in x["pair"]]
    ust_pair = [x for x in new_lst2 if x["pair"] == "ustusd"]
    xch_pair = [x for x in new_lst2 if x["pair"] == "xchusd"]
    new_lst3 = [x for x in new_lst2 if "ust" not in x["pair"] if "xch" not in x["pair"]]
    new_lst3.append(ust_pair[0])
    new_lst3.append(xch_pair[0])
    return new_lst3


def remove_symbols2(wallet, symbols_lst):
    for currency_inf in wallet:
        currency = currency_inf[1].lower()
        # This currencies are treated at the sepparately. We buy btc
        if currency == "btc" or currency == "usd":
            continue

        usd_pair = currency + "usd"
        btc_pair = currency + "btc"

        dbls_lst = []
        for pair in symbols_lst:
            if usd_pair == pair["pair"] or btc_pair == pair["pair"]:
                dbls_lst.append(pair)

        if len(dbls_lst) == 2:
            symbols_lst.remove(dbls_lst[0])

    for currency_inf in wallet:
        currency = currency_inf[1].lower()
        # This currencies are treated at the sepparately. We buy btc
        if currency == "btc" or currency == "usd":
            continue

        usd_pair = currency + ":usd"
        btc_pair = currency + ":btc"

        dbls_lst = []
        for pair in symbols_lst:
            if usd_pair == pair["pair"] or btc_pair == pair["pair"]:
                dbls_lst.append(pair)

        if len(dbls_lst) == 2:
            symbols_lst.remove(dbls_lst[0])

    return symbols_lst


def check_pair(currency, pair):
    regex = fr"^{currency}"
    matches = re.search(regex, pair)
    trade = "usd_sell"
    bad_match = False
    currency_to = ""
    if matches:
        if ":" in pair:
            pair_split = pair.split(":")
            if pair_split[0] != currency:
                bad_match = True
                return trade, bad_match, currency_to
            else:
                right_currency = pair.split(currency+":")[1]
        else:
            right_currency = pair.split(currency)[1]

        if right_currency == "btc":
            currency_to = right_currency
            trade = "btc_sell"
        elif right_currency == "usd":
            currency_to = right_currency
            return trade, bad_match, currency_to
        else:
            bad_match = True
    else:
        regex = fr"{currency}$"
        matches = re.search(regex, pair)
        if matches:
            if ":" in pair:
                left_currency = pair.split(":")[0]
            else:
                left_currency = pair.split(currency)[0]

            if left_currency == "btc":
                currency_to = left_currency
                trade = "btc_buy"
            else:
                bad_match = True
        else:
            bad_match = True
    return trade, bad_match, currency_to


def create_msg(action, currency_from, currency_to, w_amount, response):
    msg = ""
    if action == "Transfer":
        try:
            amount = str(response[4][7])
        except Exception as e:
            LOG.error(e)
            return msg
        msg = f"Transfer from margin {amount} {currency_from} to {currency_to}"
    elif action == "Trade":
        try:
            trade_amount = Decimal(format(response[4][0][6], ".8f"))
        except Exception as e:
            LOG.error(e)
            return msg
        str_amount = str(trade_amount)
        trade_amt = abs(trade_amount)
        if trade_amount == int(trade_amt):
            trd_amt_frmt = int(trade_amt)
        else:
            trd_amt_frmt = format(trade_amt, ".8f")

        try:
            price = Decimal(format(response[4][0][16], ".8f"))
        except Exception as e:
            LOG.error(e)
            return msg

        if price == int(price):
            price_frmt = int(price)
        else:
            price_frmt = format(price, ".8f")

        if "-" in str_amount:
            amt = abs(price * trade_amount)

            if amt == int(amt):
                amount = int(amt)
            else:
                amount = format(amt, ".8f")

            msg = f"Sell: {trd_amt_frmt} {currency_from} @ {price_frmt} {currency_to}, " \
                  f"got {amount} {currency_to}"
            msg = "".join(msg)
        else:
            if w_amount == int(w_amount):
                w_amount_frmt = int(w_amount)
            else:
                w_amount_frmt = format(w_amount, ".8f")

            msg = f"Buy: {trd_amt_frmt} {currency_to} @ {price_frmt} {currency_from}." \
                  f"Total {currency_from} value {w_amount_frmt}"
            msg = "".join(msg)
    elif action == "Final":
        if w_amount == int(w_amount):
            btc_amount = int(w_amount)
        else:
            btc_amount = "%.8f" % w_amount

        msg = f"Current BTC balance is {btc_amount}"

    return msg


def write_to_file(action, pair, currency_from, currency_to, w_amount, response):
    home_path = str(Path.home())
    data_path = path.join(home_path, "apps/xtobtc/data")
    alerts_file = path.join(data_path, "alerts.json")

    if not path.exists(data_path):
        Path(data_path).mkdir(parents=True, exist_ok=True)

    msg = create_msg(action, currency_from, currency_to, w_amount, response)

    if not msg:
        return

    action_info = {
        "action": action,
        "pair": pair,
        "details": msg
    }

    with open(alerts_file, 'a+') as f:
        try:
            json.dump(action_info, f)
            f.write("\n")
        except Exception as err:
            LOG.error(err)

    f.close()
    return


def trade_currency(trade, pair, w_amount, trade_min_amt, currency_from, currency_to):
    order_symbol = "t" + pair.upper()
    if trade == "usd_sell" or trade == "btc_sell":
        last_amt_order = w_amount - (Decimal(5 / 100) * w_amount)
        if last_amt_order > trade_min_amt:
            order_amount = "-" + str(last_amt_order)
            try:
                result = btfx_client2.submit_order("EXCHANGE MARKET", order_symbol, "", order_amount)
            except Exception as e:
                LOG.error(e)
                return
            else:
                LOG.info(result)
                write_to_file("Trade", pair, currency_from, currency_to, last_amt_order, result)
    elif trade == "btc_buy":
        try:
            last_price = btfx_client2.ticker(order_symbol)[6]
        except Exception as e:
            print(pair, order_symbol)
            LOG.error(e)
            return

        if last_price:
            min_amt = w_amount / Decimal(last_price)
            last_amt_order = min_amt - (Decimal(5 / 100) * min_amt)
            if last_amt_order > trade_min_amt:
                order_amount = str(last_amt_order)
                try:
                    result = btfx_client2.submit_order("EXCHANGE MARKET", order_symbol, "", order_amount)
                except Exception as e:
                    LOG.error(e)
                    return
                else:
                    LOG.info(result)
                    wallet_amount = w_amount - (Decimal(5 / 100) * w_amount)
                    write_to_file("Trade", pair, currency_from, currency_to, wallet_amount, result)
    return


def final_trades(symbols_lst_final):

    def get_inf(wallet_info, symb_lst_final, currency, pair):
        curr_amt = 0
        min_amt = 0

        for curr_inf in wallet_info:
            if curr_inf[1] == currency:
                curr_amt = Decimal(format(curr_inf[2], ".8f"))
                break

        for pair_inf in symb_lst_final:
            if pair_inf["pair"] == pair:
                min_amt = Decimal(format(float(pair_inf["minimum_order_size"]), ".8f"))
                break

        return curr_amt, min_amt

    try:
        wallet_inf = btfx_client2.wallets_balance()
    except Exception as e:
        LOG.error(e)
        return

    pair = "btcusd"
    curr_amt, min_amt = get_inf(wallet_inf, symbols_lst_final, "USD", pair)
    trade_currency("btc_buy", pair, curr_amt, min_amt, "usd", "btc")

    pair = "btceur"
    curr_amt, min_amt = get_inf(wallet_inf, symbols_lst_final, "EUR", pair)
    trade_currency("btc_buy", pair, curr_amt, min_amt, "eur", "btc")


def main():
    LOG.info("Started xtobtc")

    # Transfer from margin to exchange
    do_margin()

    # Buy Btc
    try:
        wallet_bal = btfx_client2.wallets_balance()
    except Exception as e:
        LOG.error(e)
        return
    # remove margin. already treated
    wallet = [x for x in wallet_bal if x[0] != "margin"]

    try:
        symbols_lst = btfx_client1.symbols_details()
    except Exception as e:
        LOG.error(e)
        return

    new_symb_inf_lst = remove_symbols(symbols_lst)
    symbols_lst_final = remove_symbols2(wallet, new_symb_inf_lst)

    for currency_inf in wallet:
        currency = currency_inf[1].lower()
        # This currencies are treated at the sepparately. We buy btc
        if currency == "btc" or currency == "usd":
            continue

        w_amount = Decimal(format(currency_inf[2], ".8f"))

        for pair_inf in symbols_lst_final:
            if currency not in pair_inf["pair"]:
                continue

            # This pair is treated at the end
            if pair_inf["pair"] == "btcusd":
                continue

            pair = pair_inf["pair"]
            trade, bad_match, currency_to = check_pair(currency, pair)

            if bad_match:
                continue

            trade_min_amt = Decimal(format(float(pair_inf["minimum_order_size"]), ".8f"))
            trade_currency(trade, pair, w_amount, trade_min_amt, currency, currency_to)

    # Finally. Buy BTC with USD or EUR
    final_trades(symbols_lst)

    # Get final BTC balance
    try:
        wallet = btfx_client2.wallets_balance()
    except Exception as e:
        LOG.error(e)
        return

    for curr_inf in wallet:
        if curr_inf[1] == "BTC":
            btc_amount = Decimal(format(curr_inf[2], '.8f'))
            LOG.info(f"Current BTC balance is {btc_amount}")
            write_to_file("Final", "", "", "", btc_amount, "")
            break


if __name__ == '__main__':
    main()

