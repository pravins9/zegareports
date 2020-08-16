from bs4 import BeautifulSoup
import jinja2
import pdfkit
import sys, glob, os, shutil
import datetime
from telethon import  TelegramClient, sync, functions
from telethon.errors.rpcerrorlist import  PhoneNumberBannedError
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import (InputPeerEmpty,  ChatForbidden)
from settings import phone, report_tchannel_id, api_id, api_hash

multitp_report = False

showtp = { 'tp1' : False,
        'tp2' : False,
        'tp3' : False,
        'tp4' : False
        }

dtnow = datetime.datetime.now().strftime("%d%m%Y_%H%M")
first_trade_no_parameter = 0

def make_mydirs():
    directories = ['html_reports', 'pdf_reports', 'inputs']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)

def clear_pdfs():
    pdffiles = glob.glob('*.pdf')
    for pdffile in pdffiles:
        shutil.copy(pdffile, 'pdf_reports//'+pdffile)
        try:
            os.remove(pdffile)
        except PermissionError:
            pass

def scrape_report(reportfile):
    with open(reportfile) as fp:
        soup = BeautifulSoup(fp, "html.parser")
        
    trs = soup.find_all('tr')

    trs = trs[3:]
    closed_trades_data = []
    open_trades_data = []
    is_closed = True
    for tr in trs:
        if 'open trade' in str(tr).lower():
            is_closed = False
        if 'working' in str(tr).lower():
            break
        if 'cancelled' in str(tr).lower():
            continue
        if 'balance' in str(tr).lower():
            continue
        td = tr.find_all('td')
        if is_closed:
            closed_trades_data.append(td)
        else:
            open_trades_data.append(td)
    return (closed_trades_data, open_trades_data)
        


def get_closed_trades(closed_trades_data):
    trade_count = first_trade_no_parameter
    trades = []
    for td in closed_trades_data:
        trade = {}
        trade['state'] = 'closed'
        try:
            td[0]['title']
            trade['comment'] = (' ').join(td[0]['title'].split()[1:])
            if trade['comment'] == '':
                trade['comment'] = 'Personal Trade'
            trade['provider'] = trade['comment'].split('[tp]')[0].split('[sl]')[0]
            if '[tp]' in trade['comment']:
                trade['tp_hit'] = True
                trade['sl_hit'] = False
                trade['result'] = 'TP'
            elif '[sl]' in trade['comment']:
                trade['tp_hit'] = False
                trade['sl_hit'] = True
                trade['result'] = 'SL'
            else:
                trade['tp_hit'] = None
                trade['sl_hit'] = None
                trade['result'] = 'Manual Close'
        except KeyError:
            continue

        trade_count += 1
        trade['trade_no'] = trade_count
        trade['open_time'] = td[1].text
        trade['open_date'] = td[1].text.split()[0].split('.')
        trade['open_date'] = trade['open_date'][2] +'/' + trade['open_date'][1] + '/' + trade['open_date'][0]
        trade['ttype'] = td[2].text.upper()
        trade['size'] = td[3].text
        trade['item'] = td[4].text.upper()
        trade['open_price'] = td[5].text
        trade['sl'] = td[6].text
        trade['tp1'] = td[7].text
        trade['close_price'] = td[9].text
        trade['commision'] = float(td[10].text)
        trade['taxes'] = float(td[11].text)
        trade['swap'] = float(td[12].text)
        trade['profit'] = float(td[13].text)
        trade['close_time'] = td[8].text
        trade['close_date'] = td[8].text.split()[0].split('.')
        trade['close_date'] = trade['close_date'][2] +'/' + trade['close_date'][1] + '/' + trade['close_date'][0]
        trade['tp2'] = None
        trade['tp3'] = None
        trade['tp4'] = None
        trade['tptag'] = 'tp1'

        tradepoints = abs(int(trade['open_price'].replace('.', '')) - int(trade['close_price'].replace('.', '')))
        if trade['open_price'] == trade['close_price'] or tradepoints <= 10:
            trade['be_hit'] = True
            trade['result'] = 'BE'
        else:
            trade['be_hit'] = False
        trades.append(trade)
    return trades

