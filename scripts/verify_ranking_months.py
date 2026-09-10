#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證多月份排名頁：箭頭數量/顏色、月份導覽、tooltip 仍可用"""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
def url(f): return "file:///" + os.path.join(D, f).replace("\\", "/")

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    # ---- 8 月頁（最新）----
    pg.goto(url("dividend-ranking.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    print("== 8月（最新月） ==")
    print("  h1:", pg.inner_text("h1"))
    mv = pg.eval_on_selector_all("tbody .mv", "els=>els.map(e=>e.className.replace('mv ','')+':'+e.textContent)")
    print(f"  箭頭總數 {len(mv)}（應 25）：", " ".join(mv[:12]), "...")
    up_c = pg.eval_on_selector("tbody .mv.up", "e=>getComputedStyle(e).color")
    dn_c = pg.eval_on_selector("tbody .mv.down", "e=>getComputedStyle(e).color")
    print(f"  ↑顏色 {up_c}（應 rgb(177,52,70) 紅）；↓顏色 {dn_c}（應 rgb(52,117,88) 綠）")
    prev_a = pg.query_selector(".monthnav a.mnav")
    print("  前一月 href:", prev_a.get_attribute("href") if prev_a else None)
    newest = pg.query_selector_all(".monthnav .mnav.off")
    print("  disabled 數（最新月應=1『最新月份』）:", len(newest))
    opts = pg.eval_on_selector_all(".monthnav select option", "els=>els.map(e=>e.value+(e.selected?'*':''))")
    print("  月份選項:", opts)
    tips = pg.eval_on_selector_all("th .tip", "els=>els.length")
    print("  表頭 ？ 數（應 15）:", tips)
    ok &= (len(mv) == 25 and up_c == "rgb(177, 52, 70)" and dn_c == "rgb(52, 117, 88)"
           and prev_a and prev_a.get_attribute("href") == "./dividend-ranking-2026-07.html"
           and len(newest) == 1 and tips == 15)

    # ---- 7 月頁 ----
    pg.goto(url("dividend-ranking-2026-07.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    print("== 7月（存檔） ==")
    print("  h1:", pg.inner_text("h1"))
    mv7 = pg.eval_on_selector_all("tbody .mv", "els=>els.length")
    print(f"  箭頭數（應 0）: {mv7}")
    newest7 = pg.query_selector(".monthnav a[href='./dividend-ranking.html']")
    print("  最新月份連結:", newest7.get_attribute("href") if newest7 else None)
    opts7 = pg.eval_on_selector_all(".monthnav select option", "els=>els.map(e=>e.value+(e.selected?'*':''))")
    print("  月份選項:", opts7)
    print(f"  JS 錯誤: {errs[:3] if errs else '無'}")
    ok &= (mv7 == 0 and newest7 is not None and opts7 == ['./dividend-ranking-2026-08.html',
                                                          './dividend-ranking-2026-07.html*'] and not errs)
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
