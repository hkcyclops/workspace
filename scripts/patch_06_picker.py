"""把「智能選股器」注入 06-fund-portfolio-workbench.html（在原智能條件位置就地展開）

設計原則（降低寫壞風險）：
- 只做「一次注入」：把 <style id=SP_PICKER_CSS_V1> + <script id=SP_PICKER_V1> 插到 </body> 前；重跑會先移除舊注入
- 全部 id 加 `sp-` 前綴、全部 CSS 選擇器加 `#sp-wrap ` 限定 → 不污染 06（Tailwind）既有樣式
- 資料直接用 06 已載入的 `window.__FUND_DATA__`（catalog/smart-metrics/distribution-references/manifest），只額外載 smart-vol.js
- 執行時把包好的 #sp-wrap 插到 06 原本 .smart-fund-filter 之後，並把原面板隱藏
用法：python -u scripts/patch_06_picker.py [--revert]
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(HERE, "_deploy-workspace", "06-smart-picker.html")
DST = os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html")
CSS_ID = "SP_PICKER_CSS_V1"
JS_ID = "SP_PICKER_V1"

IDS = ["toggle", "sums", "hit", "reset", "panel", "loading", "body", "presets", "groups",
       "viewRes", "savePreset", "myFav", "clearPicked", "footHint", "res", "resHead",
       "tbl", "picked", "pickedLst", "copyCodes", "pane", "toast", "dcard", "iconcmp"]


def extract(html):
    css = re.search(r"<style>(.*?)</style>", html, re.S).group(1)
    js = re.search(r"<script>(.*?)</script>", html, re.S).group(1)
    # 取 .stage 到 </section>（面板 + 結果），再加上浮層與 toast
    i = html.index('<div class="stage">')
    j = html.index("</section>") + len("</section>")
    mark = html[i:j]
    for frag in ('<div class="pane" id="pane" hidden></div>', '<div class="toast" id="toast"></div>'):
        k = html.index(frag)
        mark += "\n" + html[k:k + len(frag)]
    return css, mark, js


def scope_css(css):
    """每一條規則前面加 #sp-wrap；@media 內遞歸；html/body 直接丟掉"""
    out = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = m.group(1).strip(), m.group(2)
        if sel.startswith("@") or sel.startswith("from") or sel.startswith("to") or re.match(r"^\d+%$", sel):
            out.append("%s{%s}" % (sel, body)); continue
        if sel in ("html,body", "body", "html"):
            continue                      # 不要把 06 的 body 改掉
        sels = []
        for one in sel.split(","):
            one = one.strip()
            if one == ":root":
                sels.append("#sp-wrap")
            elif one == "*":
                sels.append("#sp-wrap *")
            else:
                sels.append("#sp-wrap " + one)
        out.append("%s{%s}" % (",".join(sels), body))
    return "\n".join(out)


def build_css(css):
    """先抽出 @media 區塊，其餘規則 scope；最後把 @media 內文也 scope 後接回"""
    medias = []
    def stash(m):
        medias.append((m.group(1).strip(), m.group(2)))
        return "\n"
    rest = re.sub(r"(@media[^{]+)\{((?:[^{}]|\{[^{}]*\})*)\}", stash, css)
    out = scope_css(rest)
    for cond, inner in medias:
        out += "\n%s{\n%s\n}" % (cond, scope_css(inner))
    return out


def rename_ids(text):
    for i in sorted(IDS, key=len, reverse=True):
        text = text.replace('id="%s"' % i, 'id="sp-%s"' % i)
        text = text.replace("$('%s')" % i, "$('sp-%s')" % i)
        text = text.replace('getElementById("%s")' % i, 'getElementById("sp-%s")' % i)
        text = text.replace("getElementById('%s')" % i, "getElementById('sp-%s')" % i)
        text = text.replace("querySelector('#%s" % i, "querySelector('#sp-%s" % i)
        text = text.replace("querySelector(\"#%s" % i, "querySelector(\"#sp-%s" % i)
    return text


