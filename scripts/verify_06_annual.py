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
    ctx = b.new_context(viewport={"width": 1440, "height": 1400})
    pg = ctx.new_page()
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
    style = pg.evaluate("""() => {
        const sec = document.querySelector('.hub-annual');
        const eb = sec.querySelector('.hub-annual-eyebrow');
        const tt = sec.querySelector('.hub-annual-title');
        const cb = sec.querySelector('.hub-annual-card b');
        const cs = sec.querySelector('.hub-annual-card span');
        const bars = Array.from(sec.querySelectorAll('.hub-annual-bar'))
            .map(b => ({bg: getComputedStyle(b).backgroundColor, h: Math.round(b.getBoundingClientRect().height)}));
        const cards = Array.from(sec.querySelectorAll('.hub-annual-card'))
            .map(c => c.querySelector('span').textContent);
        return {眉標色: getComputedStyle(eb).color, 眉標字級: getComputedStyle(eb).fontSize,
                標題字體: getComputedStyle(tt).fontFamily, 標題字級: getComputedStyle(tt).fontSize,
                卡標籤色: getComputedStyle(cb).color, 卡數值字體: getComputedStyle(cs).fontFamily,
                卡背景: getComputedStyle(sec.querySelector('.hub-annual-card')).backgroundColor,
                柱: bars.slice(0, 5), 卡片值: cards,
                有副標: !!sec.querySelector('.hub-annual-sub'), 有頁尾: !!sec.querySelector('.hub-annual-foot'),
                // 四項與頁面統一的細節
                section上線: getComputedStyle(sec).borderTop, section下線: getComputedStyle(sec).borderBottom,
                眉標金線: (function(){ const s2 = sec.querySelector('.hub-annual-eyebrow span');
                    if (!s2) return null; const c = getComputedStyle(s2);
                    return {w: c.width, h: c.height, bg: c.backgroundColor}; })(),
                卡片金線: getComputedStyle(sec.querySelector('.hub-annual-card')).borderTop,
                柱圓角: getComputedStyle(sec.querySelector('.hub-annual-bar')).borderRadius,
                網格線數: sec.querySelectorAll('.hub-annual-grid').length,
                y刻度: Array.from(sec.querySelectorAll('.hub-annual-ylab')).map(x => x.textContent),
                x標籤: (function(){ const e = sec.querySelector('.hub-annual-x span'); const c = getComputedStyle(e);
                    return {weight: c.fontWeight, size: c.fontSize, color: c.color}; })()};
    }""")
    print(f"① 位置在「各期間表現」後 = {pos_ok}｜資料載入 = {loaded}｜標題 = {s0['標題']}")
    print(f"   眉標 {style['眉標色']} / {style['眉標字級']}｜標題 {style['標題字體'][:22]} / {style['標題字級']}")
    print(f"   卡片標籤 {style['卡標籤色']}｜卡片數值字體 {style['卡數值字體'][:14]}｜卡背景 {style['卡背景']}")
    print(f"   說明文字：副標 {style['有副標']}／頁尾 {style['有頁尾']}（應都 False）")
    print(f"   柱色 = {[b['bg'] for b in style['柱']]}")
    print(f"   卡片值 = {style['卡片值']}")
    ok &= style["眉標色"] == "rgb(155, 23, 48)" and style["眉標字級"] == "10px"
    ok &= "Georgia" in style["標題字體"] and style["標題字級"] == "20px"
    ok &= style["卡標籤色"] == "rgb(143, 13, 37)" and "Georgia" in style["卡數值字體"]
    ok &= style["卡背景"] == "rgb(249, 242, 231)"
    ok &= not style["有副標"] and not style["有頁尾"]
    print(f"   統一細節：section 上線 {style['section上線']}｜眉標金線 {style['眉標金線']}｜卡片金線 {style['卡片金線']}")
    print(f"             柱圓角 {style['柱圓角']}｜網格線 {style['網格線數']} 條｜y 刻度 {style['y刻度']}")
    ok &= style["section上線"].startswith("1px solid rgb(223, 211, 194)") and style["section下線"].startswith("0px")
    ok &= style["眉標金線"] == {"w": "20px", "h": "1px", "bg": "rgb(200, 168, 91)"}
    ok &= style["卡片金線"].startswith("2px solid rgb(200, 168, 91)")
    ok &= style["柱圓角"] == "3px" and style["網格線數"] >= 3
    ok &= len(style["y刻度"]) == style["網格線數"] and all(t.endswith("%") for t in style["y刻度"])
    print(f"             x 標籤 {style['x標籤']}（頁面為 400 / 11px / rgb(116,105,93)）")
    ok &= style["x標籤"] == {"weight": "400", "size": "11px", "color": "rgb(116, 105, 93)"}
    gapv = pg.evaluate("() => { const eb = document.querySelector('.hub-annual-eyebrow'); const sp = eb.querySelector('span'); const tn = Array.from(eb.childNodes).find(n => n.nodeType === 3 && n.textContent.trim()); const r = document.createRange(); r.selectNodeContents(tn); return Math.round(r.getBoundingClientRect().left - sp.getBoundingClientRect().right); }")
    print(f"             眉標金線→文字間距 {gapv}px（頁面 7px）")
    ok &= gapv == 7
    # 正值用 06 品牌紅、負值用棕（與 06 自己的各期間長條圖一致）
    for card, bar in zip(style["卡片值"], style["柱"]):
        if card.strip() == "N/A":
            continue
        want = "rgb(143, 13, 37)" if card.strip().startswith("+") else "rgb(183, 122, 69)"
        ok &= bar["bg"] == want
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
                第一卡: card ? card.textContent : null,
                第一卡色: card ? getComputedStyle(card).color : null,
                柱類: bar ? bar.className : null};
    }""")
    print(f"⑥ 切簡體：{json.dumps(sc, ensure_ascii=False)}")
    ok &= sc["語言"] == "simplified" and "回报" in sc["標題"]
    ok &= sc["第一卡"] not in (None, "N/A") and sc["第一卡色"] == "rgb(177, 52, 70)"

    # ⑦ 列印版：按「打印／導出 PDF」開的新視窗，年度回報要接在「各期间表现」下方
    with ctx.expect_page() as pinfo:
        pg.click("button.scenario-print-button")
    pop = pinfo.value
    pop.wait_for_load_state("domcontentloaded")
    pop.wait_for_timeout(2500)
    pr = pop.evaluate("""() => {
        const block = document.querySelector('.hub-annual-print');
        const arts = Array.from(document.querySelectorAll('article.chart-card'))
            .map(a => ((a.querySelector('h3') || {}).textContent || '').trim());
        const metric = document.querySelector('.hub-annual-print .metric');
        return {標題: document.title, 卡片順序: arts,
                年度區塊數: document.querySelectorAll('.hub-annual-print').length,
                接在各期後: block && block.previousElementSibling
                    ? ((block.previousElementSibling.querySelector('h3') || {}).textContent || '').trim() : null,
                柱數: document.querySelectorAll('.hub-annual-print rect[fill]').length,
                年標籤: Array.from(document.querySelectorAll('.hub-annual-print .bar-label')).map(x => x.textContent),
                卡值: Array.from(document.querySelectorAll('.hub-annual-print .metric strong')).map(x => x.textContent),
                卡金線: metric ? getComputedStyle(metric).borderTopColor : null,
                主標題: (document.querySelector('.hub-annual-print h3') || {}).textContent};
    }""")
    print(f"⑦ 列印版：{json.dumps(pr, ensure_ascii=False)}")
    main_vals = [c["v"] for c in snap()["卡片"]]
    ok &= pr["年度區塊數"] == 2 and pr["柱數"] == 5 and pr["年標籤"] == YEARS
    ok &= pr["卡值"] == main_vals
    ok &= "各期" in (pr["接在各期後"] or "") and "年度" in (pr["主標題"] or "")
    ok &= pr["卡金線"] == "rgb(186, 141, 53)"

    # ⑧ 列印版所有圖表的 y 軸：可見標籤之間不得靠太近（<12px 會疊字），且字體需一致
    axis = pop.evaluate("""() => {
        const out = [];
        Array.from(document.querySelectorAll('article.chart-card')).forEach(art => {
            const h = ((art.querySelector('h3') || {}).textContent || '').trim();
            const svg = art.querySelector('svg');
            if (!svg) return;
            const labs = Array.from(svg.querySelectorAll('text'))
                .filter(t => parseFloat(t.getAttribute('x')) < 20)
                .map(t => {
                    const c = getComputedStyle(t);
                    return {txt: t.textContent.trim(), y: parseFloat(t.getAttribute('y')),
                            hidden: t.style.display === 'none', size: c.fontSize, weight: c.fontWeight, fill: c.fill};
                });
            out.push({chart: h, labs: labs});
        });
        return out;
    }""")
    bad = []
    for ch in axis:
        vis_ch = sorted([a for a in ch["labs"] if not a["hidden"]], key=lambda x: x["y"])
        for i in range(1, len(vis_ch)):
            if vis_ch[i]["y"] - vis_ch[i - 1]["y"] < 12:
                bad.append((ch["chart"], vis_ch[i - 1]["txt"], vis_ch[i]["txt"], round(vis_ch[i]["y"] - vis_ch[i - 1]["y"], 1)))
    styles = set((a["size"], a["weight"], a["fill"]) for ch in axis for a in ch["labs"])
    print(f"⑧ 列印 y 軸：靠太近的標籤 {bad}")
    for ch in axis:
        if ch["labs"]:
            print(f"     {ch['chart']}: 可見 {[a['txt'] for a in ch['labs'] if not a['hidden']]}"
                  f"｜隱藏 {[a['txt'] for a in ch['labs'] if a['hidden']]}")
    print(f"     標籤字體集合（所有圖表）：{styles}（應只有一組，代表字體一致）")
    ok &= not bad and len(styles) == 1

    # ⑨ 柱值標籤不得壓到 x 軸標籤列（負值小柱原本會疊在「3个月」上）
    barhit = pop.evaluate("""() => {
        const hits = [];
        Array.from(document.querySelectorAll('article.chart-card svg')).forEach(svg => {
            const xRow = Math.max(...Array.from(svg.querySelectorAll('text.bar-label'))
                .map(t => parseFloat(t.getAttribute('y')) || 0), 0);
            if (!xRow) return;
            Array.from(svg.querySelectorAll('text.bar-value')).forEach(t => {
                const y = parseFloat(t.getAttribute('y'));
                if (Math.abs(y - xRow) < 15) hits.push(t.textContent.trim());
            });
        });
        return hits;
    }""")
    print(f"⑨ 列印柱值標籤壓到 x 標籤列：{barhit}（應為空）")
    ok &= not barhit

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
