#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證「基金月榜」：兩分頁、類別 chips、欄位、箭頭、舊網址轉址"""
import os, io
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
def url(f, q=""): return "file:///" + os.path.join(D, f).replace("\\", "/") + q

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    pg.goto(url("fund-ranking.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(700)
    print("== fund-ranking.html（最新月，含兩分頁） ==")
    print("  h1:", pg.inner_text("h1"))
    tabs = pg.eval_on_selector_all(".tab", "els=>els.map(e=>e.textContent.trim())")
    print("  分頁:", tabs)
    vis = pg.eval_on_selector_all(".panel", "els=>els.map(e=>e.getAttribute('data-panel')+':'+e.classList.contains('is-on'))")
    print("  預設顯示:", vis)
    ok &= tabs == ["派息基金38", "非派息基金108"] and vis == ["div:true", "nav:false"]

    # 派息面板：15 個 ? 與箭頭
    d_tips = pg.eval_on_selector_all(".panel[data-panel='div'] .tip", "els=>els.length")
    d_rows = pg.eval_on_selector_all(".panel[data-panel='div'] tbody tr", "els=>els.length")
    d_mv = pg.eval_on_selector_all(".panel[data-panel='div'] tbody .mv", "els=>els.length")
    d_heads = pg.eval_on_selector_all(".panel[data-panel='div'] thead th", "els=>els.length")
    div_heads = pg.evaluate("""() => Array.from(document.querySelectorAll(".panel[data-panel='div'] section.card"))
        .map(c => c.querySelectorAll("thead th").length)""")
    print(f"  派息面板：各表欄數 {div_heads}（應 [9,9,9]）　列 {d_rows}（應 25）　箭頭 {d_mv}　? {d_tips}（應 15）")
    ok &= div_heads == [9, 9, 9] and d_rows == 25 and d_mv == 25 and d_tips == 15

    # 切到非派息分頁
    pg.click(".tab[data-tab='nav']")
    pg.wait_for_timeout(300)
    print("  切分頁後 URL:", pg.evaluate("location.search"))
    vis2 = pg.eval_on_selector_all(".panel", "els=>els.map(e=>e.getAttribute('data-panel')+':'+e.classList.contains('is-on'))")
    print("  顯示狀態:", vis2)
    ok &= vis2 == ["div:false", "nav:true"] and pg.evaluate("location.search") == "?tab=nav"

    chips = pg.eval_on_selector_all(".cat", "els=>els.map(e=>e.textContent.trim())")
    print("  類別 chips:", chips)
    nav_heads = pg.evaluate("""() => {
        const c = document.querySelector(".catblock.is-on section.card");
        return Array.from(c.querySelectorAll("thead th")).map(t => t.childNodes[0].textContent.trim());
    }""")
    print("  非派息欄位:", nav_heads)
    nav_rows = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on tbody tr", "els=>els.length")
    nav_mv = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on tbody .mv", "els=>els.length")
    nav_tips = pg.eval_on_selector_all(".panel[data-panel='nav'] .tip", "els=>els.length")
    print(f"  全部榜：列 {nav_rows}（應 30）　箭頭 {nav_mv}（應 30）　? {nav_tips}（應 60）")
    ok &= len(chips) == 5 and nav_rows == 30 and nav_mv == 30 and nav_tips == 60
    ok &= nav_heads == ["名次", "代號", "基金名", "幣種", "類別", "期間回報", "年化回報", "波動率", "最大回撤"]

    # 切到「貨幣市場」chips
    pg.click(".cat[data-cat='mm']")
    pg.wait_for_timeout(250)
    blocks = pg.eval_on_selector_all(".catblock", "els=>els.map(e=>e.getAttribute('data-cat')+':'+e.classList.contains('is-on'))")
    mm_rows = pg.eval_on_selector_all(".catblock[data-cat='mm'] tbody tr", "els=>els.length")
    print("  切『貨幣市場』後:", blocks, f"　該類別列數 {mm_rows}（3 檔 × 期間，缺資料者少列）")
    ok &= blocks == ["all:false", "stock:false", "fi:false", "multi:false", "mm:true"] and 3 <= mm_rows <= 9

    # 7 月存檔頁：無箭頭
    pg.goto(url("fund-ranking-2026-07.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)
    mv7 = pg.eval_on_selector_all("tbody .mv", "els=>els.length")
    print("== 7月存檔頁 ==  箭頭數（應 0）:", mv7)
    ok &= mv7 == 0

    # 舊網址已移除、06 入口指向基金月榜
    legacy = sorted(f for f in os.listdir(D) if f.startswith("dividend-ranking"))
    print("== 舊網址檔案（應為空） ==", legacy)
    h06 = io.open(os.path.join(D, "06-fund-portfolio-workbench.html"), encoding="utf-8").read()
    fab_ok = 'id="fund-ranking-fab" href="./fund-ranking.html"' in h06 and "dividend-ranking" not in h06
    print("== 06 FAB 指向 ./fund-ranking.html ==", fab_ok)
    ok &= (not legacy) and fab_ok

    print(f"  JS 錯誤: {errs[:3] if errs else '無'}")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
