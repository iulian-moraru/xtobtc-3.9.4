import re
import json
from os import environ, path
from pathlib import Path
from decimal import Decimal
from bitfinex import ClientV1, ClientV2
# from utils import initlog
from xtobtc.utils import initlog

LOG = initlog('xtobtc')
btfx_client1 = ClientV1(environ.get('API_KEY'), environ.get('API_SECRET'), 2.0)
btfx_client2 = ClientV2(environ.get('API_KEY'), environ.get('API_SECRET'), 2.0)


def do_margin():
    wallet_lst = btfx_client2.wallets_balance()
    margin_lst = [x for x in wallet_lst if x[0] == 'margin']
    for x in margin_lst:
        if x[1]:
            currency_from = x[1]
            currency_to = x[1][0:3]
            if x[2] and Decimal(format(x[2], '.5f')) > 0:
                m_amount = str(Decimal(format(x[2], '.5f')))
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
                    write_to_file("Transfer", pair, m_amount)


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

    if matches:
        if ":" in pair:
            pair_split = pair.split(":")
            if pair_split[0] != currency:
                bad_match = True
                return trade, bad_match
            else:
                right_currency = pair.split(currency+":")[1]
        else:
            right_currency = pair.split(currency)[1]

        if right_currency == "btc":
            trade = "btc_sell"
        elif right_currency == "usd":
            return trade, bad_match
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
                trade = "btc_buy"
            else:
                bad_match = True
        else:
            bad_match = True
    return trade, bad_match

def write_to_file(action, pair, response):
    home_path = str(Path.home())
    data_path = path.join(home_path, "apps/xtobtc/data")
    alerts_file = path.join(data_path, "alerts.json")
    LOG.info(alerts_file)
    if not path.exists(data_path):
        LOG.info("created dir")
        Path(data_path).mkdir(parents=True, exist_ok=True)

    amount = ""
    if action == "Transfer":
        try:
            amount = str(response[4][7])
        except Exception as e:
            LOG.error(e)
            return
    elif action == "Trade":
        try:
            amount = str(response[4][0][6])
        except Exception as e:
            LOG.error(e)
            return
        LOG.info("traded")
    action_info = {
        "action": action,
        "pair": pair,
        "amount": amount
    }

    with open(alerts_file, 'a+') as f:
        try:
            json.dump(action_info, f)
            f.write("\n")
        except Exception as err:
            LOG.error(err)
        else:
            LOG.info("WROTE")
    f.close()
    return

def trade_currency(trade, pair, w_amount, trade_min_amt):
    order_symbol = "t" + pair.upper()
    if trade == "usd_sell" or trade == "btc_sell":
        if w_amount > trade_min_amt:
            last_amt_order = w_amount - (Decimal(5 / 100) * w_amount)
            order_amount = "-" + str(last_amt_order)
            try:
                result = btfx_client2.submit_order("EXCHANGE MARKET", order_symbol, "", order_amount)
            except Exception as e:
                LOG.error(e)
                return
            else:
                LOG.info(result)
                write_to_file("Trade", pair, result)
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
                    write_to_file("Trade", pair, result)
    return


def main():
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

        w_amount = Decimal(format(currency_inf[2], '.5f'))

        for pair_inf in symbols_lst_final:
            if currency not in pair_inf["pair"]:
                continue

            # This pair is treated at the end
            if pair_inf["pair"] == "btcusd":
                continue

            pair = pair_inf["pair"]
            trade, bad_match = check_pair(currency, pair)

            if bad_match:
                continue

            trade_min_amt = Decimal(format(float(pair_inf["minimum_order_size"]), '.5f'))
            trade_currency(trade, pair, w_amount, trade_min_amt)

    # Finally. Buy BTC with USD or EUR
    try:
        wallet_inf = btfx_client2.wallets_balance()
    except Exception as e:
        LOG.error(e)
        return

    usd_amount = 0
    for curr_inf in wallet_inf:
        if curr_inf[1] == "USD":
            usd_amount = Decimal(format(curr_inf[2], '.5f'))
            break

    btcusd_min_amt = 0
    for pair_inf in symbols_lst_final:
        if pair_inf["pair"] == "btcusd":
            btcusd_min_amt = Decimal(format(float(pair_inf["minimum_order_size"]), '.5f'))
            break
    pair = "btcusd"
    trade_currency("btc_buy", pair, usd_amount, btcusd_min_amt)

    eur_amount = 0
    for curr_inf in wallet_inf:
        if curr_inf[1] == "EUR":
            eur_amount = Decimal(format(curr_inf[2], '.5f'))
            break

    btceur_min_amt = 0
    for pair_inf in symbols_lst_final:
        if pair_inf["pair"] == "btcusd":
            btceur_min_amt = Decimal(format(float(pair_inf["minimum_order_size"]), '.5f'))
            break
    pair = "btceur"
    trade_currency("btc_buy", pair, eur_amount, btceur_min_amt)

if __name__ == '__main__':
    main()
    # print(btfx_client2.wallets_balance())
    # print(btfx_client2.submit_order("EXCHANGE MARKET", "tBTCUSD", "", "-0.0003"))
    # print(btfx_client2.wallets_balance())
    # print(btfx_client2.ticker("tBTCUSD"))