def get_open_trades(open_trades_data):
    trade_count = first_trade_no_parameter
    trades = []
    for td in open_trades_data:
        trade = {}
        trade['state'] = 'open'
        try:
            td[0]['title']
            trade['comment'] = (' ').join(td[0]['title'].split()[1:])
            trade['provider'] = trade['comment'].split('[tp]')[0].split('[sl]')[0]
        except KeyError:
            continue

        trade_count += 1
        trade['trade_no'] = trade_count
        trade['open_time'] = td[1].text
        trade['open_date'] = td[1].text.split()[0].split('.')
        trade['open_date'] = trade['open_date'][2] +'/' + trade['open_date'][1] + '/' + trade['open_date'][0]
        trade['ttype'] = td[2].text.upper()
        trade['size'] = td[3].text
        trade['item'] = td[4].text.upper()
        trade['open_price'] = td[5].text
        trade['sl'] = td[6].text
        trade['tp1'] = td[7].text
        trade['close_price'] = ''
        trade['commision'] = float(td[10].text)
        trade['taxes'] = float(td[11].text)
        trade['swap'] = float(td[12].text)
        trade['profit'] = float(td[13].text)
        trade['close_time'] = td[8].text
        trade['close_date'] = ''
        trade['tp2'] = None
        trade['tp3'] = None
        trade['tp4'] = None
        trade['result'] = 'RUNNING'
        trade['be_hit'] = False
        trade['tptag'] = 'tp1'
        trades.append(trade)
    return trades

def merge_oc_trades(closed_trades, open_trades):
    for open_trade in open_trades:
        open_trade_index = len(closed_trades)
        provider = open_trade['provider']
        ttype = open_trade['ttype']
        size = open_trade['size']
        item = open_trade['item']
        open_price = open_trade['open_price']
        tradetp_1 = open_trade['tp1']
        for i, closed_trade in enumerate(closed_trades):
            if provider == closed_trade['provider'] and ttype == closed_trade['ttype'] and size == closed_trade['size']:
                if item == closed_trade['item'] and open_price == closed_trade['open_price'] and tradetp_1 != closed_trade['tp1']:
                    open_trade_index = i
        closed_trades.insert(open_trade_index, open_trade)
    return closed_trades

def tag_multitp(trades):
    for trade in trades:
        provider = trade['provider']
        ttype = trade['ttype']
        size = trade['size']
        item = trade['item']
        open_price = trade['open_price']
        tradetp_1 = trade['tp1']
        if trade['tptag'] == 'tp1':
            tptag_count = 1
            for temp_trade in trades:
                if provider == temp_trade['provider'] and ttype == temp_trade['ttype'] and size == temp_trade['size']:
                    if item == temp_trade['item'] and open_price == temp_trade['open_price'] and tradetp_1 != temp_trade['tp1']:
                        tptag_count += 1
                        temp_trade['tptag'] = 'tp'+str(tptag_count)
                        if not temp_trade['result'] in ['SL', 'BE', 'RUNNING', 'Manual Close']:
                            temp_trade['result'] = 'TP'+str(tptag_count)
    return trades

