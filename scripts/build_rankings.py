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
TOP_DIV = {1: 10, 3: 10, 5: 5}        # 派息榜名額
TOP_NAV = {1: 10, 3: 10, 5: 10}       # 非派息榜名額
PERIODS = (1, 3, 5)
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


def window(code, years, anchor):
    """回傳 (期初NAV, 期末NAV, 期末日, 區間點列) 或 None"""
    nav = nav_of(code)
    if not nav:
        return None
    ie = bisect.bisect_right([d for d, _ in nav], anchor) - 1
    if ie < 0:
        return None
    end_date, navh = nav[ie]
    start = end_date - datetime.timedelta(days=int(365.25 * years))
    i0 = bisect.bisect_left([d for d, _ in nav], start)
    if i0 >= len(nav) or not (0 <= (nav[i0][0] - start).days <= 31):
        return None
    nav0 = nav[i0][1]
    if nav0 <= 0:
        return None
    return nav0, navh, end_date, nav[i0:ie + 1]


def div_perf(code, years, anchor):
    w = window(code, years, anchor)
    if not w:
        return None
    nav0, navh, end_date, _ = w
    ds = dist_of(code)
    if not ds or ds[0][0] > end_date - datetime.timedelta(days=int(365.25 * years)) + datetime.timedelta(days=40):
        return None
    start = end_date - datetime.timedelta(days=int(365.25 * years))
    cum = sum(a for rd, a in ds if start < rd <= end_date)
    dp = cum / nav0 * 100
    np_ = (navh - nav0) / nav0 * 100
    total = dp + np_
    return {"total": total, "ann": ((1 + total / 100) ** (1 / years) - 1) * 100,
            "div": dp, "nav": np_, "vol": None, "mdd": None, "end": end_date}


def nav_perf(code, years, anchor):
    w = window(code, years, anchor)
    if not w:
        return None
    nav0, navh, end_date, pts = w
    if len(pts) < 20:
        return None
    total = (navh - nav0) / nav0 * 100
    rets = [pts[i][1] / pts[i - 1][1] - 1 for i in range(1, len(pts)) if pts[i - 1][1] > 0]
    vol = st.pstdev(rets) * (252 ** 0.5) * 100 if len(rets) > 2 else None
    peak, mdd = pts[0][1], 0.0
    for _, v in pts:
        peak = max(peak, v)
        mdd = min(mdd, (v - peak) / peak * 100)
    return {"total": total, "ann": ((1 + total / 100) ** (1 / years) - 1) * 100,
            "vol": vol, "mdd": mdd, "end": end_date}


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
    head = f"<th>名次</th><th>代號</th><th>基金名</th><th>紀錄日</th>{TH}"
    for yrs in PERIODS:
        ranks, pm = rank_map(ZCODES, yrs, anchor, div_perf)
        prev = rank_map(ZCODES, yrs, prev_anchor, div_perf)[0] if is_latest else {}
        rows = sorted(pm.items(), key=lambda x: -x[1]["total"])[:TOP_DIV[yrs]]
        ends += [r["end"] for _, r in rows]
        out = []
        for i, (c, r) in enumerate(rows, 1):
            ds = dist_of(c)
            b = bucket(ds[-1][0]) if ds else ""
            rate = refs.get(c, {}).get("annualizedDistributionRate") or 0
            pr = prev.get(c, "NA") if is_latest else None
            out.append(
                f"<tr>{rank_cell(i, pr)}<td class='code'>{c}</td>"
                f"<td class='fname'>{html.escape((meta[c].get('name') or '').strip())}</td><td>{b}</td>"
                f"<td class='num'>{rate:.2f}%</td>"
                f"<td class='num {cls(r['total'])}'>{pct(r['total'])}</td>"
                f"<td class='num {cls(r['ann'])}'>{pct(r['ann'])}</td>"
                f"<td class='num'>{pct(r['div'])}</td>"
                f"<td class='num {cls(r['nav'])}'>{pct(r['nav'])}</td></tr>")
        note = f"共 {len(pm)} 檔資料完整，取前 {len(rows)} 名"
        if yrs == 5:
            note += "；5 年區間含 2022 年股債雙殺，數字普遍偏低，屬區間效應"
        note += arrow_note(is_latest, m)
        blocks.append(table((f"{yrs} 年期", f"近 {yrs} 年實際總報酬排名"), head, out, note))
    return ''.join(blocks), ends


def arrow_note(is_latest, m, extra=""):
    if not is_latest:
        return f"；本頁為 {m} 月快照，不做前期比較"
    return ("；名次箭頭為與上月同口徑比較，<span class='mv up'>↑紅＝上升</span>、"
            "<span class='mv down'>↓綠＝下降</span>、<span class='mv flat'>—＝持平</span>、"
            "<span class='mv flat'>新＝上月無同口徑資料</span>" + extra)


