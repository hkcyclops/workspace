#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""可行性實驗（唯讀，不改產品檔）：驗證 06 能否被程式化選中某檔基金
用法：python probe_06_deeplink.py Z01 [J08 ...]
路徑：模擬輸入 #fund-search → 出現候選 → 點擊加入 → 檢查走勢圖是否出現
"""
import os, sys, json
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html").replace("\\", "/")
CODES = sys.argv[1:] or ["Z01", "J08", "A05"]

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)

    for code in CODES:
        print(f"=== 基金 {code} ===")
        r = pg.evaluate("""(code) => {
          const inp = document.querySelector('#fund-search');
          if (!inp) return 'no #fund-search';
          const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
          setter.call(inp, code);
          inp.dispatchEvent(new Event('input', {bubbles: true}));
          return 'set ' + inp.value;
        }""", code)
        print("  輸入框:", r)
        pg.wait_for_timeout(1000)
        cand = pg.evaluate("""(code) => {
          const btns = Array.from(document.querySelectorAll('.fund-suggestions button, button'))
            .filter(e => (e.innerText || '').includes(code));
          return btns.slice(0, 3).map(e => ({
            txt: e.innerText.replace(/\\s+/g, ' ').slice(0, 46),
            cls: (e.className || '').toString().slice(0, 30),
            inSuggestions: !!e.closest('.fund-suggestions')
          }));
        }""", code)
        print("  候選:", json.dumps(cand, ensure_ascii=False)[:300])
        hit = pg.evaluate("""(code) => {
          const btns = Array.from(document.querySelectorAll('.fund-suggestions button, button'))
            .filter(e => (e.innerText || '').includes(code));
          if (!btns.length) return 'none';
          btns[0].click();
          return btns[0].innerText.replace(/\\s+/g, ' ').slice(0, 46);
        }""", code)
        print("  點擊:", hit)
        pg.wait_for_timeout(1800)
        st = pg.evaluate("""(code) => {
          const charts = Array.from(document.querySelectorAll('svg,canvas'))
            .filter(e => { const r = e.getBoundingClientRect(); return r.width > 120 && r.height > 80; }).length;
          const inPortfolio = Array.from(document.querySelectorAll('*'))
            .some(e => e.children.length === 0 && (e.innerText || '').trim() === code);
          return {加入組合: inPortfolio, 大型圖表: charts};
        }""", code)
        print("  結果:", st)
    os._exit(0)
