#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生「派息基金每月排名」頁面（多月份版本）。

計算基準：每月最後一個交易日（每檔取該月最後一個有資料的交易日）
  實際總報酬 = 派息貢獻 + NAV 貢獻
  派息貢獻   = 期間累計每單位派息 / 期初 NAV
  NAV 貢獻   = (期末 NAV - 期初 NAV) / 期初 NAV
  年化回報   = (1 + 總報酬)^(1/年數) - 1

產出：
  _deploy-workspace/dividend-ranking.html            （永遠等於最新月份）
  _deploy-workspace/dividend-ranking-YYYY-MM.html    （各月份永久存檔）
最新月份頁的名次欄另加「較上月」箭頭：↑紅（上升）／↓綠（下降）／—灰（持平）／新（上月無同口徑資料）
"""
import re, os, json, datetime, bisect, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(ROOT, "_deploy-workspace")
DATA = os.path.join(DEPLOY, "data")

MONTHS = [(2026, 8), (2026, 7)]   # 由新到舊；第一個＝最新月份
TOP = {1: 10, 3: 10, 5: 5}
PERIODS = (1, 3, 5)


def load(p):
    s = open(p, encoding="utf-8").read()
    m = re.search(r'__FUND_DATA__\["[^"]+"\]\s*=\s*(\{.*\})\s*;?\s*$', s, re.S)
    return json.loads(m.group(1) if m else s[s.find("{"):])


_nav_cache, _dist_cache = {}, {}


def nav_of(c):
    if c not in _nav_cache:
        o = load(os.path.join(DATA, "nav", c + ".js"))
        _nav_cache[c] = sorted(
            (datetime.datetime.fromtimestamp(p[0] / 1000, datetime.UTC).date(), float(p[1]))
            for p in (o.get("points") or []))
    return _nav_cache[c]


def dist_of(c):
    if c not in _dist_cache:
        o = load(os.path.join(DATA, "distributions", c + ".js"))
        _dist_cache[c] = sorted(
            (datetime.date.fromisoformat(r["recordDate"]), float(r.get("amountPerUnit") or 0))
            for r in o.get("records", []) if r.get("recordDate"))
    return _dist_cache[c]


def bucket(d):
    return "月初" if d.day <= 10 else ("月中" if d.day <= 20 else "月底")


cat = load(os.path.join(DATA, "catalog.js"))["funds"]
refs = load(os.path.join(DATA, "distribution-references.js"))
names = {f["code"]: (f.get("name") or "").strip() for f in cat}
zcodes = [f["code"] for f in cat if f.get("isDistributionFund")]


def month_end(y, m):
    """該月最後一天"""
    return datetime.date(y, 12, 31) if m == 12 else datetime.date(y, m + 1, 1) - datetime.timedelta(days=1)


def prev_month(y, m):
    return (y - 1, 12) if m == 1 else (y, m - 1)


def perf(code, years, anchor):
    nav, ds = nav_of(code), dist_of(code)
    if not nav or not ds:
        return None
    ie = bisect.bisect_right([d for d, _ in nav], anchor) - 1
    if ie < 0:
        return None
    end_date, navh = nav[ie]
    start = end_date - datetime.timedelta(days=int(365.25 * years))
    if ds[0][0] > start + datetime.timedelta(days=40):
        return None
    i0 = bisect.bisect_left([d for d, _ in nav], start)
    if i0 >= len(nav) or nav[i0][0] > start + datetime.timedelta(days=25):
        return None
    nav0 = nav[i0][1]
    cum = sum(a for rd, a in ds if start < rd <= end_date)
    div_part = cum / nav0 * 100
    nav_part = (navh - nav0) / nav0 * 100
    total = div_part + nav_part
    ann = ((1 + total / 100) ** (1 / years) - 1) * 100
    return {"total": total, "ann": ann, "div": div_part, "nav": nav_part, "end": end_date}


def ranking(years, anchor):
    """回傳 (名次對照, 指標對照)，只含資料完整者"""
    rows = []
    for c in zcodes:
        p = perf(c, years, anchor)
        if p:
            rows.append((c, p))
    rows.sort(key=lambda x: -x[1]["total"])
    return {c: i for i, (c, _) in enumerate(rows, 1)}, {c: p for c, p in rows}


# ---------- 表頭 ？ 說明 ----------
TIPS = {
    "rate": ("年化派息率", "依最近一次派息推算的未來一年配息率（<b>預估</b>）。\n公式：最近一筆派息金額 ÷ 該筆派息日配對 NAV × 12。"),
    "total": ("實際總報酬", "該期間「領到的息 + 淨值漲跌」合計（<b>實際</b>）。\n＝ 派息貢獻 + NAV 貢獻，未扣贖回費。"),
    "ann": ("年化回報", "實際總報酬折算為每年複利（<b>實際</b>）。\n＝ (1 + 總報酬)^(1 ÷ 年數) − 1，方便比較 1／3／5 年。"),
    "div": ("派息貢獻", "期間累計派息 ÷ 期初淨值（<b>實際領到多少</b>）。"),
    "nav": ("NAV 貢獻", "淨值漲跌。\n＝ (期末 NAV − 期初 NAV) ÷ 期初 NAV。"),
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


TH = (th("年化派息率", "rate") + th("實際總報酬", "total") + th("年化回報", "ann")
      + th("派息貢獻", "div") + th("NAV 貢獻", "nav"))


def cls(v):
    return "pos" if v >= 0 else "neg"


def pct(v, sign=True):
    return f"{v:+.1f}%" if sign else f"{v:.1f}%"


def rank_cell(rank, prev_rank):
    """名次欄；prev_rank=None 表示不做比較（非最新月份頁）"""
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


def build_page(y, m, is_latest):
    anchor = month_end(y, m)
    py, pm = prev_month(y, m)
    compare = is_latest                      # 只有最新月份頁做「較上月」比較
    prev_anchor = month_end(py, pm) if compare else None
    prev_label = f"{pm}月" if compare else None

    blocks = []
    ends = []
    for yrs in PERIODS:
        ranks, perfmap = ranking(yrs, anchor)
        prev_ranks = ranking(yrs, prev_anchor)[0] if compare else {}
        ordered = sorted(perfmap.items(), key=lambda x: -x[1]["total"])
        rows = ordered[:TOP[yrs]]
        ends.extend(p["end"] for _, p in rows)
        tr = []
        for i, (c, p) in enumerate(rows, 1):
            ds = dist_of(c)
            b = bucket(ds[-1][0]) if ds else ""
            rate = refs.get(c, {}).get("annualizedDistributionRate") or 0
            pr = prev_ranks.get(c, "NA") if compare else None
            tr.append(
                f"<tr>{rank_cell(i, pr)}"
                f"<td class='code'>{html.escape(c)}</td>"
                f"<td class='fname'>{html.escape(names.get(c, ''))}</td><td>{b}</td>"
                f"<td class='num'>{rate:.2f}%</td>"
                f"<td class='num {cls(p['total'])}'>{pct(p['total'])}</td>"
                f"<td class='num {cls(p['ann'])}'>{pct(p['ann'])}</td>"
                f"<td class='num'>{pct(p['div'])}</td>"
                f"<td class='num {cls(p['nav'])}'>{pct(p['nav'])}</td></tr>")
        note = f"共 {len(perfmap)} 檔資料完整，取前 {len(rows)} 名"
        if yrs == 5:
            note += "；5 年區間含 2022 年股債雙殺，數字普遍偏低，屬區間效應"
        if compare:
            note += (f"；名次箭頭為與上月（{prev_label}）同口徑比較，"
                     f"<span class='mv up'>↑紅＝上升</span>、<span class='mv down'>↓綠＝下降</span>、"
                     f"<span class='mv flat'>—＝持平</span>、<span class='mv flat'>新＝上月無同口徑資料</span>")
        else:
            note += f"；本頁為 {m} 月快照，不做前期比較"
        blocks.append(f"""
