#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""06 冒烟测试：React 渲染正常 + 浮动按钮可见 + 表头无旧入口"""
import os, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html").replace("\\", "/")

with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1440, "height": 900})
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL, wait_until="domcontentloaded")
    pg.wait_for_timeout(3500)
    # 1) React 渲染：#root 有内容
    root_len = pg.evaluate("document.querySelector('#root').innerHTML.length")
    # 2) 浮动按钮存在、可见、href 正确
    fab = pg.query_selector("#dividend-ranking-fab")
    fab_vis = fab.is_visible() if fab else False
    fab_href = fab.get_attribute("href") if fab else None
    fab_target = fab.get_attribute("target") if fab else None
    box = fab.bounding_box() if fab else None
    # 3) 表头无旧入口
    old_link = pg.query_selector(".workspace-switcher .dividend-ranking-link")
    print(f"root innerHTML: {root_len}")
    print(f"fab visible: {fab_vis}, href: {fab_href}, target: {fab_target}")
    print(f"fab box: {box}")
    print(f"旧表头入口存在: {old_link is not None}")
    print(f"JS pageerror: {errors[:3] if errors else '无'}")
    ok = root_len > 1000 and fab_vis and fab_href == "./dividend-ranking.html" \
         and fab_target is None and old_link is None and not errors
    print("SMOKE:", "PASS" if ok else "FAIL")
    b.close() if False else None
    os._exit(0 if ok else 1)
