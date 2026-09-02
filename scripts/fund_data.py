# -*- coding: utf-8 -*-
"""
06 基金資料管線：從 AIA 官方 API 抓取、與既有資料合併、重建指標、輸出。

    python scripts/fund_data.py seed     # 從 06 HTML 抽出既有資料當作基底（保留 Z23 等補充來源）
    python scripts/fund_data.py fetch    # 打 API 抓最新資料並合併
    python scripts/fund_data.py check    # 只驗證不寫入

輸出目錄：calculator-hub/data/funds/
    manifest.json / catalog.json / distribution-references.json / smart-metrics.json
    nav/XX.json / distributions/XX.json

注意：本機必須用 curl 抓 AIA（系統代理 127.0.0.1:7890），
      Python 的 urllib / requests 不走代理會逾時。
"""
import argparse
import bisect
import datetime
import hashlib
import io
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data', 'funds')
HTML = os.path.join(ROOT, '06-fund-portfolio-workbench.html')
CACHE = os.path.join(ROOT, '.cache', 'aia')

HOST = 'https://www1.aia.com.hk'
CAT = 'TMP2'
START = '2000-01-01'
UA = 'Mozilla/5.0'

MARK = 'window.__CALCULATOR_HUB_EMBEDDED_FUND_DATA__='

CURRENCY_CODE = {'美元': 'USD', '港元': 'HKD', '人民幣': 'CNY', '歐元': 'EUR',
                 '澳元': 'AUD', '英鎊': 'GBP', '日圓': 'JPY', '新加坡元': 'SGD',
                 '瑞士法郎': 'CHF', '加拿大元': 'CAD', '紐西蘭元': 'NZD'}
CUR_MAP = {'usd': 'USD', 'aus': 'AUD', 'rmb': 'RMB', 'can': 'CAD', 'chf': 'CHF',
           'pound': 'GBP', 'peso': 'PHP', 'mop': 'MOP', 'nt': 'TWD', 'sing': 'SGD',
           'nzd': 'NZD', 'euro': 'EUR', 'yen': 'JPY'}


# --------------------------------------------------------------------------
# 抓取
# --------------------------------------------------------------------------
def curl_json(url, cache_name=None, max_age=0, retries=2):
    """用 curl 抓 JSON（走系統代理），可選磁碟快取。

    安全性：每次呼叫前都先刪除暫存檔。否則 curl 失敗時舊檔還在，
    會被當成這一次的回應，導致「A 基金拿到 B 基金的資料」。
    （2026-08-30 實測踩到：J14 拿到了 J07 的資料。）
    """
    os.makedirs(CACHE, exist_ok=True)
    fp = os.path.join(CACHE, cache_name) if cache_name else None
    if cache_name and fp and os.path.exists(fp) and (max_age <= 0 or
       (datetime.datetime.now().timestamp() - os.path.getmtime(fp)) < max_age):
        try:
            return json.load(io.open(fp, encoding='utf-8'))
        except Exception:
            pass

    tmp = os.path.join(CACHE, (cache_name or 'tmp') + '.json')
    last = None
    for _ in range(retries + 1):
        # 先把暫存檔截斷成 0 位元組。不能用 os.remove（沙箱會擋），
        # 但截斷同樣能避免 curl 失敗時讀到上一次的內容。
        with io.open(tmp, 'wb'):
            pass
        subprocess.run(['curl', '-s', '--max-time', '120',
                        '-H', 'User-Agent: ' + UA, '-o', tmp, url],
                       capture_output=True)
        if os.path.exists(tmp) and os.path.getsize(tmp) > 0:
            try:
                d = json.load(io.open(tmp, encoding='utf-8'))
            except Exception as e:
                last = e
                continue
            if d is not None:
                if cache_name:
                    os.replace(tmp, fp)
                return d
    if last:
        sys.stderr.write('[curl_json] 解析失敗: %s\n' % last)
    return None


def api_fund_info():
    return curl_json('%s/CorpWS/Investment/Get/FundInfo2/?fund_cat=%s'
                     '&fund_type=&fund_house=&fund_code=&name=&lang=zh' % (HOST, CAT),
                     'fundinfo.json')