<section class="card">
  <h2><span class="num">{yrs} 年期</span>近 {yrs} 年實際總報酬排名</h2>
  <div class="tw">
    <table>
      <thead><tr><th>名次</th><th>代號</th><th>基金名</th><th>紀錄日</th>{TH}</tr></thead>
      <tbody>{''.join(tr)}</tbody>
    </table>
  </div>
  <p class="note">{note}。</p>
</section>""")

    end_disp = max(ends).strftime("%Y-%m-%d")
    TITLE = f"派息基金每月排名 - {m}月"

    # 月份導覽：‹ 前一月 / 月份下拉 / 最新月份 ›
    opts = []
    for (yy, mm) in MONTHS:
        sel = " selected" if (yy, mm) == (y, m) else ""
        opts.append(f"<option value='./dividend-ranking-{yy}-{mm:02d}.html'{sel}>{yy}-{mm:02d}</option>")
    idx = MONTHS.index((y, m))
    if idx + 1 < len(MONTHS):
        oy, om = MONTHS[idx + 1]
        prev_html = f"<a class='mnav' href='./dividend-ranking-{oy}-{om:02d}.html'>&lsaquo; 前一月</a>"
    else:
        prev_html = "<span class='mnav off'>&lsaquo; 前一月</span>"
    if is_latest:
        next_html = "<span class='mnav off'>最新月份 &rsaquo;</span>"
    else:
        next_html = "<a class='mnav' href='./dividend-ranking.html'>最新月份 &rsaquo;</a>"
    monthnav = (f"<nav class='monthnav' aria-label='月份切換'>{prev_html}"
                f"<label class='mnav mnav-sel'><span>月份</span>"
                f"<select aria-label='選擇月份' onchange=\"if(this.value) location.href=this.value\">"
                f"{''.join(opts)}</select></label>{next_html}</nav>")

    HTML = f"""<!doctype html>
