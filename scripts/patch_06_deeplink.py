#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 頁：支援 deep link `?fund=CODE`（由基金月榜點基金名進來）。
行為：等 React 掛載 → 先把篩選切回「全部基金」→ 在 #fund-search 輸入代號 →
      點第一個候選（加入組合）→ 捲到「情景估算」走勢圖 → 清掉網址參數。
冪等：已注入則跳過（以 marker 判斷）。
用法：python patch_06_deeplink.py
"""
import io, os, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html")
MARKER = "HUB_FUND_DEEPLINK_V1"

JS = """
/* HUB_FUND_DEEPLINK_V1：由基金月榜 ?fund=CODE 直接帶入並捲到走勢圖 */
(function(){
  var m = /[?&]fund=([A-Za-z]{1,2}\\d{2})\\b/.exec(location.search);
  if (!m) return;
  var code = m[1].toUpperCase();
  var tries = 0, clickedAll = false, added = false, timer;
  function byText(txt){
    return Array.prototype.slice.call(document.querySelectorAll('button'))
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
        setTimeout(scrollToCharts, 1000);
        setTimeout(scrollToCharts, 2200);
        return;
      }
    }
    if (tries > 50 || (added && tries > 20)) clearInterval(timer);
  }, 400);
  window.addEventListener('load', function(){ setTimeout(cleanup, 4000); });
})();
"""

s = io.open(TARGET, encoding="utf-8", newline="").read()
if MARKER in s:
    print("已注入過，略過")
    sys.exit(0)

idx = s.rfind("</body>")
if idx < 0:
    sys.exit("找不到 </body>，中止")
s = s[:idx] + "<script>" + JS + "</script>" + s[idx:]
io.open(TARGET, "w", encoding="utf-8", newline="").write(s)
print(f"已注入 deep link 腳本（{len(JS)} chars）→ {os.path.basename(TARGET)}")
