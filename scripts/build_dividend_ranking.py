#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生「派息基金每月排名」頁面。

計算基準：每月最後一個交易日（每檔取該月最後一個有資料的交易日）
  實際總報酬 = 派息貢獻 + NAV 貢獻
  派息貢獻   = 期間累計每單位派息 / 期初 NAV
  NAV 貢獻   = (期末 NAV - 期初 NAV) / 期初 NAV
  年化回報   = (1 + 總報酬)^(1/年數) - 1

產出：_deploy-workspace/dividend-ranking.html
"""
import re, os, json, datetime, bisect, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "_deploy-workspace")
DATA = os.path.join(DEPLOY, "data")
OUT = os.path.join(DEPLOY, "dividend-ranking.html")

ANCHOR_YM = (2026, 8)          # 基準月份（每月最後交易日）
TOP = {1: 10, 3: 10, 5: 5}


def load(p):
    s = open(p, encoding="utf-8").read()
    m = re.search(r'__FUND_DATA__\["[^"]+"\]\s*=\s*(\{.*\})\s*;?\s*$', s, re.S)
    return json.loads(m.group(1) if m else s[s.find("{"):])

def nav_of(c):
    o = load(os.path.join(DATA, "nav", c + ".js"))
    return sorted((datetime.datetime.fromtimestamp(p[0] / 1000, datetime.UTC).date(), float(p[1]))
                  for p in (o.get("points") or []))
def dist_of(c):
    o = load(os.path.join(DATA, "distributions", c + ".js"))
    return sorted((datetime.date.fromisoformat(r["recordDate"]), float(r.get("amountPerUnit") or 0))
                  for r in o.get("records", []) if r.get("recordDate"))
def bucket(d): return "月初" if d.day <= 10 else ("月中" if d.day <= 20 else "月底")

cat = load(os.path.join(DATA, "catalog.js"))["funds"]
refs = load(os.path.join(DATA, "distribution-references.js"))
names = {f["code"]: (f.get("name") or "").strip() for f in cat}
zcodes = [f["code"] for f in cat if f.get("isDistributionFund")]

# 基準日：該月最後一天（每檔各自取 <= 基準日的最後一個交易日）
anchor_last = (datetime.date(ANCHOR_YM[0], ANCHOR_YM[1] + 1, 1) - datetime.timedelta(days=1))

def perf(code, years):
    nav, ds = nav_of(code), dist_of(code)
    if not nav or not ds: return None
    ie = bisect.bisect_right([d for d, _ in nav], anchor_last) - 1
    if ie < 0: return None
    end_date, navh = nav[ie]
    start = end_date - datetime.timedelta(days=int(365.25 * years))
    if ds[0][0] > start + datetime.timedelta(days=40): return None
    i0 = bisect.bisect_left([d for d, _ in nav], start)
    if i0 >= len(nav) or nav[i0][0] > start + datetime.timedelta(days=25): return None
    nav0 = nav[i0][1]
    cum = sum(a for rd, a in ds if start < rd <= end_date)
    div_part = cum / nav0 * 100
    nav_part = (navh - nav0) / nav0 * 100
    total = div_part + nav_part
    ann = ((1 + total / 100) ** (1 / years) - 1) * 100
    return {"total": total, "ann": ann, "div": div_part, "nav": nav_part, "end": end_date}


tables = {}
for y in (1, 3, 5):
    rows = []
    for c in zcodes:
        p = perf(c, y)
        if not p: continue
        ds = dist_of(c)
        rows.append({"code": c, "name": names.get(c, ""), "b": bucket(ds[-1][0]) if ds else "",
                     "rate": refs.get(c, {}).get("annualizedDistributionRate") or 0, **p})
    rows.sort(key=lambda x: -x["total"])
    tables[y] = rows

# ---------- 產生 HTML ----------
def cls(v): return "pos" if v >= 0 else "neg"
def pct(v, sign=True): return f"{v:+.1f}%" if sign else f"{v:.1f}%"

blocks = []
for y in (1, 3, 5):
    rows = tables[y][:TOP[y]]
    tr = []
    for i, r in enumerate(rows, 1):
        tr.append(
            f"<tr><td>{i}</td><td class='code'>{html.escape(r['code'])}</td>"
            f"<td class='fname'>{html.escape(r['name'])}</td><td>{r['b']}</td>"
            f"<td class='num'>{r['rate']:.2f}%</td>"
            f"<td class='num {cls(r['total'])}'>{pct(r['total'])}</td>"
            f"<td class='num {cls(r['ann'])}'>{pct(r['ann'])}</td>"
            f"<td class='num'>{pct(r['div'])}</td>"
            f"<td class='num {cls(r['nav'])}'>{pct(r['nav'])}</td></tr>")
    note = f"共 {len(tables[y])} 檔資料完整，取前 {len(rows)} 名"
    if y == 5:
        note += "；5 年區間含 2022 年股債雙殺，數字普遍偏低，屬區間效應"
    blocks.append(f"""
