#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證基金月榜的語言聯動：漲跌色、跟隨 06 語言、切換鈕、月導覽連結"""
import os
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
def url(f): return "file:///" + os.path.join(D, f).replace("\\", "/")

ok = True
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))

    def probe(f, label):
        pg.goto(url(f), wait_until="domcontentloaded")
        pg.wait_for_timeout(700)
        r = pg.evaluate("""() => {
            const pos = document.querySelector('.pos');
            const neg = document.querySelector('.neg');
            const up = document.querySelector('.mv.up');
            const h2 = document.querySelector('h2');
            const btnTr = document.querySelector('.langbtn[data-lang="traditional"]');
            const btnSc = document.querySelector('.langbtn[data-lang="simplified"]');
            const opts = Array.from(document.querySelectorAll('.monthnav select option')).map(o => o.value);
            const prev = document.querySelector('.monthnav a.mnav');
            return {
                語言: document.documentElement.dataset.lang,
                上漲色: pos ? getComputedStyle(pos).color : null,
                下跌色: neg ? getComputedStyle(neg).color : null,
                箭頭上升色: up ? getComputedStyle(up).color : null,
                第一個表標題: (h2 ? h2.innerText.replace(/\\s+/g, ' ') : ''),
                繁鈕: btnTr ? [btnTr.getAttribute('href'), btnTr.className] : null,
                簡鈕: btnSc ? [btnSc.getAttribute('href'), btnSc.className] : null,
                月份選項: opts,
                前一月: prev ? prev.getAttribute('href') : null
            };
        }""")
        print(f"== {label}（{f}）")
        print("   語言:", r["語言"], "｜上漲色:", r["上漲色"], "｜下跌色:", r["下跌色"])
        print("   箭頭↑色:", r["箭頭上升色"])
        print("   標題:", r["第一個表標題"])
        print("   繁鈕:", r["繁鈕"], "｜簡鈕:", r["簡鈕"])
        print("   月份選項:", r["月份選項"], "｜前一月:", r["前一月"])
        return r

    tr = probe("fund-ranking.html", "繁體版")
    ok &= tr["語言"] == "tr" and tr["上漲色"] == "rgb(52, 117, 88)" and tr["下跌色"] == "rgb(177, 52, 70)"
    ok &= tr["繁鈕"][0] == "fund-ranking.html" and "is-on" in tr["繁鈕"][1]
    ok &= tr["簡鈕"][0] == "fund-ranking-sc.html" and "is-on" not in tr["簡鈕"][1]
    ok &= all(v.endswith(".html") and "-sc" not in v for v in tr["月份選項"] + [tr["前一月"] or ""])
    ok &= "最佳表現基金" in tr["第一個表標題"]

    sc = probe("fund-ranking-sc.html", "簡體版")
    ok &= sc["語言"] == "sc" and sc["上漲色"] == "rgb(177, 52, 70)" and sc["下跌色"] == "rgb(52, 117, 88)"
    ok &= sc["簡鈕"][0] == "fund-ranking-sc.html" and "is-on" in sc["簡鈕"][1]
    ok &= "最佳表现基金" in sc["第一個表標題"]

    # 語言跟隨：localStorage 記為簡體 → 開繁體頁應自動換到簡體頁
    print("== 語言跟隨測試（localStorage=simplified）")
    pg.goto(url("fund-ranking.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(500)
    pg.evaluate("() => localStorage.setItem('calculator-hub-language', 'simplified')")
    pg.goto(url("fund-ranking.html") + "?tab=nav", wait_until="domcontentloaded")
    pg.wait_for_timeout(900)
    print("   繁體頁＋簡體設定 → 落在:", os.path.basename(pg.url.split("?")[0]), "｜查詢:", pg.evaluate("location.search"))
    ok &= "fund-ranking-sc.html" in pg.url and pg.evaluate("location.search") == "?tab=nav"

    print("== 語言跟隨測試（localStorage=traditional）")
    pg.evaluate("() => localStorage.setItem('calculator-hub-language', 'traditional')")
    pg.goto(url("fund-ranking-sc.html"), wait_until="domcontentloaded")
    pg.wait_for_timeout(900)
    print("   簡體頁＋繁體設定 → 落在:", os.path.basename(pg.url.split("?")[0]))
    ok &= "fund-ranking.html" in pg.url and "-sc" not in os.path.basename(pg.url.split("?")[0])

    # 存檔月份（7 月）也要維持同語言互跳（先設定該語言，避免被「語言跟隨」轉走）
    for f, label, want_lang in (("fund-ranking-2026-07.html", "7月繁體", "tr"),
                                ("fund-ranking-2026-07-sc.html", "7月簡體", "sc")):
        pg.goto(url("fund-ranking.html"), wait_until="domcontentloaded")
        pg.wait_for_timeout(300)
        pg.evaluate("(l) => localStorage.setItem('calculator-hub-language', l)",
                    "traditional" if want_lang == "tr" else "simplified")
        pg.goto(url(f), wait_until="domcontentloaded")
        pg.wait_for_timeout(600)
        r = pg.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('.langbtn')).map(a => a.getAttribute('href'));
            const opts = Array.from(document.querySelectorAll('.monthnav select option')).map(o => o.value);
            const latest = Array.from(document.querySelectorAll('.monthnav .mnav'))
                .map(a => a.getAttribute('href')).filter(Boolean);
            return {lang: document.documentElement.dataset.lang, 語言鈕: btns, 月份選項: opts, 連結: latest};
        }""")
        print(f"== {label}（{f}）語言:{r['lang']}｜繁簡鈕:{r['語言鈕']}｜月份:{r['月份選項']}｜其他連結:{r['連結']}")
        suffix = "" if want_lang == "tr" else "-sc"
        ok &= r["lang"] == want_lang
        # 繁簡鈕順序固定為「繁、简」，各自指向同一個月的兩個語言版本
        ok &= r["語言鈕"] == ["fund-ranking-2026-07.html", "fund-ranking-2026-07-sc.html"]
        ok &= all((suffix in v) if suffix else ("-sc" not in v) for v in r["月份選項"])

    print("JS 錯誤:", errs[:3] if errs else "無")
    ok &= not errs
    print("VERIFY:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
