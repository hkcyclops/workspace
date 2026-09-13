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
    nav_all_rows = pg.eval_on_selector_all(".panel[data-panel='nav'] tbody tr", "els=>els.length")
    nav_exp = 5 * 15 + 5 * nav_all_rows   # 表頭 5 個 ? × 15 張表 + 每列 5 個數值欄提示
    print(f"  全部榜：列 {nav_rows}（應 30）　箭頭 {nav_mv}（應 30）　? {nav_tips}（應 {nav_exp}）")
    ok &= len(chips) == 5 and nav_rows == 30 and nav_mv == 30 and nav_tips == nav_exp
    ok &= nav_heads == ["名次", "代號", "基金名", "幣種", "類別", "期間回報", "年化回報", "波動率", "最大回撤", "收復時間"]

    # 收復時間欄：數值 + 懸停顯示時間段
    cells = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on .tip-cell[data-c='rec']",
                                    "els=>els.slice(0,6).map(e=>e.textContent)")
    print("  收復時間值樣本:", cells)
    ok &= any(v.endswith("月") for v in cells)

    # 縮略圖：hover 最大回撤儲存格 → 生成 SVG（45 點折線 + 回撤／收復陰影）
    pg.hover(".panel[data-panel='nav'] .catblock.is-on .tip-cell[data-c='mdd']")
    pg.wait_for_timeout(400)
    sp = pg.evaluate("""() => {
        const t = document.querySelector(".panel[data-panel='nav'] .catblock.is-on .tip-cell[data-c='mdd']");
        const svg = t.querySelector('.spark');
        if (!svg) return {err: 'no .spark'};
        const path = svg.querySelector('.line');
        const pts = (path.getAttribute('d').match(/[ML]/g) || []).length;
        return {打開: t.classList.contains('is-open'), 點數: pts,
                陰影帶: svg.querySelectorAll('rect').length,
                深色帶: !!svg.querySelector('.band-a'), 淺色帶: !!svg.querySelector('.band-b'),
                虛線: svg.querySelectorAll('.dash').length, 圓點: svg.querySelectorAll('.dot').length,
                提示文字: t.querySelector('.tip-pop').textContent.replace(/\\s+/g,' ').slice(0, 80),
                全部提示寬: Math.round(t.querySelector('.tip-pop').getBoundingClientRect().width)};
    }""")
    print("  縮略圖:", sp)
    ok &= (not sp.get("err")) and sp["打開"] and 40 <= sp["點數"] <= 50 and sp["陰影帶"] == 2 \
        and sp["深色帶"] and sp["淺色帶"] and sp["虛線"] == 2 and sp["圓點"] == 2

    # 基金名連結 → 06 帶 ?fund=
    links = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on .flink",
                                    "els=>els.slice(0,3).map(e=>e.getAttribute('href')+' | '+e.textContent.slice(0,18))")
    spark_n = pg.evaluate("() => Object.keys(window.__SPARK__ || {}).length")
    print("  基金名連結樣本:", links)
    print("  內嵌序列組數:", spark_n)
    ok &= all("06-fund-portfolio-workbench.html?fund=" in l for l in links) and spark_n >= 85

    # 版面寬度利用：1920 視窗下 .wrap 應接近全寬
    pg.set_viewport_size({"width": 1920, "height": 1000})
    pg.wait_for_timeout(300)
    wrap_w = pg.evaluate("document.querySelector('.wrap').getBoundingClientRect().width")
    table_w = pg.evaluate("document.querySelector('.panel[data-panel=\"nav\"] .catblock.is-on table').getBoundingClientRect().width")
    print(f"  1920 視窗：.wrap 寬 {wrap_w:.0f}（應 ≥1800）　表格寬 {table_w:.0f}")
    ok &= wrap_w >= 1800
    pg.set_viewport_size({"width": 1440, "height": 1000})
    pg.wait_for_timeout(200)

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
