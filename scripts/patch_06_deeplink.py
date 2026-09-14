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
MARKER = "HUB_FUND_DEEPLINK_V2"

JS = """
/* HUB_FUND_DEEPLINK_V2：由基金月榜 ?fund=CODE&y=1|3|5 帶入基金並設定走勢圖期間 */
(function(){
  var m = /[?&]fund=([A-Za-z]{1,2}\\d{2})\\b/.exec(location.search);
  if (!m) return;
  var code = m[1].toUpperCase();
  var ym = /[?&]y=([1-9]\\d*)\\b/.exec(location.search);
  var periodLabel = ym ? (ym[1] + '年') : null;
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
        setTimeout(applyPeriod, 800);
        setTimeout(scrollToCharts, 1200);
        setTimeout(scrollToCharts, 2400);
        return;
      }
    }
    if (tries > 50 || (added && tries > 20)) clearInterval(timer);
  }, 400);

  /* 期間：把 1/3/5 轉成 06 的「1年/3年/5年」並點擊（限情景估算區塊內，避免誤點） */
  function applyPeriod(){
    if (!periodLabel) return;
    var n = 0;
    var t = setInterval(function(){
      n++;
      if (periodDone || n > 12){ clearInterval(t); return; }
      var sec = chartSection();
      var b = byText(periodLabel, sec);
      if (b){
        if (!b.classList.contains('active')) b.click();
        periodDone = true;
        clearInterval(t);
        setTimeout(scrollToCharts, 600);
      }
    }, 400);
  }
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
print(f"{'已替換舊版；' if removed else ''}已注入 deep link 腳本 V2（{len(JS)} chars）→ {os.path.basename(TARGET)}")