def find_multitps(trades):
    no_tp_activated = [1]
    for i,trade in enumerate(trades):
        trade_no = trade['trade_no']
        if not trade_no or i == len(trades):
            continue
        provider = trade['provider']
        ttype = trade['ttype']
        size = trade['size']
        item = trade['item']
        open_price = trade['open_price']
        tradetp_1 = trade['tp1']

        for temp_trade in  trades[i+1:]:
            tp_found = False
            if temp_trade['trade_no'] == None:
                continue
            if provider == temp_trade['provider'] and ttype == temp_trade['ttype'] and size == temp_trade['size']:
                if item == temp_trade['item'] and open_price == temp_trade['open_price'] and tradetp_1 != temp_trade['tp1']:
                    tp_found = True

            if tp_found:
                if not trade['tp2']:
                    trade['tp2'] = temp_trade['tp1']
                    temp_trade['trade_no'] = None
                    if showtp['tp2']:
                        trade['profit']  = trade['profit']+ temp_trade['profit']
                elif not trade['tp3']:
                    trade['tp3'] = temp_trade['tp1']
                    temp_trade['trade_no'] = None
                    if showtp['tp3']:
                        trade['profit']  = trade['profit']+ temp_trade['profit']
                elif not trade['tp4']:
                    trade['tp4'] = temp_trade['tp1']
                    temp_trade['trade_no'] = None
                    if showtp['tp4']:
                        trade['profit']  = trade['profit']+ temp_trade['profit']
        listtp = [trade['tp1']]

        
        if trade['tp2']:
            if not 2 in no_tp_activated:
                no_tp_activated.append(2)
            listtp.append(trade['tp2'])
        if trade['tp3']:
            if not 3 in no_tp_activated:
                no_tp_activated.append(3)
            listtp.append(trade['tp3'])
        if trade['tp4']:
            if not 4 in no_tp_activated:
                no_tp_activated.append(4)
            listtp.append(trade['tp4'])

        if len(listtp) > 1:
            if ttype.lower() == 'buy':
                listtp.sort()
            else:
                listtp.sort(reverse=True)
            trade['tp1'] = listtp[0]
            trade['tp2'] = listtp[1]

            try:
                trade['tp3'] = listtp[2]
            except IndexError:
                pass
            try:
                trade['tp4'] = listtp[3]
            except IndexError:
                pass

    i = first_trade_no_parameter
    multitp_trades = []
    for trade in trades:
        if trade['trade_no']:
            multitp_trade = dict(trade)
            multitp_trade['trade_no'] = i + 1
            i +=1
            multitp_trades.append(multitp_trade)

##    og_trades = []
##    i = first_trade_no_parameter
##    for trade in trades:
##        og_trade = dict(trade)
##        og_trade['trade_no'] = i + 1
##        og_trade['tp2'] = None
##        og_trade['tp3'] = None
##        og_trade['tp4'] = None
##        i +=1
##        og_trades.append(og_trade)

    
    no_tp_activated = max(no_tp_activated)
    return (multitp_trades, no_tp_activated)

        
def printtrades(trades):
    if not isinstance(trades, list):
        trades = [trades]
    for i, trade in enumerate(trades):
        print()
        print(trade['trade_no'],':  ', trade['provider'])
        print('     ', trade['ttype'].upper(), trade['item'].upper(), '@', trade['open_price'], ', SL:', trade['sl'])
        print('      TP1:', trade['tp1'])
        if trade['tp2']:
            print('      TP2:', trade['tp2'])
        if trade['tp3']:
            print('      TP3:', trade['tp3'])
        if trade['be_hit']:
            print('Breakeven hit')
        print('      Close Price:', trade['close_price'], ', P/L', trade['profit'])


def get_tradeoverview(trades):
    netpl = 0
    order_dates = []
    for trade in trades:
        netpl = netpl + trade['profit']
        closing_date = trade['close_date']
##        opening_date = trade['open_date']
        if closing_date != '':
            order_dates.append(closing_date)
##        order_dates.append(opening_date)
    order_dates.sort(key = lambda date: datetime.datetime.strptime(date,"%d/%m/%Y"))
    start_date = '/'.join(order_dates[0].split('.'))
    end_date = '/'.join(order_dates[-1].split('.'))
    tradeperiod = start_date + ' - ' + end_date

    return (netpl, tradeperiod)
def generate_html_report(trades, report_name, custom_notes):
    
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = "templates//" + "report_template.html"
    template = templateEnv.get_template(TEMPLATE_FILE)
    netpl, tradeperiod = get_tradeoverview(trades)
    
    if netpl > 0:
        htmlreportfile = "html_reports//" + report_name +'_P'+str(abs(netpl))+'.html'
    elif netpl == 0:
        htmlreportfile = "html_reports//" + report_name + '_BE'+ str(abs(netpl))+'.html'
    else:
        htmlreportfile = "html_reports//" + report_name + '_L'+str(abs(netpl)) + '.html'
        
    outputText = template.render(trades = trades, netpl = netpl, tradeperiod = tradeperiod, custom_notes = custom_notes, showtp = {'tp1': True, 'tp2': False, 'tp3': False})      #,interest_rate=d['interest_rate'])
    html_file = open(htmlreportfile, 'w')
    html_file.write(outputText)
    html_file.close()
    return htmlreportfile

