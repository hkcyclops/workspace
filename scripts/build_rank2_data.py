#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
月榜新版（fund-ranking-2）資料打包器：產出 data/rank2.js
一檔 JSON 驅動整個新版頁面（跨期比較表 + 明細檢視 + hover 資訊卡），
資料層完全重用 build_rankings.py（同一套口徑，確保與現版數字一致）。

結構：
window.__RANK2__ = {
  meta:{anchor, months:[...], built, note},
  cats:[["all","全部"],...],
  panels:{
    div:{label, funds:[codes...], periods:["YTD",1,3,5],
         p:{ period: {code:{t,a,dv,nv,e,b}} } },
    nav:{label, funds:[codes...], periods:["YTD",1,3,5,10],
         p:{ period: {code:{t,a,vol,mdd,rec,cur,rm,pk,tr,recD,e}} } }
  },
  funds:{ code:{n,c,cat,h,d,r} },
  cov:{ panel: { period: {cat: count} } }
}
用法：python build_rank2_data.py [--month 2026-08]
"""
import io, os, sys, json, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_rankings as B


def period_key(p):
    return "YTD" if p == "YTD" else str(p)


def build_panel(codes, periods, fn, anchor, is_div):
    by_period, cov = {}, {}
    for p in periods:
        _, pm = B.rank_map(codes, p, anchor, fn)
        k = period_key(p)
        by_period[k] = {}
        for c, r in pm.items():
            if is_div:
                by_period[k][c] = {
                    "t": round(r["total"], 2),
                    "a": round(r["ann"], 2) if r.get("ann") is not None else None,
                    "dv": round(r["div"], 2),
                    "nv": round(r["nav"], 2),
                    "e": r["end"].isoformat(),
                    "b": B.bucket(r["end"]),
                }
            else:
                by_period[k][c] = {
                    "t": round(r["total"], 2),
                    "a": round(r["ann"], 2) if r.get("ann") is not None else None,
                    "vol": round(r["vol"], 1) if r.get("vol") is not None else None,
                    "mdd": round(r["mdd"], 1) if r.get("mdd") is not None else None,
                    "rec": B.rec_txt(r),
                    "rm": r.get("rec_m"),
                    "cur": round(r["cur"], 1) if r.get("cur") is not None else None,
                    "pk": r["pk"].isoformat(), "tr": r["tr"].isoformat(),
                    "recD": r["rec"].isoformat() if r.get("rec") else None,
                    "e": r["end"].isoformat(),
                }
        cov[k] = len(pm)
    return by_period, cov


def prev_ranks(codes, periods, fn, prev_anchor, top_of, cat_of):
    """回傳 {period: {cat: {code: 名次}}}（與畫面同口徑：同類別內排名、取前 top）"""
    out = {}
    for p in periods:
        _, pm = B.rank_map(codes, p, prev_anchor, fn)
        k = period_key(p)
        out[k] = {}
        for cat, _lab in B.CATS:
            sub = [c for c in pm if cat == "all" or cat_of.get(c) == cat]
            sub.sort(key=lambda c: -pm[c]["total"])
            n = top_of[p]
            out[k][cat] = {c: i + 1 for i, c in enumerate(sub[:n])}
    return out


def pack(y, m):
    """產生該月份的資料 JS 字串（不回寫檔案）"""
    anchor = B.month_end(y, m)
    div_p, div_cov = build_panel(B.ZCODES, B.DIV_PERIODS, B.div_perf, anchor, True)
    nav_p, nav_cov = build_panel(B.NCODES, B.NAV_PERIODS, B.nav_perf, anchor, False)

    py, pm_ = B.prev_month(y, m)
    prev_anchor = B.month_end(py, pm_)
    prev = {
        "asof": prev_anchor.isoformat(),
        "div": prev_ranks(B.ZCODES, B.DIV_PERIODS, B.div_perf, prev_anchor, B.TOP_DIV, B.CAT_OF),
        "nav": prev_ranks(B.NCODES, B.NAV_PERIODS, B.nav_perf, prev_anchor, B.TOP_NAV, B.CAT_OF),
    }

    funds = {}
    for c in B.ZCODES + B.NCODES:
        f = B.meta[c]
        funds[c] = {
            "n": (f.get("name") or "").strip(),
            "c": f.get("currencyCode") or "",
            "cat": B.CAT_OF.get(c, "other"),
            "h": 1 if f.get("hedged") else 0,
            "d": 1 if f.get("isDistributionFund") else 0,
            "r": round((B.refs.get(c, {}).get("annualizedDistributionRate") or 0), 2),
            "m": int(f.get("rating") or 0),          # Morningstar 星級（0＝無評級）
        }

    # spark：先收集「各期前 N 名的聯集」（進過榜的基金），再替它們補齊「全部期間」
    # 目的：點得到任一格（該列上的任何期間）都有走勢圖；進不了榜的基金不做（只有全部類別＝100%）
    sparks = {}
    for key, codes, by_p, periods in (("div", B.ZCODES, div_p, B.DIV_PERIODS),
                                      ("nav", B.NCODES, nav_p, B.NAV_PERIODS)):
        t = B.TOP_DIV if key == "div" else B.TOP_NAV
        listed = set()
        for p in periods:
            k = period_key(p)
            rows = sorted(by_p[k].items(), key=lambda x: -x[1]["t"])[:t[p]]
            for c, _ in rows:
                listed.add(c)
        for c in sorted(listed):
            for p in periods:
                k = period_key(p)
                if c not in by_p[k]:
                    continue
                sk = f"{c}|{k}"
                if sk not in sparks:
                    sp = B.spark(c, p, anchor)
                    if sp:
                        sparks[sk] = sp

    payload = {
        "meta": {"anchor": anchor.isoformat(), "month": f"{y}-{m:02d}",
                 "months": [f"{a}-{b:02d}" for a, b in B.MONTHS],
                 "built": datetime.datetime.now().strftime("%Y-%m-%d %H:%M")},
        "cats": [[k, v] for k, v in B.CATS],
        "panels": {
            "div": {"label": "派息基金", "periods": [period_key(p) for p in B.DIV_PERIODS],
                    "top": {period_key(p): B.TOP_DIV[p] for p in B.DIV_PERIODS}, "p": div_p},
            "nav": {"label": "非派息基金", "periods": [period_key(p) for p in B.NAV_PERIODS],
                    "top": {period_key(p): B.TOP_NAV[p] for p in B.NAV_PERIODS}, "p": nav_p},
        },
        "cov": {"div": div_cov, "nav": nav_cov},
        "funds": funds,
        "prev": prev,
        "spark": sparks,
    }
    return "window.__RANK2__=" + json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + ";"


def main():
    ym = None
    if "--month" in sys.argv:
        ym = sys.argv[sys.argv.index("--month") + 1]
    y, m = (int(x) for x in ym.split("-")) if ym else B.MONTHS[0]
    js = pack(y, m)
    out = os.path.join(B.DEPLOY, "data", "rank2.js")
    io.open(out, "w", encoding="utf-8", newline="").write(js + "\n")
    d = json.loads(js.split("=", 1)[1].rstrip(";"))
    print(f"{y}-{m:02d}｜基準 {d['meta']['anchor']}｜已寫入 data/rank2.js（{len(js.encode())/1024:.0f} KB）")
    for key, label in (("div", "派息"), ("nav", "非派息")):
        cov = d["cov"][key]
        print(f"  {label}覆蓋：" + "　".join(f"{k} {v} 檔" for k, v in cov.items()))


if __name__ == "__main__":
    main()