def api_nav(code, end_date):
    return curl_json('%s/CorpWS/Investment/Get/FundHistorical/value/?fund_code=%s'
                     '&fund_cat=%s&start_date=%s&end_date=%s&interval=86400000'
                     % (HOST, code, CAT, START, end_date), None)


def api_dividends(code, end_date):
    return curl_json('%s/CorpWS/Investment/Get/FundDividendRecord/?fund_code=%s'
                     '&start_date=%s&end_date=%s&lang=zh' % (HOST, code, START, end_date),
                     'div_%s.json' % code)


def api_fx():
    return curl_json('%s/CorpWS/Investment/Get/ExchangeRate2' % HOST, 'fx.json')


# --------------------------------------------------------------------------
# 既有資料（基底）
# --------------------------------------------------------------------------
def read_html_embedded(path=None):
    """讀出 06 HTML 裡的內嵌資料物件。"""
    s = io.open(path or HTML, encoding='utf-8').read()
    i = s.find(MARK)
    if i < 0:
        return None
    j = s.find('{', i)
    depth, p = 1, j + 1
    while p < len(s) and depth > 0:
        if s[p] == '{':
            depth += 1
        elif s[p] == '}':
            depth -= 1
        p += 1
    return json.loads(s[j:p])


JS_LINE = re.compile(
    r'window\.__FUND_DATA__=window\.__FUND_DATA__\|\|\{\};'
    r'window\.__FUND_DATA__\["(?P<key>[^"]+)"\]=(?P<body>.*);\s*$', re.S)


def read_published_js(rel_js):
    """讀取已發布的 data/*.js（GitHub Actions 全新克隆時沒有 JSON，就用這個當基底）。"""
    fp = os.path.join(ROOT, rel_js.replace('/', os.sep))
    if not os.path.exists(fp):
        return None
    s = io.open(fp, encoding='utf-8').read()
    m = JS_LINE.match(s.strip())
    if not m:
        return None
    try:
        return json.loads(m.group('body'))
    except Exception:
        return None


def load_existing(prefer_json=True):
    """讀既有資料。優先用 data/funds/*.json（本機），
    沒有則退回解析已發布的 data/*.js（CI 環境）。"""
    out = {'nav': {}, 'distributions': {}, 'tops': {}}
    if prefer_json:
        for name in ('manifest', 'catalog', 'distribution-references', 'smart-metrics'):
            fp = os.path.join(DATA, name + '.json')
            if os.path.exists(fp):
                out['tops'][name] = json.load(io.open(fp, encoding='utf-8'))
        nd = os.path.join(DATA, 'nav')
        if os.path.isdir(nd):
            for fn in os.listdir(nd):
                if fn.endswith('.json'):
                    out['nav'][fn[:-5]] = json.load(io.open(os.path.join(nd, fn), encoding='utf-8'))
        dd = os.path.join(DATA, 'distributions')
        if os.path.isdir(dd):
            for fn in os.listdir(dd):
                if fn.endswith('.json'):
                    out['distributions'][fn[:-5]] = json.load(
                        io.open(os.path.join(dd, fn), encoding='utf-8'))
        if out['nav']:
            return out

    # 退回讀已發布的 .js
    for name in ('manifest', 'catalog', 'distribution-references', 'smart-metrics'):
        o = read_published_js('data/%s.js' % name)
        if o is not None:
            out['tops'][name] = o
    idx = out['tops'].get('manifest', {}).get('navIndex') or {}
    for code in idx:
        o = read_published_js('data/nav/%s.js' % code)
        if o is not None:
            out['nav'][code] = o
    for code in list(out['tops'].get('distribution-references') or {}):
        o = read_published_js('data/distributions/%s.js' % code)
        if o is not None:
            out['distributions'][code] = o
    return out


