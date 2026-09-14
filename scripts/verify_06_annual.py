#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證 06 年度回報區塊：位置、總覽圖、逐隻表、權重連動、定投、繁簡與漲跌色"""
import os, json, re
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
URL = "file:///" + os.path.join(D, "06-fund-portfolio-workbench.html").replace("\\", "/")

# 讀資料檔當作期望值（單檔時組合值 = 該檔值）
data = json.loads(open(os.path.join(D, "data", "annual-returns.js"), encoding="utf-8")
                  .read().split("=", 1)[1].rstrip(";\n"))
FUNDS = data["funds"]
YEARS = [str(y) for y in data["meta"]["years"]]
J08 = FUNDS["J08"]

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1400})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    def add(code):
        pg.evaluate("""(c) => { const i = document.querySelector('#fund-search');
            const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
            s.call(i, c); i.dispatchEvent(new Event('input', {bubbles: true})); }""", code)
        pg.wait_for_timeout(900)
        pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('.fund-suggestions button'))[0]; if (b) b.click(); }""")
        pg.wait_for_timeout(1800)

    def snap():
        return pg.evaluate("""() => {
            const sec = document.querySelector('.hub-annual');
            if (!sec) return {err: 'no .hub-annual'};
            const t = sec.querySelector('table');
            const bar = sec.querySelector('.hub-annual-bar');
            return {有表格: !!t,
                    卡片: Array.from(sec.querySelectorAll('.hub-annual-card')).map(c => ({
                        y: c.querySelector('b').textContent, v: c.querySelector('span').textContent,
                        cls: c.querySelector('span').className })),
                    柱數: sec.querySelectorAll('.hub-annual-bar').length,
                    柱類: bar ? bar.className : null,
                    表頭: t ? Array.from(t.querySelectorAll('thead th')).map(x => x.textContent.trim()) : null,
                    表格列: t ? Array.from(t.querySelectorAll('tbody tr')).map(tr =>
                        Array.from(tr.children).map(td => td.textContent.trim())) : null,
                    定投: (sec.querySelector('.hub-annual-dca') || {}).textContent || null,
                    標題: sec.querySelector('.hub-annual-title').textContent,
                    語言: document.documentElement.dataset.hubLanguage};
        }""")

    # 1) 單檔 J08：總覽數字應等於資料檔
    pg.goto(URL + "?fund=J08", wait_until="domcontentloaded")
    pg.wait_for_timeout(10000)
    s0 = snap()
    loaded = pg.evaluate("() => !!window.__ANNUAL__")
    pos_ok = pg.evaluate("""() => {
        const cross = document.querySelector('.cross-period-section');
        const sec = document.querySelector('.hub-annual');
        return !!(cross && sec && (cross.compareDocumentPosition(sec) & 4));
    }""")
    geom = pg.evaluate("""() => {
        const plot = document.querySelector('.hub-annual-plot');
        const pr = plot.getBoundingClientRect();
        return Array.from(plot.querySelectorAll('.hub-annual-bar')).map(b => {
            const r = b.getBoundingClientRect();
            return {left: Math.round(r.left - pr.left), w: Math.round(r.width), h: Math.round(r.height)};
        });
    }""")
    xs = [g["left"] for g in geom]
    print(f"① 區塊位置：在「各期間表現」之後 = {pos_ok}｜資料檔載入 = {loaded}｜標題 = {s0['標題']}")
    print(f"   柱幾何 = {geom}")
    plot_w = pg.evaluate("() => Math.round(document.querySelector('.hub-annual-plot').getBoundingClientRect().width)")
    widths = [g["w"] for g in geom]
    distinct = len(set(xs)) == len(xs)
    narrow = all(w < plot_w / 5 for w in widths)
    print(f"   柱幾何檢查：位置互異={distinct}｜每根寬 {widths} < 圖寬/5 ({round(plot_w / 5)})={narrow}")
    ok &= distinct and narrow and len(geom) == 5
    print(f"   卡片 = {[c['y'] + ' ' + c['v'] for c in s0['卡片']]}")
    ok &= pos_ok and loaded and s0["柱數"] == 5 and len(s0["卡片"]) == 5 and "no .hub-annual" not in s0
    for c in s0["卡片"]:
        exp = J08[c["y"]][0]
        got = float(c["v"].replace("%", "").replace("+", ""))
        ok &= abs(got - exp) < 0.06

    # 2) 逐隻基金
    pg.evaluate("""() => { const h = document.querySelector('.cross-period-section .performance-head');
        const bs = Array.from(h.querySelectorAll('button')); if (bs[1]) bs[1].click(); }""")
    pg.wait_for_timeout(1200)
    s1 = snap()
    print(f"② 逐隻基金：表頭 = {s1['表頭']}")
    for r in (s1["表格列"] or []):
        print("   ", " | ".join(r))
    ok &= s1["有表格"] and s1["表頭"][0] == "基金" and s1["表頭"][1:1 + len(YEARS)] == YEARS and len(s1["表頭"]) == len(YEARS) + 2
    ok &= s1["表格列"][0][0].startswith("J08")
    ok &= abs(float(s1["表格列"][0][1].replace("%", "").replace("+", "")) - J08["2021"][0]) < 0.06

    # 3) 加新基金 Z16 → 早期年度 N/A
    add("Z16")
    s2 = snap()
    z16 = [r for r in s2["表格列"] if r[0].startswith("Z16")]
    print(f"③ 加入 Z16：{z16[0] if z16 else '（找不到）'}")
    ok &= bool(z16) and z16[0][1] == "N/A" and z16[0][-1] == "N/A"

    # 4) 權重變更 → 總覽數字改變
    pg.evaluate("""() => { const h = document.querySelector('.cross-period-section .performance-head');
        const bs = Array.from(h.querySelectorAll('button')); if (bs[0]) bs[0].click(); }""")
    pg.wait_for_timeout(900)
    before = [c["v"] for c in snap()["卡片"]]
    pg.evaluate("""() => { const ins = Array.from(document.querySelectorAll('input[type=number]'))
            .filter(i => /^[A-Z]{1,2}[0-9]{2}\\s/.test(i.getAttribute('aria-label') || ''));
        const s = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
        ['90', '10'].forEach((v, i) => { if (ins[i]) { s.call(ins[i], v); ins[i].dispatchEvent(new Event('input', {bubbles: true})); } }); }""")
    pg.wait_for_timeout(1200)
    after = [c["v"] for c in snap()["卡片"]]
    print(f"④ 權重 50/50 → 90/10：{before} → {after}（應改變）")
    ok &= before != after and after[0] != "N/A"

    # 5) 定投模式 → 出現「你的定投实际」且 2022 值 = J08 ratio
    pg.evaluate("""() => { const sw = document.querySelector('.investment-mode-switch');
        const bs = Array.from(sw.querySelectorAll('button')); if (bs[1]) bs[1].click(); }""")
    pg.wait_for_timeout(1500)
    s3 = snap()
    print(f"⑤ 定投模式：{s3['定投']}")
    ok &= bool(s3["定投"]) and "定投" in s3["定投"] and ("实际" in s3["定投"] or "實際" in s3["定投"])
    if s3["定投"]:
        m = re.search(r"2022\s+([+-][0-9.]+)%", s3["定投"])
        exp = (J08["2022"][1] - 1) * 100
        print(f"   2022 定投實際 = {m.group(1) if m else '?'}%（期望 {exp:+.1f}%）")
        ok &= bool(m) and abs(float(m.group(1)) - exp) < 0.15

    # 6) 切簡體：文字簡體、數字仍正確、gain 變紅
    pg.evaluate("""() => { const b = Array.from(document.querySelectorAll('button'))
        .find(x => (x.getAttribute('aria-label') || '').indexOf('簡體') > -1); if (b) b.click(); }""")
    pg.wait_for_timeout(1500)
    sc = pg.evaluate("""() => {
        const sec = document.querySelector('.hub-annual');
        const card = sec.querySelector('.hub-annual-card span');
        const bar = sec.querySelector('.hub-annual-bar');
        return {語言: document.documentElement.dataset.hubLanguage,
                標題: sec.querySelector('.hub-annual-title').textContent,
                副標: sec.querySelector('.hub-annual-sub').textContent.slice(0, 30),
                第一卡: card ? card.textContent : null,
                第一卡色: card ? getComputedStyle(card).color : null,
                柱類: bar ? bar.className : null};
    }""")
    print(f"⑥ 切簡體：{json.dumps(sc, ensure_ascii=False)}")
    ok &= sc["語言"] == "simplified" and "回报" in sc["標題"] and ("历年" in sc["副標"] or "日历年" in sc["副標"])
    ok &= sc["第一卡"] not in (None, "N/A") and sc["第一卡色"] == "rgb(177, 52, 70)"

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
