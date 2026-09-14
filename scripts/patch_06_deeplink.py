#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 頁：支援 deep link `?fund=CODE`（由基金月榜點基金名進來）。
行為：等 React 掛載 → 先把篩選切回「全部基金」→ 在 #fund-search 輸入代號 →
      點第一個候選（加入組合）→ 捲到「情景估算」走勢圖 → 清掉網址參數。
冪等：已注入則跳過（以 marker 判斷）。
用法：python patch_06_deeplink.py
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html")
MARKER = "HUB_FUND_DEEPLINK_V5"

JS = """
/* HUB_FUND_DEEPLINK_V5：由基金月榜 ?fund=CODE&y=YTD|1|3|5|10 帶入基金並設定走勢圖區間
   - YTD：點 06 的「YTD」期間鈕（用它自己的年度邏輯）
   - 數字：直接設定下方「完整歷史起點／終點」兩個 range 滑桿（可支援 06 沒按鈕的 10 年）
   設定完成後捲到「情景估算」並清掉網址參數 */
(function(){
  var m = /[?&]fund=([A-Za-z]{1,2}\\d{2})\\b/.exec(location.search);
  if (!m) return;
  var code = m[1].toUpperCase();
  var ym = /[?&]y=(YTD|[1-9]\\d*)\\b/i.exec(location.search);
  var period = ym ? (/^ytd$/i.test(ym[1]) ? 'YTD' : ym[1]) : null;
  var tries = 0, clickedAll = false, added = false, periodDone = false, timer;

  function byText(txt, scope){
    var root = scope || document;
    return Array.prototype.slice.call(root.querySelectorAll('button'))
      .filter(function(b){ return (b.innerText || '').trim() === txt; })[0];
  }
  function suggest(){
    return Array.prototype.slice.call(document.querySelectorAll('.fund-suggestions button'))
      .filter(function(e){ return (e.innerText || '').indexOf(code) > -1; })[0];
  }
  function setInput(inp, val){
    var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
    setter.call(inp, val);
    inp.dispatchEvent(new Event('input', {bubbles: true}));
  }
  function sliders(){
    var rs = Array.prototype.slice.call(document.querySelectorAll('input[type=range]'));
    var pick = function(word){
      return rs.filter(function(e){ return (e.getAttribute('aria-label') || '').indexOf(word) > -1; })[0];
    };
    var s = pick('起點'), e = pick('終點');
    return (s && e) ? {start: s, end: e} : null;
  }
  function chartSection(){
    var h = Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,h4'))
      .filter(function(e){ return (e.innerText || '').indexOf('情景估算') > -1; })[0];
    if (!h) return null;
    return h.closest('section') || h.parentElement.parentElement;
  }
  function scrollToCharts(){
    var h = Array.prototype.slice.call(document.querySelectorAll('h1,h2,h3,h4'))
      .filter(function(e){ return (e.innerText || '').indexOf('情景估算') > -1; })[0];
    if (h){ var y = h.getBoundingClientRect().top + window.scrollY - 16; window.scrollTo({top: y, behavior: 'smooth'}); }
  }
  function cleanup(){
    if (history.replaceState) history.replaceState(null, '', location.pathname);
  }
  function setRange(years){
    var sl = sliders();
    if (!sl) return false;
    var minV = +sl.start.min;
    var endV = +sl.end.value || +sl.end.max;
    var want = Math.max(minV, Math.round(endV - years * 365.25 * 24 * 3600 * 1000));
    if (Math.abs(+sl.start.value - want) > 24 * 3600 * 1000){
      var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(sl.start, String(want));
      sl.start.dispatchEvent(new Event('input', {bubbles: true}));
      sl.start.dispatchEvent(new Event('change', {bubbles: true}));
    }
    return true;
  }
  function clickButton(label){
    var b = byText(label, chartSection());
    if (!b) return false;
    if (!b.classList.contains('active')) b.click();
    return true;
  }
  /* 有對應按鈕的期間（YTD／1／3／5 年）優先用按鈕，讓按鈕狀態與圖表一致；
     06 沒有 10 年按鈕 → 直接設定下方區間滑桿。
     注意：剛加入基金時按鈕可能還沒渲染，故先等幾輪再退回滑桿，避免按鈕狀態與圖表不一致 */
  function tryApply(n){
    var years = parseInt(period, 10);
    if (period === 'YTD') return clickButton('YTD') || (n > 6 ? setRange(1) : false);
    if (years === 1 || years === 3 || years === 5){
      if (clickButton(years + '年')) return true;
      if (n <= 5) return false;              // 先等按鈕出現
    }
    return setRange(years);
  }
  function applyPeriod(){
    if (!period) return;
    var n = 0;
    var t = setInterval(function(){
      n++;
      if (periodDone || n > 15){ clearInterval(t); return; }
      if (tryApply(n)){
        periodDone = true;
        clearInterval(t);
        setTimeout(scrollToCharts, 600);
      }
    }, 400);
  }

  timer = setInterval(function(){
    tries++;
    if (!clickedAll){
      var all = byText('全部基金');
      if (all){ all.click(); clickedAll = true; }
    }
    var inp = document.querySelector('#fund-search');
    if (inp){
      if (inp.value !== code) setInput(inp, code);
      var btn = suggest();
      if (btn){
        btn.click();
        added = true;
        clearInterval(timer);
        cleanup();
        setTimeout(applyPeriod, 700);
        setTimeout(scrollToCharts, 1200);
        setTimeout(scrollToCharts, 2400);
        return;
      }
    }
    if (tries > 50 || (added && tries > 20)) clearInterval(timer);
  }, 400);

  window.addEventListener('load', function(){ setTimeout(cleanup, 4000); });
})();
"""

s = io.open(TARGET, encoding="utf-8", newline="").read()
removed = False
if MARKER in s:
    print("已是最新版本，略過")
    sys.exit(0)

# 移除舊版本注入（V1 及更早）
s, n = re.subn(r"<script>\s*/\* HUB_FUND_DEEPLINK_V\d+.*?</script>", "", s, flags=re.S)
if n:
    removed = True

idx = s.rfind("</body>")
if idx < 0:
    sys.exit("找不到 </body>，中止")
s = s[:idx] + "<script>" + JS + "</script>" + s[idx:]
io.open(TARGET, "w", encoding="utf-8", newline="").write(s)
print(f"{'已替換舊版；' if removed else ''}已注入 deep link 腳本 {MARKER}（{len(JS)} chars）→ {os.path.basename(TARGET)}")
