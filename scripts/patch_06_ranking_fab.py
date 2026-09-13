#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 頁：右下角浮動按鈕「基金月榜」→ 指向 fund-ranking.html（同分頁開啟）。
冪等：先移除任何既有版本的浮動按鈕（含舊「派息基金排名」）再注入最新版。
用法：python patch_06_ranking_fab.py
"""
import io, re, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html")

s = io.open(TARGET, encoding="utf-8", newline="").read()
orig_len = len(s)
changed = []

# 1) 移除表頭 switcher 內的舊入口（若有殘留）
m = re.search(r'<a class="workspace-context-action dividend-ranking-link"[^>]*>.*?</a>', s)
if m:
    s = s[:m.start()] + s[m.end():]
    changed.append("移除表頭殘留入口")

# 2) 移除既有的浮動按鈕（任何版本）
m = re.search(r'<a id="dividend-ranking-fab".*?</a>', s, re.S)
if m:
    s = s[:m.start()] + s[m.end():]
    changed.append("移除舊浮動按鈕")

# 3) 注入新版浮動按鈕：基金月榜
FAB = ('<a id="dividend-ranking-fab" href="./fund-ranking.html" '
       'title="基金月榜（派息／非派息，同分頁開啟）">'
       '<span aria-hidden="true"><svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" '
       'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
       'stroke-linecap="round" stroke-linejoin="round" style="flex:none">'
       '<path d="M3 3v18h18"/><path d="M7 15l4-5 3 3 5-7"/></svg></span>'
       '<span data-traditional="基金月榜" data-simplified="基金月榜">基金月榜</span></a>')
anchor = "</main></div><script>"
idx = s.find(anchor)
if idx < 0:
    sys.exit("錨點 </main></div><script> 不存在，中止")
s = s[:idx] + "</main></div>" + FAB + "<script>" + s[idx + len(anchor):]
changed.append("注入「基金月榜」浮動按鈕")

# 4) CSS（若尚未有）
FAB_CSS = (
    "#dividend-ranking-fab{position:fixed;right:18px;bottom:18px;z-index:80;"
    "border:1px solid var(--hub-line);background:#fff;color:#56585b;"
    "display:inline-flex;align-items:center;gap:6px;padding:9px 12px;"
    "font-size:10px;font-weight:800;text-decoration:none;"
    "box-shadow:0 6px 16px #3c281e1f;"
    "transition:border-color .16s var(--hub-ease),color .16s var(--hub-ease),transform .16s var(--hub-ease)}"
    "#dividend-ranking-fab:hover{border-color:var(--hub-red);color:var(--hub-red)}"
    "#dividend-ranking-fab:active{transform:scale(.97)}"
    "@media (max-width:700px){#dividend-ranking-fab{right:12px;bottom:12px;padding:8px 9px}}"
)
if "#dividend-ranking-fab{" not in s:
    i = s.find("</style>")
    if i < 0:
        sys.exit("找不到 </style>，中止")
    s = s[:i] + FAB_CSS + s[i:]
    changed.append("注入浮動按鈕 CSS")

io.open(TARGET, "w", encoding="utf-8", newline="").write(s)
print("完成：", "; ".join(changed) if changed else "無改動", f"({orig_len} → {len(s)} bytes)")
