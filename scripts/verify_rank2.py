#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證基金月榜 2.0：桌面（跨期/明細/hover 卡/展開）、手機直屏與橫屏、繁簡與語言跟隨"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
TR = "file:///" + os.path.join(D, "fund-ranking-2.html").replace("\\", "/")
SC = "file:///" + os.path.join(D, "fund-ranking-2-sc.html").replace("\\", "/")

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    def grab():
        return pg.evaluate("""() => ({
            表頭: Array.from(document.querySelectorAll('thead th')).map(x => x.textContent.trim()),
            列數: document.querySelectorAll('tbody tr:not(.mrow)').length,
            名次: Array.from(document.querySelectorAll('td.rank')).slice(0, 3).map(x => x.textContent.trim()),
            基準欄: (function(){ const c = document.querySelector('td.basis'); return c ? {bg: getComputedStyle(c).backgroundColor, bar: getComputedStyle(c).boxShadow.slice(0, 24)} : null; })(),
            基準表頭: (function(){ const c = document.querySelector('th.basis'); return c ? getComputedStyle(c).backgroundColor : null; })(),
            首列連結: (document.querySelector('td.name a') || {}).getAttribute ? document.querySelector('td.name a').getAttribute('href') : null,
            卡顯示: (function(){ const c = document.getElementById('hcard'); return c ? c.style.display : 'none'; })(),
            卡文字: (function(){ const c = document.getElementById('hcard'); return c ? c.innerText.replace(/\\s+/g, ' ').slice(0, 90) : null; })(),
            卡走勢: document.querySelectorAll('#hcard svg').length,
            期間chips: Array.from(document.querySelectorAll('#periods .chip')).map(x => x.textContent.trim()),
            期間chips有檔數: document.querySelectorAll('#periods .chip b').length,
            類別chips有檔數: document.querySelectorAll('#cats .chip b').length,
            基準欄陰影: getComputedStyle(document.querySelector('td.basis')).boxShadow,
            數值字體: (function(){ const e = document.querySelector('td.num'); const c = getComputedStyle(e);
                return {f: c.fontFamily.slice(0, 13), w: c.fontWeight, size: c.fontSize}; })(),
            標題字級: getComputedStyle(document.querySelector('h1')).fontSize,
            眉標: (function(){ const c = getComputedStyle(document.querySelector('.eyebrow'));
                return {size: c.fontSize, color: c.color}; })(),
            展開列: document.querySelectorAll('tbody tr.mrow').length,
            展開文字: (function(){ const r = document.querySelector('tbody tr.mrow'); return r ? r.innerText.replace(/\\s+/g, ' ').slice(0, 110) : null; })(),
        })""")

    # ① 桌面 · 跨期比較
    pg.goto(TR, wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    s = grab()
    print(f"① 桌面跨期：表頭={s['表頭']}｜列={s['列數']}｜名次={s['名次']}")
    print(f"   基準欄 bg={s['基準欄']['bg'] if s['基準欄'] else None}｜表頭={s['基準表頭']}")
    print(f"   首列連結={s['首列連結']}")
    ok &= s["表頭"] == ["名次", "基金", "YTD", "1 年", "3 年", "5 年"] and s["列數"] == 10
    ok &= s["名次"][0].startswith("1") and s["基準表頭"] == "rgb(200, 168, 91)"
    print(f"   字體：h1 {s['標題字級']}｜眉標 {s['眉標']}｜數值 {s['數值字體']}")
    print(f"   chips：期間 {s['期間chips']}（檔數項 {s['期間chips有檔數']}）｜類別檔數項 {s['類別chips有檔數']}")
    print(f"   基準欄陰影 {s['基準欄陰影']}")
    ok &= s["期間chips有檔數"] == 0 and s["類別chips有檔數"] >= 1   # 類別仍要顯示檔數（0 檔類別會隱藏，故非固定 5 個）
    ok &= s["基準欄陰影"] == "none"
    ok &= s["數值字體"]["f"].startswith("Georgia") and s["數值字體"]["w"] == "700"
    ok &= s["標題字級"] == "32px" and s["眉標"] == {"size": "11.5px", "color": "rgb(140, 125, 112)"}
    ok &= "06-fund-portfolio-workbench.html?fund=Z17" in (s["首列連結"] or "")

    # ② hover 基金名 → 資訊卡（含走勢）
    pg.hover("tbody tr:first-child td.name")
    pg.wait_for_timeout(400)
    s2 = grab()
    print(f"② hover 基金名 → 卡顯示={s2['卡顯示']}｜走勢svg={s2['卡走勢']}｜{s2['卡文字']}")
    ok &= s2["卡顯示"] == "block" and s2["卡走勢"] >= 1

    # ③ hover 期間數值 → 該期間資訊卡
    pg.hover("tbody tr:first-child td.num")
    pg.wait_for_timeout(400)
    s3 = grab()
    print(f"③ hover 數值 → 卡顯示={s3['卡顯示']}｜走勢svg={s3['卡走勢']}｜{s3['卡文字']}")
    ok &= s3["卡顯示"] == "block" and s3["卡走勢"] >= 1

    # ④ 點列 → 展開明細（含其他期間與 06 連結）
    pg.click("tbody tr:first-child td.rank")
    pg.wait_for_timeout(400)
    s4 = grab()
    print(f"④ 點列展開 → 展開列={s4['展開列']}｜{s4['展開文字']}")
    ok &= s4["展開列"] == 1 and "幣種" in (s4["展開文字"] or "") and "06" in (s4["展開文字"] or "")

    # ⑤ 明細檢視
    pg.evaluate("""() => { Array.from(document.querySelectorAll('#views .chip')).find(x => /明細/.test(x.textContent)).click(); }""")
    pg.wait_for_timeout(500)
    s5 = grab()
    print(f"⑤ 明細檢視：表頭={s5['表頭']}｜列={s5['列數']}")
    ok &= s5["表頭"][:2] == ["名次", "基金"] and s5["列數"] == 10

    # ⑥ 切類別＋期間＋分頁
    pg.evaluate("""() => { Array.from(document.querySelectorAll('#cats .chip')).find(x => /股票/.test(x.textContent)).click(); }""")
    pg.wait_for_timeout(400)
    pg.evaluate("""() => { Array.from(document.querySelectorAll('#periods .chip')).find(x => /3 年/.test(x.textContent)).click(); }""")
    pg.wait_for_timeout(400)
    s6 = grab()
    print(f"⑥ 股票+3年：表頭={s6['表頭']}｜列={s6['列數']}｜URL={pg.evaluate('location.search')}")
    ok &= "3 年" in s6["表頭"] and "basis=3" in pg.evaluate("location.search")
    pg.evaluate("""() => { Array.from(document.querySelectorAll('.tab')).find(x => /非派息/.test(x.textContent)).click(); }""")
    pg.wait_for_timeout(500)
    s7 = grab()
    print(f"   切非派息：表頭={s7['表頭']}｜列={s7['列數']}")
    ok &= "波動率" in s7["表頭"] and "3 年" in s7["表頭"]   # 明細檢視只有基準期間欄

    # ⑦ 手機直屏 390×844
    m = ctx.new_page()
    m.set_viewport_size({"width": 390, "height": 844})
    m.goto(TR + "?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
    m.wait_for_timeout(1200)
    mm = m.evaluate("""() => {
        const tw = document.querySelector('.wrapx');
        const vis = Array.from(document.querySelectorAll('thead th')).filter(x => x.offsetParent !== null).map(x => x.textContent.trim());
        return {可見欄: vis, 橫向溢出: tw.scrollWidth > tw.clientWidth + 2,
                表格寬: Math.round(document.querySelector('table').getBoundingClientRect().width),
                列高: Math.round(document.querySelector('tbody tr').offsetHeight)};
    }""")
    m.click("tbody tr:first-child td.rank")
    m.wait_for_timeout(400)
    mrow = m.evaluate("() => { const r = document.querySelector('tbody tr.mrow'); return r ? r.innerText.replace(/\\s+/g,' ').slice(0,80) : null; }")
    print(f"⑦ 手機直屏：可見欄={mm['可見欄']}｜橫向溢出={mm['橫向溢出']}｜表寬={mm['表格寬']}｜列高={mm['列高']}")
    print(f"   tap 展開：{mrow}")
    ok &= mm["可見欄"] == ["名次", "基金", "1 年"] and not mm["橫向溢出"] and mm["表格寬"] <= 380
    ok &= bool(mrow)

    # ⑧ 手機橫屏 844×390
    m.set_viewport_size({"width": 844, "height": 390})
    m.wait_for_timeout(400)
    mm2 = m.evaluate("""() => {
        const tw = document.querySelector('.wrapx');
        return {可見欄: Array.from(document.querySelectorAll('thead th')).filter(x => x.offsetParent !== null).length,
                橫向溢出: tw.scrollWidth > tw.clientWidth + 2};
    }""")
    print(f"⑧ 手機橫屏：可見欄數={mm2['可見欄']}｜橫向溢出={mm2['橫向溢出']}")
    ok &= mm2["可見欄"] >= 6 and not mm2["橫向溢出"]

    # ⑨⑩ 簡體版與語言跟隨（須用 http，file:// 下 localStorage 被瀏覽器拒絕）
    import re
    for f in ("fund-ranking-2.html", "fund-ranking-2-sc.html"):
        txt = io.open(os.path.join(D, f), encoding="utf-8").read()
        left = sorted(set(re.findall(r"__[A-Z_]+__", txt)))
        print(f"⑨ {f}：殘留佔位符 {left}（應為空）")
        ok &= not left

    srv = None
    try:
        import subprocess, socket
        srv = subprocess.Popen([sys.executable, "-m", "http.server", "8901", "--bind", "127.0.0.1"],
                               cwd=D, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(40):
            try:
                socket.create_connection(("127.0.0.1", 8901), 0.3).close()
                break
            except OSError:
                time.sleep(0.25)
        B = "http://127.0.0.1:8901/"
        t = ctx.new_page()
        t.goto(B + "fund-ranking-2.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1200)
        lang0 = t.evaluate("() => document.documentElement.dataset.lang")
        t.evaluate("() => localStorage.setItem('calculator-hub-language', 'simplified')")
        t.goto(B + "fund-ranking-2.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1500)
        sc = t.evaluate("""() => { const up = document.querySelector('td.num.up');
            return {url: location.pathname.split('/').pop(), lang: document.documentElement.dataset.lang,
                    標題: document.querySelector('h1').textContent, 正報酬色: up ? getComputedStyle(up).color : null}; }""")
        print(f"⑩ 語言跟隨：繁版 lang={lang0} → 設 simplified 後 {sc}")
        ok &= lang0 == "tr" and sc["url"] == "fund-ranking-2-sc.html" and sc["lang"] == "sc"
        ok &= sc["正報酬色"] == "rgb(177, 52, 70)"
        t.evaluate("() => localStorage.setItem('calculator-hub-language', 'traditional')")
        t.goto(B + "fund-ranking-2.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1500)
        back = t.evaluate("() => location.pathname.split('/').pop() + ' / ' + document.documentElement.dataset.lang")
        print(f"   設 traditional → {back}")
        ok &= back.startswith("fund-ranking-2.html") and back.endswith("tr")
    finally:
        if srv:
            srv.terminate()

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
