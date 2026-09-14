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

    # 派息面板：4 張表（YTD/1Y/3Y/5Y）；YTD 少一欄（不列年化回報）
    d_rows = pg.eval_on_selector_all(".panel[data-panel='div'] tbody tr", "els=>els.length")
    d_mv = pg.eval_on_selector_all(".panel[data-panel='div'] tbody .mv", "els=>els.length")
    div_heads = pg.evaluate("""() => Array.from(document.querySelectorAll(".panel[data-panel='div'] section.card"))
        .map(c => c.querySelectorAll("thead th").length)""")
    div_titles = pg.evaluate("""() => Array.from(document.querySelectorAll(".panel[data-panel='div'] h2"))
        .map(h => h.innerText.replace(/\\s+/g, ' ').trim())""")
    print(f"  派息面板：各表欄數 {div_heads}（應 [8,9,9,9]）　列 {d_rows}（應 35=10+10+10+5）　箭頭 {d_mv}（應 35）")
    print("  派息表標題:", div_titles)
    ok &= div_heads == [8, 9, 9, 9] and d_rows == 35 and d_mv == 35
    ok &= div_titles == ["YTD YTD 最佳表現基金", "1 年期 近 1 年最佳表現基金",
                         "3 年期 近 3 年最佳表現基金", "5 年期 近 5 年最佳表現基金"]

    # 最右欄「表頭 ?」提示不得被表格容器裁切（原 bug：貼右邊被切掉）
    EDGE_JS = """() => {
        const t = document.querySelector('.tip.is-open');
        if (!t || !t.__pop) return {err: 'no pop'};
        const r = t.__pop.getBoundingClientRect();
        return {欄: (t.closest('th') || {}).childNodes ? t.closest('th').childNodes[0].textContent.trim() : '',
                在body: t.__pop.parentNode === document.body,
                完整可見: r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth,
                右緣: Math.round(r.right), 視窗寬: window.innerWidth};
    }"""
    pg.hover(".panel[data-panel='div'] section.card thead th:last-child .tip-btn")
    pg.wait_for_timeout(400)
    div_edge = pg.evaluate(EDGE_JS)
    print("  派息最右欄表頭提示:", div_edge)
    ok &= (not div_edge.get("err")) and div_edge["在body"] and div_edge["完整可見"]

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
    nav_structure = pg.evaluate("""() => Array.from(document.querySelectorAll(".catblock.is-on section.card")).map(c => ({
        欄: c.querySelectorAll('thead th').length,
        列: c.querySelectorAll('tbody tr').length,
        表頭提示: c.querySelectorAll('thead .tip').length,
        儲存格提示: c.querySelectorAll('tbody .tip-cell').length
    }))""")
    print("  非派息 YTD 表欄位:", nav_heads)
    print("  非派息五張表結構:", nav_structure)
    ok &= nav_heads == ["名次", "代號", "基金名", "幣種", "類別", "期間回報", "波動率", "最大回撤", "收復時間"]
    ok &= [t["欄"] for t in nav_structure] == [9, 10, 10, 10, 10]
    ok &= [t["列"] for t in nav_structure] == [10, 10, 10, 10, 10]
    ok &= [t["表頭提示"] for t in nav_structure] == [4, 5, 5, 5, 5]
    ok &= all(t["儲存格提示"] == t["列"] * (4 if t["欄"] == 9 else 5) for t in nav_structure)
    nav_rows = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on tbody tr", "els=>els.length")
    nav_mv = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on tbody .mv", "els=>els.length")
    nav_tips = pg.eval_on_selector_all(".panel[data-panel='nav'] .tip", "els=>els.length")
    nav_all_rows = pg.eval_on_selector_all(".panel[data-panel='nav'] tbody tr", "els=>els.length")
    # 每一張表都要滿足：YTD 表 4 個表頭提示／列 4 個儲存格提示；其餘 5／5
    nav_bad = pg.evaluate("""() => {
        const bad = [];
        document.querySelectorAll(".panel[data-panel='nav'] section.card").forEach((c, i) => {
            const cols = c.querySelectorAll('thead th').length;
            const thTips = c.querySelectorAll('thead .tip').length;
            const rows = c.querySelectorAll('tbody tr').length;
            const tdTips = c.querySelectorAll('tbody .tip-cell').length;
            const wantTh = (cols === 9) ? 4 : 5, wantTd = (cols === 9) ? 4 : 5;
            if (thTips !== wantTh || tdTips !== rows * wantTd) bad.push({表: i + 1, 欄: cols, 表頭提示: thTips, 列: rows, 儲存格提示: tdTips});
        });
        return bad;
    }""")
    print(f"  全部榜：列 {nav_rows}（應 50=YTD+1Y+3Y+5Y+10Y 各 10）　箭頭 {nav_mv}（應 50）　? {nav_tips}　不符結構的表: {nav_bad}")
    ok &= len(chips) == 5 and nav_rows == 50 and nav_mv == 50 and not nav_bad

    # 收復時間欄：數值 + 懸停顯示時間段
    cells = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on .tip-cell[data-c='rec']",
                                    "els=>els.slice(0,6).map(e=>e.textContent)")
    print("  收復時間值樣本:", cells)
    ok &= any(v.endswith("月") for v in cells)

    # 非派息最右欄（收復時間）表頭提示：窄視窗下也要完整可見
    pg.set_viewport_size({"width": 900, "height": 800})
    pg.wait_for_timeout(250)
    pg.hover(".panel[data-panel='nav'] .catblock.is-on section.card thead th:last-child .tip-btn")
    pg.wait_for_timeout(400)
    nav_edge = pg.evaluate(EDGE_JS)
    print("  非派息最右欄表頭提示（900px）:", nav_edge)
    ok &= (not nav_edge.get("err")) and nav_edge["在body"] and nav_edge["完整可見"]
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.wait_for_timeout(250)

    # 縮略圖：hover 最大回撤儲存格 → 生成浮動 SVG（45 點折線 + 回撤／收復陰影）
    pg.hover(".panel[data-panel='nav'] .catblock.is-on tbody tr:nth-child(1) .tip-cell[data-c='mdd']")
    pg.wait_for_timeout(400)
    sp = pg.evaluate("""() => {
        const t = document.querySelector(".panel[data-panel='nav'] .catblock.is-on tbody tr:nth-child(1) .tip-cell[data-c='mdd']");
        const pop = document.querySelector('.tip-pop.tip-float.is-open');
        if (!pop) return {err: 'no floating pop'};
        const svg = pop.querySelector('.spark');
        if (!svg) return {err: 'no .spark'};
        const pts = (svg.querySelector('.line').getAttribute('d').match(/[ML]/g) || []).length;
        const r = pop.getBoundingClientRect();
        return {浮動到body: document.body.contains(pop) && !pop.closest('.tw'), 點數: pts,
                陰影帶: svg.querySelectorAll('rect').length,
                深色帶: !!svg.querySelector('.band-a'), 淺色帶: !!svg.querySelector('.band-b'),
                虛線: svg.querySelectorAll('.dash').length, 圓點: svg.querySelectorAll('.dot').length,
                在視窗內: r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth,
                提示文字: pop.textContent.replace(/\\s+/g,' ').slice(0, 70)};
    }""")
    print("  縮略圖（第 1 列）:", sp)
    ok &= (not sp.get("err")) and sp["浮動到body"] and 40 <= sp["點數"] <= 60 and sp["陰影帶"] == 2 \
        and sp["深色帶"] and sp["淺色帶"] and sp["虛線"] == 2 and sp["圓點"] == 2

    # 第 10 列：把該列精準定位到「視窗底部上方 60px」再 hover → 提示框必須自動上彈且完整可見
    pg.evaluate("""() => {
        const t = document.querySelector(".panel[data-panel='nav'] .catblock.is-on tbody tr:nth-child(10) .tip-cell[data-c='mdd']");
        const r = t.getBoundingClientRect();
        window.scrollTo(0, window.scrollY + r.bottom - window.innerHeight + 60);
    }""")
    pg.wait_for_timeout(350)
    pg.hover(".panel[data-panel='nav'] .catblock.is-on tbody tr:nth-child(10) .tip-cell[data-c='mdd']")
    pg.wait_for_timeout(450)
    low = pg.evaluate("""() => {
        const t = document.querySelector(".panel[data-panel='nav'] .catblock.is-on tbody tr:nth-child(10) .tip-cell[data-c='mdd']");
        const pop = t.__pop;
        if (!pop || !pop.classList.contains('is-open')) return {err: 'pop 未開啟'};
        const r = pop.getBoundingClientRect(), c = t.getBoundingClientRect();
        return {完整可見: r.top >= 0 && r.bottom <= window.innerHeight && r.left >= 0 && r.right <= window.innerWidth,
                翻到上方: r.bottom <= c.top + 1, 高: Math.round(r.height)};
    }""")
    print("  縮略圖（第 10 列，表格底部）:", low)
    ok &= (not low.get("err")) and low["完整可見"] and low["翻到上方"]

    # 基金名連結 → 06 帶 ?fund= 與期間 &y=1|3|5（每張表要對應自己的期間）
    per_table = pg.evaluate("""() => Array.from(document.querySelectorAll(".catblock.is-on section.card"))
        .map(card => Array.from(card.querySelectorAll('.flink')).map(a => {
            const m = /[?&]y=(YTD|\\d+)/.exec(a.getAttribute('href')); return m ? m[1] : null;
        }))""")
    div_y = pg.evaluate("""() => Array.from(document.querySelectorAll(".panel[data-panel='div'] section.card"))
        .map(card => Array.from(card.querySelectorAll('.flink')).map(a => {
            const m = /[?&]y=(YTD|\\d+)/.exec(a.getAttribute('href')); return m ? m[1] : null;
        }))""")
    t10 = pg.evaluate("""() => Array.from(document.querySelectorAll(".catblock.is-on section.card"))[4]
        .querySelector('.flink').getAttribute('title')""")
    print("  10Y 表連結標題:", t10)
    ok &= "5 年" in t10
    print("  非派息各表期間:", [sorted(set(v)) for v in per_table])
    print("  派息各表期間:", [sorted(set(v)) for v in div_y])
    ok &= [sorted(set(v)) for v in per_table] == [["YTD"], ["1"], ["3"], ["5"], ["5"]]   # 10Y 無對應按鈕 → 退回 y=5
    ok &= [sorted(set(v)) for v in div_y] == [["YTD"], ["1"], ["3"], ["5"]]

    links = pg.eval_on_selector_all(".panel[data-panel='nav'] .catblock.is-on .flink",
                                    "els=>els.slice(0,3).map(e=>e.getAttribute('href')+' | '+e.textContent.slice(0,18))")
    div_links = pg.eval_on_selector_all(".panel[data-panel='div'] .flink", "els=>els.length")
    spark_n = pg.evaluate("() => Object.keys(window.__SPARK__ || {}).length")
    print("  非派息榜名稱連結樣本:", links)
    print(f"  派息榜名稱連結數: {div_links}（應 35）")
    print("  內嵌序列組數:", spark_n)
    ok &= all("06-fund-portfolio-workbench.html?fund=" in l for l in links) and div_links == 35 and spark_n >= 85

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
    ok &= blocks == ["all:false", "stock:false", "fi:false", "multi:false", "mm:true"] and 3 <= mm_rows <= 15

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
