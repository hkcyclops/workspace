#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證基金月榜 2.0：桌面（跨期/明細/hover 卡/展開）、手機直屏與橫屏、繁簡與語言跟隨"""
import os, sys, io, json, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
TR = "file:///" + os.path.join(D, "fund-ranking.html").replace("\\", "/")
SC = "file:///" + os.path.join(D, "fund-ranking-sc.html").replace("\\", "/")

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
            chip未選: (function(){ const c = Array.from(document.querySelectorAll('#views .chip')).find(x => !x.classList.contains('on'));
                if (!c) return null; const s = getComputedStyle(c);
                return {bg: s.backgroundColor, border: s.borderColor, radius: s.borderRadius}; })(),
            基金名對齊: (function(){ const c = document.querySelector('td.name'); return c ? getComputedStyle(c).textAlign : null; })(),
            基金表頭對齊: (function(){ const c = document.querySelector('thead th:nth-child(3)'); return c ? getComputedStyle(c).textAlign : null; })(),
            數值字體: (function(){ const e = document.querySelector('td.num'); const c = getComputedStyle(e);
                return {f: c.fontFamily.slice(0, 13), w: c.fontWeight, size: c.fontSize}; })(),
            標題字級: getComputedStyle(document.querySelector('h1')).fontSize,
            分頁: (function(){ const t = Array.from(document.querySelectorAll('.tab'));
                const on = t.find(x => x.classList.contains('is-on')), off = t.find(x => !x.classList.contains('is-on'));
                const g = e => { const c = getComputedStyle(e); return {bg: c.backgroundColor, radius: c.borderRadius, bbc: c.borderBottomColor, bbw: c.borderBottomWidth}; };
                return {選中: g(on), 未選: g(off), 檔數字體: getComputedStyle(document.querySelector('.tab b')).fontFamily.slice(0, 7)}; })(),
            基金名字體: getComputedStyle(document.querySelector('td.name')).fontFamily.slice(0, 12),
            頁標題: document.querySelector('h1').textContent,
            返回: (function(){ const a = document.querySelector('.backlink a'); return a ? a.getAttribute('href') : null; })(),
            LANG外框: (function(){ const c = getComputedStyle(document.querySelector('.langsw'));
                return {border: c.border, radius: c.borderRadius}; })(),
            代號欄: (function(){ const td = document.querySelector('td.cell-code'); if (!td) return null;
                return {txt: td.textContent.trim(), 連結: td.querySelector('a') ? td.querySelector('a').getAttribute('href') : null,
                        字體: getComputedStyle(td.querySelector('.code') || td).fontFamily.slice(0, 13)}; })(),
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
    ok &= s["表頭"] == ["名次", "代號", "基金", "YTD", "1 年", "3 年", "5 年"] and s["列數"] == 10
    ok &= s["名次"][0].startswith("1") and s["基準表頭"] == "rgb(200, 168, 91)"
    print(f"   字體：h1 {s['標題字級']}｜眉標 {s['眉標']}｜數值 {s['數值字體']}")
    print(f"   chips：期間 {s['期間chips']}（檔數項 {s['期間chips有檔數']}）｜類別檔數項 {s['類別chips有檔數']}")
    print(f"   基準欄陰影 {s['基準欄陰影']}")
    ok &= s["期間chips有檔數"] == 0 and s["類別chips有檔數"] >= 1   # 類別仍要顯示檔數（0 檔類別會隱藏，故非固定 5 個）
    ok &= s["基準欄陰影"] == "none"
    # chips 未選＝白底（同 v1 .cat：bg var(--surface) #fffdf8／border var(--line-3) #d8c8b3）
    print(f"   chip 未選：{s['chip未選']}")
    ok &= bool(s["chip未選"]) and s["chip未選"]["bg"] == "rgb(255, 253, 248)" \
        and s["chip未選"]["border"] == "rgb(216, 200, 179)" and s["chip未選"]["radius"] == "0px"
    # 基金名／表頭都靠左（先前缺這條 → 整欄貼右）
    print(f"   對齊：基金名={s['基金名對齊']}｜基金表頭={s['基金表頭對齊']}")
    ok &= s["基金名對齊"] == "left" and s["基金表頭對齊"] == "left"
    ok &= s["數值字體"]["f"].startswith("Georgia") and s["數值字體"]["w"] == "700"
    ok &= s["標題字級"] == "32px" and s["眉標"] == {"size": "11.5px", "color": "rgb(140, 125, 112)"}
    print(f"   標題「{s['頁標題']}」｜返回 {s['返回']}｜LANG {s['LANG外框']}｜代號欄 {s['代號欄']}")
    ok &= s["頁標題"].startswith("基金月榜 - ") and (s["返回"] or "").endswith("06-fund-portfolio-workbench.html")
    ok &= s["LANG外框"]["radius"] == "0px" and "1px solid" in s["LANG外框"]["border"]
    ok &= s["代號欄"] and s["代號欄"]["字體"].startswith("Georgia")
    ok &= s["代號欄"]["連結"] is None                       # 代號不可點（只有基金名連 06）
    ok &= "?fund=" in (s["首列連結"] or "")
    print(f"   分頁：{s['分頁']}｜基金名字體 {s['基金名字體']}")
    ok &= s["分頁"]["選中"]["bbc"] == "rgb(143, 13, 37)" and s["分頁"]["選中"]["radius"] == "0px"
    ok &= s["分頁"]["未選"]["bg"] == "rgba(0, 0, 0, 0)" and s["分頁"]["檔數字體"] == "Georgia"
    ok &= not s["基金名字體"].startswith("Georgia")   # 基金名回無襯線
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
    ok &= s5["表頭"][:3] == ["名次", "代號", "基金"] and s5["列數"] == 10

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
    m.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
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
    ok &= mm["可見欄"] == ["名次", "代號", "基金", "1 年"] and not mm["橫向溢出"] and mm["表格寬"] <= 380
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
    ok &= mm2["可見欄"] >= 7 and not mm2["橫向溢出"]

    # ⑨⑩ 簡體版與語言跟隨（須用 http，file:// 下 localStorage 被瀏覽器拒絕）
    import re
    for f in ("fund-ranking.html", "fund-ranking-sc.html"):
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
        t.goto(B + "fund-ranking.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1200)
        lang0 = t.evaluate("() => document.documentElement.dataset.lang")
        t.evaluate("() => localStorage.setItem('calculator-hub-language', 'simplified')")
        t.goto(B + "fund-ranking.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1500)
        sc = t.evaluate("""() => { const up = document.querySelector('td.num.up');
            return {url: location.pathname.split('/').pop(), lang: document.documentElement.dataset.lang,
                    標題: document.querySelector('h1').textContent, 正報酬色: up ? getComputedStyle(up).color : null}; }""")
        print(f"⑩ 語言跟隨：繁版 lang={lang0} → 設 simplified 後 {sc}")
        ok &= lang0 == "tr" and sc["url"] == "fund-ranking-sc.html" and sc["lang"] == "sc"
        ok &= sc["正報酬色"] == "rgb(177, 52, 70)"
        t.evaluate("() => localStorage.setItem('calculator-hub-language', 'traditional')")
        t.goto(B + "fund-ranking.html?tab=nav&cat=all&basis=1&view=cross", wait_until="domcontentloaded")
        t.wait_for_timeout(1500)
        back = t.evaluate("() => location.pathname.split('/').pop() + ' / ' + document.documentElement.dataset.lang")
        print(f"   設 traditional → {back}")
        ok &= back.startswith("fund-ranking.html") and back.endswith("tr")
    finally:
        if srv:
            srv.terminate()

    # ⑪ 月份導覽（最新頁）：前一月 → 存檔頁；最新月份為 off
    nav = pg.evaluate("() => { const n = document.querySelector('.monthnav'); if (!n) return null; return {項: Array.from(n.children).map(x => x.textContent.replace(/\\s+/g, ' ').trim()), 連結: Array.from(n.querySelectorAll('a')).map(a => a.textContent.trim() + ' -> ' + a.getAttribute('href')), 選項: Array.from(n.querySelectorAll('option')).map(o => o.value + (o.selected ? '[選]' : ''))}; }")
    print(f"⑪ 月份導覽（最新頁）：{json.dumps(nav, ensure_ascii=False)}")
    ok &= bool(nav) and any("前一月" in l and "2026-07" in l for l in nav["連結"])
    ok &= any(o.endswith("[選]") and o.startswith("fund-ranking.html") for o in nav["選項"])

    # ⑫ 存檔頁（2026-07）：標題/基準日/導覽都要指向自己的月份
    arc = "file:///" + os.path.join(D, "fund-ranking-2026-07.html").replace("\\", "/")
    pg.goto(arc, wait_until="domcontentloaded")
    pg.wait_for_timeout(1300)
    arc2 = pg.evaluate("() => ({標題: document.querySelector('h1').textContent, 基準日: document.getElementById('anchor').textContent, 導覽連結: Array.from(document.querySelectorAll('.monthnav a')).map(x => x.textContent.trim() + ' -> ' + x.getAttribute('href')), 列: document.querySelectorAll('tbody tr:not(.mrow)').length})")
    print(f"⑫ 存檔頁 2026-07：{json.dumps(arc2, ensure_ascii=False)}")
    ok &= arc2["標題"] == "基金月榜 - 7月" and arc2["基準日"] == "2026-07-31" and arc2["列"] == 10
    ok &= any("最新月份" in l and "fund-ranking.html" in l for l in arc2["導覽連結"])

    # ⑬ 橫屏（landscape 斷點，701–1100px 寬且 ≤600px 高）：所有欄位都要塞得下，不留橫向卷軸
    #    最壞情況＝小機 800×360 ＋ 派息明細 9 欄；還要求 ≥100px 餘裕（吸收 iOS 較寬中文字體）
    for (vw, vh, tab, view, label) in [(844, 390, "nav", "cross", "iPhone 14/15"),
                                       (800, 360, "div", "detail", "小機·派息明細9欄")]:
        m.set_viewport_size({"width": vw, "height": vh})
        m.goto(TR + f"?tab={tab}&cat=all&basis=1&view={view}&shot=0", wait_until="domcontentloaded")
        m.wait_for_timeout(1300)
        lr = m.evaluate("""() => {
            const wrapx=document.querySelector('.wrapx'), tb=document.querySelector('table');
            const ths=Array.from(document.querySelectorAll('thead th'));
            const last=ths[ths.length-1].getBoundingClientRect(), cx=wrapx.getBoundingClientRect();
            const s=document.createElement('style'); s.textContent='table{width:1px !important}';
            document.head.appendChild(s); const mc=Math.round(tb.getBoundingClientRect().width); s.remove();
            const st=getComputedStyle(document.querySelector('td.num'));
            const thead=document.querySelector('thead'), trh=document.querySelector('tbody tr').getBoundingClientRect().height;
            const chipRows=Array.from(document.querySelectorAll('.row')).map(e=>Math.round(e.getBoundingClientRect().top));
            return {欄數: ths.length, 需捲: wrapx.scrollWidth>wrapx.clientWidth+1,
                    末欄超出: Math.round(last.right-cx.right), 容器: Math.round(cx.width), minContent: mc,
                    餘裕: Math.round(cx.width-mc), 內距: st.padding, 字級: st.fontSize,
                    可見列數: Math.max(0, Math.floor((innerHeight - thead.getBoundingClientRect().bottom) / trh)),
                    chip行數: new Set(chipRows).size};
        }""")
        print(f"⑬ 橫屏 {label} {vw}×{vh}：欄={lr['欄數']} 需捲={lr['需捲']} 末欄超出={lr['末欄超出']}"
              f" 餘裕={lr['餘裕']}px｜內距={lr['內距']} 字級={lr['字級']}｜可見列={lr['可見列數']} chip行={lr['chip行數']}")
        ok &= (not lr["需捲"]) and lr["末欄超出"] <= 0 and lr["餘裕"] >= 100
        ok &= lr["內距"] == "6px 8px" and lr["字級"] == "13px"
        ok &= lr["可見列數"] >= 3 and lr["chip行數"] <= 2   # 橫屏要真的看得到資料列、chip 不可散成三行

    # ⑭ 截圖模式（?shot=1）：工具列隱藏、基金名單行省略、Top 10 要在一張橫屏裡全塞下
    for (vw, vh, tab, basis, view, label) in [(844, 390, "nav", "1", "cross", "iPhone 14/15 8欄"),
                                              (800, 360, "div", "1", "detail", "小機 派息明細9欄")]:
        m.set_viewport_size({"width": vw, "height": vh})
        m.goto(TR + f"?tab={tab}&cat=all&basis={basis}&view={view}&shot=1", wait_until="domcontentloaded")
        m.wait_for_timeout(1300)
        sh = m.evaluate("""() => {
            const rows=Array.from(document.querySelectorAll('tbody tr:not(.mrow)'));
            const last=rows[rows.length-1].getBoundingClientRect();
            const ths=Array.from(document.querySelectorAll('thead th'));
            const wrapx=document.querySelector('.wrapx');
            const nm=rows[0].children[2], st=getComputedStyle(nm);
            return {是shot: document.documentElement.classList.contains('shot'),
                    列數: rows.length, 最後列底部: Math.round(last.bottom), 視窗高: innerHeight,
                    餘高: Math.round(innerHeight-last.bottom),
                    列高: Math.round(rows[1].getBoundingClientRect().height),
                    單行: st.whiteSpace==='nowrap' && st.textOverflow==='ellipsis',
                    工具列隱藏: getComputedStyle(document.querySelector('.row')).display==='none'
                              && getComputedStyle(document.querySelector('.tabs')).display==='none'
                              && getComputedStyle(document.querySelector('.langsw')).display==='none',
                    脈絡: document.getElementById('shotctx').textContent.trim(),
                    按鈕: document.getElementById('shotbtn').textContent.trim()};
        }""")
        print(f"⑭ 截圖模式 {label} {vw}×{vh}：列={sh['列數']} 最後列底={sh['最後列底部']}/{sh['視窗高']}"
              f" 餘高={sh['餘高']} 列高={sh['列高']}｜工具列隱藏={sh['工具列隱藏']} 基金名單行={sh['單行']}"
              f"｜脈絡「{sh['脈絡']}」按鈕={sh['按鈕']}")
        ok &= sh["是shot"] and sh["列數"] == 10 and sh["餘高"] >= 20
        ok &= sh["工具列隱藏"] and sh["單行"] and sh["按鈕"] == "✕ 退出"
    m.set_viewport_size({"width": 390, "height": 844})

    # ⑮ 版面細節：手機直屏要有基準日＋LANG 回右上；橫屏基準日不被 LANG 遮；截圖模式按鈕在表格外右上方
    m.set_viewport_size({"width": 390, "height": 844})
    m.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    m.wait_for_timeout(1200)
    lay = m.evaluate("""() => {
        const R=s=>{const e=document.querySelector(s); if(!e) return null; const r=e.getBoundingClientRect(); const st=getComputedStyle(e);
            return {x:Math.round(r.left),y:Math.round(r.top),right:Math.round(r.right),bottom:Math.round(r.bottom),disp:st.display,pos:st.position};};
        const lw=R('.langsw'), sub=R('.sub'), eb=R('.eyebrow'), wrap=R('.wrap'), sb=R('.shotbtn'), card=R('.card'), h1=R('h1'), bl=R('.backlink');
        // 眉標是 block（矩形恆滿寬）→ 用 Range 量文字真實右緣
        const ebTxt=(function(){ const e=document.querySelector('.eyebrow'); if(!e) return null;
            const rg=document.createRange(); rg.selectNodeContents(e); const r=rg.getBoundingClientRect();
            return {x:Math.round(r.left),right:Math.round(r.right)}; })();
        return {直屏_LANG:lw, 直屏_基準日:sub, 直屏_眉標:eb, 直屏_wrap:wrap,
                眉標文字右緣:ebTxt, 眉標與LANG重疊:(ebTxt&&lw)?ebTxt.right>lw.x:null, 直屏_基準日可見:(sub&&sub.disp!=='none'&&sub.bottom>0),
                按鈕位置:{btn:sb, card:card}, 按鈕在表頭上方:sb?sb.bottom<=Math.round(document.querySelector('thead').getBoundingClientRect().top)+2:null,
                按鈕右對齊:sb&&card?Math.round(card.right-sb.right):null,
                h1右緣:h1?h1.right:null, 返回:bl};
    }""")
    print(f"⑮ 手機直屏：基準日可見={lay['直屏_基準日可見']}（{lay['直屏_基準日']}）")
    print(f"   LANG={lay['直屏_LANG']}｜眉標文字右緣={lay['眉標文字右緣']}｜與 LANG 重疊={lay['眉標與LANG重疊']}")
    print(f"   截圖模式按鈕：在表頭上方={lay['按鈕在表頭上方']} 距卡片右緣={lay['按鈕右對齊']}px｜眉標文字右緣={lay['眉標文字右緣']}")
    ok &= lay["直屏_基準日可見"] and lay["直屏_LANG"]["pos"] == "absolute"
    ok &= abs(lay["直屏_LANG"]["right"] - (lay["直屏_wrap"]["right"] - 8)) <= 6   # 貼齊右上（wrap 內距 8）
    ok &= lay["眉標與LANG重疊"] is False    # 用文字實際右緣比對
    # 橫屏：基準日要與 LANG 留 ≥20px 餘量，且標題與返回／基準日分兩行
    m.set_viewport_size({"width": 844, "height": 390})
    m.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    m.wait_for_timeout(1200)
    land = m.evaluate("""() => {
        const R=s=>{const e=document.querySelector(s); const r=e.getBoundingClientRect(); return {x:Math.round(r.left),y:Math.round(r.top),right:Math.round(r.right)};};
        return {LANG:R('.langsw'), 基準日:R('.sub'), 標題:R('h1'), 返回:R('.backlink')};
    }""")
    gap = land["LANG"]["x"] - land["基準日"]["right"] if land["基準日"] else None
    print(f"⑮ 橫屏：基準日右緣={land['基準日']['right'] if land['基準日'] else None} LANG左緣={land['LANG']['x']} 餘量={gap}px"
          f"｜標題top={land['標題']['y']} 返回top={land['返回']['y']}")
    ok &= gap is not None and gap >= 20                      # 不被 LANG 遮
    ok &= land["返回"]["y"] > land["標題"]["y"] + 10          # 返回／基準日 換到標題下一行
    ok &= lay["按鈕在表頭上方"] and lay["按鈕右對齊"] <= 20     # 按鈕在表外右上方

    # ⑯ 觸控（手機／平板）：名稱不跳轉、點列＝展開、點某一期格＝展開那一期；桌機行為不變
    TPROBE = """() => {
        const mr=document.querySelector('tbody tr.mrow');
        const st=mr?getComputedStyle(mr):null;
        return {名稱有連結: !!document.querySelector('td.name a'),
                mrow顯示: st?st.display:null,
                dataPer: mr?mr.getAttribute('data-per'):null,
                mrow文字: mr?mr.innerText.replace(/\\s+/g,' ').slice(0,160):null,
                mrow有圖: mr?mr.querySelectorAll('svg').length:0,
                mrow連結: mr&&mr.querySelector('a')?mr.querySelector('a').getAttribute('href'):null};
    }"""
    tctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True)
    tp = tctx.new_page()
    tp.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    tp.wait_for_timeout(1300)
    t1 = tp.evaluate(TPROBE)
    print(f"⑯ 觸控直屏：基金名有連結={t1['名稱有連結']}（應為 False）")
    ok &= t1["名稱有連結"] is False
    tp.click("tbody tr:first-child td.name")
    tp.wait_for_timeout(500)
    t2 = tp.evaluate(TPROBE)
    print(f"   點基金名 → mrow 顯示={t2['mrow顯示']} data-per={t2['dataPer']} 圖={t2['mrow有圖']}")
    print(f"   內容：{t2['mrow文字']}")
    print(f"   06 連結：{t2['mrow連結']}")
    ok &= t2["mrow顯示"] == "table-row" and t2["dataPer"] == "1"
    ok &= "幣種" in (t2["mrow文字"] or "") and "類別" in (t2["mrow文字"] or "")
    ok &= "回撤期" in (t2["mrow文字"] or "") and "06" in (t2["mrow文字"] or "")   # 圖例 + 06 入口
    ok &= t2["mrow有圖"] >= 1
    ok &= t2["mrow連結"] and "?fund=" in t2["mrow連結"] and "y=1" in t2["mrow連結"]
    tp.click("tbody tr:first-child td.name")
    tp.wait_for_timeout(400)
    ok &= not tp.evaluate("() => !!document.querySelector('tbody tr.mrow')")
    print("   再點同一列 → 已收合")

    tp.set_viewport_size({"width": 844, "height": 390})
    tp.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    tp.wait_for_timeout(1300)
    tp.click("tbody tr:first-child td:nth-child(6)")      # 3 年
    tp.wait_for_timeout(500)
    l1 = tp.evaluate(TPROBE)
    print(f"⑯ 觸控橫屏：點「3 年」格 → data-per={l1['dataPer']} 圖={l1['mrow有圖']} 連結={l1['mrow連結']}")
    print(f"   內容：{l1['mrow文字']}")
    ok &= l1["dataPer"] == "3" and "3 年" in (l1["mrow文字"] or "") and "y=3" in (l1["mrow連結"] or "")
    tp.click("tbody tr:first-child td:nth-child(7)")      # 5 年
    tp.wait_for_timeout(500)
    l2 = tp.evaluate(TPROBE)
    print(f"   改點「5 年」格 → data-per={l2['dataPer']}（應切成 5）")
    ok &= l2["dataPer"] == "5"
    tp.click("tbody tr:first-child td:nth-child(7)")
    tp.wait_for_timeout(400)
    ok &= not tp.evaluate("() => !!document.querySelector('tbody tr.mrow')")
    print("   再點同一格 → 已收合")
    tp.set_viewport_size({"width": 1024, "height": 768})   # 觸控平板橫屏（不吃 landscape 斷點）
    tp.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    tp.wait_for_timeout(1300)
    tp.click("tbody tr:first-child td.name")
    tp.wait_for_timeout(500)
    t4 = tp.evaluate(TPROBE)
    print(f"⑯ 觸控平板 1024×768：mrow 顯示={t4['mrow顯示']}")
    ok &= t4["mrow顯示"] == "table-row"
    tctx.close()

    # 桌機（有滑鼠）行為必須不變：名稱仍有連結、點列仍不會顯示明細、data-per 固定為排名基準
    pg.set_viewport_size({"width": 1440, "height": 1000})
    pg.goto(TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    pg.wait_for_timeout(1300)
    d1 = pg.evaluate(TPROBE)
    pg.click("tbody tr:first-child td:nth-child(6)")
    pg.wait_for_timeout(500)
    d2 = pg.evaluate(TPROBE)
    print(f"⑯ 桌機：名稱有連結={d1['名稱有連結']}｜點 3 年格後 mrow 顯示={d2['mrow顯示']} data-per={d2['dataPer']}")
    ok &= d1["名稱有連結"] is True and d1["mrow顯示"] is None
    ok &= d2["mrow顯示"] == "none" and d2["dataPer"] == "1"

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
