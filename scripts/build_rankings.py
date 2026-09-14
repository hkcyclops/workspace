#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生「基金月榜」頁面（單一入口＋兩分頁＋類別切換）。

分頁一：派息基金（Z 開頭，isDistributionFund）
  欄位：名次 · 代號 · 基金名 · 紀錄日 · 年化派息率 · 實際總報酬 · 年化回報 · 派息貢獻 · NAV 貢獻
分頁二：非派息基金
  欄位：名次 · 代號 · 基金名 · 幣種 · 類別 · 期間回報 · 年化回報 · 波動率 · 最大回撤 · 較上月
  並有類別 chips：全部 / 股票 / 固定收入 / 多元資產 / 貨幣市場（名次為該類別內名次）

基準：每月最後一個交易日（每檔取該月最後有資料的交易日）
  派息榜 實際總報酬 = 期間累計派息 ÷ 期初 NAV + (期末 NAV − 期初 NAV) ÷ 期初 NAV
  非派息榜 期間回報   = (期末 NAV − 期初 NAV) ÷ 期初 NAV
           波動率     = 區間內日報酬標準差 × √252（年化）
           最大回撤   = 區間內由峰值回落的最大幅度
最新月份頁另加「較上月同口徑」名次箭頭：↑紅（上升）／↓綠（下降）／—灰（持平）／新（上月無資料）

產出：
  fund-ranking.html                 （永遠等於最新月份；含兩分頁）
  fund-ranking-YYYY-MM.html         （各月份永久存檔）
