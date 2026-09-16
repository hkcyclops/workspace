#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""驗證「基金月榜 2.0」線上版（GitHub Pages）—— 本機 verify_rank2.py 的線上對應

用法：python -u scripts/verify_rank2_live.py [--wait 180]

① GitHub API 取遠端 blob，與本機 _deploy-workspace 產出**逐位元**比對
   （本機 raw.githubusercontent.com 被擋，故走 api.github.com + Accept: raw）
② HTTP 輪詢 Pages，確認已部署新版（Pages 重建通常 30–90 秒）
③ Playwright 在 https 上端到端檢查：桌面／hover 卡位置／月份導覽／存檔頁／手機直屏tap展開／語言跟隨
"""
import os, sys, json, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, "_deploy-workspace")
REPO = "hkcyclops/workspace"
BASE = "https://hkcyclops.github.io/workspace/"
API = "https://api.github.com/repos/%s/" % REPO
FILES = ["fund-ranking.html", "fund-ranking-sc.html",
         "fund-ranking-2026-07.html", "fund-ranking-2026-07-sc.html", "data/rank2.js"]

# 沙箱環境的對外網路走本機代理（HTTPS_PROXY）；urllib 會自動讀，Chromium 不會
# → 不顯式設 proxy 時 chromium 連任何外部主機都 net::ERR_CONNECTION_CLOSED
PROXY = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
LAUNCH_KW = {"proxy": {"server": PROXY, "bypass": "127.0.0.1,localhost"}} if PROXY else {}

WAIT = 180
if "--wait" in sys.argv:
    WAIT = int(sys.argv[sys.argv.index("--wait") + 1])

ok = True
notes = []


def _bye(signum, frame):
    """此環境 Playwright 段落偶被 SIGTERM；至少把已得的結論吐出來（報告已即時落盤）"""
    print("   （收到 SIGTERM，Playwright 段落中斷；以上為已完成項目）")
    print("問題：%s" % ("; ".join(notes) if notes else "無"))
    print("VERIFY LIVE:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)


try:
    import signal
    signal.signal(signal.SIGTERM, _bye)
except Exception:  # noqa
    pass


def http(url, accept=None, timeout=40, tries=3):
    """帶身分編碼避免 gzip 亂碼；簡單重試"""
    last = None
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "rank2-verify", "Accept-Encoding": "identity", "Cache-Control": "no-cache"})
            if accept:
                req.add_header("Accept", accept)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            last = "HTTPError %s" % e.code
        except Exception as e:  # noqa
            last = "%s: %s" % (type(e).__name__, e)
        time.sleep(2)
    raise RuntimeError("%s -> %s" % (url, last))


def local(name):
    return open(os.path.join(D, name.replace("/", os.sep)), "rb").read()


def nav(page, url, wait="domcontentloaded", pause=1200, tries=3):
    """線上 goto 偶有 net::ERR_CONNECTION_CLOSED，重試"""
    for i in range(tries):
        try:
            page.goto(url, wait_until=wait)
            page.wait_for_timeout(pause)
            return
        except Exception as e:  # noqa
            if i == tries - 1:
                raise
            print("   (goto 重試 %d/%d：%s)" % (i + 1, tries, type(e).__name__))
            time.sleep(3)


# ── ① 遠端 blob vs 本機產出 ───────────────────────────────────────────────
print("① GitHub API：確認遠端檔案與本機產出一致")
try:
    _, body = http(API + "commits/main")
    sha = json.loads(body)["sha"]
    print("   遠端 main = %s（%s）" % (sha[:7], json.loads(body)["commit"]["committer"]["date"]))
    for f in FILES:
        st, blob = http(API + "contents/%s?ref=%s" % (f, sha), accept="application/vnd.github.raw")
        mine = local(f)
        same = blob == mine
        print("   %-34s remote=%7d local=%7d %s" % (f, len(blob), len(mine), "OK" if same else "DIFF!"))
        if not same:
            ok = False
            notes.append("遠端 %s 與本機不同（可能有人又推了新提交）" % f)
except Exception as e:  # noqa
    print("   ✗ API 檢查失敗：%s" % e)
    ok = False
    sha = None

# ── ② Pages 部署狀態 ─────────────────────────────────────────────────────
print("② Pages：等待線上部署新版（最多 %d 秒）" % WAIT)
t0 = time.time()
pending = list(FILES)
while pending and time.time() - t0 < WAIT:
    remain = []
    for f in pending:
        try:
            st, body = http(BASE + f + "?cb=%d" % int(time.time()), tries=1)
            if st == 200 and (f.endswith(".js") or body == local(f)):
                print("   %-34s 200（%6d bytes）in %.0fs" % (f, len(body), time.time() - t0))
            else:
                remain.append(f)
        except Exception:
            remain.append(f)
    pending = remain
    if pending:
        time.sleep(8)
if pending:
    print("   ✗ 逾時未部署：%s" % ", ".join(pending))
    notes.append("Pages 逾時：%s（可能仍在重建，或 CDN 快取未過）" % ", ".join(pending))
    ok = False
else:
    print("   全部部署完成 ✓")

# ── ③ 線上端到端（Playwright / https） ────────────────────────────────────
print("③ Playwright（https 線上）：")
TR = BASE + "fund-ranking.html"
ARC = BASE + "fund-ranking-2026-07.html"
REPORT = os.path.join(HERE, "_reports", "rank2_live.json")
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
rpt = {"checks": {}, "notes": []}


def record(name, detail):
    """每步立刻落盤 —— 此環境多次 goto 有機會被 SIGTERM，避免結論遺失"""
    rpt["checks"][name] = detail
    rpt["notes"] = notes
    rpt["ok"] = ok
    with open(REPORT, "w", encoding="utf-8") as fh:
        json.dump(rpt, fh, ensure_ascii=False, indent=1)


# 單一 context／單一 page：此環境「多頁多 goto」容易觸發 SIGTERM
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH_KW)
    if PROXY:
        print("   （chromium 經代理 %s）" % PROXY)
    ctx = b.new_context(viewport={"width": 1440, "height": 1000})
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    m = pg

    # A 桌面（預設＝派息跨期）
    nav(pg, TR, pause=1500)
    a = pg.evaluate("""() => ({
        表頭: Array.from(document.querySelectorAll('thead th')).map(x=>x.textContent.trim()),
        列: document.querySelectorAll('tbody tr:not(.mrow)').length,
        名次: Array.from(document.querySelectorAll('td.rank')).slice(0,3).map(x=>x.textContent.trim()),
        首列: (function(){ const td=document.querySelector('td.name a'); return td?td.getAttribute('href'):null; })(),
        代號: (function(){ const td=document.querySelector('td.cell-code'); return td?td.textContent.trim():null; })(),
        代號連結: (function(){ const td=document.querySelector('td.cell-code'); return td&&td.querySelector('a')?td.querySelector('a').getAttribute('href'):null; })(),
        基金名連結: (function(){ const a=document.querySelector('td.name a'); return a?a.getAttribute('href'):null; })(),
        期間chip檔數: document.querySelectorAll('#periods .chip b').length,
        chip未選: (function(){ const c=Array.from(document.querySelectorAll('#views .chip')).find(x=>!x.classList.contains('on'));
            if(!c) return null; const s=getComputedStyle(c); return {bg:s.backgroundColor, border:s.borderColor}; })(),
        基金名對齊: (function(){ const c=document.querySelector('td.name'); return c?getComputedStyle(c).textAlign:null; })(),
        基金表頭對齊: (function(){ const c=document.querySelector('thead th:nth-child(3)'); return c?getComputedStyle(c).textAlign:null; })(),
        基準欄底: getComputedStyle(document.querySelector('td.basis')).backgroundColor,
        標題: document.querySelector('h1').textContent,
        導覽: Array.from(document.querySelectorAll('.monthnav a')).map(x=>x.textContent.trim()+' -> '+x.getAttribute('href'))
    })""")
    print("   A 桌面：表頭=%s｜列=%d｜名次=%s" % (a["表頭"], a["列"], a["名次"]))
    print("     標題「%s」｜首列=%s｜期間chips檔數=%d｜基準欄=%s" % (a["標題"], a["首列"], a["期間chip檔數"], a["基準欄底"]))
    print("     月份導覽=%s" % a["導覽"])
    if not (a["表頭"][:3] == ["名次", "代號", "基金"] and a["列"] == 10):
        ok = False; notes.append("桌面表頭/列數異常")
    if not (a["基準欄底"] == "rgb(251, 246, 234)" and a["期間chip檔數"] == 0):
        ok = False; notes.append("基準欄底色或期間 chips 檔數異常")
    if not ("?fund=" in (a["首列"] or "") and "06-fund-portfolio-workbench.html" in (a["首列"] or "")):
        ok = False; notes.append("首列 06 deep link 異常")
    if not (a["chip未選"] and a["chip未選"]["bg"] == "rgb(255, 253, 248)" and a["chip未選"]["border"] == "rgb(216, 200, 179)"):
        ok = False; notes.append("chips 未選不是白底（v1 .cat 樣式）")
    if not (a["基金名對齊"] == "left" and a["基金表頭對齊"] == "left"):
        ok = False; notes.append("基金名/表頭未左對齊")
    if not (a["代號連結"] is None and "?fund=" in (a["基金名連結"] or "")):
        ok = False; notes.append("代號仍是連結，或基金名連結缺失")
    print("     對齊：基金名=%s 表頭=%s｜chip 未選=%s" % (a["基金名對齊"], a["基金表頭對齊"], a["chip未選"]))
    print("     代號連結=%s｜基金名連結=%s" % (a["代號連結"], a["基金名連結"]))
    if not any("前一月" in x and "2026-07" in x for x in a["導覽"]):
        ok = False; notes.append("月份導覽缺『前一月 → 2026-07』")
    record("A 桌面", a)

    # B hover 卡要在該列下方（不遮當列）
    pg.hover("tbody tr:first-child td:nth-child(6)")   # 3 年（名稱/代號已不掛 hover）
    pg.wait_for_timeout(500)
    h = pg.evaluate("""() => {
        const row=document.querySelector('tbody tr:first-child td.name').getBoundingClientRect();
        const c=document.getElementById('hcard');
        if(!c) return null;
        const b=c.getBoundingClientRect();
        return {display:getComputedStyle(c).display, rowBottom:Math.round(row.bottom), cardTop:Math.round(b.top), svg:c.querySelectorAll('svg').length,
                文字:c.innerText.replace(/\\s+/g,' ').slice(0,60)};
    }""")
    h["星級"] = pg.evaluate("""() => { const c=document.getElementById('hcard'); if(!c) return null;
        const ce=c.querySelector('.hc-t .code'); const k=ce?ce.textContent.trim():null;
        return {code:k, m:((window.__RANK2__.funds[k]||{}).m)||0, f:c.querySelectorAll('.ms .f').length,
                e:c.querySelectorAll('.ms .e').length, na:!!c.querySelector('.ms .na')}; }""")
    print("   B hover 卡：%s" % h)
    st = h["星級"]
    if not (st and ((st["na"] and st["m"] == 0) or (st["f"] == st["m"] and st["f"] + st["e"] == 5))):
        ok = False; notes.append("hover 卡星級與資料不符")
    print("     ★ 星級：%s" % st)
    for sel, nm in (("tbody tr:first-child td.name", "基金名"), ("tbody tr:first-child td.cell-code", "代號")):
        pg.hover(sel); pg.wait_for_timeout(350)
        shown = pg.evaluate("() => { const c=document.getElementById('hcard'); return !!c && getComputedStyle(c).display !== 'none'; }")
        print("     hover %s → 卡顯示=%s（應為 False）" % (nm, shown))
        if shown is not False:
            ok = False; notes.append("hover %s 仍出卡（應與基準欄重複而取消）" % nm)
    pg.hover("tbody tr:first-child td:nth-child(6)"); pg.wait_for_timeout(350)
    hint = pg.evaluate("""() => { const row=document.querySelector('tbody tr:not(.mrow)');
        const hvs=Array.from(row.children).filter(td=>td.classList.contains('hv'));
        return {hv數: hvs.length, 欄數: row.children.length,
                游標: hvs.length?getComputedStyle(hvs[0]).cursor:null,
                非hv游標: getComputedStyle(row.children[2]).cursor}; }""")
    print("     ① 游標提示：.hv 格=%s（期間欄應為 %s）游標=%s（非 hv=%s）" % (hint["hv數"], hint["欄數"]-3, hint["游標"], hint["非hv游標"]))
    if not (hint["hv數"] == hint["欄數"] - 3 and hint["游標"] == "help" and hint["非hv游標"] == "default"):
        ok = False; notes.append("hover 提示（.hv/游標 help）異常")
    record("B-2 hover提示", hint)
    if not h or h["display"] != "block" or h["cardTop"] < h["rowBottom"] - 8:
        ok = False; notes.append("hover 卡未顯示在該列下方")
    if h and h["svg"] < 1:
        ok = False; notes.append("hover 卡缺走勢圖")
    record("B hover卡", h)

    # C 手機直屏 390（同一頁改視窗）
    m.set_viewport_size({"width": 390, "height": 844})
    nav(m, TR + "?tab=nav&cat=all&basis=1&view=cross", pause=1500)
    mv = m.evaluate("""() => {
        const tw=document.querySelector('.wrapx');
        return {可見欄: Array.from(document.querySelectorAll('thead th')).filter(x=>x.offsetParent!==null).map(x=>x.textContent.trim()),
                溢出: tw.scrollWidth > tw.clientWidth+2,
                表寬: Math.round(document.querySelector('table').getBoundingClientRect().width)};
    }""")
    m.click("tbody tr:first-child td.rank")
    m.wait_for_timeout(500)
    mx = m.evaluate("() => { const r=document.querySelector('tbody tr.mrow'); return r?r.innerText.replace(/\\s+/g,' ').slice(0,70):null; }")
    print("   C 手機直屏：可見欄=%s｜溢出=%s｜表寬=%s" % (mv["可見欄"], mv["溢出"], mv["表寬"]))
    print("     tap 展開：%s" % mx)
    if not (mv["可見欄"] == ["名次", "代號", "基金", "1 年"] and not mv["溢出"] and mv["表寬"] <= 380 and mx):
        ok = False; notes.append("手機直屏 4 欄/tap 展開異常")
    record("C 手機直屏", mv)

    # D 語言跟隨（https 下 localStorage 才可用）
    pg.set_viewport_size({"width": 1440, "height": 1000})
    t = pg
    nav(t, TR + "?tab=nav&cat=all&basis=1&view=cross", pause=1500)
    lang0 = t.evaluate("() => document.documentElement.dataset.lang")
    t.evaluate("() => localStorage.setItem('calculator-hub-language','simplified')")
    nav(t, TR + "?tab=nav&cat=all&basis=1&view=cross", pause=2000)
    sc = t.evaluate("""() => { const up=document.querySelector('td.num.up');
        return {url:location.pathname.split('/').pop(), lang:document.documentElement.dataset.lang,
                標題:document.querySelector('h1').textContent, 正報酬色:up?getComputedStyle(up).color:null}; }""")
    print("   D 語言跟隨：繁版 lang=%s → 設 simplified 後 %s" % (lang0, sc))
    if not (lang0 == "tr" and sc["url"] == "fund-ranking-sc.html" and sc["lang"] == "sc" and sc["正報酬色"] == "rgb(177, 52, 70)"):
        ok = False; notes.append("語言跟隨/簡體配色異常")
    t.evaluate("() => localStorage.setItem('calculator-hub-language','traditional')")
    nav(t, TR + "?tab=nav&cat=all&basis=1&view=cross", pause=1800)
    back = t.evaluate("() => location.pathname.split('/').pop() + ' / ' + document.documentElement.dataset.lang")
    print("     設 traditional → %s" % back)
    if not (back.startswith("fund-ranking.html") and back.endswith("tr")):
        ok = False; notes.append("切回繁體失敗")
    record("D 語言跟隨", sc)

    # E 存檔頁（2026-07）
    nav(pg, ARC, pause=1500)
    arc = pg.evaluate("""() => ({標題:document.querySelector('h1').textContent,
        基準日:document.getElementById('anchor').textContent,
        導覽:Array.from(document.querySelectorAll('.monthnav a')).map(x=>x.textContent.trim()+' -> '+x.getAttribute('href')),
        列:document.querySelectorAll('tbody tr:not(.mrow)').length})""")
    print("   E 存檔頁：%s" % json.dumps(arc, ensure_ascii=False))
    if not (arc["標題"] == "基金月榜 - 7月" and arc["基準日"] == "2026-07-31" and arc["列"] == 10
            and any("最新月份" in x for x in arc["導覽"])):
        ok = False; notes.append("存檔頁標題/基準日/導覽異常")
    record("E 存檔頁", arc)

    # F 06 的浮動按鈕 → 新版月榜（同頁開啟；此為「新版取代舊版」的關鍵串接）
    nav(pg, BASE + "06-fund-portfolio-workbench.html", pause=3000)
    fab = pg.evaluate("() => { const a=document.getElementById('fund-ranking-fab'); return a?{href:a.getAttribute('href'),target:a.getAttribute('target')}:null; }")
    pg.click("#fund-ranking-fab")
    pg.wait_for_load_state("domcontentloaded")
    pg.wait_for_timeout(1800)
    f = pg.evaluate("""() => ({url: location.pathname.split('/').pop(),
        是v2: document.documentElement.hasAttribute('data-rank2'),
        檢視chips: Array.from(document.querySelectorAll('#views .chip')).map(x=>x.textContent.trim()),
        列: document.querySelectorAll('tbody tr:not(.mrow)').length})""")
    print("   F 06 FAB：%s → %s" % (fab, f))
    if not (fab and fab["href"] == "./fund-ranking.html" and fab["target"] is None
            and f["url"] == "fund-ranking.html" and f["是v2"] and f["檢視chips"] == ["基本", "明細"] and f["列"] == 10):
        ok = False; notes.append("06 FAB 未落到新版月榜")
    record("F 06 FAB", {"fab": fab, "land": f})

    # G 橫屏（landscape 斷點）：欄位要全塞得下、且看得到資料列
    for (vw, vh, tab, view) in [(844, 390, "nav", "cross"), (800, 360, "div", "detail")]:
        pg.set_viewport_size({"width": vw, "height": vh})
        nav(pg, TR + f"?tab={tab}&cat=all&basis=1&view={view}", pause=1400)
        g = pg.evaluate("""() => {
            const wrapx=document.querySelector('.wrapx'), tb=document.querySelector('table');
            const ths=Array.from(document.querySelectorAll('thead th'));
            const last=ths[ths.length-1].getBoundingClientRect(), cx=wrapx.getBoundingClientRect();
            const s=document.createElement('style'); s.textContent='table{width:1px !important}';
            document.head.appendChild(s); const mc=Math.round(tb.getBoundingClientRect().width); s.remove();
            const thead=document.querySelector('thead'), trh=document.querySelector('tbody tr').getBoundingClientRect().height;
            return {欄數: ths.length, 需捲: wrapx.scrollWidth>wrapx.clientWidth+1,
                    末欄超出: Math.round(last.right-cx.right), 餘裕: Math.round(cx.width-mc),
                    可見列數: Math.max(0, Math.floor((innerHeight-thead.getBoundingClientRect().bottom)/trh))};
        }""")
        print("   G 橫屏 %d×%d：%s" % (vw, vh, g))
        if g["需捲"] or g["末欄超出"] > 0 or g["餘裕"] < 100 or g["可見列數"] < 3:
            ok = False; notes.append("橫屏 %d×%d 欄位或列數異常" % (vw, vh))
        record("G 橫屏 %d×%d" % (vw, vh), g)
    pg.set_viewport_size({"width": 1440, "height": 1000})

    # H 截圖模式（?shot=1）：https 上 Top 10 要在一張橫屏裡全塞下
    for (vw, vh, tab, view) in [(844, 390, "nav", "cross"), (800, 360, "div", "detail")]:
        pg.set_viewport_size({"width": vw, "height": vh})
        nav(pg, TR + f"?tab={tab}&cat=all&basis=1&view={view}&shot=1", pause=1400)
        h = pg.evaluate("""() => {
            const rows=Array.from(document.querySelectorAll('tbody tr:not(.mrow)'));
            const last=rows[rows.length-1].getBoundingClientRect();
            const nm=rows[0].children[2], st=getComputedStyle(nm);
            return {是shot: document.documentElement.classList.contains('shot'), 列數: rows.length,
                    視窗高: innerHeight, 最後列底部: Math.round(last.bottom),
                    餘高: Math.round(innerHeight-last.bottom), 列高: Math.round(rows[1].getBoundingClientRect().height),
                    單行: st.whiteSpace==='nowrap' && st.textOverflow==='ellipsis',
                    工具列隱藏: getComputedStyle(document.querySelector('.row')).display==='none',
                    脈絡: document.getElementById('shotctx').textContent.trim(),
                    按鈕: document.getElementById('shotbtn').textContent.trim()};
        }""")
        print("   H 截圖模式 %d×%d：%s" % (vw, vh, h))
        if not (h["是shot"] and h["列數"] == 10 and h["餘高"] >= 20 and h["工具列隱藏"] and h["單行"]):
            ok = False; notes.append("截圖模式 %d×%d 未能在單屏塞下 Top 10" % (vw, vh))
        record("H 截圖模式 %d×%d" % (vw, vh), h)
    pg.set_viewport_size({"width": 1440, "height": 1000})

    # J 觸控（https）：名稱不跳轉、點列＝展開、點某一期格＝展開那一期
    tctx = b.new_context(viewport={"width": 844, "height": 390}, has_touch=True)
    tp = tctx.new_page()
    nav(tp, TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", pause=1400)
    j0 = tp.evaluate("() => ({名稱有連結: !!document.querySelector('td.name a'), touch: document.documentElement.classList.contains('touch')})")
    tp.click("tbody tr:first-child td:nth-child(6)")
    tp.wait_for_timeout(600)
    j1 = tp.evaluate("""() => { const mr=document.querySelector('tbody tr.mrow');
        const st=mr?getComputedStyle(mr):null;
        return {mrow顯示: st?st.display:null, dataPer: mr?mr.getAttribute('data-per'):null,
                圖: mr?mr.querySelectorAll('svg').length:0,
                有圖例: mr?mr.innerText.indexOf('回撤期')>=0:false,
                連結: mr&&mr.querySelector('a')?mr.querySelector('a').getAttribute('href'):null,
                文字: mr?mr.innerText.replace(/\\s+/g,' ').slice(0,120):null,
                星級: (function(){ if(!mr) return null; const cd=mr.getAttribute('data-code');
                    return {有評級欄: mr.innerText.indexOf('評級')>=0, f:mr.querySelectorAll('.ms .f').length,
                            e:mr.querySelectorAll('.ms .e').length, na:!!mr.querySelector('.ms .na'),
                            m:((window.__RANK2__.funds[cd]||{}).m)||0}; })()}; }""")
    print("   J 觸控橫屏：%s" % j0)
    print("     點「3 年」格 → %s" % j1)
    js = j1.get("星級")
    print("     ★ 展開列星級：%s" % js)
    if not (js and js["有評級欄"] and ((js["na"] and js["m"] == 0) or (js["f"] == js["m"] and js["f"] + js["e"] == 5))):
        ok = False; notes.append("展開列星級與資料不符")
    if not (j0["名稱有連結"] is False and j0["touch"] and j1["dataPer"] == "3"
            and j1["mrow顯示"] == "table-row" and j1["圖"] >= 1 and j1["有圖例"]
            and j1["連結"] and "y=3" in j1["連結"]):
        ok = False; notes.append("觸控行為（名稱不跳轉／點期展開／圖例／06 連結）異常")
    record("J 觸控", {"probe": j0, "expanded": j1})
    tctx.close()

    pg.set_viewport_size({"width": 1440, "height": 1000})

    # I 版面位置：手機直屏要有基準日＋LANG 貼右上；橫屏基準日不被 LANG 遮；按鈕在表格外右上方
    pg.set_viewport_size({"width": 390, "height": 844})
    nav(pg, TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", pause=1300)
    mi = pg.evaluate("""() => {
        const R=s=>{const e=document.querySelector(s); const r=e.getBoundingClientRect(); const st=getComputedStyle(e);
            return {x:Math.round(r.left),y:Math.round(r.top),right:Math.round(r.right),bottom:Math.round(r.bottom),disp:st.display,pos:st.position};};
        const rg=document.createRange(); rg.selectNodeContents(document.querySelector('.eyebrow'));
        const eb=rg.getBoundingClientRect();
        const sb=R('.shotbtn'), card=R('.card'), thead=R('thead'), wrap=R('.wrap'), sub=R('.sub');
        return {LANG:R('.langsw'), 基準日:sub, 眉標右緣:Math.round(eb.right),
                基準日可見:sub.disp!=='none'&&sub.bottom>0,
                按鈕在表頭上方:sb.bottom<=thead.y+2,
                按鈕右對齊:Math.round(card.right-sb.right), wrap右:wrap.right};
    }""")
    print("   I 手機直屏：基準日可見=%s｜LANG=%s（眉標右緣 %s）｜按鈕在表頭上方=%s 距卡右緣=%s"
          % (mi["基準日可見"], mi["LANG"], mi["眉標右緣"], mi["按鈕在表頭上方"], mi["按鈕右對齊"]))
    if not (mi["基準日可見"] and mi["LANG"]["pos"] == "absolute" and mi["眉標右緣"] < mi["LANG"]["x"]
            and abs(mi["LANG"]["right"] - (mi["wrap右"] - 8)) <= 6
            and mi["按鈕在表頭上方"] and mi["按鈕右對齊"] <= 20):
        ok = False; notes.append("手機直屏版面（基準日／LANG／按鈕）異常")
    record("I 手機直屏版面", mi)

    pg.set_viewport_size({"width": 844, "height": 390})
    nav(pg, TR + "?tab=nav&cat=all&basis=1&view=cross&shot=0", pause=1300)
    li = pg.evaluate("""() => {
        const R=s=>{const e=document.querySelector(s); const r=e.getBoundingClientRect();
            return {x:Math.round(r.left),y:Math.round(r.top),right:Math.round(r.right)};};
        return {LANG:R('.langsw'), 基準日:R('.sub'), 標題:R('h1'), 返回:R('.backlink')};
    }""")
    gapx = li["LANG"]["x"] - li["基準日"]["right"]
    print("   I 橫屏：基準日右緣=%s LANG左緣=%s 餘量=%spx｜標題top=%s 返回top=%s"
          % (li["基準日"]["right"], li["LANG"]["x"], gapx, li["標題"]["y"], li["返回"]["y"]))
    if not (gapx >= 20 and li["返回"]["y"] > li["標題"]["y"] + 10):
        ok = False; notes.append("橫屏版面（基準日被遮／標題未換行）異常")
    record("I 橫屏版面", li)
    pg.set_viewport_size({"width": 1440, "height": 1000})

    print("   JS 錯誤：%s" % (errs[:3] if errs else "無"))
    if errs:
        ok = False; notes.append("JS 錯誤：%s" % errs[:2])
    record("JS 錯誤", errs[:3] if errs else "無")

    # 切勿 b.close()／讓 with 區塊自然結束 —— 此環境 Playwright 收尾會無限掛住
    # （verify_rank2.py 同樣用 os._exit 收尾）；瀏覽器由 OS 回收
    if notes:
        print("問題：")
        for n in notes:
            print("  - " + n)
    print("VERIFY LIVE:", "PASS" if ok else "FAIL")
    os._exit(0 if ok else 1)
