import http.server, socketserver, threading, os, functools, json, traceback
from playwright.sync_api import sync_playwright
HERE = os.path.dirname(os.path.abspath(__file__))
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(HERE, "_deploy-workspace"))
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 9021), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
out = []
def p(*a): out.append(" ".join(str(x) for x in a))
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_context(viewport={"width": 1360, "height": 1000}).new_page()
        pg.on("dialog", lambda d: d.accept("測試方案"))
        pg.goto("http://127.0.0.1:9021/06-smart-picker.html", wait_until="domcontentloaded")
        try: pg.wait_for_selector("#body:not([hidden])", timeout=60000)
        except Exception: p("⚠ 載入超時")
        pg.wait_for_timeout(1000)
        # ① 表頭
        th = pg.eval_on_selector_all("#tbl thead th", "els=>els.map(e=>e.textContent.replace(/[▼▲ ]/g,''))")
        p("① 表頭:", th)
        p("   含『上架』:", any("上架" in x for x in th), "（應為 False）")
        # ② 條件組
        labs = pg.eval_on_selector_all(".groups .g>.gl", "els=>els.map(e=>e.textContent)")
        p("② 條件組(%d):" % len(labs), " / ".join(labs))
        # ③ 期間回報浮層：5 期 × 2 輸入
        pg.click(".groups .g:nth-child(%d) .pop" % (labs.index("期間回報")+1)); pg.wait_for_timeout(500)
        p("③ 期間回報浮層:", pg.inner_text("#pane").replace("\n", " ")[:100])
        ins = pg.query_selector_all("#pane input[type=number]")
        p("   輸入框數:", len(ins), "（應為 10＝5 期×2）")
        perlab = pg.eval_on_selector_all("#pane .plab", "els=>els.map(e=>e.textContent)")
        p("   期別標籤:", perlab)
        # ④ 多期 AND：1Y≥0 → 加 3Y≥0 → 加 5Y≥0，數量應遞減
        def fill(idx, val):
            el = pg.query_selector_all("#pane input[type=number]")[idx]
            el.fill(str(val)); el.dispatch_event("input"); pg.wait_for_timeout(700)
        counts = []
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        for label, idx in (("1Y≥0", 4), ("3Y≥0", 6), ("5Y≥0", 8)):
            pg.click(".groups .g:nth-child(%d) .pop" % (labs.index("期間回報")+1)); pg.wait_for_timeout(400)
            fill(idx, 0)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
            counts.append((label, pg.inner_text("#hit")))
        p("④ 逐期疊加（AND）:", counts)
        got = [int(c[1].split()[1]) for c in counts]
        p("   遞減:", got[0] >= got[1] >= got[2], "（%s）" % got)
        # ⑤ 交叉核對：用頁面自己的資料獨立算 1Y/3Y/5Y 皆 ≥0 的檔數
        expect = pg.evaluate("""() => {
            const arr = (window.__FUND_DATA__['data/smart-metrics.js']||{}).default || [];
            let n = 0;
            arr.forEach(r => {
                const f = r.performancePeriods || {};
                const g = k => f[k] && f[k].returnPercent;
                const a = g('1Y'), b = g('3Y'), c = g('5Y');
                if (a != null && b != null && c != null && a >= 0 && b >= 0 && c >= 0) n++;
            });
            return n;
        }""")
        p("⑤ 獨立計算（1Y/3Y/5Y 皆 ≥0）:", expect, "｜頁面:", got[2], "→", "OK" if expect == got[2] else "**不一致**")
        # ⑥ 摘要（按大類別）
        p("⑥ 摘要:", pg.inner_text("#sums").replace("\n", " | "))
        # ⑦ 收藏 → 我的收藏 → 取回
        pg.click("#savePreset"); pg.wait_for_timeout(600)
        pg.click("#reset"); pg.wait_for_timeout(600)
        p("⑦ 重置後:", pg.inner_text("#hit"), "｜摘要:", pg.inner_text("#sums").replace("\n"," | ") or "（空）")
        pg.click("#myFav"); pg.wait_for_timeout(600)
        p("   我的收藏面板:", pg.inner_text("#pane").replace("\n", " | ")[:120])
        pg.locator("#pane .chip").first.click(); pg.wait_for_timeout(800)
        p("   取回後:", pg.inner_text("#hit"), "｜摘要:", pg.inner_text("#sums").replace("\n"," | "))
        # ⑧ 效能
        r = pg.evaluate("""(async () => {
            const btn=document.getElementById('toggle');
            const one=async()=>{const t0=performance.now(); btn.click();
              await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); return Math.round(performance.now()-t0);};
            const a=await one(); await new Promise(r=>setTimeout(r,300)); const b=await one();
            return {收合:a, 展開:b};
        })()""")
        p("⑧ 點 toggle 耗時:", r, "ms")
        pg.screenshot(path="_verify_out/picker_v4.png")
except Exception:
    p("EXC: " + traceback.format_exc()[-700:])
open(os.path.join(HERE, "_verify_out", "picker_v4.txt"), "w", encoding="utf-8").write("\n".join(out))
os._exit(0)