def build_nav_panel(y, m, is_latest, anchor, prev_anchor):
    """非派息榜：5 個類別 chips × 3 個期間"""
    head = ("<th>名次</th><th>代號</th><th>基金名</th><th>幣種</th><th>類別</th>"
            + th("期間回報", "r1") + th("年化回報", "ann") + th("波動率", "vol") + th("最大回撤", "mdd"))
    counts, catblocks, ends = {}, [], []
    for key, label in CATS:
        codes = NCODES if key == "all" else [c for c in NCODES if CAT_OF.get(c) == key]
        if not codes:
            continue
        pcodes = codes
        inner = []
        n_ok = 0
        for yrs in PERIODS:
            ranks, pm = rank_map(pcodes, yrs, anchor, nav_perf)
            n_ok = max(n_ok, len(pm))
            prev = rank_map(pcodes, yrs, prev_anchor, nav_perf)[0] if is_latest else {}
            rows = sorted(pm.items(), key=lambda x: -x[1]["total"])[:TOP_NAV[yrs]]
            ends += [r["end"] for _, r in rows]
            out = []
            for i, (c, r) in enumerate(rows, 1):
                f = meta[c]
                pr = prev.get(c, "NA") if is_latest else None
                catlabel = dict(CATS).get(CAT_OF.get(c), "其他")
                hedged = "（對沖）" if f.get("hedged") else ""
                out.append(
                    f"<tr>{rank_cell(i, pr)}<td class='code'>{c}</td>"
                    f"<td class='fname'>{html.escape((f.get('name') or '').strip())}"
                    f"<span class='tag'>{hedged}</span></td>"
                    f"<td>{f.get('currencyCode') or '—'}</td><td>{catlabel}</td>"
                    f"<td class='num {cls(r['total'])}'>{pct(r['total'])}</td>"
                    f"<td class='num {cls(r['ann'])}'>{pct(r['ann'])}</td>"
                    f"<td class='num'>{r['vol']:.1f}%</td>"
                    f"<td class='num {cls(r['mdd'])}'>{r['mdd']:.1f}%</td></tr>")
            note = f"共 {len(pm)} 檔資料完整，取前 {len(rows)} 名"
            note += arrow_note(is_latest, m)
            inner.append(table((f"{yrs} 年期", f"近 {yrs} 年淨值回報排名"), head, out, note))
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


def month_nav(y, m, is_latest):
    opts = []
    for (yy, mm) in MONTHS:
        sel = " selected" if (yy, mm) == (y, m) else ""
        opts.append(f"<option value='./fund-ranking-{yy}-{mm:02d}.html'{sel}>{yy}-{mm:02d}</option>")
    idx = MONTHS.index((y, m))
    if idx + 1 < len(MONTHS):
        oy, om = MONTHS[idx + 1]
        prev_html = f"<a class='mnav' href='./fund-ranking-{oy}-{om:02d}.html'>&lsaquo; 前一月</a>"
    else:
        prev_html = "<span class='mnav off'>&lsaquo; 前一月</span>"
    next_html = ("<span class='mnav off'>最新月份 &rsaquo;</span>" if is_latest
                 else "<a class='mnav' href='./fund-ranking.html'>最新月份 &rsaquo;</a>")
    return (f"<nav class='monthnav' aria-label='月份切換'>{prev_html}"
            f"<label class='mnav mnav-sel'><span>月份</span>"
            f"<select aria-label='選擇月份' onchange=\"if(this.value) location.href=this.value\">"
            f"{''.join(opts)}</select></label>{next_html}</nav>")


