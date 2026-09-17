"""驗證 06 智能選股器試用頁（06-smart-picker.html）
涵蓋：資料載入／副標雙行／基本與風險檢視／點列展開／桌面 hover 卡／排序／收藏取回／效能／手機
用法：python -u scripts/verify_smart_picker.py
"""
import http.server, socketserver, threading, os, functools, traceback
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=os.path.join(HERE, "_deploy-workspace"))
socketserver.TCPServer.allow_reuse_address = True
srv = socketserver.TCPServer(("127.0.0.1", 9101), Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start()
URL = "http://127.0.0.1:9101/06-smart-picker.html"
out, ok = [], True
def p(*a): out.append(" ".join(str(x) for x in a))
def chk(cond, msg):
    global ok
    ok = ok and bool(cond)
    p(("  OK  " if cond else "  FAIL ") + msg)

def wait_body(pg):
    try: pg.wait_for_selector("#body:not([hidden])", timeout=60000)
    except Exception: p("  ⚠ 載入超時")

try:
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_context(viewport={"width": 1360, "height": 1000}).new_page()
        pg.on("dialog", lambda d: d.accept("驗證方案"))
        errs = []; pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
        pg.goto(URL, wait_until="domcontentloaded"); wait_body(pg); pg.wait_for_timeout(1000)
        p("【桌面 1360x1000】")
        chk(not errs, "無 JS 錯誤" + ("" if not errs else repr(errs[:1])))
        chk("146" in pg.inner_text("#hit"), "命中 146 檔：%s" % pg.inner_text("#hit"))
        # (1) 副標雙行
        sub = pg.evaluate("""() => {
            const tr = document.querySelector('#tbl tbody tr.drow');
            const a = tr.children[0].querySelector('.sub');
            const b2 = tr.children[1].querySelector('.sub');
            return {代號副標: a?a.textContent.trim():null, 名稱副標: b2?b2.textContent.trim():null};
        }""")
        p("  副標：代號=%r 名稱=%r" % (sub["代號副標"], sub["名稱副標"]))
        chk(sub["代號副標"] and ("★" in sub["代號副標"] or "—" in sub["代號副標"]), "代號副標＝星級")
        chk(sub["名稱副標"] and sub["名稱副標"].count("·") == 2, "名稱副標＝類型 · 地區 · 幣種")
        # (2) 已撤掉檢視切換（單一表現檢視）
        chk(len(pg.query_selector_all(".vchip")) == 0, "無檢視切換 chips（已依用戶要求移除）")
        th1 = pg.eval_on_selector_all("#tbl thead th", "els=>els.map(e=>e.textContent.replace(/[▼▲ ]/g,''))")
        p("  表頭:", th1)
        chk(th1 == ["代號","基金名","年初至今","3個月","1年","3年","5年","最新年化派息率","加入"], "欄位符合規格")
        chk(len(th1) == 9, "列數＝9（不橫向滾）")
        # (4) 點列展開
        pg.locator("#tbl tbody tr.drow").first.click(); pg.wait_for_timeout(500)
        det = pg.evaluate("""() => { const x=document.querySelector('tr.xrow');
            if(!x) return null; const t=x.innerText;
            const keys=['各期回報','NAV 分位','波動率','最大回撤','類型','地區','幣種','風險','評級','派息日','上架','在 06 開啟'];
            return {長度:t.length, 全有:keys.every(k=>t.includes(k)), 缺:keys.filter(k=>!t.includes(k))}; }""")
        p("  展開列長度 %d｜欄位齊全=%s 缺=%s" % (det["長度"], det["全有"], det["缺"]))
        chk(det and det["全有"], "展開列含長尾全部欄位（回報/分位/波動/回撤/類型/地區/幣種/風險/評級/派息日/上架/06 連結）")
        pg.locator("#tbl tbody tr.drow").first.click(); pg.wait_for_timeout(400)
        chk(pg.evaluate("()=>!document.querySelector('tr.xrow')"), "再點同一列＝收合")
        # (5) 桌面 hover 卡
        pg.locator("#tbl tbody tr.drow").nth(1).hover(); pg.wait_for_timeout(500)
        hc = pg.evaluate("""() => { const c=document.getElementById('dcard'); return c && !c.hidden ? c.innerText.replace(/\\s+/g,' ').slice(0,110):null; }""")
        p("  hover 卡:", (hc or "（無）")[:105])
        chk(hc and "各期回報" in hc, "桌面 hover 顯示卡片")
        # (6) 排序：風險檢視點「波動率 3 年」
        pg.locator("#tbl thead th").nth(3).click(); pg.wait_for_timeout(700)
        seq = pg.eval_on_selector_all("#tbl tbody tr.drow td:nth-child(4)", "els=>els.slice(0,4).map(e=>parseFloat(e.textContent))")
        p("  依波動率3年排序（前4）:", seq)
        chk(seq == sorted(seq, reverse=True), "排序生效（大到小）")
        # (7) 收藏取回
        pg.click("#savePreset"); pg.wait_for_timeout(500)
        pg.click("#reset"); pg.wait_for_timeout(400)
        pg.click("#myFav"); pg.wait_for_timeout(500)
        fav = pg.inner_text("#pane").replace("\n", " | ")
        p("  我的收藏:", fav[:90])
        chk("取回" in fav and "刪除" in fav, "我的收藏可取回／刪除")
        pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
        # (8) 效能
        r = pg.evaluate("""(async () => {
            const btn=document.getElementById('toggle');
            const one=async()=>{const t0=performance.now(); btn.click();
              await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))); return Math.round(performance.now()-t0);};
            const a=await one(); await new Promise(r=>setTimeout(r,300)); const c=await one();
            return {收合:a, 展開:c};
        })()""")
        p("  點 toggle:", r, "ms")
        chk(r["收合"] < 300 and r["展開"] < 300, "展開／收合 < 300ms")
        pg.screenshot(path=os.path.join(HERE, "_verify_out", "picker_v5_desktop.png"))
        # ---------- 手機 ----------
        pg2 = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True).new_page()
        pg2.goto(URL, wait_until="domcontentloaded"); wait_body(pg2); pg2.wait_for_timeout(1000)
        p("【手機 390x844（觸控）】")
        pn = pg2.evaluate("()=>document.getElementById('panel').hidden")
        p("  條件抽屜預設:", "收合（正確）" if pn else "展開")
        chk(pn, "手機預設收合條件抽屜（不擋結果）")
        pg2.tap("#tbl tbody tr.drow"); pg2.wait_for_timeout(500)
        det2 = pg2.evaluate("""() => { const x=document.querySelector('tr.xrow'); return x? x.innerText.replace(/\\s+/g,' ').slice(0,80):null; }""")
        p("  點列展開:", det2)
        chk(det2 and "各期回報" in det2, "手機點列可展開（不依賴 hover）")
        chk(pg2.evaluate("()=>{const c=document.getElementById('dcard'); return !c || c.hidden;}"), "手機不出 hover 卡")
        pg2.screenshot(path=os.path.join(HERE, "_verify_out", "picker_v5_mobile.png"))
except Exception:
    p("EXC: " + traceback.format_exc()[-600:]); ok = False
open(os.path.join(HERE, "_verify_out", "picker_v5.txt"), "w", encoding="utf-8").write("\n".join(out))
print("\n".join(out))
print("\nRESULT:", "PASS" if ok else "FAIL")
os._exit(0 if ok else 1)
