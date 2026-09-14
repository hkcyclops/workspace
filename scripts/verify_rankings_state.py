#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證：LANG 鈕在右上角、切換月份／語言都保留 tab 與類別狀態"""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
def url(f, q=""): return "file:///" + os.path.join(D, f).replace("\\", "/") + q

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    pg.goto(url("fund-ranking.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(600)

    r = pg.evaluate("""() => {
        const m = document.querySelector('.masthead').getBoundingClientRect();
        const l = document.querySelector('.langsw').getBoundingClientRect();
        const eb = document.querySelector('.eyebrow');
        const rg = document.createRange(); rg.selectNodeContents(eb);
        const e = rg.getBoundingClientRect();          // 文字實際範圍（p 是區塊元素，不能用它的 rect）
        return {貼右上: Math.abs(m.right - l.right) < 2 && (l.top - m.top) < 6,
                與標題文字重疊: !(l.left >= e.right - 1 || l.right <= e.left + 1),
                位置: [Math.round(l.left), Math.round(l.top), Math.round(l.width)],
                文字右緣: Math.round(e.right)};
    }""")
    print("① LANG 鈕:", r)
    ok &= r["貼右上"] and not r["與標題文字重疊"]

    # 800px（尚未落到手機斷點）也要貼在右上、不壓到標題文字
    pg.set_viewport_size({"width": 800, "height": 900})
    pg.wait_for_timeout(250)
    narrow = pg.evaluate("""() => {
        const m = document.querySelector('.masthead').getBoundingClientRect();
        const l = document.querySelector('.langsw').getBoundingClientRect();
        const eb = document.querySelector('.eyebrow');
        const rg = document.createRange(); rg.selectNodeContents(eb);
        const e = rg.getBoundingClientRect();
        return {貼右上: Math.abs(m.right - l.right) < 2 && l.right <= window.innerWidth,
                與標題文字重疊: !(l.left >= e.right - 1 || l.right <= e.left + 1),
                位置: [Math.round(l.left), Math.round(l.top)]};
    }""")
    print("   800px 寬:", narrow)
    ok &= narrow["貼右上"] and not narrow["與標題文字重疊"]
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.wait_for_timeout(200)

    # ② 非派息 + 股票 → 網址應記住；換月／換語言都要保留
    pg.click(".tab[data-tab='nav']")
    pg.wait_for_timeout(200)
    pg.click(".cat[data-cat='stock']")
    pg.wait_for_timeout(250)
    st = pg.evaluate("""() => ({
        search: location.search,
        tab: document.querySelector('.tab.is-on') && document.querySelector('.tab.is-on').dataset.tab,
        cat: document.querySelector('.cat.is-on') && document.querySelector('.cat.is-on').dataset.cat,
        月份: Array.from(document.querySelectorAll('.monthnav a.mnav[href]')).map(a => a.getAttribute('href')),
        選項: Array.from(document.querySelectorAll('.monthnav option')).map(o => o.value),
        語言鈕: Array.from(document.querySelectorAll('.langbtn')).map(a => a.getAttribute('href'))
    })""")
    print("② 切到非派息＋股票：", st["search"], "｜tab:", st["tab"], "｜cat:", st["cat"])
    print("   月份連結:", st["月份"], "｜語言鈕:", st["語言鈕"])
    ok &= st["search"] == "?tab=nav&cat=stock" and st["tab"] == "nav" and st["cat"] == "stock"
    ok &= all("tab=nav&cat=stock" in u for u in st["月份"] + st["語言鈕"] if u)
    ok &= all("tab=nav&cat=stock" in u for u in st["選項"])

    pg.click(".monthnav a.mnav[href]")
    pg.wait_for_timeout(900)
    after = pg.evaluate("""() => ({
        file: location.pathname.split('/').pop(), search: location.search,
        tab: document.querySelector('.tab.is-on') && document.querySelector('.tab.is-on').dataset.tab,
        cat: document.querySelector('.cat.is-on') && document.querySelector('.cat.is-on').dataset.cat,
        方塊: Array.from(document.querySelectorAll('.panel')).filter(x => x.classList.contains('is-on')).map(x => x.dataset.panel)
    })""")
    print("③ 點『前一月』→", after)
    ok &= after["file"] == "fund-ranking-2026-07.html" and after["search"] == "?tab=nav&cat=stock"
    ok &= after["tab"] == "nav" and after["cat"] == "stock" and after["方塊"] == ["nav"]

    pg.click(".langbtn[data-lang='simplified']")
    pg.wait_for_timeout(900)
    after2 = pg.evaluate("""() => ({
        file: location.pathname.split('/').pop(), search: location.search,
        lang: document.documentElement.dataset.lang,
        cat: document.querySelector('.cat.is-on') && document.querySelector('.cat.is-on').dataset.cat
    })""")
    print("④ 點『简』→", after2)
    ok &= after2["file"] == "fund-ranking-2026-07-sc.html" and after2["search"] == "?tab=nav&cat=stock"
    ok &= after2["lang"] == "sc" and after2["cat"] == "stock"

    # ⑤ 直接帶參數開啟（可分享連結）
    pg.goto(url("fund-ranking.html", "?tab=nav&cat=fi"), wait_until="domcontentloaded")
    pg.wait_for_timeout(800)
    share = pg.evaluate("""() => ({
        lang: document.documentElement.dataset.lang,
        tab: document.querySelector('.tab.is-on') && document.querySelector('.tab.is-on').dataset.tab,
        cat: document.querySelector('.cat.is-on') && document.querySelector('.cat.is-on').dataset.cat
    })""")
    print("⑤ 直接開 ?tab=nav&cat=fi →", share)
    ok &= share["tab"] == "nav" and share["cat"] == "fi"

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