STYLE = """
  :root{
    --page:#f4efe5; --surface:#fffdf8; --surface-2:#fffaf2; --surface-3:#f9f2e7;
    --head:#f0e8dc; --gold:#c8a85b; --gold-soft:#d9c7a9;
    --line:#e1d6c4; --line-2:#eee3d4; --line-3:#d8c8b3;
    --ink:#342d28; --ink-2:#5e5145; --th-ink:#49372f;
    --red:#8f0d25; --gray:#8c7d70;
    --gain:#b13446; --loss:#347558;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--page);color:var(--ink);
    background-image:linear-gradient(90deg,#20212407 1px,#0000 1px),linear-gradient(#20212405 1px,#0000 1px);
    background-size:32px 32px;
    font-family:"Noto Sans TC",ui-sans-serif,system-ui,"Segoe UI",sans-serif;
    font-size:16px;line-height:1.8;-webkit-font-smoothing:antialiased;min-width:320px}
  .wrap{max-width:1200px;margin:0 auto;padding:38px 26px 74px}
  header.masthead{border-bottom:2px solid var(--red);padding-bottom:18px;margin-bottom:20px}
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
  table{border-collapse:collapse;width:100%;font-size:14.5px;min-width:960px}
  th,td{border-bottom:1px solid var(--line-2);padding:11px 12px;text-align:right;white-space:nowrap;line-height:1.4}
  th{color:var(--th-ink);background:var(--head);border-bottom:1px solid var(--line-3);font-weight:700;font-size:13px}
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
  .pos{color:var(--gain);font-weight:700}
  .neg{color:var(--loss);font-weight:700}
  .mv.up{color:var(--gain)}
  .mv.down{color:var(--loss)}
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
  @media (max-width:700px){
    .tip-pop{left:auto;right:0;transform:translateY(-4px)}
    .tip:hover .tip-pop,.tip:focus-within .tip-pop,.tip.is-open .tip-pop{transform:translateY(0)}
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
  Array.prototype.forEach.call(document.querySelectorAll('.tab'), function(b){
    b.addEventListener('click', function(){
      var name = b.getAttribute('data-tab');
      showTab(name);
      if (history.replaceState) history.replaceState(null, '', '?tab=' + name);
    });
  });
  Array.prototype.forEach.call(document.querySelectorAll('.cat'), function(b){
    b.addEventListener('click', function(){
      var k = b.getAttribute('data-cat');
      Array.prototype.forEach.call(document.querySelectorAll('.cat'), function(x){
        x.classList.toggle('is-on', x === b);
      });
      Array.prototype.forEach.call(document.querySelectorAll('.catblock'), function(x){
        x.classList.toggle('is-on', x.getAttribute('data-cat') === k);
      });
    });
  });
  var m = /[?&]tab=(div|nav)/.exec(location.search);
  showTab(m ? m[1] : 'div');
})();
"""


def build_page(y, m, is_latest):
    anchor = month_end(y, m)
    py, pm = prev_month(y, m)
    prev_anchor = month_end(py, pm) if is_latest else None

    div_html, div_ends = build_div_panel(y, m, is_latest, anchor, prev_anchor)
    nav_html, nav_ends = build_nav_panel(y, m, is_latest, anchor, prev_anchor)
    end_disp = max(div_ends + nav_ends).strftime("%Y-%m-%d")

    n_ok_nav = sum(1 for c in NCODES if nav_perf(c, 1, anchor))
    TITLE = f"基金月榜 - {m}月"
    stale = "、".join(f"{c}（{d}）" for c, d in sorted(STALE_DIV.items()))

    HTML = f"""<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}｜AIA TMP2</title>
<style>{STYLE}</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <p class="eyebrow">AIA · TMP2 / FUND MONTHLY RANKING</p>
  <h1>{TITLE}</h1>
  <p class="backlink"><a href="./06-fund-portfolio-workbench.html" style="color:var(--red);text-decoration:none;font-size:13.5px">&larr; 返回 06 基金組合測算</a></p>
  <p class="sub">計算基準日 <b>{end_disp}</b>（每月最後一個交易日；各檔取該月最後一個有資料的交易日）。
     派息基金以「實際總報酬」（派息 + 淨值）排序；非派息基金以「淨值回報」排序，名次可切換類別。</p>
  {month_nav(y, m, is_latest)}
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
  歷史資料不代表未來表現，非投資建議。
</footer>

</div>
<script>{SCRIPT}</script>
</body>
</html>
"""
    return HTML, f"fund-ranking-{y}-{m:02d}.html", end_disp, len(ZCODES), n_ok_nav


for i, (y, m) in enumerate(MONTHS):
    is_latest = (i == 0)
    HTML, fname_month, end_disp, nz, nnz = build_page(y, m, is_latest)
    paths = [os.path.join(DEPLOY, fname_month)]
    if is_latest:
        paths.append(os.path.join(DEPLOY, "fund-ranking.html"))
    for p in paths:
        open(p, "w", encoding="utf-8", newline="").write(HTML)
    print(f"{y}-{m:02d}：{fname_month}{' ＋ fund-ranking.html' if is_latest else ''}"
          f"　基準 {end_disp}　{len(HTML)} bytes")
    for yrs in PERIODS:
        _, pm = rank_map(ZCODES, yrs, month_end(y, m), div_perf)
        if pm:
            c, r = max(pm.items(), key=lambda x: x[1]["total"])
            print(f"   派息 {yrs}Y：{len(pm)} 檔，冠軍 {c} {r['total']:+.1f}%")
        _, pn = rank_map(NCODES, yrs, month_end(y, m), nav_perf)
        if pn:
            c, r = max(pn.items(), key=lambda x: x[1]["total"])
            print(f"   非派息 {yrs}Y：{len(pn)} 檔，冠軍 {c} {r['total']:+.1f}%")
