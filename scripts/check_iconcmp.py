import os, json
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "file:///" + os.path.join(HERE, "_deploy-workspace", "fund-ranking.html").replace("\\", "/")
OUT = os.path.join(HERE, "_verify-shots")

SIG = """() => {
  const ths=Array.from(document.querySelectorAll('thead th'));
  const n=ths[ths.length-1].querySelector('.hicon');
  if(!n) return null;
  return {rect:n.querySelectorAll('rect').length, poly:n.querySelectorAll('polyline').length,
          path:n.querySelectorAll('path').length, fill:getComputedStyle(n).color};
}"""
EXPECT = {"A": (0,1,0), "B": (0,1,1), "C": (3,0,0), "D": (1,1,0), "E": (0,0,2)}

with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, device_scale_factor=2)
    pg = ctx.new_page()
    ok = True
    for k, exp in EXPECT.items():
        pg.goto(URL + "?tab=nav&cat=all&basis=1&view=cross&shot=0&iconcompare=1&icon=" + k, wait_until="domcontentloaded")
        pg.wait_for_timeout(1200)
        sig = pg.evaluate(SIG)
        got = (sig["rect"], sig["poly"], sig["path"]) if sig else None
        good = got == exp
        ok &= good
        print("%s → rect/poly/path = %s（期望 %s）%s｜顏色=%s" % (k, got, exp, "OK" if good else "**不符**", sig["fill"] if sig else None))
    # 對照列是否存在、有 5 顆
    chips = pg.evaluate("""() => { const box=document.getElementById('iconcmp');
        return {顯示: getComputedStyle(box).display, 按鈕數: box.querySelectorAll('button').length,
                按鈕內圖示數: box.querySelectorAll('button .hicon').length}; }""")
    print("對照列：", chips)
    ok &= chips["顯示"] == "flex" and chips["按鈕數"] == 5 and chips["按鈕內圖示數"] == 5
    # 無參數時應維持原狀（A）且不顯示對照列
    pg.goto(URL + "?tab=nav&cat=all&basis=1&view=cross&shot=0", wait_until="domcontentloaded")
    pg.wait_for_timeout(1200)
    d = pg.evaluate("""() => { const ths=Array.from(document.querySelectorAll('thead th'));
        const n=ths[ths.length-1].querySelector('.hicon');
        return {sig:{rect:n.querySelectorAll('rect').length, poly:n.querySelectorAll('polyline').length, path:n.querySelectorAll('path').length},
                對照列: getComputedStyle(document.getElementById('iconcmp')).display,
                網址: location.search}; }""")
    print("無參數：", d)
    ok &= d["sig"] == {"rect":0,"poly":1,"path":0} and d["對照列"] == "none"
    # 截圖：對照列 + 表頭（選 C）
    pg.goto(URL + "?tab=nav&cat=all&basis=1&view=cross&shot=0&iconcompare=1&icon=C", wait_until="domcontentloaded")
    pg.wait_for_timeout(1300)
    box = pg.evaluate("""() => { const a=document.getElementById('iconcmp').getBoundingClientRect();
        const th=document.querySelector('thead').getBoundingClientRect();
        return {x:Math.round(a.left), y:Math.round(a.top), w:Math.round(th.width), h:Math.round(th.bottom-a.top)+8}; }""")
    pg.screenshot(path=os.path.join(OUT, "iconcompare.png"),
                  clip={"x": max(0, box["x"] - 8), "y": max(0, box["y"] - 8),
                        "width": min(1280, box["w"] + 16), "height": min(900, box["h"] + 16)})
    print("已截 iconcompare.png")
    print("RESULT:", "PASS" if ok else "FAIL")
    ctx.close()
    os._exit(0 if ok else 1)
