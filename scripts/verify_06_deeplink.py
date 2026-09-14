#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證 06 deep link：?fund=CODE&y=1|3|5 → 自動加入基金、切到對應走勢圖期間、捲到情景估算"""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
BASE = "file:///" + os.path.join(D, "06-fund-portfolio-workbench.html").replace("\\", "/")

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    def state():
        return pg.evaluate("""() => {
            const act = Array.prototype.slice.call(document.querySelectorAll('button'))
                .filter(b => b.classList.contains('active'))
                .map(b => (b.innerText || '').trim());
            const rs = Array.prototype.slice.call(document.querySelectorAll('input[type=range]'));
            const s0 = rs.filter(e => (e.getAttribute('aria-label') || '').indexOf('起點') > -1)[0];
            const e0 = rs.filter(e => (e.getAttribute('aria-label') || '').indexOf('終點') > -1)[0];
            const charts = Array.from(document.querySelectorAll('svg'))
                .filter(e => { const r = e.getBoundingClientRect(); return r.width > 400 && r.height > 150; }).length;
            return {期間鈕: ['3個月','6個月','YTD','1年','3年','5年'].filter(t => act.includes(t)),
                    跨度年: (s0 && e0) ? (+e0.value - +s0.value) / 31557600000 : null,
                    捲動量: Math.round(window.scrollY), 走勢圖: charts,
                    網址: location.search || '(已清空)'};
        }""")

    # 期間：1／3／5 有按鈕（按鈕要亮）；10 無按鈕 → 用下方區間滑桿（跨度需約 10 年）；YTD 用按鈕
    for code, y, label, want_btn, want_years in (
            ("H01", "10", "10年", None, 10), ("Z01", "5", "5年", "5年", 5),
            ("Z01", "3", "3年", "3年", 3), ("J08", "1", "1年", "1年", 1),
            ("J08", "YTD", "YTD", "YTD", 0.69)):
        pg.goto(BASE + "?fund=" + code + "&y=" + y, wait_until="domcontentloaded")
        pg.wait_for_timeout(9500)
        s = state()
        in_pf = pg.evaluate("""(c) => Array.from(document.querySelectorAll('*'))
            .some(e => e.children.length === 0 && (e.innerText || '').trim() === c)""", code)
        btn_ok = (s["期間鈕"] == [want_btn]) if want_btn else (s["期間鈕"] == ["3個月"])
        span_ok = s["跨度年"] is not None and abs(s["跨度年"] - want_years) < 0.15
        print(f"?fund={code}&y={y} → 期間鈕 {s['期間鈕']}（按鈕判斷 {btn_ok}）｜滑桿跨度 {s['跨度年']:.2f} 年"
              f"（應 {want_years}，{span_ok}）｜加入 {in_pf}｜捲動 {s['捲動量']}｜{s['網址']}")
        ok &= in_pf and btn_ok and span_ok and s["捲動量"] > 100 and s["走勢圖"] >= 1 and s["網址"] == "(已清空)"

    # 無參數：不應有任何動作
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    s = state()
    print("無參數 →", s)
    ok &= s["捲動量"] == 0 and s["走勢圖"] == 0

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
