#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
06 頁注入「年度回報」區塊（06 / CALENDAR-YEAR RETURNS）。
- 位置：緊接在「05 / CROSS-PERIOD SUMMARY 各期間表現」區塊之後（runtime 插入，實測可存活於 React 重繪）
- 跟隨 06 現有的「組合總覽／逐隻基金」與「一次性投入／每月月初定投」狀態
- 文案一律寫簡體，由 06 自己的繁簡引擎轉換；漲跌色用 06 的 .gain/.loss（隨語言自動切換）
- 資料：./data/annual-returns.js（由 build_annual_returns.py 產生）
用法：python patch_06_annual.py
"""
import io, os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGET = os.path.join(HERE, "_deploy-workspace", "06-fund-portfolio-workbench.html")
MARKER = "HUB_ANNUAL_RETURNS_V3"

JS = r"""
/* HUB_ANNUAL_RETURNS_V3：年度回报区块（组合总览／逐只基金，跟随 06 的切换钮与语言） */
(function(){
  if (window.__HUB_ANNUAL_V1__) return; window.__HUB_ANNUAL_V1__ = 1;

  var CSS =
    '.hub-annual{background:#fffdf8;border:1px solid var(--hub-line,#e3dccd);border-radius:14px;padding:22px 24px;margin:20px 0 0}' +
    '.hub-annual-eyebrow{margin:0;font-size:11px;letter-spacing:.12em;font-weight:800;color:var(--hub-red,#8f0d25)}' +
    '.hub-annual-title{margin:6px 0 0;font-size:19px;font-weight:800;color:var(--hub-ink,#24211e)}' +
    '.hub-annual-sub{margin:8px 0 0;font-size:12.5px;line-height:1.7;color:var(--hub-gray,#6b6d70)}' +
    '.hub-annual-plot{position:relative;height:170px;margin:20px 0 0;border-bottom:1px solid var(--hub-line,#e3dccd)}' +
    '.hub-annual-zero{position:absolute;left:0;right:0;height:1px;background:var(--hub-line,#e3dccd)}' +
    '.hub-annual-bar{position:absolute;left:12%;right:12%;background:currentColor;border-radius:3px}' +
    '.hub-annual-bar.na{opacity:.22}' +
    '.hub-annual-x{display:flex;margin-top:6px}' +
    '.hub-annual-x span{flex:1;text-align:center;font-size:12px;color:var(--hub-gray,#6b6d70)}' +
    '.hub-annual-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(112px,1fr));gap:10px;margin-top:16px}' +
    '.hub-annual-card{background:#f7f3ea;border-radius:10px;padding:10px 12px}' +
    '.hub-annual-card b{display:block;font-size:11px;font-weight:700;color:var(--hub-gray,#6b6d70)}' +
    '.hub-annual-card span{display:block;margin-top:3px;font-size:16px;font-weight:800}' +
    '.hub-annual-dca{margin:14px 0 0;font-size:12.5px;line-height:1.8;color:var(--hub-gray,#6b6d70)}' +
    '.hub-annual-foot{margin:14px 0 0;font-size:11.5px;line-height:1.7;color:var(--hub-gray,#6b6d70)}' +
    '.hub-annual table{width:100%;border-collapse:collapse;margin-top:16px}' +
    '.hub-annual th,.hub-annual td{border-bottom:1px solid var(--hub-line,#e3dccd);padding:9px 8px;font-size:13px;text-align:right;white-space:nowrap}' +
    '.hub-annual th:first-child,.hub-annual td:first-child{text-align:left;white-space:normal}' +
    '.hub-annual thead th{font-size:12px;font-weight:700;color:var(--hub-gray,#6b6d70)}' +
    '@media (max-width:700px){.hub-annual-cards{grid-template-columns:repeat(2,minmax(0,1fr))}}';

  function injectStyle(){
    if (document.getElementById('hub-annual-css')) return;
    var st = document.createElement('style');
    st.id = 'hub-annual-css';
    st.textContent = CSS;
    document.head.appendChild(st);
  }

  function years(){ return ((window.__ANNUAL__ || {}).meta || {}).years || []; }
  function dataFor(code){ return ((window.__ANNUAL__ || {}).funds || {})[code] || null; }
  function pct(v){
    if (v === null || v === undefined || isNaN(v)) return 'N/A';
    return (v >= 0 ? '+' : '-') + Math.abs(v).toFixed(1) + '%';
  }
  function clsOf(v){
    if (v === null || v === undefined || isNaN(v)) return 'na';
    return v >= 0 ? 'gain' : 'loss';
  }

  function portfolio(){
    var out = [];
    // aria-label 會隨語言變（組合權重／组合权重）→ 只認「基金代號 + 空白」開頭的數字輸入
    Array.prototype.forEach.call(document.querySelectorAll('input[type=number][aria-label]'), function(inp){
      var m = /^([A-Z]{1,2}[0-9]{2})\s/.exec(inp.getAttribute('aria-label') || '');
      if (!m) return;
      var row = inp, depth = 0;
      while (row && row.parentElement && depth < 6){
        row = row.parentElement; depth++;
        if (((row.innerText || '').length) > 12) break;
      }
      var txt = row ? (row.innerText || '').replace(/\s+/g, ' ').trim() : '';
      var nm = /^(.+?)\s+[A-Z]{1,2}[0-9]{2}\b/.exec(txt);
      out.push({ code: m[1], weight: (parseFloat(inp.value) || 0), name: nm ? nm[1] : m[1] });
    });
    if (out.length && out.reduce(function(a, b){ return a + (b.weight || 0); }, 0) <= 0){
      out.forEach(function(x){ x.weight = 1; });
    }
    return out;
  }

  function modeButtons(){
    // .investment-mode-switch 是語言無關的容器 class；內含 [一次性投入, 每月月初定投]
    var sw = document.querySelector('.investment-mode-switch');
    return sw ? Array.prototype.slice.call(sw.querySelectorAll('button')) : [];
  }
  function dcaOn(){
    var bs = modeButtons();
    return bs.length >= 2 ? bs[1].classList.contains('active') : false;
  }
  function viewName(){
    var head = document.querySelector('.cross-period-section .performance-head');
    if (!head) return 'overview';
    var bs = Array.prototype.slice.call(head.querySelectorAll('button'));
    return (bs.length >= 2 && bs[1].classList.contains('active')) ? 'perfund' : 'overview';
  }

  function portValue(year, field){
    var pf = portfolio();
    if (!pf.length) return null;
    var tw = 0, acc = 0;
    pf.forEach(function(f){
      var d = dataFor(f.code);
      if (!d) return;
      var row = d[String(year)];
      if (!row) return;
      var v = row[field];
      if (v === null || v === undefined || isNaN(v)) return;
      tw += f.weight; acc += f.weight * v;
    });
    return tw > 0 ? acc / tw : null;
  }

  function el(tag, cls, text){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function renderOverview(box){
    var YS = years();
    var vals = YS.map(function(y){ return portValue(y, 0); });
    var ratios = YS.map(function(y){ return portValue(y, 1); });
    var finite = vals.filter(function(v){ return v !== null && v !== undefined && !isNaN(v); });
    var top = Math.max.apply(null, [0].concat(finite));
    var bot = Math.min.apply(null, [0].concat(finite));
    if (finite.length === 0){ top = 1; bot = 0; }
    var span = (top - bot) || 1, H = 170;
    var y0 = top / span * H;

    var plot = el('div', 'hub-annual-plot');
    plot.appendChild((function(){ var z = el('div', 'hub-annual-zero'); z.style.top = Math.round(y0) + 'px'; return z; })());
    vals.forEach(function(v){
      var isN = (v === null || v === undefined || isNaN(v));
      var bar = el('div', 'hub-annual-bar ' + clsOf(v));
      if (isN){
        bar.style.top = Math.round(y0) + 'px';
        bar.style.height = '2px';
      } else {
        var yv = (top - v) / span * H;
        if (v >= 0){ bar.style.top = Math.round(yv) + 'px'; bar.style.height = Math.max(2, Math.round(y0 - yv)) + 'px'; }
        else { bar.style.top = Math.round(y0) + 'px'; bar.style.height = Math.max(2, Math.round(yv - y0)) + 'px'; }
      }
      plot.appendChild(bar);
    });
    box.appendChild(plot);

    var ax = el('div', 'hub-annual-x');
    YS.forEach(function(y){ ax.appendChild(el('span', '', String(y))); });
    box.appendChild(ax);

    var cards = el('div', 'hub-annual-cards');
    YS.forEach(function(y, i){
      var c = el('div', 'hub-annual-card');
      c.appendChild(el('b', '', String(y)));
      c.appendChild(el('span', clsOf(vals[i]), pct(vals[i])));
      cards.appendChild(c);
    });
    box.appendChild(cards);

    if (dcaOn()){
      var parts = YS.map(function(y, i){
        var r = ratios[i];
        var p = (r === null || r === undefined || isNaN(r)) ? 'N/A' : pct((r - 1) * 100);
        return y + ' ' + p;
      });
      var d = el('p', 'hub-annual-dca');
      d.textContent = '你的定投实际（每月月初定额）：' + parts.join('　·　');
      box.appendChild(d);
    }
  }

  function renderPerFund(box){
    var YS = years();
    var pf = portfolio();
    var table = el('table');
    var thead = el('thead');
    var tr = el('tr');
    tr.appendChild(el('th', '', '基金'));
    YS.forEach(function(y){ tr.appendChild(el('th', '', String(y))); });
    tr.appendChild(el('th', '', '5 年累计'));
    thead.appendChild(tr);
    table.appendChild(thead);

    var tbody = el('tbody');
    if (!pf.length){
      var tr0 = el('tr'), td0 = el('td', '', '尚未加入基金');
      td0.setAttribute('colspan', String(YS.length + 2));
      tr0.appendChild(td0); tbody.appendChild(tr0);
    }
    pf.forEach(function(f){
      var d = dataFor(f.code);
      var tr2 = el('tr');
      tr2.appendChild(el('th', '', f.code + ' ' + f.name));
      var cum = 1, all = true;
      YS.forEach(function(y){
        var v = (d && d[String(y)]) ? d[String(y)][0] : null;
        if (v === null || v === undefined || isNaN(v)) all = false;
        else cum = cum * (1 + v / 100);
        var td = el('td', clsOf(v), pct(v));
        tr2.appendChild(td);
      });
      var cumV = all ? (cum - 1) * 100 : null;
      tr2.appendChild(el('td', clsOf(cumV), pct(cumV)));
      tbody.appendChild(tr2);
    });
    table.appendChild(tbody);
    box.appendChild(table);
  }

  function render(){
    injectStyle();
    var sec = document.querySelector('.hub-annual');
    if (!sec){
      var cross = document.querySelector('.cross-period-section');
      if (!cross || !cross.parentElement) return false;
      sec = el('section', 'hub-annual');
      sec.setAttribute('data-hub-annual', 'v1');
      sec.appendChild((function(){
        var head = el('div', 'hub-annual-head');
        head.appendChild(el('p', 'hub-annual-eyebrow', '06 / CALENDAR-YEAR RETURNS'));
        var YS = years();
        head.appendChild(el('h3', 'hub-annual-title',
          '年度回报 ' + (YS.length ? (YS[0] + '–' + YS[YS.length - 1]) : '')));
        head.appendChild(el('p', 'hub-annual-sub',
          '按日历年计算（1/1–12/31）；派息基金含派息（实际总报酬），其余为净值回报。资料不足显示 N/A。'));
        return head;
      })());
      sec.appendChild(el('div', 'hub-annual-body'));
      sec.appendChild(el('p', 'hub-annual-foot',
        '年度回报为基金口径（年初一次性），可与基金年报直接对照；资料来源：AIA 官方日频 NAV 与派息纪录。'));
      cross.parentElement.insertBefore(sec, cross.nextSibling);
    }
    var body = sec.querySelector('.hub-annual-body');
    if (!body) return false;
    body.innerHTML = '';
    if (viewName() === 'perfund') renderPerFund(body); else renderOverview(body);
    return true;
  }

  var timer = null;
  function schedule(){
    clearTimeout(timer);
    timer = setTimeout(function(){
      try { render(); } catch (e) {}
    }, 140);
  }

  function attach(){
    var mo = new MutationObserver(schedule);
    var head = document.querySelector('.cross-period-section .performance-head');
    if (head) mo.observe(head, { subtree: true, attributes: true, attributeFilter: ['class'] });
    var inp = document.querySelector('input[type=number][aria-label]');
    var listWrap = inp ? (inp.closest('.results-row') ? inp.closest('.results-row').parentElement : null) : null;
    if (listWrap) mo.observe(listWrap, { childList: true, subtree: true });
    var mb = modeButtons();
    if (mb.length) mo.observe(mb[0].parentElement, { subtree: true, attributes: true, attributeFilter: ['class'] });
    document.addEventListener('input', function(e){
      var t = e.target;
      var a = (t && t.getAttribute) ? (t.getAttribute('aria-label') || '') : '';
      var isWeight = t && t.type === 'number' && /^[A-Z]{1,2}[0-9]{2}\s/.test(a);
      var isAmount = t && t.type === 'number' && /期初|投入|principal/i.test(a);
      if (isWeight || isAmount) schedule();
    }, true);
    document.addEventListener('click', function(){ setTimeout(schedule, 60); }, true);
  }

  var tries = 0;
  function boot(){
    tries++;
    var ready = !!window.__ANNUAL__ && !!document.querySelector('.cross-period-section');
    if (ready){ render(); attach(); return; }
    if (tries < 60) setTimeout(boot, 400);
  }
  if (window.__ANNUAL__){ boot(); }
  else {
    var s = document.createElement('script');
    s.src = './data/annual-returns.js';
    s.onload = boot;
    s.onerror = function(){ boot(); };
    document.head.appendChild(s);
  }
  window.addEventListener('load', function(){ setTimeout(schedule, 800); });
})();
"""

s = io.open(TARGET, encoding="utf-8", newline="").read()
if MARKER in s:
    print("已是最新版本，略過")
    sys.exit(0)

s, n = re.subn(r"<script>\s*/\* HUB_ANNUAL_RETURNS_V\d+.*?</script>", "", s, flags=re.S)

idx = s.rfind("</body>")
if idx < 0:
    sys.exit("找不到 </body>，中止")
s = s[:idx] + "<script>" + JS + "</script>" + s[idx:]
io.open(TARGET, "w", encoding="utf-8", newline="").write(s)
print(f"{'已替換舊版；' if n else ''}已注入年度回報區塊 {MARKER}（{len(JS)} chars）→ {os.path.basename(TARGET)}")