"""
import re, os, json, datetime, bisect, html, statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "_deploy-workspace")
DATA = os.path.join(DEPLOY, "data")

MONTHS = [(2026, 8), (2026, 7)]       # 由新到舊；第一個＝最新月份
TOP_DIV = {"YTD": 10, 1: 10, 3: 10, 5: 5}     # 派息榜名額
TOP_NAV = {"YTD": 10, 1: 10, 3: 10, 5: 10}    # 非派息榜名額
PERIODS = ("YTD", 1, 3, 5)          # YTD 排最前（最短區間）


def plabel(p):
    """表頭用標籤"""
    return "YTD" if p == "YTD" else f"{p} 年"


def pname(p):
    """表格標題用名稱"""
    return "YTD" if p == "YTD" else f"近 {p} 年"


def pyears(p):
    """年化用的年數；YTD 不年化 → None"""
    return None if p == "YTD" else p


def ptitle(p):
    """表格主標題"""
    return "YTD 最佳表現基金" if p == "YTD" else f"近 {p} 年最佳表現基金"


def ptag(p):
    """deep link 用的期間代號（06 的按鈕文字：YTD／1年／3年／5年）"""
    return "YTD" if p == "YTD" else f"{p}"
CATS = [("all", "全部"), ("stock", "股票"), ("fi", "固定收入"), ("multi", "多元資產"), ("mm", "貨幣市場")]

# 非派息比較窗口內另有零星派息的 3 檔（未計入回報，頁尾註明）
STALE_DIV = {"Q01": "2022-02-09", "Q02": "2022-02-09", "F07": "2021-09-08"}


def load(p):
    s = open(p, encoding="utf-8").read()
    m = re.search(r'__FUND_DATA__\["[^"]+"\]\s*=\s*(\{.*\})\s*;?\s*$', s, re.S)
    return json.loads(m.group(1) if m else s[s.find("{"):])


_nc, _dc = {}, {}


def nav_of(c):
    if c not in _nc:
        o = load(os.path.join(DATA, "nav", c + ".js"))
        _nc[c] = sorted((datetime.datetime.fromtimestamp(p[0] / 1000, datetime.UTC).date(), float(p[1]))
                        for p in (o.get("points") or []))
    return _nc[c]


def dist_of(c):
    if c not in _dc:
        o = load(os.path.join(DATA, "distributions", c + ".js"))
        _dc[c] = sorted((datetime.date.fromisoformat(r["recordDate"]), float(r.get("amountPerUnit") or 0))
                        for r in o.get("records", []) if r.get("recordDate"))
    return _dc[c]


cat = load(os.path.join(DATA, "catalog.js"))["funds"]
refs = load(os.path.join(DATA, "distribution-references.js"))
meta = {f["code"]: f for f in cat}
ZCODES = [f["code"] for f in cat if f.get("isDistributionFund")]
NCODES = [f["code"] for f in cat if not f.get("isDistributionFund")]


def category(f):
    a = str(f.get("assetClass") or "")
    if "貨幣市場" in a or "流動" in a:
        return "mm"
    if a.startswith("固定收入") or "固定收入" in a:
        return "fi"
    if "多元" in a:
        return "multi"
    if a.startswith("股票") or "股票" in a:
        return "stock"
    return "other"


CAT_OF = {f["code"]: category(f) for f in cat}


def month_end(y, m):
    return datetime.date(y, 12, 31) if m == 12 else datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)


def prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def window(code, period, anchor):
    """回傳 (期初NAV, 期末NAV, 期末日, 區間點列) 或 None
    period：'YTD'（去年最後一個交易日為基準）或 1／3／5（自期末回推年數）"""
    nav = nav_of(code)
    if not nav:
        return None
    ie = bisect.bisect_right([d for d, _ in nav], anchor) - 1
    if ie < 0:
        return None
    end_date, navh = nav[ie]
    if period == "YTD":
        start = datetime.date(end_date.year - 1, 12, 31)
        i0 = bisect.bisect_right([d for d, _ in nav], start) - 1     # 不晚於去年底的最近一點
        if i0 < 0 or (start - nav[i0][0]).days > 45:
            return None
    else:
        start = end_date - datetime.timedelta(days=int(365.25 * period))
        i0 = bisect.bisect_left([d for d, _ in nav], start)
        if i0 >= len(nav) or not (0 <= (nav[i0][0] - start).days <= 31):
            return None
    nav0 = nav[i0][1]
    if nav0 <= 0:
        return None
    return nav0, navh, end_date, nav[i0:ie + 1]


def period_start(end_date, period):
    return (datetime.date(end_date.year - 1, 12, 31) if period == "YTD"
            else end_date - datetime.timedelta(days=int(365.25 * period)))


def div_perf(code, period, anchor):
    w = window(code, period, anchor)
    if not w:
        return None
    nav0, navh, end_date, _ = w
    start = period_start(end_date, period)
    ds = dist_of(code)
    if not ds or ds[0][0] > start + datetime.timedelta(days=40):
        return None
    cum = sum(a for rd, a in ds if start < rd <= end_date)
    dp = cum / nav0 * 100
    np_ = (navh - nav0) / nav0 * 100
    total = dp + np_
    yrs = pyears(period)
    return {"total": total,
            "ann": ((1 + total / 100) ** (1 / yrs) - 1) * 100 if yrs else None,
            "div": dp, "nav": np_, "vol": None, "mdd": None, "end": end_date}


def nav_perf(code, period, anchor):
    w = window(code, period, anchor)
    if not w:
        return None
    nav0, navh, end_date, pts = w
    if len(pts) < 20:
        return None
    total = (navh - nav0) / nav0 * 100
    rets = [pts[i][1] / pts[i - 1][1] - 1 for i in range(1, len(pts)) if pts[i - 1][1] > 0]
    vol = st.pstdev(rets) * (252 ** 0.5) * 100 if len(rets) > 2 else None
    # 最大回撤：記錄高點日、低點日，以及之後是否收復（回到高點價位）
    peak, peak_i, worst = pts[0][1], 0, (0.0, 0, 0)
    for i, (_, v) in enumerate(pts):
        if v > peak:
            peak, peak_i = v, i
        dd = (v - peak) / peak * 100
        if dd < worst[0]:
            worst = (dd, peak_i, i)
    mdd, pi, ti = worst
    peak_v = pts[pi][1]
    rec_i = next((i for i in range(ti + 1, len(pts)) if pts[i][1] >= peak_v), None)
    pk_date, tr_date = pts[pi][0], pts[ti][0]
    cur = (pts[-1][1] / peak_v - 1) * 100
    yrs = pyears(period)
    return {"total": total,
            "ann": ((1 + total / 100) ** (1 / yrs) - 1) * 100 if yrs else None,
            "vol": vol, "mdd": mdd, "end": end_date,
            "pk": pk_date, "tr": tr_date,
            "rec": pts[rec_i][0] if rec_i is not None else None,
            "rec_m": (pts[rec_i][0] - tr_date).days / 30.44 if rec_i is not None else None,
            "uw_m": ((pts[rec_i][0] if rec_i is not None else pts[-1][0]) - pk_date).days / 30.44,
            "cur": cur}



def bucket(d):
    return "月初" if d.day <= 10 else ("月中" if d.day <= 20 else "月底")


def rank_map(codes, years, anchor, fn):
    rows = [(c, fn(c, years, anchor)) for c in codes]
    rows = [(c, r) for c, r in rows if r]
    rows.sort(key=lambda x: -x[1]["total"])
    return {c: i for i, (c, _) in enumerate(rows, 1)}, dict(rows)


def cls(v):
    return "pos" if v >= 0 else "neg"


def pct(v, sign=True):
    return f"{v:+.1f}%" if sign else f"{v:.1f}%"


def rank_cell(rank, prev_rank):
    if prev_rank is None:
        return f"<td class='rk'>{rank}</td>"
    if prev_rank == "NA":
        return f"<td class='rk'>{rank}<span class='mv flat'>新</span></td>"
    d = prev_rank - rank
    if d > 0:
        return f"<td class='rk'>{rank}<span class='mv up'>↑{d}</span></td>"
    if d < 0:
        return f"<td class='rk'>{rank}<span class='mv down'>↓{-d}</span></td>"
    return f"<td class='rk'>{rank}<span class='mv flat'>—</span></td>"


# ---------- 表頭 ？ 說明 ----------
TIPS = {
    "rate": ("年化派息率", "依最近一次派息推算的未來一年配息率（<b>預估</b>）。\n公式：最近一筆派息金額 ÷ 該筆派息日配對 NAV × 12。"),
    "total": ("實際總報酬", "該期間「領到的息 + 淨值漲跌」合計（<b>實際</b>）。\n＝ 派息貢獻 + NAV 貢獻，未扣贖回費。"),
    "ann": ("年化回報", "期間回報折算為每年複利（<b>實際</b>）。\n＝ (1 + 期間回報)^(1 ÷ 年數) − 1，方便比較 1／3／5 年。"),
    "div": ("派息貢獻", "期間累計派息 ÷ 期初淨值（<b>實際領到多少</b>）。"),
    "nav": ("NAV 貢獻", "淨值漲跌。\n＝ (期末 NAV − 期初 NAV) ÷ 期初 NAV。"),
    "r1": ("期間回報", "該期間淨值漲跌（<b>累積型基金無派息</b>）。\n＝ (期末 NAV − 期初 NAV) ÷ 期初 NAV，未扣費用。"),
    "vol": ("波動率", "區間內日報酬標準差 × √252，<b>年化</b>。\n數字越大＝淨值上下起伏越劇烈（風險越高）。"),
    "mdd": ("最大回撤", "區間內由最高點回落的最大幅度。\n例：−32.8% 表示曾經由高位跌掉三成二，是「最壞時刻」的參考。"),
    "rec": ("收復時間", "由最大回撤的低點，回到先前高點價位所需的時間（月）。\n<b>未收復</b>＝到基準日仍未回到該高點。滑鼠移到數字上看三個日期。"),
}


def th(label, key=None):
    if not key:
        return f"<th>{label}</th>"
    t, body = TIPS[key]
    body = body.replace("\n", "<br>")
    return (f"<th>{label}"
            f"<span class='tip'><button type='button' class='tip-btn' "
            f"aria-label='{t}說明' aria-expanded='false'>?</button>"
            f"<span class='tip-pop' role='tooltip'><b>{t}</b><span>{body}</span></span></span></th>")


def table(period_label, head, body_rows, note):
    return f"""
<section class="card">
  <h2><span class="num">{period_label[0]}</span>{period_label[1]}</h2>
  <div class="tw">
    <table>
      <thead><tr>{head}</tr></thead>
      <tbody>{''.join(body_rows)}</tbody>
    </table>
  </div>
  <p class="note">{note}</p>
