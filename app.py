from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import requests
import pandas as pd
from io import StringIO
from datetime import date, timedelta
import zipfile
import io

app = Flask(__name__)
CORS(app)

HTML = open('index.html').read()

def fetch_nse_bhavcopy():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.nseindia.com/',
    }
    session = requests.Session()
    session.get('https://www.nseindia.com', headers=headers, timeout=10)
    for days_back in range(0, 6):
        try_date = date.today() - timedelta(days=days_back)
        date_str = try_date.strftime("%d%b%Y").upper()
        year = try_date.year
        month = try_date.strftime('%b').upper()
        url = f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{year}/{month}/cm{date_str}bhav.csv.zip"
        try:
            r = session.get(url, headers=headers, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                csv_data = z.read(z.namelist()[0]).decode('utf-8')
                df = pd.read_csv(StringIO(csv_data))
                return df, str(try_date)
        except:
            continue
    return None, None

def fetch_bse_bhavcopy():
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bseindia.com/'}
    for days_back in range(0, 6):
        try_date = date.today() - timedelta(days=days_back)
        date_str = try_date.strftime("%d%m%y")
        url = f"https://www.bseindia.com/download/BhavCopy/Equity/EQ{date_str}_CSV.ZIP"
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200 and len(r.content) > 1000:
                z = zipfile.ZipFile(io.BytesIO(r.content))
                csv_data = z.read(z.namelist()[0]).decode('utf-8')
                df = pd.read_csv(StringIO(csv_data))
                return df, str(try_date)
        except:
            continue
    return None, None

def get_sector(symbol):
    sectors = {
        'RELIANCE':'Energy','ONGC':'Energy','BPCL':'Energy','IOC':'Energy',
        'TCS':'IT','INFY':'IT','WIPRO':'IT','HCLTECH':'IT','TECHM':'IT',
        'HDFCBANK':'Banking','ICICIBANK':'Banking','SBIN':'Banking','KOTAKBANK':'Banking','AXISBANK':'Banking',
        'SUNPHARMA':'Pharma','DRREDDY':'Pharma','CIPLA':'Pharma',
        'TATASTEEL':'Metals','JSWSTEEL':'Metals','HINDALCO':'Metals',
        'MARUTI':'Auto','TATAMOTORS':'Auto','HEROMOTOCO':'Auto','EICHERMOT':'Auto',
        'HINDUNILVR':'FMCG','NESTLEIND':'FMCG','BRITANNIA':'FMCG','DABUR':'FMCG',
        'BAJFINANCE':'Finance','BAJAJFINSV':'Finance','HDFCLIFE':'Insurance',
        'LT':'Infrastructure','ADANIPORTS':'Infrastructure',
    }
    return sectors.get(symbol, 'Other')

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/losers')
def get_losers():
    results = []
    data_date = None
    errors = []
    try:
        df, nse_date = fetch_nse_bhavcopy()
        if df is not None:
            data_date = nse_date
            df.columns = df.columns.str.strip()
            if 'SERIES' in df.columns:
                df = df[df['SERIES'].str.strip() == 'EQ']
            if all(col in df.columns for col in ['SYMBOL','OPEN','CLOSE','TOTTRDQTY']):
                df['OPEN'] = pd.to_numeric(df['OPEN'], errors='coerce')
                df['CLOSE'] = pd.to_numeric(df['CLOSE'], errors='coerce')
                df['TOTTRDQTY'] = pd.to_numeric(df['TOTTRDQTY'], errors='coerce').fillna(0)
                if 'PREVCLOSE' in df.columns:
                    df['PREVCLOSE'] = pd.to_numeric(df['PREVCLOSE'], errors='coerce')
                else:
                    df['PREVCLOSE'] = df['OPEN']
                if 'HIGH' in df.columns:
                    df['HIGH'] = pd.to_numeric(df['HIGH'], errors='coerce')
                if 'LOW' in df.columns:
                    df['LOW'] = pd.to_numeric(df['LOW'], errors='coerce')
                df = df.dropna(subset=['OPEN','CLOSE'])
                df = df[df['OPEN'] > 0]
                df['CHANGE_FROM_OPEN'] = ((df['CLOSE'] - df['OPEN']) / df['OPEN'] * 100).round(2)
                losers = df[df['CHANGE_FROM_OPEN'] <= -20].copy()
                losers = losers.sort_values('CHANGE_FROM_OPEN')
                for _, row in losers.iterrows():
                    sym = str(row.get('SYMBOL','')).strip()
                    pc = float(row.get('PREVCLOSE', row.get('OPEN',0)))
                    cl = float(row.get('CLOSE',0))
                    results.append({
                        'symbol': sym, 'exchange': 'NSE', 'sector': get_sector(sym),
                        'open': round(float(row.get('OPEN',0)),2),
                        'high': round(float(row.get('HIGH', row.get('OPEN',0))),2),
                        'low': round(float(row.get('LOW', row.get('CLOSE',0))),2),
                        'close': round(cl,2), 'prev_close': round(pc,2),
                        'change_from_open': float(row.get('CHANGE_FROM_OPEN',0)),
                        'change_from_prev': round((cl-pc)/pc*100,2) if pc > 0 else 0,
                        'volume': int(row.get('TOTTRDQTY',0)),
                        'lower_circuit': bool(row.get('LOW',0) > 0 and abs(cl - float(row.get('LOW',0))) < 0.01),
                    })
        else:
            errors.append('NSE data available nahi hai abhi')
    except Exception as e:
        errors.append(f'NSE error: {str(e)}')
    try:
        df_bse, bse_date = fetch_bse_bhavcopy()
        if df_bse is not None:
            if not data_date:
                data_date = bse_date
            df_bse.columns = df_bse.columns.str.strip()
            col_map = {}
            for col in df_bse.columns:
                cu = col.upper().strip()
                if 'OPEN' in cu and 'PREV' not in cu: col_map['OPEN'] = col
                elif 'CLOSE' in cu and 'PREV' not in cu: col_map['CLOSE'] = col
                elif 'HIGH' in cu: col_map['HIGH'] = col
                elif 'LOW' in cu: col_map['LOW'] = col
                elif 'PREV' in cu and 'CLOSE' in cu: col_map['PREVCLOSE'] = col
                elif 'SCRIP' in cu or ('NAME' in cu and 'SC' in cu): col_map['SYMBOL'] = col
                elif 'NO_OF_SHRS' in cu or ('TRAD' in cu and 'QTY' in cu): col_map['VOLUME'] = col
            if 'OPEN' in col_map and 'CLOSE' in col_map:
                df_bse['_O'] = pd.to_numeric(df_bse[col_map['OPEN']], errors='coerce')
                df_bse['_C'] = pd.to_numeric(df_bse[col_map['CLOSE']], errors='coerce')
                df_bse['_V'] = pd.to_numeric(df_bse.get(col_map.get('VOLUME',''), pd.Series([0]*len(df_bse))), errors='coerce').fillna(0)
                df_bse = df_bse.dropna(subset=['_O','_C'])
                df_bse = df_bse[df_bse['_O'] > 0]
                df_bse['_CHG'] = ((df_bse['_C'] - df_bse['_O']) / df_bse['_O'] * 100).round(2)
                bse_losers = df_bse[df_bse['_CHG'] <= -20].copy()
                nse_symbols = {r['symbol'] for r in results}
                for _, row in bse_losers.iterrows():
                    sym = str(row.get(col_map.get('SYMBOL',''),'') if col_map.get('SYMBOL') else '').strip()
                    if sym and sym not in nse_symbols:
                        results.append({
                            'symbol': sym, 'exchange': 'BSE', 'sector': get_sector(sym),
                            'open': round(float(row['_O']),2), 'high': round(float(row['_O']),2),
                            'low': round(float(row['_C']),2), 'close': round(float(row['_C']),2),
                            'prev_close': round(float(row['_O']),2),
                            'change_from_open': float(row['_CHG']), 'change_from_prev': 0,
                            'volume': int(row['_V']), 'lower_circuit': False,
                        })
        else:
            errors.append('BSE data available nahi hai abhi')
    except Exception as e:
        errors.append(f'BSE error: {str(e)}')
    results.sort(key=lambda x: x['change_from_open'])
    return jsonify({'data': results, 'total': len(results), 'date': data_date or str(date.today()), 'errors': errors})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=10000)