def generate_html_netreport(providersummarytable, trades, report_name, custom_notes):
    templateLoader = jinja2.FileSystemLoader(searchpath="./")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = "templates//" + "netreport_template.html"
    template = templateEnv.get_template(TEMPLATE_FILE)
    netpl, tradeperiod = get_tradeoverview(trades)
    
    if netpl > 0:
        htmlreportfile = "html_reports//" + report_name +'_P'+str(abs(netpl))+'.html'
    elif netpl == 0:
        htmlreportfile = "html_reports//" + report_name + '_BE'+ str(abs(netpl))+'.html'
    else:
        htmlreportfile = "html_reports//" + report_name + '_L'+str(abs(netpl)) + '.html'
        
    outputText = template.render(providersummarytable = providersummarytable, netpl = netpl, tradeperiod = tradeperiod, custom_notes = custom_notes, showtp = {'tp1': True, 'tp2': False, 'tp3': False})      #,interest_rate=d['interest_rate'])
    html_file = open(htmlreportfile, 'w')
    html_file.write(outputText)
    html_file.close()
    return htmlreportfile


def generate_pdf_report(trades, report_name, custom_notes):
    htmlreportfile = generate_html_report(trades, report_name, custom_notes)
    pdfreportfile = htmlreportfile.split('.')[0].split('//')[-1] + '.pdf'
    pdfkit.from_file(htmlreportfile, pdfreportfile)
    os.remove(htmlreportfile)
    return pdfreportfile

def generate_pdf_netreport(providersummarytable, trades, report_name, custom_notes):
    htmlreportfile = generate_html_netreport(providersummarytable, trades, report_name, custom_notes)
    pdfreportfile = htmlreportfile.split('.')[0].split('//')[-1] + '.pdf'
    pdfkit.from_file(htmlreportfile, pdfreportfile)
    os.remove(htmlreportfile)
    return pdfreportfile

def get_provider_trades(trades, provider_name):
    provider_trades = []
    for trade in trades:
        if provider_name.lower() == trade['provider'].lower():
           provider_trades.append(trade)
           provider_name = trade['provider']
    return (provider_trades, provider_name)

def tradesummary_report(trades):
    providersummary = {}
    for trade in trades:
        if not trade['provider'] in providersummary.keys():
            providersummary[trade['provider']] = {}
            providersummary[trade['provider']]['no_trades'] = 1
            providersummary[trade['provider']]['no_of_tp'] = 0
            providersummary[trade['provider']]['no_of_sl'] = 0
            providersummary[trade['provider']]['no_of_be'] = 0
            providersummary[trade['provider']]['no_of_mc'] = 0
            providersummary[trade['provider']]['no_of_rt'] = 0
            if 'TP' in trade['result']:
                providersummary[trade['provider']]['no_of_tp'] = 1
            elif 'SL' in trade['result']:
                providersummary[trade['provider']]['no_of_sl'] = 1
            elif 'BE' in trade['result']:
                providersummary[trade['provider']]['no_of_be'] = 1
            elif 'MANUAL CLOSE' in trade['result']:
                providersummary[trade['provider']]['no_of_mc'] = 1
            providersummary[trade['provider']]['provider_total_pl'] = trade['profit']
            providersummary[trade['provider']]['total_trades_lot'] = float(trade['size'])*1000000000000000000000
        else:
            providersummary[trade['provider']]['no_trades'] += 1
            if 'TP' in trade['result']:
                providersummary[trade['provider']]['no_of_tp'] += 1
            elif 'SL' in trade['result']:
                providersummary[trade['provider']]['no_of_sl'] += 1
            elif 'BE' in trade['result']:
                providersummary[trade['provider']]['no_of_be'] += 1
            elif 'Manual Close' in trade['result']:
                providersummary[trade['provider']]['no_of_mc'] += 1
            elif 'RUNNING' in trade['result']:
                providersummary[trade['provider']]['no_of_rt'] += 1
            providersummary[trade['provider']]['provider_total_pl'] += trade['profit']
            providersummary[trade['provider']]['total_trades_lot'] += float(trade['size'])*1000000000000000000000
    return providersummary
    