</section>"""


def build_div_panel(y, m, is_latest, anchor, prev_anchor):
    blocks, ends = [], []
    TH = (th("年化派息率", "rate") + th("實際總報酬", "total") + th("年化回報", "ann")
          + th("派息貢獻", "div") + th("NAV 貢獻", "nav"))
    TH_YTD = (th("年化派息率", "rate") + th("實際總報酬", "total")
              + th("派息貢獻", "div") + th("NAV 貢獻", "nav"))
    for p in PERIODS:
        ytd = (p == "YTD")
        head = f"<th>名次</th><th>代號</th><th>基金名</th><th>紀錄日</th>{TH_YTD if ytd else TH}"
        ranks, pm = rank_map(ZCODES, p, anchor, div_perf)
        prev = rank_map(ZCODES, p, prev_anchor, div_perf)[0] if is_latest else {}
        rows = sorted(pm.items(), key=lambda x: -x[1]["total"])[:TOP_DIV[p]]
        ends += [r["end"] for _, r in rows]
        out = []
        for i, (c, r) in enumerate(rows, 1):
            ds = dist_of(c)
            b = bucket(ds[-1][0]) if ds else ""
            rate = refs.get(c, {}).get("annualizedDistributionRate") or 0
            pr = prev.get(c, "NA") if is_latest else None
            ann_cell = "" if ytd else f"<td class='num {cls(r['ann'])}'>{pct(r['ann'])}</td>"
            out.append(
                f"<tr>{rank_cell(i, pr)}<td class='code'>{c}</td>"
                f"<td class='fname'><a class='flink' href='./06-fund-portfolio-workbench.html?fund={c}&y={ptag(p)}' "
                f"title='在 06 開啟 {c} 的 {plabel(p)}走勢圖'>{html.escape((meta[c].get('name') or '').strip())}</a></td><td>{b}</td>"
                f"<td class='num'>{rate:.2f}%</td>"
                f"<td class='num {cls(r['total'])}'>{pct(r['total'])}</td>"
                + ann_cell +
                f"<td class='num'>{pct(r['div'])}</td>"
                f"<td class='num {cls(r['nav'])}'>{pct(r['nav'])}</td></tr>")
        note = f"共 {len(pm)} 檔資料完整，取前 {len(rows)} 名；依<b>實際總報酬</b>（派息＋淨值）排序"
        if p == 5:
            note += "；5 年區間含 2022 年股債雙殺，數字普遍偏低，屬區間效應"
        if ytd:
            note += "；<b>YTD</b>＝去年最後一個交易日至基準日，期間未滿一年故不列年化回報"
        note += arrow_note(is_latest, m)
        blocks.append(table((plabel(p) if ytd else f"{p} 年期", ptitle(p)), head, out, note))
    return ''.join(blocks), ends


def arrow_note(is_latest, m, extra=""):
    if not is_latest:
        return f"；本頁為 {m} 月快照，不做前期比較"
    return ("；名次箭頭為與上月同口徑比較，<span class='mv up'>↑紅＝上升</span>、"
            "<span class='mv down'>↓綠＝下降</span>、<span class='mv flat'>—＝持平</span>、"
            "<span class='mv flat'>新＝上月無同口徑資料</span>" + extra)


def rec_txt(r):
    """收復時間欄的顯示值"""
    return f"{r['rec_m']:.1f}月" if r["rec"] is not None else "未收復"


SPARK_N = 45          # 縮略圖點數


def spark(code, years, anchor):
    """縮略圖資料：降採樣 0–100 序列 + 回撤／收復時間比例 + 文字用的日期與數值"""
    w = window(code, years, anchor)
    if not w:
        return None
    _, _, _, pts = w
    if len(pts) < 20:
        return None
    vals = [v for _, v in pts]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    step = max(1, len(pts) // SPARK_N)
    sampled = pts[::step]
    if sampled[-1][0] != pts[-1][0]:
        sampled.append(pts[-1])
    v = [int(round((val - lo) / rng * 100)) for _, val in sampled]

    peak, pi, worst = vals[0], 0, (0.0, 0, 0)
    for i, x in enumerate(vals):
        if x > peak:
            peak, pi = x, i
        d = (x - peak) / peak * 100
        if d < worst[0]:
            worst = (d, pi, i)
    mdd, pi, ti = worst
    rec_i = next((i for i in range(ti + 1, len(vals)) if vals[i] >= vals[pi]), None)
    n = len(vals) - 1 or 1
    pk_d, tr_d = pts[pi][0], pts[ti][0]
    rec_d = pts[rec_i][0] if rec_i is not None else None
    end_d = pts[-1][0]
    return {"v": v, "pk": round(pi / n, 3), "tr": round(ti / n, 3),
            "rec": round(rec_i / n, 3) if rec_i is not None else None,
            "pkd": pk_d.isoformat(), "trd": tr_d.isoformat(),
            "recd": rec_d.isoformat() if rec_d else None,
            "rm": round((rec_d - tr_d).days / 30.44, 1) if rec_d else None,
            "uw": round(((rec_d or end_d) - pk_d).days / 30.44, 1),
            "cur": round((pts[-1][1] / pts[pi][1] - 1) * 100, 1),
            "end": end_d.isoformat()}


def tip_cell(value, skey, col, cls_extra=""):
    """數值欄：標記精簡，hover 時由 JS 依 __SPARK__ 組出提示（含縮略圖）"""
    return (f"<td class='num {cls_extra}'>"
            f"<span class='tip tip-cell' tabindex='0' data-s='{skey}' data-c='{col}'>{value}</span></td>")


def build_nav_panel(y, m, is_latest, anchor, prev_anchor, sparks):
    """非派息榜：5 個類別 chips × 4 個期間（YTD／1／3／5）"""
    head = ("<th>名次</th><th>代號</th><th>基金名</th><th>幣種</th><th>類別</th>"
            + th("期間回報", "r1") + th("年化回報", "ann") + th("波動率", "vol")
            + th("最大回撤", "mdd") + th("收復時間", "rec"))
    head_ytd = ("<th>名次</th><th>代號</th><th>基金名</th><th>幣種</th><th>類別</th>"
                + th("期間回報", "r1") + th("波動率", "vol")
                + th("最大回撤", "mdd") + th("收復時間", "rec"))
    counts, catblocks, ends = {}, [], []
    for key, label in CATS:
        codes = NCODES if key == "all" else [c for c in NCODES if CAT_OF.get(c) == key]
        if not codes:
            continue
        pcodes = codes
        inner = []
        n_ok = 0
        for p in PERIODS:
            ytd = (p == "YTD")
            ranks, pm = rank_map(pcodes, p, anchor, nav_perf)
            n_ok = max(n_ok, len(pm))
            prev = rank_map(pcodes, p, prev_anchor, nav_perf)[0] if is_latest else {}
            rows = sorted(pm.items(), key=lambda x: -x[1]["total"])[:TOP_NAV[p]]
            ends += [r["end"] for _, r in rows]
            out = []
            for i, (c, r) in enumerate(rows, 1):
                f = meta[c]
                pr = prev.get(c, "NA") if is_latest else None
                catlabel = dict(CATS).get(CAT_OF.get(c), "其他")
                hedged = "（對沖）" if f.get("hedged") else ""
                skey = f"{c}|{p}"
                sp = spark(c, p, anchor)
                if sp:
                    sparks[skey] = sp
                ann_cell = "" if ytd else tip_cell(pct(r["ann"]), skey, "ann", cls(r["ann"]))
                out.append(
                    f"<tr>{rank_cell(i, pr)}<td class='code'>{c}</td>"
                    f"<td class='fname'><a class='flink' href='./06-fund-portfolio-workbench.html?fund={c}&y={ptag(p)}' "
                    f"title='在 06 開啟 {c} 的 {plabel(p)}走勢圖'>{html.escape((f.get('name') or '').strip())}</a>"
                    f"<span class='tag'>{hedged}</span></td>"
                    f"<td>{f.get('currencyCode') or '—'}</td><td>{catlabel}</td>"
                    + tip_cell(pct(r["total"]), skey, "r1", cls(r["total"]))
                    + ann_cell
                    + tip_cell(f"{r['vol']:.1f}%", skey, "vol")
                    + tip_cell(f"{r['mdd']:.1f}%", skey, "mdd", cls(r["mdd"]))
                    + tip_cell(rec_txt(r), skey, "rec")
                    + "</tr>")
            note = f"共 {len(pm)} 檔資料完整，取前 {len(rows)} 名；依<b>淨值回報</b>排序"
            if ytd:
                note += "；<b>YTD</b>＝去年最後一個交易日至基準日，期間未滿一年故不列年化回報"
            note += arrow_note(is_latest, m)
            inner.append(table((plabel(p) if ytd else f"{p} 年期", ptitle(p)),
                               head_ytd if ytd else head, out, note))
        counts[key] = n_ok
        on = " is-on" if key == "all" else ""
        catblocks.append(f"<div class='catblock{on}' data-cat='{key}'>{''.join(inner)}</div>")
    chips = []
    for key, label in CATS:
        if key not in counts:
            continue
        on = " is-on" if key == "all" else ""
        chips.append(f"<button type='button' class='cat{on}' data-cat='{key}'>{label}"
                     f"<b>{counts[key]}</b></button>")
    return f"<div class='catbar'>{''.join(chips)}</div>{''.join(catblocks)}", ends


def fname_for(y, m, lang):
    """各月份／語言的檔名（最新月份的繁體版固定為 fund-ranking.html）"""
    latest = (y, m) == MONTHS[0]
    suf = "" if lang == "tr" else "-sc"
    return ("fund-ranking" if latest else f"fund-ranking-{y}-{m:02d}") + suf + ".html"


def month_nav_tpl(y, m, is_latest):
    """月份導覽（以 __URL_*__ 佔位，產檔時再依語言替換）"""
    opts = []
    for (yy, mm) in MONTHS:
        sel = " selected" if (yy, mm) == (y, m) else ""
        opts.append(f"<option value='__URL_{yy}-{mm:02d}__'{sel}>{yy}-{mm:02d}</option>")
    idx = MONTHS.index((y, m))
    if idx + 1 < len(MONTHS):
        oy, om = MONTHS[idx + 1]
        prev_html = f"<a class='mnav' href='__URL_{oy}-{om:02d}__'>&lsaquo; 前一月</a>"
    else:
        prev_html = "<span class='mnav off'>&lsaquo; 前一月</span>"
    next_html = ("<span class='mnav off'>最新月份 &rsaquo;</span>" if is_latest
                 else "<a class='mnav' href='__URL_LATEST__'>最新月份 &rsaquo;</a>")
    return (f"<nav class='monthnav' aria-label='月份切換'>{prev_html}"
            f"<label class='mnav mnav-sel'><span>月份</span>"
            f"<select aria-label='選擇月份' onchange=\"if(this.value) location.href=this.value\">"
            f"{''.join(opts)}</select></label>{next_html}</nav>")


def localize(html, y, m, lang):
    """把佔位符替換成該語言的網址與語言標記"""
    other = "sc" if lang == "tr" else "tr"
    out = (html
           .replace("__URL_LATEST__", fname_for(MONTHS[0][0], MONTHS[0][1], lang))
           .replace("__URL_TR__", fname_for(y, m, "tr"))
           .replace("__URL_SC__", fname_for(y, m, "sc"))
           .replace("__SELF__", fname_for(y, m, lang))
           .replace("__OTHER__", fname_for(y, m, other))
           .replace("__LANGTAG__", "zh-HK" if lang == "tr" else "zh-Hans")
           .replace("__LANGVAL__", lang)
           .replace("__TR_ON__", " is-on" if lang == "tr" else "")
           .replace("__SC_ON__", " is-on" if lang == "sc" else ""))
    for (yy, mm) in MONTHS:
        out = out.replace(f"__URL_{yy}-{mm:02d}__", fname_for(yy, mm, lang))
    return out


STYLE = """
  :root{
    --page:#f4efe5; --surface:#fffdf8; --surface-2:#fffaf2; --surface-3:#f9f2e7;
    --head:#f0e8dc; --gold:#c8a85b; --gold-soft:#d9c7a9;
    --line:#e1d6c4; --line-2:#eee3d4; --line-3:#d8c8b3;
    --ink:#342d28; --ink-2:#5e5145; --th-ink:#49372f;
    --red:#8f0d25; --gray:#8c7d70;
    --up:#b13446; --down:#347558;
  }
  /* 漲跌色：繁體版＝綠漲紅跌、簡體版＝紅漲綠跌（跟隨頁面 data-lang） */
  html[data-lang="tr"]{--up:#347558;--down:#b13446}
  html[data-lang="sc"]{--up:#b13446;--down:#347558}
  *{box-sizing:border-box}
  body{margin:0;background:var(--page);color:var(--ink);
    background-image:linear-gradient(90deg,#20212407 1px,#0000 1px),linear-gradient(#20212405 1px,#0000 1px);
    background-size:32px 32px;
    font-family:"Noto Sans TC",ui-sans-serif,system-ui,"Segoe UI",sans-serif;
    font-size:16px;line-height:1.8;-webkit-font-smoothing:antialiased;min-width:320px}
  .wrap{max-width:100%;margin:0 auto;padding:34px clamp(16px,2.2vw,44px) 70px}
  header.masthead{border-bottom:2px solid var(--red);padding-bottom:18px;margin-bottom:20px;position:relative}
  .eyebrow{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.16em;margin:0 0 8px}
  h1{font-family:Georgia,"Noto Serif TC",serif;font-size:32px;font-weight:500;margin:0;color:var(--ink);line-height:1.35}
  .sub{color:var(--ink-2);font-size:14px;margin:12px 0 0;line-height:1.8}
  .monthnav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0 0}
  .mnav{border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);
    padding:7px 11px;font-size:13px;font-weight:700;text-decoration:none;
    display:inline-flex;align-items:center;gap:6px;line-height:1.4}
  .mnav:hover{border-color:var(--red);color:var(--red)}
  .mnav.off{opacity:.42;pointer-events:none}
  .mnav-sel select{border:0;background:transparent;color:inherit;font:inherit;font-weight:700;cursor:pointer;padding:0 2px}
  .mnav-sel span{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.08em}
  .tabs{display:flex;gap:0;border-bottom:2px solid var(--line-3);margin:22px 0 0;flex-wrap:wrap}
  .tab{appearance:none;border:0;background:transparent;cursor:pointer;font:inherit;font-weight:700;
    color:var(--ink-2);padding:11px 18px;border-bottom:2px solid transparent;margin-bottom:-2px}
  .tab b{font-family:Georgia,serif;color:var(--gray);font-weight:700;margin-left:6px}
  .tab:hover{color:var(--red)}
  .tab.is-on{color:var(--red);border-bottom-color:var(--red)}
  .tab.is-on b{color:var(--red)}
  .panel{display:none}
  .panel.is-on{display:block}
  .catbar{display:flex;gap:8px;flex-wrap:wrap;margin:22px 0 0;align-items:center}
  .cat{appearance:none;cursor:pointer;font:inherit;font-size:13px;font-weight:700;
    border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);
    padding:6px 12px;line-height:1.5}
  .cat b{font-family:Georgia,serif;color:var(--gray);margin-left:6px;font-weight:700}
  .cat:hover{border-color:var(--red);color:var(--red)}
  .cat.is-on{background:#fdf6e6;border-color:var(--gold);color:var(--th-ink)}
  .cat.is-on b{color:var(--th-ink)}
  .catblock{display:none}
  .catblock.is-on{display:block}
  section.card{background:#fffdf8e6;border:1px solid var(--line);box-shadow:0 13px 28px #422f2012;padding:26px;margin:24px 0}
  h2{font-family:Georgia,"Noto Serif TC",serif;font-size:22px;font-weight:500;color:var(--red);margin:0 0 16px}
  h2 .num{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.14em;display:block;margin-bottom:6px}
  .tw{background:var(--surface);border:1px solid #decfb8;box-shadow:inset 0 2px var(--gold);overflow-x:auto;margin:12px 0}
  table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:1080px}
  th,td{border-bottom:1px solid var(--line-2);padding:11px 12px;text-align:right;white-space:nowrap;line-height:1.4}
  th{color:var(--th-ink);background:var(--head);border-bottom:1px solid var(--line-3);font-weight:700;font-size:13px}
  @media (min-width:1500px){table{font-size:15px}th,td{padding:12px 15px}th{font-size:13.5px}td.fname{font-size:14px}}
  @media (min-width:1900px){table{font-size:15.5px}th,td{padding:13px 17px}}
  th:nth-child(-n+5),td:nth-child(-n+5){text-align:left}
  td.fname{white-space:normal;min-width:240px;font-size:13.5px;color:var(--ink-2);line-height:1.5}
  td.code{font-family:Georgia,serif;font-weight:700;color:var(--ink)}
  td.rk{font-family:Georgia,serif;font-weight:700;color:var(--ink);white-space:nowrap}
  td.rk .mv{margin-left:6px;font-size:11.5px;font-weight:800}
  .tag{color:var(--gray);font-size:11.5px}
  tbody tr:nth-child(odd){background:var(--surface-2)}
  tbody tr:nth-child(2n){background:var(--surface-3)}
  tbody tr:hover{background:#fcf5e9}
  .num{font-family:Georgia,serif;font-variant-numeric:tabular-nums lining-nums}
  .pos{color:var(--up);font-weight:700}
  .neg{color:var(--down);font-weight:700}
  .mv.up{color:var(--up)}
  .mv.down{color:var(--down)}
  .mv.flat{color:#a89b8c}
  .note{color:var(--gray);font-size:13px;margin:10px 0 0}
  .backlink{margin:8px 0 0;font-size:13.5px}
  .tip{position:relative;display:inline-flex;vertical-align:middle;margin-left:4px}
  .tip-btn{width:16px;height:16px;border-radius:50%;border:1px solid var(--gold);background:#fffdf8;color:#ae8a46;
    font-size:10.5px;font-weight:700;line-height:1;display:grid;place-items:center;cursor:help;padding:0}
  .tip-btn:hover,.tip-btn:focus-visible{background:var(--gold);border-color:var(--gold);color:#fff}
  .tip-btn:focus-visible{outline:2px solid #b78e42;outline-offset:2px}
  .tip-pop{position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%) translateY(-4px);
    z-index:60;width:max-content;max-width:min(320px,80vw);display:grid;gap:4px;text-align:left;
    background:#4b302b;color:#fffaf1;border:1px solid var(--gold-soft);
    padding:11px 13px;font-size:12.5px;line-height:1.7;font-weight:400;white-space:normal;
    box-shadow:0 8px 20px #422f2033;opacity:0;visibility:hidden;transition:opacity .16s,transform .16s,visibility .16s}
  .tip-pop b{color:#f1d58e;font-size:12px;font-weight:800;letter-spacing:.04em}
  .tip:hover .tip-pop,.tip:focus-within .tip-pop,.tip.is-open .tip-pop{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}
  .tip-cell{cursor:help;position:relative;border-bottom:1px dashed #cbbba2;padding-bottom:1px}
  .tip-cell:focus{outline:2px solid #b78e42;outline-offset:2px}
  /* 數值欄提示框：浮動到 body（避開表格容器的 overflow 裁切），空間不足自動上彈 */
  .tip-pop.tip-float{position:fixed;left:0;top:0;z-index:200;max-width:min(300px,86vw);
    transform:none;transition:opacity .12s;pointer-events:auto}
  .tip-pop.tip-float.is-open{opacity:1;visibility:visible}
  .spark{width:262px;height:74px;display:block;background:#3f2823;margin:2px 0 4px}
  .spark .line{fill:none;stroke:#f1d58e;stroke-width:1.6;vector-effect:non-scaling-stroke}
  .spark .band-a{fill:#c8a85b;opacity:.30}
  .spark .band-b{fill:#c8a85b;opacity:.13}
  .spark .dash{stroke:#e8dcc0;stroke-width:1;stroke-dasharray:3 3}
  .spark .dot{fill:#f1d58e}
  a.flink{color:inherit;text-decoration:none;border-bottom:1px solid #d8c8b3}
  a.flink:hover{color:var(--red);border-bottom-color:var(--red)}
  .langsw{display:inline-flex;align-items:center;gap:0;border:1px solid var(--line-3);background:var(--surface);
    line-height:1;position:absolute;top:0;right:0;vertical-align:middle}
  .langsw-lbl{color:var(--gray);font-size:10px;font-weight:800;letter-spacing:.08em;padding:0 6px 0 5px;
    font-family:ui-monospace,Consolas,monospace}
  .langbtn{color:var(--ink-2);min-width:30px;text-align:center;text-decoration:none;padding:7px 6px;
    font-size:13px;font-weight:700}
  .langbtn:hover{color:var(--red)}
  .langbtn.is-on{background:var(--ink);color:#fff}
  @media (max-width:700px){
    .tip-pop{left:auto;right:0;transform:translateY(-4px)}
    .tip:hover .tip-pop,.tip:focus-within .tip-pop,.tip.is-open .tip-pop{transform:translateY(0)}
    .spark{width:200px;height:58px}
    .langsw{position:static;margin:12px 0 0}
    .langsw-lbl{display:none}
  }
  footer{margin-top:28px;color:var(--gray);font-size:13px;line-height:1.8}
"""

SCRIPT = """
(function(){
  var tips = Array.prototype.slice.call(document.querySelectorAll('.tip'));
  function closeAll(except){
    tips.forEach(function(t){
      if (t === except) return;
      t.classList.remove('is-open');
      var b = t.querySelector('.tip-btn'); if (b) b.setAttribute('aria-expanded','false');
    });
  }
  tips.forEach(function(t){
    var btn = t.querySelector('.tip-btn');
    if (!btn) return;
    btn.addEventListener('click', function(e){
      e.preventDefault(); e.stopPropagation();
      var open = t.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      closeAll(t);
    });
  });
  document.addEventListener('click', function(e){
    if (!e.target.closest || !e.target.closest('.tip')) closeAll(null);
  });
  document.addEventListener('keydown', function(e){ if (e.key === 'Escape') closeAll(null); });

  function showTab(name){
    Array.prototype.forEach.call(document.querySelectorAll('.tab'), function(b){
      var on = b.getAttribute('data-tab') === name;
      b.classList.toggle('is-on', on);
      b.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    Array.prototype.forEach.call(document.querySelectorAll('.panel'), function(p){
      p.classList.toggle('is-on', p.getAttribute('data-panel') === name);
    });
  }
  function showCat(k){
    var found = false;
    Array.prototype.forEach.call(document.querySelectorAll('.cat'), function(x){
      var on = x.getAttribute('data-cat') === k;
      if (on) found = true;
      x.classList.toggle('is-on', on);
    });
    if (!found) return false;
    Array.prototype.forEach.call(document.querySelectorAll('.catblock'), function(x){
      x.classList.toggle('is-on', x.getAttribute('data-cat') === k);
    });
    return true;
  }

  /* 檢視狀態（tab / 類別）寫進網址，並讓月份導覽與語言鈕帶住狀態 → 換月不跳回派息榜 */
  var state = {tab: 'div', cat: 'all'};
  function qs(){
    var p = [];
    if (state.tab !== 'div') p.push('tab=' + state.tab);
    if (state.cat !== 'all') p.push('cat=' + state.cat);
    return p.length ? '?' + p.join('&') : '';
  }
  function syncLinks(){
    var q = qs();
    function fix(el, attr){
      var base = el.getAttribute('data-base');
      if (base === null){
        base = (attr === 'value' ? el.value : el.getAttribute('href')) || '';
        el.setAttribute('data-base', base);
      }
      var url = base + q;
      if (attr === 'value') el.value = url; else el.setAttribute('href', url);
    }
    Array.prototype.forEach.call(document.querySelectorAll('.monthnav a.mnav[href]'), function(a){ fix(a, 'href'); });
    Array.prototype.forEach.call(document.querySelectorAll('.monthnav option'), function(o){ fix(o, 'value'); });
    Array.prototype.forEach.call(document.querySelectorAll('.langbtn[href]'), function(a){ fix(a, 'href'); });
  }
  function sync(){
    if (history.replaceState) history.replaceState(null, '', location.pathname + qs());
    syncLinks();
  }
  Array.prototype.forEach.call(document.querySelectorAll('.tab'), function(b){
    b.addEventListener('click', function(){
      state.tab = b.getAttribute('data-tab');
      showTab(state.tab);
      sync();
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('.cat'), function(b){
    b.addEventListener('click', function(){
      var k = b.getAttribute('data-cat');
      if (showCat(k)){ state.cat = k; sync(); }
    });
  });

  /* 數值欄提示：第一次 hover 才組內容（文字 + 45 點縮略圖 + 回撤／收復陰影） */
  var SPARK = window.__SPARK__ || {};
  var NS = 'http://www.w3.org/2000/svg';
  var LEGEND = '深色＝回撤期（高點→低點）、淺色＝收復期';
  var COLS = {r1: '期間回報', ann: '年化回報', vol: '波動率', mdd: '最大回撤', rec: '最大回撤收復'};

  function buildChart(d){
    var W = 262, H = 74, pad = 3, n = d.v.length;
    var X = function(i){ return pad + i * (W - 2 * pad) / (n - 1); };
    var Y = function(val){ return H - pad - val * (H - 2 * pad) / 100; };
    var svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('class', 'spark');
    svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
    svg.setAttribute('preserveAspectRatio', 'none');
    var idx = function(f){ return f * (n - 1); };
    function band(x0, x1, cls){
      if (x1 <= x0) return;
      var r = document.createElementNS(NS, 'rect');
      r.setAttribute('class', cls);
      r.setAttribute('x', X(x0)); r.setAttribute('y', 0);
      r.setAttribute('width', Math.max(0.5, X(x1) - X(x0))); r.setAttribute('height', H);
      svg.appendChild(r);
    }
    var ipk = idx(d.pk), itr = idx(d.tr);
    band(ipk, itr, 'band-a');
    band(itr, (d.rec === null || d.rec === undefined) ? n - 1 : idx(d.rec), 'band-b');
    [ipk, itr].forEach(function(i){
      var l = document.createElementNS(NS, 'line');
      l.setAttribute('class', 'dash');
      l.setAttribute('x1', X(i)); l.setAttribute('x2', X(i));
      l.setAttribute('y1', 0); l.setAttribute('y2', H);
      svg.appendChild(l);
    });
    var path = document.createElementNS(NS, 'path');
    path.setAttribute('class', 'line');
    path.setAttribute('d', d.v.map(function(val, i){
      return (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(val).toFixed(1);
    }).join(' '));
    svg.appendChild(path);
    [[ipk, d.v[Math.round(ipk)]], [itr, d.v[Math.round(itr)]]].forEach(function(p){
      var c = document.createElementNS(NS, 'circle');
      c.setAttribute('class', 'dot');
      c.setAttribute('r', 2.6);
      c.setAttribute('cx', X(p[0])); c.setAttribute('cy', Y(p[1]));
      svg.appendChild(c);
    });
    return svg;
  }

  function buildPop(t){
    var key = t.getAttribute('data-s'), col = t.getAttribute('data-c'), d = SPARK[key];
    if (!d) return null;
    var val = t.textContent, per = (key || '').split('|')[1] || '';
    var perTxt = /^[0-9]+$/.test(per) ? ('近 ' + per + ' 年') : 'YTD';
    var lines = [];
    if (col === 'r1') lines.push(perTxt + '淨值漲跌 ' + val);
    else if (col === 'ann') lines.push('年化 ' + val);
    else if (col === 'vol') lines.push('年化波動率 ' + val);
    else if (col === 'mdd') lines.push('最大回撤 ' + val + '<br>高點 ' + d.pkd + ' → 低點 ' + d.trd);
    else {
      lines.push('高點 ' + d.pkd + ' → 低點 ' + d.trd);
      if (d.recd) lines.push('回到高點 ' + d.recd + '<br>低點起算 ' + d.rm + ' 個月；自高點起水下 ' + d.uw + ' 個月');
      else lines.push('至 ' + d.end + ' 仍未回到該高點<br>已 ' + d.uw + ' 個月，現距高點 ' + d.cur + '%');
    }
    lines.push(LEGEND);
    var pop = document.createElement('span');
    pop.className = 'tip-pop tip-float';
    pop.setAttribute('role', 'tooltip');
    var b = document.createElement('b'); b.textContent = COLS[col] || '';
    var txt = document.createElement('span'); txt.innerHTML = lines.join('<br>');
    pop.appendChild(b); pop.appendChild(buildChart(d)); pop.appendChild(txt);
    pop.addEventListener('mouseenter', function(){ cancelClose(); });
    pop.addEventListener('mouseleave', function(){ scheduleClose(t); });
    document.body.appendChild(pop);
    t.__pop = pop;
    return pop;
  }

  /* 浮動定位：預設貼在數值下方；下方空間不足就翻到上方；水平右對齊並夾在視窗內 */
  function placePop(t){
    var pop = t.__pop;
    if (!pop) return;
    var r = t.getBoundingClientRect();
    pop.classList.add('is-open');
    pop.style.visibility = 'hidden';
    var w = pop.offsetWidth, h = pop.offsetHeight;
    var below = window.innerHeight - r.bottom, above = r.top;
    var top = (below >= h + 14 || below >= above) ? (r.bottom + 8) : (r.top - h - 8);
    var left = r.right - w;
    if (left + w > window.innerWidth - 8) left = window.innerWidth - w - 8;
    if (left < 8) left = 8;
    if (top + h > window.innerHeight - 8) top = Math.max(8, window.innerHeight - h - 8);
    if (top < 8) top = 8;
    pop.style.top = Math.round(top) + 'px';
    pop.style.left = Math.round(left) + 'px';
    pop.style.visibility = '';
  }
  function closeTip(t){
    if (t.__pop) t.__pop.classList.remove('is-open');
    t.classList.remove('is-open');
  }
  function closeOthers(except){
    Array.prototype.forEach.call(document.querySelectorAll('.tip-cell.is-open'), function(x){
      if (x !== except) closeTip(x);
    });
  }
  function openTip(t){
    cancelClose();
    if (!t.__pop) buildPop(t);
    if (!t.__pop) return;
    t.classList.add('is-open');
    placePop(t);
  }
  var closeTimer = null;
  function scheduleClose(t){
    clearTimeout(closeTimer);
    closeTimer = setTimeout(function(){ closeTip(t); }, 180);
  }
  function cancelClose(){ clearTimeout(closeTimer); }
  Array.prototype.forEach.call(document.querySelectorAll('.tip-cell'), function(t){
    t.addEventListener('mouseenter', function(){ closeOthers(t); openTip(t); });
    t.addEventListener('mouseleave', function(){ scheduleClose(t); });
    t.addEventListener('focusin', function(){ closeOthers(t); openTip(t); });
    t.addEventListener('blur', function(){ scheduleClose(t); });
    t.addEventListener('click', function(e){
      e.preventDefault(); e.stopPropagation();
      if (t.classList.contains('is-open')) closeTip(t); else { closeOthers(t); openTip(t); }
    });
  });
  document.addEventListener('click', function(){ closeOthers(null); });
  window.addEventListener('scroll', function(){
    var open = document.querySelector('.tip-cell.is-open');
    if (!open) return;
    var r = open.getBoundingClientRect();
    if (r.bottom < 0 || r.top > window.innerHeight){ closeTip(open); return; }
    placePop(open);
  }, true);
  window.addEventListener('resize', function(){
    var open = document.querySelector('.tip-cell.is-open');
    if (open) placePop(open);
  });

  var mTab = /[?&]tab=(div|nav)/.exec(location.search);
  if (mTab) state.tab = mTab[1];
  var mCat = /[?&]cat=([a-z]+)/.exec(location.search);
  if (mCat && showCat(mCat[1])) state.cat = mCat[1];
  showTab(state.tab);
  sync();

  /* 語言：1) 跟隨 06（同源 localStorage 'calculator-hub-language'）2) 本頁切換時寫回同一鍵 */
  var PAGE_LANG = '__LANGVAL__';
  var OTHER_URL = '__OTHER__';
  function swapTo(url){
    if (history.replaceState) history.replaceState(null, '', location.pathname + location.search);
    location.replace(url + location.search);
  }
  try {
    var want = localStorage.getItem('calculator-hub-language');
    if (want === 'traditional' && PAGE_LANG !== 'tr') swapTo(OTHER_URL);
    else if (want === 'simplified' && PAGE_LANG !== 'sc') swapTo(OTHER_URL);
  } catch (e) {}
  Array.prototype.forEach.call(document.querySelectorAll('.langbtn'), function(a){
    a.addEventListener('click', function(){
      try { localStorage.setItem('calculator-hub-language', a.getAttribute('data-lang')); } catch (e) {}
    });
  });
})();
"""


def build_page(y, m, is_latest):
    anchor = month_end(y, m)
    py, pm = prev_month(y, m)
    prev_anchor = month_end(py, pm) if is_latest else None

    div_html, div_ends = build_div_panel(y, m, is_latest, anchor, prev_anchor)
    sparks = {}
    nav_html, nav_ends = build_nav_panel(y, m, is_latest, anchor, prev_anchor, sparks)
    end_disp = max(div_ends + nav_ends).strftime("%Y-%m-%d")
    spark_json = json.dumps(sparks, separators=(",", ":"), ensure_ascii=False)

    n_ok_nav = sum(1 for c in NCODES if nav_perf(c, 1, anchor))
    TITLE = f"基金月榜 - {m}月"
    stale = "、".join(f"{c}（{d}）" for c, d in sorted(STALE_DIV.items()))

    HTML = f"""<!doctype html>
<html lang="__LANGTAG__" data-lang="__LANGVAL__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}｜AIA TMP2</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <div class="langsw" role="group" aria-label="切換中文顯示">
    <span class="langsw-lbl">LANG</span>
    <a class="langbtn__TR_ON__" data-lang="traditional" href="__URL_TR__">繁</a>
    <a class="langbtn__SC_ON__" data-lang="simplified" href="__URL_SC__">简</a>
  </div>
  <p class="eyebrow">AIA · TMP2 / FUND MONTHLY RANKING</p>
  <h1>{TITLE}</h1>
  <p class="backlink"><a href="./06-fund-portfolio-workbench.html" style="color:var(--red);text-decoration:none;font-size:13.5px">&larr; 返回 06 基金組合測算</a></p>
  <p class="sub">計算基準日 <b>{end_disp}</b>（每月最後一個交易日；各檔取該月最後一個有資料的交易日）。
     統一以<b>YTD／近 1／3／5 年最佳表現</b>排名：派息基金看「實際總報酬」（派息 + 淨值），非派息基金看「淨值回報」，名次可切換類別。</p>
  {month_nav_tpl(y, m, is_latest)}
</header>

<div class="tabs" role="tablist">
  <button type="button" class="tab is-on" data-tab="div" role="tab" aria-selected="true">派息基金<b>{len(ZCODES)}</b></button>
  <button type="button" class="tab" data-tab="nav" role="tab" aria-selected="false">非派息基金<b>{len(NCODES)}</b></button>
</div>

<div class="panel is-on" data-panel="div">{div_html}</div>
<div class="panel" data-panel="nav">{nav_html}</div>

<footer>
  資料來源：AIA 官方日頻 NAV 與派息紀錄（本頁為每月手動更新）。
  派息基金實際領回金額另須扣除平台遞減贖回費（第1年 7.5%、第2年 6%、第3年 4.5%、第4年 3%、第5年 1.5%、第6年起 0%）；派息不計入贖回。
  非派息基金回報以各基金自身幣別計，<b>不含匯率影響</b>；名稱後標「（對沖）」者為對沖股份類別。
  另有 3 檔非派息基金在比較窗口內曾派息（{stale}），本頁僅計淨值變動，該等派息未計入，實際總回報略高於表列。
  非派息榜前段多為單一行業或地區（黃金、台灣、韓國、科技），<b>高回報代表已漲多，並非買入建議</b>。
  YTD 榜＝去年最後一個交易日至基準日（未滿一年，不列年化回報）。
  非派息榜的數值欄<a href='#top' style='color:inherit'>（期間回報／年化回報／波動率／最大回撤／收復時間）</a>可<b>滑鼠懸停看該期間淨值走勢圖</b>（深色＝回撤期、淺色＝收復期）；<b>點基金名</b>會在 06 開啟該檔走勢圖。
  歷史資料不代表未來表現，非投資建議。
  漲跌色跟隨語言：繁體版<b>綠漲紅跌</b>、簡體版<b>紅漲綠跌</b>（由 06 的語言設定決定，本頁右上可切換）。
</footer>

</div>
<script>var __SPARK__={spark_json};</script>
<script>{SCRIPT}</script>
</body>
</html>
"""
    return HTML, end_disp


try:
    from opencc import OpenCC
    _T2S = OpenCC("t2s").convert
except Exception as e:                                    # opencc 不可用時只產繁體版
    print("⚠️ opencc 不可用（%s），本次只產繁體版" % e)
    _T2S = None

for i, (y, m) in enumerate(MONTHS):
    is_latest = (i == 0)
    base, end_disp = build_page(y, m, is_latest)
    variants = [("tr", base)]
    if _T2S:
        variants.append(("sc", _T2S(base)))
    written = []
    for lang, doc in variants:
        out = localize(doc, y, m, lang)
        fn = fname_for(y, m, lang)
        open(os.path.join(DEPLOY, fn), "w", encoding="utf-8", newline="").write(out)
        written.append(f"{fn}（{len(out)} bytes）")
    print(f"{y}-{m:02d}　基準 {end_disp}：" + "、".join(written))
    for p_ in PERIODS:
        _, pm = rank_map(ZCODES, p_, month_end(y, m), div_perf)
        if pm:
            c, r = max(pm.items(), key=lambda x: x[1]["total"])
            print(f"   派息 {plabel(p_)}：{len(pm)} 檔，冠軍 {c} {r['total']:+.1f}%")
        _, pn = rank_map(NCODES, p_, month_end(y, m), nav_perf)
        if pn:
            c, r = max(pn.items(), key=lambda x: x[1]["total"])
            print(f"   非派息 {plabel(p_)}：{len(pn)} 檔，冠軍 {c} {r['total']:+.1f}%")