def seed_from_html(path=None):
    """把 HTML 內嵌資料寫成 data/funds/*.json，作為合併基底。
    path 省略時用 06-fund-portfolio-workbench.html；
    外置後那個檔案已無內嵌資料，可指向 _archive 裡的備份。"""
    d = read_html_embedded(path)
    if not d:
        print('找不到內嵌資料（來源: %s）' % (path or HTML)); return 1
    for tgt in ('nav', 'distributions'):
        os.makedirs(os.path.join(DATA, tgt), exist_ok=True)
    n_nav = n_div = 0
    for k, v in d.items():
        if not k.startswith('/data/'):
            continue
        rel = k[len('/data/'):]
        if rel.startswith('nav/'):
            code = rel[4:-5]
            json.dump(v, io.open(os.path.join(DATA, 'nav', code + '.json'), 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
            n_nav += 1
        elif rel.startswith('distributions/'):
            code = rel[14:-5]
            json.dump(v, io.open(os.path.join(DATA, 'distributions', code + '.json'), 'w',
                                encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
            n_div += 1
        elif rel.endswith('.json'):
            json.dump(v, io.open(os.path.join(DATA, rel), 'w', encoding='utf-8'),
                      ensure_ascii=False, separators=(',', ':'))
            print('  寫出', rel)
    print('seed 完成：nav %d 檔 / distributions %d 檔' % (n_nav, n_div))
    return 0


# --------------------------------------------------------------------------
# 指標計算（依 Manus 官方規則）
# --------------------------------------------------------------------------
def clean_points(raw):
    """過濾無效時間戳、無效數值、<=0 的 NAV，按時間戳升序。"""
    pts = []
    for r in raw or []:
        try:
            ts, v = int(r[0]), float(r[1])
        except (TypeError, ValueError, IndexError):
            continue
        if ts <= 0 or v <= 0:
            continue
        pts.append((ts, v))
    pts.sort(key=lambda x: x[0])
    return pts


def months_before(ts, n):
    """最新 NAV 日往前 n 個自然月的同日（毫秒）。"""
    d = datetime.datetime.utcfromtimestamp(ts / 1000)
    y, m = d.year, d.month
    m -= n
    while m <= 0:
        m += 12
        y -= 1
    day = d.day
    while day > 0:
        try:
            dt = datetime.datetime(y, m, day)
        except ValueError:
            day -= 1
            continue
        return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    return ts


def year_start(ts):
    d = datetime.datetime.utcfromtimestamp(ts / 1000)
    return int(datetime.datetime(d.year, 1, 1).replace(tzinfo=datetime.timezone.utc)
               .timestamp() * 1000)


def years_before(ts, n):
    """最新 NAV 日往前 n 個自然年的同日（毫秒）。
    對應 Manus 的 new Date(endYear - N, endMonth, endDay)。"""
    d = datetime.datetime.utcfromtimestamp(ts / 1000)
    y, m, day = d.year - n, d.month, d.day
    while day > 0:
        try:
            dt = datetime.datetime(y, m, day)
        except ValueError:
            day -= 1
            continue
        return int(dt.replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
    return ts


def _mk_periods(pts, ts_list, latest_ts):
    """產生 periods / performancePeriods（default 與 customYears 共用同一份）。"""
    periods = {}
    for key, n, req in DEFAULT_PERIODS:
        periods[key] = period_metric(pts, ts_list, months_before(latest_ts, n), req)
    perf = {}
    for key, n, req in PERF_PERIODS:
        tgt = year_start(latest_ts) if n is None else months_before(latest_ts, n)
        perf[key] = period_metric(pts, ts_list, tgt, req)
    return periods, perf


def period_metric(pts, ts_list, target, required):
    """依 Manus 規則算單一期間指標。"""
    latest_ts, latest_nav = pts[-1]
    idx = bisect.bisect_right(ts_list, target) - 1
    if idx < 0:
        # 目標日之前沒有任何 NAV → 全 null
        return {'eligible': False, 'observationCount': 0,
                'requiredObservationCount': required,
                'startTimestamp': None, 'endTimestamp': None,
                'returnPercent': None, 'navPercentile': None}
    window = pts[idx:]
    cnt = len(window)
    start_ts, start_nav = window[0]
    if cnt < required:
        return {'eligible': False, 'observationCount': cnt,
                'requiredObservationCount': required,
                'startTimestamp': start_ts, 'endTimestamp': latest_ts,
                'returnPercent': None, 'navPercentile': None}
    le = sum(1 for _, p in window if p <= latest_nav)
    return {'eligible': True, 'observationCount': cnt,
            'requiredObservationCount': required,
            'startTimestamp': start_ts, 'endTimestamp': latest_ts,
            'returnPercent': (latest_nav / start_nav - 1) * 100,
            'navPercentile': le / cnt * 100}


DEFAULT_PERIODS = [('1Y', 12, 200), ('3Y', 36, 600), ('5Y', 60, 1000)]
PERF_PERIODS = [('YTD', None, 20), ('3M', 3, 45), ('1Y', 12, 200),
                ('3Y', 36, 600), ('5Y', 60, 1000)]


def build_smart_metrics(navs):
    """navs: {code: [(ts, nav), ...]}"""
    entries = []
    for code in sorted(navs):
        pts = navs[code]
        if not pts:
            continue
        ts_list = [p[0] for p in pts]
        latest_ts = pts[-1][0]
        periods, perf = _mk_periods(pts, ts_list, latest_ts)
        entries.append({'code': code, 'latestTimestamp': latest_ts,
                        'periods': periods, 'performancePeriods': perf,
                        'customPeriod': None})

    custom_years = {}
    for n in range(1, 31):
        req = max(200, n * 200)      # ceil(n*200)，n 為整數所以直接乘
        arr = []
        for code in sorted(navs):
            pts = navs[code]
            if not pts:
                continue
            ts_list = [p[0] for p in pts]
            latest_ts = pts[-1][0]
            periods, perf = _mk_periods(pts, ts_list, latest_ts)
            arr.append({'code': code, 'latestTimestamp': latest_ts,
                        'periods': periods, 'performancePeriods': perf,
                        'customPeriod': {'years': n,
                                         'metric': period_metric(pts, ts_list,
                                                                 years_before(latest_ts, n), req)}})
        custom_years[str(n)] = arr

    return {'default': entries, 'customYears': custom_years}


# --------------------------------------------------------------------------
# catalog / manifest / 派息
# --------------------------------------------------------------------------
NUM = re.compile(r'\[([\d.]+)\]')


def first_num(s):
    m = NUM.search(s or '')
    return float(m.group(1)) if m else None


def build_catalog(info, by_code, fx_rates, fx_date):
    funds = []
    for r in sorted(info, key=lambda x: x['code']):
        code = r['code']
        cur = r.get('currency') or ''
        bid = first_num(r.get('bidPrice') or '')
        offer = first_num(r.get('offerPrice') or '')
        vd = (r.get('valuationDate') or '').strip('[]')
        is_dist = str(r.get('distribution_fund', '')).upper() == 'Y'
        base = ('https://www.aia.com.hk/zh-hk/help-and-support/individuals/'
                'investment-information/investment-options-prices/')
        funds.append({
            'code': code,
            'name': r.get('name') or '',
            'currency': cur,
            'currencyCode': CURRENCY_CODE.get(cur, ''),
            'isin': r.get('ISIN') or None,
            'shareClass': None,
            'hedged': ('對沖' in (r.get('name') or '')) or ('hedged' in (r.get('name') or '').lower()),
            'bidPrice': bid,
            'offerPrice': offer,
            'dailyChange': r.get('dd_change') or 0,
            'valuationDate': vd or None,
            'risk': r.get('risk') or None,
            'assetClass': r.get('type') or None,
            'house': r.get('house') or None,
            'rating': r.get('rating') or 0,
            'isDistributionFund': is_dist,
            'detailUrl': base + 'details.html?id=%s&cat=%s&lang=zh' % (code, CAT),
            'distributionUrl': (base + 'records.html?id=%s&cat=%s&lang=zh' % (code, CAT))
                               if is_dist else None,
        })
    return {
        'funds': funds,
        'exchangeDate': fx_date,
        'exchangeRatesHkd': fx_rates,
        'identities': {r['code']: (r.get('ISIN') or None) for r in info},
    }


def build_manifest(navs, dists, prev):
    nav_index, total, latest = {}, 0, 0
    for code in sorted(navs):
        pts = navs[code]
        if not pts:
            continue
        nav_index[code] = {'path': 'data/nav/%s.json' % code,
                           'recordCount': len(pts),
                           'firstTimestamp': pts[0][0],
                           'lastTimestamp': pts[-1][0]}
        total += len(pts)
        latest = max(latest, pts[-1][0])
    files = {}
    for code in sorted(navs):
        p = 'data/nav/%s.json' % code
        blob = json.dumps({'fundCode': code, 'points': navs[code]},
                          ensure_ascii=False, separators=(',', ':'))
        files[p] = {'bytes': len(blob.encode('utf-8')),
                    'sha256': hashlib.sha256(blob.encode('utf-8')).hexdigest()}
    for code in sorted(dists):
        p = 'data/distributions/%s.json' % code
        blob = json.dumps(dists[code], ensure_ascii=False, separators=(',', ':'))
        files[p] = {'bytes': len(blob.encode('utf-8')),
                    'sha256': hashlib.sha256(blob.encode('utf-8')).hexdigest()}
    src = dict((prev or {}).get('source') or {})
    src.update({'navFundCount': len(nav_index), 'navPointCount': total,
                'navLatestTimestamp': latest, 'workbookCoverageEnd': latest})
    return {'source': src, 'navIndex': nav_index, 'files': files}


def build_distribution_references(dists, navs, info_by_code):
    """取每只基金最近一次派息，算年化派息率。"""
    out = {}
    for code in sorted(dists):
        recs = dists[code].get('records') or []
        if not recs:
            continue
        r = recs[-1]
        amt, nav = r.get('amountPerUnit'), r.get('eligibleNav')
        if not amt or not nav:
            continue
        cur = (info_by_code.get(code) or {}).get('currency') or ''
        base = ('https://www.aia.com.hk/zh-hk/help-and-support/individuals/'
                'investment-information/investment-options-prices/')
        out[code] = {
            'latestDistributionDate': r.get('recordDate'),
            'latestDistributionAmount': amt,
            'eligibleNavDate': r.get('recordDate'),
            'eligibleNav': nav,
            'singlePaymentYield': amt / nav * 100,
            'annualizedDistributionRate': amt / nav * 12 * 100,
            'impliedPaymentsPerYear': 12,
            'sourceUrl': base + 'records.html?id=%s&cat=%s&lang=zh' % (code, CAT),
            'overrideAuthorized': False,
        }
    return out


# --------------------------------------------------------------------------
def merge_points(old, new, code='', strict=True):
    """依時間戳聯集；新值優先。

    strict=True 時會做完整性檢查：歷史區間一旦重疊，數值理應完全一致
    （歷史價格不會事後被改）。若重疊區有超過 2% 的數值不符，
    判定這批新資料有問題（例如抓錯基金），直接丟棄、保留舊資料。
    """
    if not old:
        return list(new or [])
    if not new:
        return list(old)
    if strict:
        om = dict(old)
        overlap = [(t, om[t], v) for t, v in new if t in om]
        if overlap:
            bad = sum(1 for _, a, b in overlap
                      if not (isinstance(a, (int, float)) and isinstance(b, (int, float))
                              and abs(float(a) - float(b)) < 1e-9))
            if bad > max(3, len(overlap) * 0.02):
                print('  [警告] %s 重疊區 %d 筆中有 %d 筆數值不符，'
                      '判定新資料異常，保留既有資料' % (code, len(overlap), bad))
                return list(old)
    m = {t: v for t, v in old}
    for t, v in new:
        m[t] = v
    return sorted(m.items(), key=lambda x: x[0])


def cmd_fetch(args):
    end_date = args.end or datetime.date.today().strftime('%Y-%m-%d')
    print('抓取截止日:', end_date)

    ex = load_existing()
    if not ex['nav']:
        print('data/funds 沒有基底，先跑 seed'); return 1

    print('既有: nav %d 檔 / distributions %d 檔' % (len(ex['nav']), len(ex['distributions'])))

    info = api_fund_info()
    if not info:
        print('FundInfo2 抓取失敗'); return 1
    print('API 基金數:', len(info))
    info_by_code = {r['code']: r for r in info}

    navs, changed, failed = {}, [], []
    for n, r in enumerate(info, 1):
        code = r['code']
        raw = api_nav(code, end_date)
        if raw is None:
            failed.append(code)
            navs[code] = clean_points((ex['nav'].get(code) or {}).get('points'))
            continue
        new = clean_points(raw)
        old = clean_points((ex['nav'].get(code) or {}).get('points'))
        merged = merge_points(old, new, code=code)
        navs[code] = merged
        if len(merged) != len(old):
            changed.append((code, len(old), len(merged)))
        if n % 25 == 0:
            print('  ...NAV %d/%d (新增 %d 檔)' % (n, len(info), len(changed)))
            sys.stdout.flush()

    print('NAV 完成：%d 檔，其中 %d 檔有新增，失敗 %d 檔 %s'
          % (len(navs), len(changed), len(failed), failed[:6]))

    # 派息
    dists = {}
    for code in sorted(info_by_code):
        r = info_by_code[code]
        if not (str(r.get('distribution_fund', '')).upper() == 'Y'
                or str(r.get('distribution_dividend_record', '')).upper() == 'Y'):
            continue
        raw = api_dividends(code, end_date)
        recs = []
        for d in (raw or []):
            try:
                dt = datetime.datetime.strptime(d['record_date'], '%m/%d/%Y').date()
                amt = float(d['dividend_rate'])
            except (KeyError, ValueError):
                continue
            # 當天或之前最近一筆 NAV
            ts = int(datetime.datetime(dt.year, dt.month, dt.day)
                     .replace(tzinfo=datetime.timezone.utc).timestamp() * 1000)
            pts = navs.get(code) or []
            idx = bisect.bisect_right([p[0] for p in pts], ts) - 1
            nav = pts[idx][1] if idx >= 0 else None
            recs.append({'recordDate': dt.strftime('%Y-%m-%d'),
                         'amountPerUnit': amt,
                         'eligibleNav': nav,
                         'annualizedRate': round(amt / nav * 12 * 100, 2) if nav else None})
        recs.sort(key=lambda x: x['recordDate'])
        if recs:
            dists[code] = {'records': recs}
    print('派息完成：%d 檔' % len(dists))

    # 匯率
    fx_rates, fx_date = {}, None
    fx = api_fx()
    if fx:
        fx_rates = {'HKD': 1.0}
        for item in fx:
            k = CUR_MAP.get((item.get('type') or '').lower())
            if k:
                try:
                    fx_rates[k] = float(item['value'])
                except (KeyError, ValueError):
                    pass
        fx_rates.setdefault('CNY', fx_rates.get('RMB'))
        d = next((i['value'] for i in fx if i.get('type') == 'date'), None)
        fx_date = d
    print('匯率: %d 種，日期 %s' % (len(fx_rates), fx_date))

    prev_manifest = ex['tops'].get('manifest')
    catalog = build_catalog(info, navs, fx_rates, fx_date)
    manifest = build_manifest(navs, dists, prev_manifest)
    drefs = build_distribution_references(dists, navs, info_by_code)
    print('重建 smart-metrics ...')
    smart = build_smart_metrics(navs)
    sys.stdout.flush()

    if args.dry:
        print('\n--dry 模式，不寫入')
        for c, o, nw in changed[:15]:
            print('   %-5s %5d → %5d' % (c, o, nw))
        return 0

    os.makedirs(os.path.join(DATA, 'nav'), exist_ok=True)
    os.makedirs(os.path.join(DATA, 'distributions'), exist_ok=True)
    for code in navs:
        json.dump({'fundCode': code, 'points': navs[code]},
                  io.open(os.path.join(DATA, 'nav', code + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    for code in dists:
        json.dump(dists[code],
                  io.open(os.path.join(DATA, 'distributions', code + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    for name, obj in (('manifest', manifest), ('catalog', catalog),
                      ('distribution-references', drefs), ('smart-metrics', smart)):
        json.dump(obj, io.open(os.path.join(DATA, name + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
    print('\n寫出完成 →', DATA)
    return 0


def cmd_pack(args):
    """data/funds/*.json  →  data/*.js（掛到 window.__FUND_DATA__，供 script 標籤載入）

    file:// 下 fetch() 讀 .json 會被 CORS 擋，但 <script src="*.js"> 可以正常載入，
    所以外置檔案一律輸出成 .js。
    """
    ex = load_existing()
    if not ex['nav']:
        print('沒有資料可打包'); return 1

    written, total = 0, 0

    def emit(rel_json, obj):
        """rel_json 例如 'data/nav/A05.json'"""
        nonlocal written, total
        rel_js = rel_json[:-5] + '.js'
        key = rel_js
        body = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
        # 避免字串裡出現 </script> 截斷標籤
        body = body.replace('</', '<\\/')
        out = ('window.__FUND_DATA__=window.__FUND_DATA__||{};'
               'window.__FUND_DATA__[%s]=%s;\n'
               % (json.dumps(key, ensure_ascii=False), body))
        fp = os.path.join(ROOT, rel_js.replace('/', os.sep))
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with io.open(fp, 'w', encoding='utf-8') as f:
            f.write(out)
        written += 1
        total += len(out.encode('utf-8'))

    for name in ('manifest', 'catalog', 'distribution-references', 'smart-metrics'):
        if name in ex['tops']:
            emit('data/%s.json' % name, ex['tops'][name])
    for code in sorted(ex['nav']):
        emit('data/nav/%s.json' % code, ex['nav'][code])
    for code in sorted(ex['distributions']):
        emit('data/distributions/%s.json' % code, ex['distributions'][code])

    print('打包完成：%d 個 .js，共 %.2f MB' % (written, total / 1024 / 1024))
    return 0


def cmd_check(args):
    ex = load_existing()
    print('nav %d 檔 / distributions %d 檔 / 頂層 %s'
          % (len(ex['nav']), len(ex['distributions']), sorted(ex['tops'])))
    if not ex['nav']:
        print('沒有資料，先跑 seed'); return 1
    tot = 0
    mn = mx = None
    for code, o in sorted(ex['nav'].items()):
        pts = o.get('points') or []
        tot += len(pts)
        if pts:
            if mn is None or pts[0][0] < mn: mn = pts[0][0]
            if mx is None or pts[-1][0] > mx: mx = pts[-1][0]
    f = lambda ms: datetime.datetime.utcfromtimestamp(ms / 1000).strftime('%Y-%m-%d')
    print('總筆數 %d，範圍 %s ~ %s' % (tot, f(mn), f(mx)))
    sm = ex['tops'].get('smart-metrics')
    if sm:
        print('smart-metrics: default %d 筆 / customYears %s 組'
              % (len(sm.get('default') or []), len(sm.get('customYears') or {})))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd')
    p = sub.add_parser('seed')
    p.add_argument('--from', dest='src', default=None,
                   help='指定來源 HTML（外置後預設檔已無內嵌資料）')
    q = sub.add_parser('fetch')
    q.add_argument('--end', default=None, help='抓取截止日 YYYY-MM-DD，預設今天')
    q.add_argument('--dry', action='store_true', help='只比對不寫入')
    sub.add_parser('pack')
    sub.add_parser('check')
    a = ap.parse_args()
    if a.cmd == 'seed':
        return seed_from_html(a.src)
    if a.cmd == 'fetch':
        return cmd_fetch(a)
    if a.cmd == 'pack':
        return cmd_pack(a)
    if a.cmd == 'check':
        return cmd_check(a)
    ap.print_help()
    return 1


if __name__ == '__main__':
    sys.exit(main())