def main():
    dst = io.open(DST, encoding="utf-8").read()
    # 冪等：先移除舊注入
    dst = re.sub(r'<style id="%s">.*?</style>\n?' % CSS_ID, "", dst, flags=re.S)
    dst = re.sub(r'<script id="%s">.*?</script>\n?' % JS_ID, "", dst, flags=re.S)
    if "--revert" in sys.argv:
        io.open(DST, "w", encoding="utf-8").write(dst)
        print("已移除注入（回到 06 原狀）")
        return 0

    css, mark, js = extract(io.open(SRC, encoding="utf-8").read())
    css2 = build_css(css)
    mark2 = rename_ids(mark)
    js2 = rename_ids(js)

    # JS 適配：資料改讀 06 既有；只補載 smart-vol；掛到 06 的智能條件位置
    js2 = js2.replace("""    step('載入基本資料…');
    for (var f of ['catalog','smart-vol','distribution-references','manifest']) await loadScript(f);
    D.cat = fd('catalog')||{}; D.vol = fd('smart-vol')||{funds:{}};
    D.dref = fd('distribution-references')||{}; D.man = fd('manifest')||{};
    step('載入歷史指標（約 8 MB，首次較久）…');
    await loadScript('smart-metrics');
    D.sm = fd('smart-metrics')||{};""",
"""    step('等待 06 載入資料…');
    var _t0 = Date.now();
    while ((!fd('catalog') || !((fd('catalog')||{}).funds||[]).length) && (Date.now()-_t0) < 30000){
      await new Promise(function(r){ setTimeout(r, 300); });
    }
    step('讀取 06 已載入的資料…');
    D.cat = fd('catalog')||{}; D.dref = fd('distribution-references')||{};
    D.man = fd('manifest')||{}; D.sm = fd('smart-metrics')||{};
    D.vol = fd('smart-vol') || {funds:{}};
    if (!D.vol.funds || !Object.keys(D.vol.funds).length){ await loadScript('smart-vol'); D.vol = fd('smart-vol')||{funds:{}}; }""")
    # 掛載：插到 06 原本智能條件之後，原面板隱藏
    js2 = js2.replace("void 0", "void 0")  # noop，保持字串不變
    js2 = js2.replace("""  boot();""",
"""  /* 掛到 06：插在原本智能條件面板後方，並把原面板隱藏（保留 DOM，不動 React） */
  function mountInto06(){
    var host = document.querySelector('.smart-fund-filter') || document.querySelector('details');
    var wrap = document.getElementById('sp-wrap');
    if (host && wrap){
      if (!wrap.getAttribute('data-mounted')){
        host.parentNode.insertBefore(wrap, host.nextSibling);
        wrap.setAttribute('data-mounted','1');
      }
    }
    var pf = document.querySelector('.smart-fund-filter');
    if (pf){
      var d = pf.closest('details'); if (d) d.style.display = 'none';
      pf.style.display = 'none';                 /* 原面板本身也藏（details 不存在時的保險） */
    }
  }
  document.addEventListener('DOMContentLoaded', mountInto06);
  var _boot = boot;
  boot = function(){ return _boot().then(mountInto06); };
  /* React 掛載 & 資料載入都晚於本腳本 → 輪詢掛載／隱藏原面板，直到成功 */
  var _mt = setInterval(mountInto06, 700);
  setTimeout(function(){ clearInterval(_mt); }, 60000);
  if (document.readyState !== 'loading') setTimeout(mountInto06, 800);
  boot();""")

    import base64
    b64 = base64.b64encode(mark2.encode("utf-8")).decode("ascii")
    block = ('<style id="%s">\n%s\n</style>\n'
             '<script id="%s">\n(function(){\n'
             'if (document.getElementById("sp-wrap")) return;   /* 已注入 */\n'
             'var __b64 = "%s";\n'
             'var __bytes = Uint8Array.from(atob(__b64), function(c){ return c.charCodeAt(0); });\n'
             'var __mark = new TextDecoder("utf-8").decode(__bytes);\n'
             'var __wrap = document.createElement("div"); __wrap.id = "sp-wrap";\n'
             '__wrap.innerHTML = __mark;\n'
             'document.body.appendChild(__wrap);\n'
             '%s\n})();\n</script>\n') % (CSS_ID, css2, JS_ID, b64, js2)

    # ⚠️ 06 的 bundle 內另有一處 </body> 是 JS 模板字串（約 @1.41MB）→ 必須插在「檔案最後」那一個
    pos = dst.rfind("</body>")
    assert pos > 0 and pos > len(dst) - 5000, "找不到檔案末尾的 </body>"
    out = dst[:pos] + block + dst[pos:]
    io.open(DST, "w", encoding="utf-8").write(out)
    print("已注入：CSS %d 字、標記 %d 字、JS %d 字｜06 檔案 %.1f KB → %.1f KB"
          % (len(css2), len(mark2), len(js2), len(dst.encode())/1024, len(out.encode())/1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