<html lang="zh-HK">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{TITLE}｜AIA TMP2</title>
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
    font-size:16px;line-height:1.8;-webkit-font-smoothing:antialiased;min-width:320px}}
  .wrap{{max-width:1160px;margin:0 auto;padding:38px 26px 74px}}
  header.masthead{{border-bottom:2px solid var(--red);padding-bottom:18px;margin-bottom:20px}}
  .eyebrow{{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.16em;margin:0 0 8px}}
  h1{{font-family:Georgia,"Noto Serif TC",serif;font-size:32px;font-weight:500;margin:0;color:var(--ink);line-height:1.35}}
  .sub{{color:var(--ink-2);font-size:14px;margin:12px 0 0;line-height:1.8}}
  section.card{{background:#fffdf8e6;border:1px solid var(--line);box-shadow:0 13px 28px #422f2012;padding:26px;margin:24px 0}}
  h2{{font-family:Georgia,"Noto Serif TC",serif;font-size:22px;font-weight:500;color:var(--red);margin:0 0 16px}}
  h2 .num{{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.14em;display:block;margin-bottom:6px}}
  .tw{{background:var(--surface);border:1px solid #decfb8;box-shadow:inset 0 2px var(--gold);overflow-x:auto;margin:12px 0}}
  table{{border-collapse:collapse;width:100%;font-size:14.5px;min-width:940px}}
  th,td{{border-bottom:1px solid var(--line-2);padding:11px 12px;text-align:right;white-space:nowrap;line-height:1.4}}
  th{{color:var(--th-ink);background:var(--head);border-bottom:1px solid var(--line-3);font-weight:700;font-size:13px}}
  th:nth-child(-n+4),td:nth-child(-n+4){{text-align:left}}
  td.fname{{white-space:normal;min-width:250px;font-size:13.5px;color:var(--ink-2);line-height:1.5}}
  td.code{{font-family:Georgia,serif;font-weight:700;color:var(--ink)}}
  td.rk{{font-family:Georgia,serif;font-weight:700;color:var(--ink);white-space:nowrap}}
  td.rk .mv{{margin-left:6px;font-size:11.5px;font-weight:800}}
  tbody tr:nth-child(odd){{background:var(--surface-2)}}
  tbody tr:nth-child(2n){{background:var(--surface-3)}}
  tbody tr:hover{{background:#fcf5e9}}
  .num{{font-family:Georgia,serif;font-variant-numeric:tabular-nums lining-nums}}
  .pos{{color:var(--gain);font-weight:700}}
  .neg{{color:var(--loss);font-weight:700}}
  .mv.up{{color:var(--gain)}}
  .mv.down{{color:var(--loss)}}
  .mv.flat{{color:#a89b8c}}
  .note{{color:var(--gray);font-size:13px;margin:10px 0 0}}
  .backlink{{margin:8px 0 0;font-size:13.5px}}
  .backlink a{{font-size:13.5px}}
  .monthnav{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0 0}}
  .mnav{{border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);
    padding:7px 11px;font-size:13px;font-weight:700;text-decoration:none;
    display:inline-flex;align-items:center;gap:6px;line-height:1.4}}
  .mnav:hover{{border-color:var(--red);color:var(--red)}}
  .mnav.off{{opacity:.42;pointer-events:none}}
  .mnav-sel select{{border:0;background:transparent;color:inherit;font:inherit;font-weight:700;cursor:pointer;padding:0 2px}}
  .mnav-sel span{{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.08em}}

  /* 表頭 ？ 說明（沿用 06 .calculation-tooltip 視覺） */
  .tip{{position:relative;display:inline-flex;vertical-align:middle;margin-left:4px}}
  .tip-btn{{width:16px;height:16px;border-radius:50%;border:1px solid var(--gold);background:#fffdf8;color:#ae8a46;
    font-size:10.5px;font-weight:700;line-height:1;display:grid;place-items:center;cursor:help;padding:0}}
  .tip-btn:hover,.tip-btn:focus-visible{{background:var(--gold);border-color:var(--gold);color:#fff}}
  .tip-btn:focus-visible{{outline:2px solid #b78e42;outline-offset:2px}}
  .tip-pop{{position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%) translateY(-4px);
    z-index:60;width:max-content;max-width:min(320px,80vw);display:grid;gap:4px;text-align:left;
    background:#4b302b;color:#fffaf1;border:1px solid var(--gold-soft);
    padding:11px 13px;font-size:12.5px;line-height:1.7;font-weight:400;white-space:normal;
    box-shadow:0 8px 20px #422f2033;opacity:0;visibility:hidden;transition:opacity .16s,transform .16s,visibility .16s}}
  .tip-pop b{{color:#f1d58e;font-size:12px;font-weight:800;letter-spacing:.04em}}
  .tip:hover .tip-pop,.tip:focus-within .tip-pop,.tip.is-open .tip-pop{{opacity:1;visibility:visible;transform:translateX(-50%) translateY(0)}}
  @media (max-width:700px){{
    .tip-pop{{left:auto;right:0;transform:translateY(-4px)}}
    .tip:hover .tip-pop,.tip:focus-within .tip-pop,.tip.is-open .tip-pop{{transform:translateY(0)}}
  }}
  footer{{margin-top:28px;color:var(--gray);font-size:13px;line-height:1.8}}
</style>
</head>
<body>
<div class="wrap">

<header class="masthead">
  <p class="eyebrow">AIA · TMP2 / DISTRIBUTION FUND MONTHLY RANKING</p>
  <h1>{TITLE}</h1>
  <p class="backlink"><a href="./06-fund-portfolio-workbench.html" style="color:var(--red);text-decoration:none;font-size:13.5px">&larr; 返回 06 基金組合測算</a></p>
  <p class="sub">計算基準日 <b>{end_disp}</b>（每月最後一個交易日；各檔取該月最後一個有資料的交易日）。
     實際總報酬 = 派息貢獻 + NAV 貢獻，依實際總報酬排序；資料不足的期間不列入。</p>
  {monthnav}
</header>

{''.join(blocks)}
<footer>
  資料來源：AIA 官方日頻 NAV 與派息紀錄（本頁為每月手動更新）。
  實際領回金額另須扣除平台遞減贖回費（第1年 7.5%、第2年 6%、第3年 4.5%、第4年 3%、第5年 1.5%、第6年起 0%）；派息不計入贖回。
  歷史資料不代表未來表現，非投資建議。
</footer>

</div>

<script>
/* 表頭 ？ 說明：hover / focus 由 CSS 處理；此處補點擊切換（觸控螢幕）與 Esc、點外部關閉 */
(function(){{
  var tips = Array.prototype.slice.call(document.querySelectorAll('.tip'));
  function closeAll(except){{
    tips.forEach(function(t){{
      if (t === except) return;
      t.classList.remove('is-open');
      var b = t.querySelector('.tip-btn'); if (b) b.setAttribute('aria-expanded','false');
    }});
  }}
  tips.forEach(function(t){{
    var btn = t.querySelector('.tip-btn');
    if (!btn) return;
    btn.addEventListener('click', function(e){{
      e.preventDefault(); e.stopPropagation();
      var open = t.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      closeAll(t);
    }});
  }});
  document.addEventListener('click', function(e){{
    if (!e.target.closest || !e.target.closest('.tip')) closeAll(null);
  }});
  document.addEventListener('keydown', function(e){{ if (e.key === 'Escape') closeAll(null); }});
}})();
</script>
</body>
</html>
"""
    fname_month = f"dividend-ranking-{y}-{m:02d}.html"
    paths = [os.path.join(DEPLOY, fname_month)]
    fname_latest = None
    if is_latest:
        fname_latest = "dividend-ranking.html"
        paths.append(os.path.join(DEPLOY, fname_latest))
    for path in paths:
        open(path, "w", encoding="utf-8", newline="").write(HTML)
    return fname_month, fname_latest, len(HTML)


for i, (y, m) in enumerate(MONTHS):
    fm, fl, size = build_page(y, m, is_latest=(i == 0))
    print(f"{y}-{m:02d}：{fm}" + (f" ＋ {fl}" if fl else "") + f"　{size} bytes")
    for yrs in PERIODS:
        _, perfmap = ranking(yrs, month_end(y, m))
        top = sorted(perfmap.items(), key=lambda x: -x[1]["total"])[:1]
        if top:
            c, p = top[0]
            print(f"   {yrs}Y：{len(perfmap)} 檔完整，取前 {min(TOP[yrs], len(perfmap))} 名　冠軍 {c} {p['total']:+.1f}%")
