#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性收尾：FAB id 更名、verify 腳本改為檢查舊網址已移除、刪除舊檔與淘汰腳本"""
import io, os

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(HERE, "_deploy-workspace")

# 1) FAB id 更名 dividend-ranking-fab -> fund-ranking-fab
targets = [os.path.join(DEPLOY, "06-fund-portfolio-workbench.html"),
           os.path.join(HERE, "scripts", "patch_06_ranking_fab.py"),
           os.path.join(HERE, "scripts", "smoke_06_fab.py"),
           os.path.join(DEPLOY, "scripts", "patch_06_ranking_fab.py"),
           os.path.join(DEPLOY, "scripts", "smoke_06_fab.py")]
for p in targets:
    if not os.path.exists(p):
        print("  略過", p)
        continue
    s = io.open(p, encoding="utf-8", newline="").read()
    n = s.count("dividend-ranking-fab")
    if n:
        io.open(p, "w", encoding="utf-8", newline="").write(s.replace("dividend-ranking-fab", "fund-ranking-fab"))
    print(f"  {os.path.relpath(p, HERE)}: 改名 {n} 處")

# 2) verify_rankings.py：轉址檢查 -> 舊檔不存在檢查
p = os.path.join(HERE, "scripts", "verify_rankings.py")
s = io.open(p, encoding="utf-8", newline="").read()
i = s.find("    # 舊網址轉址")
j = s.find('    print(f"  JS 錯誤')
if i > 0 and j > i:
    new = (
        '    # 舊網址已移除、06 入口指向基金月榜\n'
        '    legacy = sorted(f for f in os.listdir(D) if f.startswith("dividend-ranking"))\n'
        '    print("== 舊網址檔案（應為空） ==", legacy)\n'
        '    h06 = io.open(os.path.join(D, "06-fund-portfolio-workbench.html"), encoding="utf-8").read()\n'
        '    fab_ok = \'id="fund-ranking-fab" href="./fund-ranking.html"\' in h06 and "dividend-ranking" not in h06\n'
        '    print("== 06 FAB 指向 ./fund-ranking.html ==", fab_ok)\n'
        '    ok &= (not legacy) and fab_ok\n\n'
    )
    s = s[:i] + new + s[j:]
    if "import os, io" not in s:
        s = s.replace("import os\n", "import os, io\n", 1)
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("  verify_rankings.py: 已改為舊檔不存在檢查")
else:
    print("  verify_rankings.py: 找不到轉址段落，略過")

# 3) 刪除舊網址頁與淘汰腳本
for f in ["dividend-ranking.html", "dividend-ranking-2026-07.html", "dividend-ranking-2026-08.html"]:
    fp = os.path.join(DEPLOY, f)
    if os.path.exists(fp):
        os.remove(fp)
        print("  刪除", f)
for f in [os.path.join(HERE, "scripts", "build_dividend_ranking.py"),
          os.path.join(DEPLOY, "scripts", "build_dividend_ranking.py")]:
    if os.path.exists(f):
        os.remove(f)
        print("  刪除", os.path.relpath(f, HERE))
print("完成")
