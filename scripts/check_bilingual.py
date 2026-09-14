#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速檢查雙語產物：語言標記、漲跌色變數、簡繁文字、連結、殘留佔位符"""
import io, os, re

D = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "_deploy-workspace")
FILES = ["fund-ranking.html", "fund-ranking-sc.html",
         "fund-ranking-2026-07.html", "fund-ranking-2026-07-sc.html"]
for f in FILES:
    s = io.open(os.path.join(D, f), encoding="utf-8", newline="").read()
    lang = re.search(r'data-lang="([a-z]+)"', s)
    tag = re.search(r'<html lang="([^"]+)"', s)
    h1 = re.search(r"<h1>(.*?)</h1>", s, re.S)
    toks = sorted(set(re.findall(r"__[A-Z_0-9-]+__", s)))
    links = re.findall(r'href="\./(fund-ranking[^"]*)"', s)
    print(f"{f}: {len(s.encode())//1024} KB｜lang={tag.group(1) if tag else '?'}"
          f"｜data-lang={lang.group(1) if lang else '?'}｜h1={h1.group(1) if h1 else '?'}")
    print(f"   殘留佔位符: {toks[:4] if toks else '無'}")
    print(f"   站內連結: {sorted(set(links))[:5]}")
    print(f"   色票規則: {'html[data-lang=\"tr\"]{--up:#347558;--down:#b13446}' in s}")

sc = io.open(os.path.join(D, "fund-ranking-sc.html"), encoding="utf-8", newline="").read()
tr = io.open(os.path.join(D, "fund-ranking.html"), encoding="utf-8", newline="").read()
print("\n簡體版抽查（應為 True）：")
for k in ["实际总报酬", "贝莱德", "收复时间", "净值回报", "记录日", "前一月", "最佳表现基金"]:
    print(f"   {k}: {k in sc}")
print("繁體版抽查（應為 True）：")
for k in ["實際總報酬", "貝萊德", "收復時間", "紀錄日", "最佳表現基金"]:
    print(f"   {k}: {k in tr}")
print("簡體版殘留繁體（應為 False）:", "實際總報酬" in sc, "收復時間" in sc, "最佳表現基金" in sc)
print("\n漲跌色抽查：")
for name, s in (("繁體", tr), ("簡體", sc)):
    up = re.search(r'html\[data-lang="(tr|sc)"\]\{--up:(#[0-9a-f]{6})', s)
    print(f"   {name}: 上漲色 {up.group(2) if up else '?'}（繁體應 #347558 綠、簡體應 #b13446 紅）")