def start_tg():
    try:
        apiidint = int(api_id)
    except ValueError:
        print('ValueError')
        return
    client = TelegramClient(phone, api_id, api_hash)
    try:
        client.start(phone)
    except:
        sys.exit(0)
    chats = []
    groups = []
    result = client(GetDialogsRequest(
             offset_date=None,
             offset_id=0,
             offset_peer=InputPeerEmpty(),
             limit=200,
             hash = 0
         ))
    chats.extend(result.chats)
     
    for chat in chats:
        if isinstance(chat , ChatForbidden):
            continue
        groups.append(chat)
        if chat.id == report_tchannel_id:
            report_tchannel = chat
    return (client, report_tchannel)

def send_reports(pdfreportfiles, client, report_tchannel):
    if not client:
        return
    for pdfreportfile in  pdfreportfiles:
        print('Uploading', pdfreportfile)

        if showtp['tp1'] and showtp['tp2'] and showtp['tp3']:
            client.send_file(1196114775, pdfreportfile)
        elif showtp['tp1']:
            if showtp['tp2']:
                client.send_file(1200205718, pdfreportfile)
            elif showtp['tp3']:
                client.send_file(1400423525, pdfreportfile)
            else:
                client.send_file(1235014823, pdfreportfile)
        elif showtp['tp2']:
            if showtp['tp3']:
                client.send_file(1385706962, pdfreportfile)
            else:
                client.send_file(1257375925, pdfreportfile)
        elif showtp['tp3']:
            client.send_file(1412196856, pdfreportfile)

def mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel):
    custom_note_1 += 'Activated'
    custom_notes = [custom_note_1, custom_note_2]
    if multitp_report:
        multitp_trades, no_tp_activated = find_multitps(temp_trades)
        trades = multitp_trades
        tps_activated_line = ''
        for i in range(1,no_tp_activated+1):
            if no_tp_activated == 1:
                tps_activated_line = 'TP1'
                break
            if i == no_tp_activated:
                tps_activated_line = tps_activated_line[:-2]
                tps_activated_line = tps_activated_line+' & TP'+str(i)
                break
            tps_activated_line = tps_activated_line+'TP'+str(i)+', '
    else:
        tptagedtrades = tag_multitp(trades)
        trades = []

        for trade in tptagedtrades:
            if showtp['tp1'] and trade['tptag'] == 'tp1':
                trades.append(trade)

            if showtp['tp2'] and trade['tptag'] == 'tp2':
                trades.append(trade)

            if showtp['tp3'] and trade['tptag'] == 'tp3':
                trades.append(trade)

    print('-------------------------------------------------------------')
    
    pdfreportfiles = []
    if provider_mode == 'yes':
        provider_trades, provider_name = get_provider_trades(trades, provider_name)
        report_name = provider_name +'_' + custom_note_1.split('Activated')[0] + '_trades_'+dtnow
        pdfreportfile = generate_pdf_report(provider_trades, report_name, custom_notes)
        pdfreportfiles.append(pdfreportfile)
        
    elif provider_mode == 'all_individual':
        providers = []
        for trade in trades:
            if not trade['provider'] in providers:
                providers.append(trade['provider'])
        for provider in providers:
            provider_trades, provider_name = get_provider_trades(trades, provider)
            report_name = provider_name +'_' + custom_note_1.split('Activated')[0] + '_trades_'+dtnow
            if '/' in report_name:
                report_name = report_name.replace('/', '-')
            pdfreportfile = generate_pdf_report(provider_trades, report_name, custom_notes)
            pdfreportfiles.append(pdfreportfile)
            
            
    else:
        providersummary = tradesummary_report(trades)
        providersummarytable = []
        for provider in providersummary.keys():
            providerreport = providersummary[provider]
            providerreport['provider'] = provider
