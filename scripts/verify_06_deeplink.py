#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證 06 deep link：?fund=J08 / Z01 / A05 會自動加入並捲到走勢圖；無參數時不動"""
import os, sys
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

    for code in ["J08", "Z01", "A05"]:
        pg.goto(BASE + "?fund=" + code, wait_until="domcontentloaded")
        pg.wait_for_timeout(6500)
        r = pg.evaluate("""(code) => {
            const inPortfolio = Array.from(document.querySelectorAll('*'))
              .some(e => e.children.length === 0 && (e.innerText || '').trim() === code);
            const charts = Array.from(document.querySelectorAll('svg'))
              .filter(e => { const b = e.getBoundingClientRect(); return b.width > 400 && b.height > 150; }).length;
            const h3 = Array.from(document.querySelectorAll('h3'))
              .find(e => (e.innerText || '').includes('情景估算'));
            const y = h3 ? Math.round(h3.getBoundingClientRect().top + window.scrollY) : null;
            return {加入組合: inPortfolio, 走勢圖: charts, 情景估算位置: y,
                    捲動量: Math.round(window.scrollY), 網址: location.search || '(已清空)'};
        }""", code)
        print(f"?fund={code} →", r)
        ok &= r["加入組合"] and r["走勢圖"] >= 1 and r["捲動量"] > 100 and r["網址"] == "(已清空)"

    # 無參數：不應有捲動或加入
    pg.goto(BASE, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)
    r0 = pg.evaluate("""() => ({
        捲動量: Math.round(window.scrollY),
        圖表: Array.from(document.querySelectorAll('svg')).filter(e => {
            const b = e.getBoundingClientRect(); return b.width > 400 && b.height > 150; }).length
    })""")
    print("無參數 →", r0, "（應不捲動、無大圖）")
    ok &= r0["捲動量"] == 0 and r0["圖表"] == 0

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
