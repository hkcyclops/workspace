#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
產生 06 年度回報資料檔：data/annual-returns.js
每個基金、每一年存兩個數字：
  [0] 年度回報%  = 上一年最後一個交易日 → 該年最後一個交易日（派息基金含派息＝實際總報酬）
  [1] 定投比率   = 該年每月月初定投，年底價值 ÷ 總投入（例如 1.111 代表 +11.1%）
年份預設取「基準年 - 1」往回 5 年（2026 → 2021~2025）。
用法：python build_annual_returns.py [--years 5]
"""
import re, os, sys, glob, json, datetime, bisect

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 雙佈局自適應：
#   本地：<workspace>/calculator-hub/scripts/ → 資料在 <workspace>/calculator-hub/_deploy-workspace/data
#   Actions：repo 根就是 deploy workspace → 資料在 <repo>/data
#   （2026-09-14 加入本步驟時只寫了本地佈局，導致 Actions 連續 3 天 FileNotFoundError、
#     後面的 Commit 步驟被跳過、線上資料自 9/13 起停止更新）
_WS = os.path.join(HERE, "_deploy-workspace")
ROOT = _WS if os.path.isdir(_WS) else HERE
D = os.path.join(ROOT, "data")
OUT = os.path.join(D, "annual-returns.js")
START_YEAR = 2021            # 固定起點（2021 起；之後每年自動追加，不會丟掉舊年份）
FALLBACK_ANCHOR = datetime.date(2026, 9, 10)


def load(p):
    s = open(p, encoding="utf-8").read()
    m = re.search(r'__FUND_DATA__\["[^"]+"\]\s*=\s*(\{.*\})\s*;?\s*$', s, re.S)
    return json.loads(m.group(1) if m else s[s.find("{"):])


def nav(c):
    p = os.path.join(D, "nav", c + ".js")
    if not os.path.exists(p):
        return []
    o = load(p)
    return sorted((datetime.datetime.fromtimestamp(x[0] / 1000, datetime.UTC).date(), float(x[1]))
                  for x in (o.get("points") or []))


def dist(c):
    p = os.path.join(D, "distributions", c + ".js")
    if not os.path.exists(p):
        return []
    o = load(p)
    return sorted((datetime.date.fromisoformat(r["recordDate"]), float(r.get("amountPerUnit") or 0))
                  for r in o.get("records", []) if r.get("recordDate"))


def annual_total(c, year, n, ds):
    """年度回報（含派息）；資料不足回 None"""
    if not n:
        return None
    dates = [d for d, _ in n]
    base_d, end_d = datetime.date(year - 1, 12, 31), datetime.date(year, 12, 31)
    ib = bisect.bisect_right(dates, base_d) - 1
    ie = bisect.bisect_right(dates, end_d) - 1
    if ib < 0 or ie <= ib:
        return None
    if (base_d - n[ib][0]).days > 45 or (end_d - n[ie][0]).days > 31:
        return None
    v0, v1 = n[ib][1], n[ie][1]
    if v0 <= 0:
        return None
    cum = sum(a for d, a in ds if base_d < d <= end_d)
    return (v1 - v0 + cum) / v0 * 100


def dca_ratio(c, year, n):
    """每月月初定投、年底價值 ÷ 總投入（資料不足回 None）"""
    if not n:
        return None
    dates = [d for d, _ in n]
    base_d, end_d = datetime.date(year - 1, 12, 31), datetime.date(year, 12, 31)
    ib = bisect.bisect_right(dates, base_d) - 1
    ie = bisect.bisect_right(dates, end_d) - 1
    if ib < 0 or ie <= ib:
        return None
    buys = []
    for mth in range(1, 13):
        i = bisect.bisect_left(dates, datetime.date(year, mth, 1))
        if ib < i <= ie:
            buys.append(i)
    if not buys:
        return None
    end_v = sum(n[ie][1] / n[i][1] for i in buys)
    return end_v / len(buys)


def latest_nav_date():
    """從 data/nav/*.js 取最新 NAV 日期當基準（取不到就用 FALLBACK_ANCHOR）"""
    best = None
    for f in glob.glob(os.path.join(D, "nav", "*.js")):
        try:
            o = load(f)
        except Exception:
            continue
        pts = o.get("points") or []
        if not pts:
            continue
        d = datetime.datetime.fromtimestamp(pts[-1][0] / 1000, datetime.UTC).date()
        if best is None or d > best:
            best = d
    return best or FALLBACK_ANCHOR


def main():
    anchor = latest_nav_date()
    years = list(range(START_YEAR, anchor.year))     # 只算「已完結」的日曆年
    cat = load(os.path.join(D, "catalog.js"))
    codes = [f["code"] for f in cat["funds"]]
    out, miss = {}, 0
    for c in codes:
        n, ds = nav(c), dist(c)
        row = {}
        for y in years:
            r1 = annual_total(c, y, n, ds)
            r2 = dca_ratio(c, y, n)
            if r1 is None and r2 is None:
                miss += 1
                continue
            row[str(y)] = [round(r1, 2) if r1 is not None else None,
                           round(r2, 4) if r2 is not None else None]
        if row:
            out[c] = row
    payload = {"meta": {"years": years, "anchor": anchor.isoformat(),
                        "source": "AIA 官方日頻 NAV + 派息紀錄"},
               "funds": out}
    js = "window.__ANNUAL__=" + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";\n"
    open(OUT, "w", encoding="utf-8", newline="").write(js)
    print(f"基準 {anchor}｜年份 {years[0]}~{years[-1]}")
    print(f"已寫入 {os.path.relpath(OUT, ROOT)}：{len(out)} 檔 × {len(years)} 年"
          f"（{len(js.encode())/1024:.1f} KB，無資料格 {miss}）")
    for y in years:
        k = sum(1 for c in out if str(y) in out[c])
        print(f"  {y}：{k} 檔有年度回報")


if __name__ == "__main__":
    main()