<section class="card">
  <h2><span class="num">{y} 年期</span>近 {y} 年實際總報酬排名</h2>
  <div class="tw">
    <table>
      <thead><tr><th>名次</th><th>代號</th><th>基金名</th><th>時段</th><th>年化派息率</th>
        <th>實際總報酬</th><th>年化回報</th><th>派息貢獻</th><th>NAV 貢獻</th></tr></thead>
      <tbody>{''.join(tr)}</tbody>
    </table>
  </div>
  <p class="note">{note}。</p>
</section>""")

end_disp = max(tables[1][0]["end"], tables[3][0]["end"], tables[5][0]["end"]).strftime("%Y-%m-%d")

HTML = f"""<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>派息基金每月排名｜AIA TMP2</title>
<style>
  :root{{
    --page:#f4efe5; --surface:#fffdf8; --surface-2:#fffaf2; --surface-3:#f9f2e7;
    --head:#f0e8dc; --gold:#c8a85b; --gold-soft:#d9c7a9;
    --line:#e1d6c4; --line-2:#eee3d4; --line-3:#d8c8b3;
    --ink:#342d28; --ink-2:#5e5145; --th-ink:#49372f;
    --red:#8f0d25; --red-2:#7e293e; --gray:#8c7d70;
    --gain:#b13446; --loss:#347558;
  }}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--page);color:var(--ink);
    background-image:linear-gradient(90deg,#20212407 1px,#0000 1px),linear-gradient(#20212405 1px,#0000 1px);
    background-size:32px 32px;
    font-family:"Noto Sans TC",ui-sans-serif,system-ui,"Segoe UI",sans-serif;
    font-size:14px;line-height:1.8;-webkit-font-smoothing:antialiased;min-width:320px}}
  .wrap{{max-width:1080px;margin:0 auto;padding:34px 22px 70px}}
  header.masthead{{border-bottom:2px solid var(--red);padding-bottom:16px;margin-bottom:22px}}
  .eyebrow{{color:var(--gray);font-size:10px;font-weight:800;letter-spacing:.16em;margin:0 0 8px}}
  h1{{font-family:Georgia,"Noto Serif TC",serif;font-size:27px;font-weight:500;margin:0;color:var(--ink);line-height:1.35}}
  .sub{{color:var(--ink-2);font-size:12.5px;margin:10px 0 0;line-height:1.8}}
  section.card{{background:#fffdf8e6;border:1px solid var(--line);box-shadow:0 13px 28px #422f2012;padding:22px;margin:20px 0}}
  h2{{font-family:Georgia,"Noto Serif TC",serif;font-size:19px;font-weight:500;color:var(--red);margin:0 0 14px}}
  h2 .num{{color:var(--gray);font-size:10px;font-weight:800;letter-spacing:.14em;display:block;margin-bottom:6px}}
  .tw{{background:var(--surface);border:1px solid #decfb8;box-shadow:inset 0 2px var(--gold);overflow-x:auto;margin:12px 0}}
  table{{border-collapse:collapse;width:100%;font-size:12.5px;min-width:820px}}
  th,td{{border-bottom:1px solid var(--line-2);padding:9px 10px;text-align:right;white-space:nowrap;line-height:1.4}}
  th{{color:var(--th-ink);background:var(--head);border-bottom:1px solid var(--line-3);font-weight:700;font-size:11.5px}}
  th:nth-child(-n+4),td:nth-child(-n+4){{text-align:left}}
  td.fname{{white-space:normal;min-width:230px;font-size:11.5px;color:var(--ink-2);line-height:1.5}}
  td.code{{font-family:Georgia,serif;font-weight:700;color:var(--ink)}}
  tbody tr:nth-child(odd){{background:var(--surface-2)}}
  tbody tr:nth-child(2n){{background:var(--surface-3)}}
  tbody tr:hover{{background:#fcf5e9}}
  .num{{font-family:Georgia,serif;font-variant-numeric:tabular-nums lining-nums}}
  .pos{{color:var(--gain);font-weight:700}}
  .neg{{color:var(--loss);font-weight:700}}
  .note{{color:var(--gray);font-size:11.5px;margin:8px 0 0}}
  .backlink{{margin:8px 0 0;font-size:12px}}
  .defs{{background:var(--surface-3);border-top:2px solid var(--gold);padding:14px 16px;margin:0 0 20px;font-size:12.5px;line-height:1.9}}
  .defs>b{{color:var(--red);font-size:10px;font-weight:800;letter-spacing:.1em;display:block;margin-bottom:8px}}
  .defs dd b{{color:var(--red-2);font-weight:700}}
  .defs dl{{margin:0;display:grid;grid-template-columns:auto 1fr;gap:4px 14px}}
  .defs dt{{color:var(--th-ink);font-weight:700;white-space:nowrap}}
  .defs dd{{margin:0;color:var(--ink-2)}}
  footer{{margin-top:26px;color:var(--gray);font-size:11px;line-height:1.8}}
</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <p class="eyebrow">AIA · TMP2 / DISTRIBUTION FUND MONTHLY RANKING</p>
  <h1>派息基金每月排名</h1>
  <p class="backlink"><a href="./06-fund-portfolio-workbench.html" style="color:var(--red);text-decoration:none;font-size:12px">&larr; 返回 06 基金組合測算</a></p>
  <p class="sub">計算基準日 <b>{end_disp}</b>（每月最後一個交易日；各檔取該月最後一個有資料的交易日）。
     實際總報酬 = 派息貢獻 + NAV 貢獻，依實際總報酬排序；資料不足的期間不列入。</p>
</header>

<div class="defs">
  <b>欄位說明</b>
  <dl>
    <dt>年化派息率</dt><dd>依最近一次派息推算的未來一年配息率（<b>預估</b>）</dd>
    <dt>實際總報酬</dt><dd>該期間「領到的息 + 淨值漲跌」合計（<b>實際</b>）</dd>
    <dt>年化回報</dt><dd>實際總報酬折算為每年複利（<b>實際</b>）</dd>
    <dt>派息貢獻</dt><dd>期間累計派息 ÷ 期初淨值（<b>實際領到多少</b>）</dd>
    <dt>NAV 貢獻</dt><dd>淨值漲跌</dd>
  </dl>
</div>
{''.join(blocks)}
<footer>
  資料來源：AIA 官方日頻 NAV 與派息紀錄（本頁為每月手動更新）。
  實際領回金額另須扣除平台遞減贖回費（第1年 7.5%、第2年 6%、第3年 4.5%、第4年 3%、第5年 1.5%、第6年起 0%）；派息不計入贖回。
  歷史資料不代表未來表現，非投資建議。
</footer>

</div>
</body>
</html>
"""

open(OUT, "w", encoding="utf-8", newline="").write(HTML)
print("已產生", OUT, len(HTML), "bytes")
for y in (1, 3, 5):
    print(f"  {y}Y：{len(tables[y])} 檔完整，取前 {min(TOP[y], len(tables[y]))} 名　冠軍 "
          f"{tables[y][0]['code']} {tables[y][0]['total']:+.1f}%")
