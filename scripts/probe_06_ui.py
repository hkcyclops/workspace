#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""唯讀探查：06 頁的基金選擇 UI、走勢圖容器、可程式化操作點"""
import os, json
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html").replace("\\", "/")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 1000})
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_timeout(4000)

    print("=== 互動元素 ===")
    els = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll("input,select,textarea,button,[role=button],[role=combobox],[contenteditable=true]").forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 5 || r.height < 5) return;
        out.push({
          tag: e.tagName.toLowerCase(),
          type: e.getAttribute("type") || "",
          id: e.id || "",
          cls: (e.className || "").toString().slice(0, 60),
          ph: e.getAttribute("placeholder") || "",
          al: e.getAttribute("aria-label") || "",
          txt: (e.innerText || "").replace(/\\s+/g, " ").slice(0, 40),
          y: Math.round(r.top + window.scrollY), x: Math.round(r.left)
        });
      });
      return out.slice(0, 40);
    }""")
    for e in els:
        print(f"  y={e['y']:>5} x={e['x']:>5} <{e['tag']} type={e['type']}> id={e['id']} ph='{e['ph']}' aria='{e['al']}' txt='{e['txt']}' cls={e['cls']}")

    print("\n=== 圖表容器（svg/canvas） ===")
    charts = pg.evaluate("""() => {
      const out = [];
      document.querySelectorAll("svg,canvas").forEach(e => {
        const r = e.getBoundingClientRect();
        if (r.width < 120 || r.height < 80) return;
        out.push({tag: e.tagName.toLowerCase(), w: Math.round(r.width), h: Math.round(r.height),
                  y: Math.round(r.top + window.scrollY), cls: (e.getAttribute("class") || "").slice(0, 50),
                  parent: (e.parentElement && e.parentElement.className || "").toString().slice(0, 50)});
      });
      return out.slice(0, 15);
    }""")
    for c in charts:
        print("  ", c)

    print("\n=== 區塊標題（h1-h4 / 卡片標題） ===")
    heads = pg.evaluate("""() => Array.from(document.querySelectorAll("h1,h2,h3,h4"))
        .map(e => (e.innerText||"").replace(/\\s+/g," ").slice(0,50) + "  @y=" + Math.round(e.getBoundingClientRect().top + window.scrollY))
        .slice(0, 30)""")
    for h in heads:
        print("  ", h)

    print("\n=== 是否已有基金代碼清單（含 Z01/J08 等） ===")
    body = pg.inner_text("body")
    import re
    codes = sorted(set(re.findall(r"\b[ZAFIJDMXHTWGQ]\d{2}\b", body)))
    print("  頁面文字中出現的代號數:", len(codes), codes[:20])

    print("\n=== localStorage 內容 ===")
    print("  ", pg.evaluate("() => Object.keys(localStorage).map(k => k + '=' + localStorage.getItem(k).slice(0,60))"))
    os._exit(0)
