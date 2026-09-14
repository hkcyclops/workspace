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
            const charts = Array.from(document.querySelectorAll('svg'))
                .filter(e => { const r = e.getBoundingClientRect(); return r.width > 400 && r.height > 150; }).length;
            return {期間鈕: ['3個月','6個月','YTD','1年','3年','5年'].filter(t => act.includes(t)),
                    捲動量: Math.round(window.scrollY), 走勢圖: charts,
                    網址: location.search || '(已清空)'};
        }""")

    for code, y, label in (("J08", "YTD", "YTD"), ("J08", "1", "1年"), ("Z01", "3", "3年"), ("A05", "5", "5年")):
        pg.goto(BASE + "?fund=" + code + "&y=" + y, wait_until="domcontentloaded")
        pg.wait_for_timeout(7000)
        s = state()
        in_pf = pg.evaluate("""(c) => Array.from(document.querySelectorAll('*'))
            .some(e => e.children.length === 0 && (e.innerText || '').trim() === c)""", code)
        print(f"?fund={code}&y={y} → 加入組合:{in_pf}　期間鈕:{s['期間鈕']}（應 ['{label}']）"
              f"　捲動:{s['捲動量']}　走勢圖:{s['走勢圖']}　網址:{s['網址']}")
        ok &= in_pf and s["期間鈕"] == [label] and s["捲動量"] > 100 and s["走勢圖"] >= 1 \
            and s["網址"] == "(已清空)"

    # 不帶 y：維持預設 3個月，且仍會加入＋捲動
    pg.goto(BASE + "?fund=J08", wait_until="domcontentloaded")
    pg.wait_for_timeout(6000)
    s = state()
    print(f"?fund=J08（無 y）→ 期間鈕:{s['期間鈕']}（應 ['3個月']）　捲動:{s['捲動量']}")
    ok &= s["期間鈕"] == ["3個月"] and s["捲動量"] > 100

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