##            providerreport['total_trades_lot'] = format(providerreport['total_trades_lot'], '.10f')
            providerreport['total_trades_lot'] =  providerreport['total_trades_lot'] / 1000000000000000000000
            providersummarytable.append(providerreport)

        providersummarytable = sorted(providersummarytable, key = lambda i: i['provider_total_pl'],reverse=True) 

        report_name = 'net_trades_' + custom_note_1.split('Activated')[0] +'_'+ dtnow
        pdfnetreportfile = generate_pdf_netreport(providersummarytable, trades, report_name, custom_notes)
        pdfreportfiles.append(pdfnetreportfile)
            
        

    try:
        send_reports(pdfreportfiles, client, report_tchannel)
    except Exception as e:
        print(e)

if __name__ or '__main__':
    make_mydirs()
    clear_pdfs()

##    try:
##        provider_mode = sys.argv[1]
##    except IndexError:
##        provider_mode = 'no'
##    
##    if provider_mode == 'yes':
##        provider_name = input('Enter Provider Name(Exact) : ')

    while True:
        try:
            report_type_inp = int(input("""
Main Menu
1. All providers individual trades.
2. All providers net trades.
 Enter a number: """))
            break
        except ValueError:
            print('Enter a valid number from above!')
            print()

    if report_type_inp == 1:
        provider_mode = 'all_individual'
    else:
        provider_mode = 'no'
        

    
    custom_note_2 = input('Enter custome note: ')
    


    closed_trades_data, open_trades_data = scrape_report("inputs//" + "Statement.htm")

    closed_trades = get_closed_trades(closed_trades_data)
    open_trades = get_open_trades(open_trades_data)
##    trades = merge_oc_trades(closed_trades, open_trades)
    trades = closed_trades + open_trades
    temp_trades = []
    for trade in trades:
        temp_trades.append(dict(trade))

    client, report_tchannel = None, None
    try:
        client, report_tchannel = start_tg()
    except TypeError:
        print('TypeError')
    while True:
        try:
            tpcolumnsinp = int(input('''1. TP1 Only
2. TP2 Only
3. TP3 Only
4. TP1 + TP2
5. TP2 + TP3
6. TP1 + TP3
7. TP1 + TP2 + TP3
8. All Combinations

Enter a number: '''))
            break
        except ValueError:
            print()
            print('Enter a valid number.')

    custom_note_1 = ''
    if tpcolumnsinp in [1, 4, 6, 7]:
        showtp['tp1'] = True
        custom_note_1 += 'TP1 '

    if tpcolumnsinp in [2, 4, 5, 7]:
        showtp['tp2'] = True
        custom_note_1 += 'TP2 '

    if tpcolumnsinp in [3, 5, 6, 7]:
        showtp['tp3'] = True
        custom_note_1 += 'TP3 '

    if tpcolumnsinp == 8:
        print('option 8 selected')
        showtp['tp1'] = True
        showtp['tp2'] = False
        showtp['tp3'] = False
        custom_note_1 = 'TP1'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)
        print('TP1 printed')
        
        showtp['tp1'] = False
        showtp['tp2'] = True
        showtp['tp3'] = False
        custom_note_1 = 'TP2'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)
        print('TP2 printed')
        
        showtp['tp1'] = False
        showtp['tp2'] = False
        showtp['tp3'] = True
        custom_note_1 = 'TP3'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)

        showtp['tp1'] = True
        showtp['tp2'] = True
        showtp['tp3'] = False
        custom_note_1 = 'TP1 TP2'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)

        showtp['tp1'] = False
        showtp['tp2'] = True
        showtp['tp3'] = True
        custom_note_1 = 'TP2 TP3'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)

        showtp['tp1'] = True
        showtp['tp2'] = False
        showtp['tp3'] = True
        custom_note_1 = 'TP1 TP3'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)

        showtp['tp1'] = True
        showtp['tp2'] = True
        showtp['tp3'] = True
        custom_note_1 = 'TP1 TP2 TP3'
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)
    else:
        mainprog(trades, temp_trades, provider_mode, custom_note_1, custom_note_2, client, report_tchannel)

    
        
        
    
    


    

    


