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
MARKER = "HUB_ANNUAL_RETURNS_V10"

JS = r"""
/* HUB_ANNUAL_RETURNS_V10：年度回报区块（组合总览／逐只基金，跟随 06 的切换钮与语言） */
(function(){
  if (window.__HUB_ANNUAL_V1__) return; window.__HUB_ANNUAL_V1__ = 1;

  var CSS =
    '.hub-annual{border-top:1px solid #dfd3c2;margin:24px 0 0;padding:20px 0 0;' +
      'font-family:"Noto Sans TC",ui-sans-serif,system-ui,sans-serif;color:#202124}' +
    '.hub-annual-eyebrow{display:flex;align-items:center;gap:7px;margin:0 0 5px;font-size:10px;font-weight:800;' +
      'letter-spacing:1.5px;line-height:15px;color:#9b1730}' +
    '.hub-annual-eyebrow span{display:block;width:20px;height:1px;background:#c8a85b;flex:0 0 auto}' +
    '.hub-annual-title{margin:0;font-family:Georgia,"Noto Serif TC",serif;font-size:20px;font-weight:500;line-height:30px;color:#202124}' +
    '.hub-annual-chart{position:relative;margin:18px 0 0;padding-left:42px}' +
    '.hub-annual-plot{position:relative;height:170px}' +
    '.hub-annual-grid{position:absolute;left:0;right:0;height:1px;background:#eadfce}' +
    '.hub-annual-zero{position:absolute;left:0;right:0;height:1px;background:#dfd3c2}' +
    '.hub-annual-ylab{position:absolute;left:0;width:36px;text-align:right;font-size:10px;line-height:1;color:#938878}' +
    '.hub-annual-col{position:absolute;top:0;bottom:0}' +
    '.hub-annual-bar{position:absolute;left:14%;right:14%;border-radius:3px}' +
    '.hub-annual-x{display:flex;margin:7px 0 0 42px}' +
    '.hub-annual-x span{flex:1;text-align:center;font-size:11px;font-weight:400;color:#74695d}' +
    '.hub-annual-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;margin-top:9px}' +
    '.hub-annual-card{background:#f9f2e7;border-top:2px solid #c8a85b;padding:8px}' +
    '.hub-annual-card b{display:block;font-size:10px;font-weight:700;line-height:15px;color:#8f0d25}' +
    '.hub-annual-card span{display:block;margin-top:2px;font-family:Georgia,serif;font-size:15px;font-weight:400;line-height:22.5px;color:#403126}' +
    '.hub-annual-dca{margin:12px 0 0;font-size:12px;line-height:1.7;color:#6b6d70}' +
    '.hub-annual table{width:100%;border-collapse:collapse;margin-top:16px}' +
    '.hub-annual th,.hub-annual td{border-bottom:1px solid #e7d6be;padding:8px;text-align:right;white-space:nowrap;' +
      'font-family:Georgia,serif;font-size:15px;font-weight:400;color:#403126}' +
    '.hub-annual th:first-child,.hub-annual td:first-child{text-align:left;white-space:normal;' +
      'font-family:"Noto Sans TC",ui-sans-serif,system-ui,sans-serif;font-size:13px}' +
    '.hub-annual thead th{font-family:"Noto Sans TC",ui-sans-serif,system-ui,sans-serif;font-size:10px;font-weight:700;color:#8f0d25}';

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

  function niceTicks(lo, hi, count){
    var span = (hi - lo) || 1;
    var raw = span / count;
    var mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10));
    var norm = raw / mag;
    var step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * mag;
    var start = Math.floor(lo / step) * step, end = Math.ceil(hi / step) * step;
    var ticks = [];
    for (var v = start; v <= end + step / 2; v += step) ticks.push(Math.round(v * 1000) / 1000);
    return ticks;
  }

  function renderOverview(box){
    var YS = years();
    var vals = YS.map(function(y){ return portValue(y, 0); });
    var ratios = YS.map(function(y){ return portValue(y, 1); });
    var finite = vals.filter(function(v){ return v !== null && v !== undefined && !isNaN(v); });
    var lo = Math.min.apply(null, [0].concat(finite));
    var hi = Math.max.apply(null, [0].concat(finite));
    var ticks = niceTicks(lo, hi, 4);
    var tMin = ticks[0], tMax = ticks[ticks.length - 1];
    var H = 170;
    var Y = function(v){ return (tMax - v) / ((tMax - tMin) || 1) * H; };

    var chart = el('div', 'hub-annual-chart');
    var plot = el('div', 'hub-annual-plot');
    ticks.forEach(function(t){
      var g = el('div', 'hub-annual-grid');
      g.style.top = Math.round(Y(t)) + 'px';
      plot.appendChild(g);
      var lab = el('div', 'hub-annual-ylab');
      lab.textContent = Math.round(t) + '%';
      lab.style.top = Math.round(Y(t) - 5) + 'px';
      chart.appendChild(lab);
    });
    var zl = el('div', 'hub-annual-zero');
    zl.style.top = Math.round(Y(0)) + 'px';
    plot.appendChild(zl);

    vals.forEach(function(v, i){
      var isN = (v === null || v === undefined || isNaN(v));
      var col = el('div', 'hub-annual-col');
      col.style.left = (i * 100 / YS.length) + '%';
      col.style.width = (100 / YS.length) + '%';
      var bar = el('div', 'hub-annual-bar');
      bar.style.background = isN ? '#cbbfae' : (v >= 0 ? '#8f0d25' : '#b77a45');
      var y0 = Y(0);
      if (isN){
        bar.style.top = Math.round(y0) + 'px';
        bar.style.height = '2px';
      } else {
        var yv = Y(v);
        if (v >= 0){ bar.style.top = Math.round(yv) + 'px'; bar.style.height = Math.max(2, Math.round(y0 - yv)) + 'px'; }
        else { bar.style.top = Math.round(y0) + 'px'; bar.style.height = Math.max(2, Math.round(yv - y0)) + 'px'; }
      }
      col.appendChild(bar);
      plot.appendChild(col);
    });
    chart.appendChild(plot);
    box.appendChild(chart);

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

  /* ── 列印版：06 是按鈕開新視窗、寫入自己組的 HTML 模板（無 @media print），
        因此在 window.open 之後、等文件寫完，把年度回報插到「各期间表现」卡片後面 ── */
  function esc(t){ return String(t).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

  function buildPrintHTML(){
    var YS = years();
    var vals = YS.map(function(y){ return portValue(y, 0); });
    var finite = vals.filter(function(v){ return v !== null && v !== undefined && !isNaN(v); });
    var lo = Math.min.apply(null, [0].concat(finite));
    var hi = Math.max.apply(null, [0].concat(finite));
    var ticks = niceTicks(lo, hi, 4);
    var tMin = ticks[0], tMax = ticks[ticks.length - 1];
    var X0 = 46, X1 = 704, Y0 = 12, Y1 = 138;
    var Y = function(v){ return Y0 + (tMax - v) / ((tMax - tMin) || 1) * (Y1 - Y0); };
    var step = (X1 - X0) / Math.max(1, YS.length);
    var svg = ['<svg class="chart-svg" viewBox="0 0 720 180" role="img" aria-label="组合年度回报 2021-2025">'];
    ticks.forEach(function(t){
      if (t === 0) return;
      svg.push('<line x1="' + X0 + '" x2="' + X1 + '" y1="' + Y(t).toFixed(1) + '" y2="' + Y(t).toFixed(1) + '" class="grid"/>');
      svg.push('<text x="4" y="' + (Y(t) + 3.5).toFixed(1) + '">' + Math.round(t) + '%</text>');
    });
    svg.push('<line x1="' + X0 + '" x2="' + X1 + '" y1="' + Y(0).toFixed(1) + '" y2="' + Y(0).toFixed(1) + '" class="baseline"/>');
    svg.push('<text x="4" y="' + (Y(0) + 3.5).toFixed(1) + '">0%</text>');
    vals.forEach(function(v, i){
      var cx = X0 + step * (i + 0.5);
      var bw = Math.max(10, step * 0.5);
      var isN = (v === null || v === undefined || isNaN(v));
      if (isN){
        svg.push('<text x="' + cx.toFixed(1) + '" y="' + (Y(0) - 4).toFixed(1) + '" text-anchor="middle" class="na">N/A</text>');
      } else {
        var y0 = Y(0), yv = Y(v), top = Math.min(y0, yv), h = Math.max(2, Math.abs(yv - y0));
        svg.push('<rect x="' + (cx - bw / 2).toFixed(1) + '" y="' + top.toFixed(1) + '" width="' + bw.toFixed(1) +
                 '" height="' + h.toFixed(1) + '" rx="3" fill="' + (v >= 0 ? '#8f0d25' : '#b77a45') + '"/>');
        svg.push('<text x="' + cx.toFixed(1) + '" y="' + ((v >= 0 ? top - 4 : top + h + 11)).toFixed(1) +
                 '" text-anchor="middle" class="bar-value">' + pct(v) + '</text>');
      }
      svg.push('<text x="' + cx.toFixed(1) + '" y="166" text-anchor="middle" class="bar-label">' + YS[i] + '</text>');
    });
    svg.push('</svg>');

    var cards = YS.map(function(y, i){
      return '<section class="metric"><span>' + y + '</span><strong>' + pct(vals[i]) + '</strong>' +
             '<small>年度回报</small></section>';
    }).join('');

    return '<article class="chart-card wide hub-annual-print"><h3>年度回报 ' +
           (YS.length ? (YS[0] + '–' + YS[YS.length - 1]) : '') + '</h3>' + svg.join('') + '</article>' +
           '<div class="metric-grid hub-annual-print">' + cards + '</div>';
  }

  function printTarget(doc){
    var hs = Array.prototype.slice.call(doc.querySelectorAll('article.chart-card h3'));
    var h = hs.filter(function(x){ return /各期[间間]\s*表现|各期[间間]\s*表現/.test((x.textContent || '').trim()); })[0];
    return h ? h.closest('article') : null;
  }

  function watchPrintWindow(w){
    var tries = 0;
    var t = setInterval(function(){
      tries++;
      try {
        var doc = w.document;
        if (doc && doc.body && !doc.querySelector('.hub-annual-print')){
          var art = printTarget(doc);
          if (art) art.insertAdjacentHTML('afterend', buildPrintHTML());
        }
      } catch (e) {}
      if (tries > 60) clearInterval(t);
    }, 120);
  }

  function hookPrint(){
    if (window.__hubAnnualPrintHooked) return;
    window.__hubAnnualPrintHooked = 1;
    var orig = window.open;
    window.open = function(){
      var w = orig.apply(window, arguments);
      try { if (w && w.document) watchPrintWindow(w); } catch (e) {}
      return w;
    };
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
        var eb = el('p', 'hub-annual-eyebrow');
        eb.appendChild(el('span'));
        eb.appendChild(document.createTextNode(' 06 / CALENDAR-YEAR RETURNS'));
        head.appendChild(eb);
        var YS = years();
        head.appendChild(el('h3', 'hub-annual-title',
          '年度回报 ' + (YS.length ? (YS[0] + '–' + YS[YS.length - 1]) : '')));
        return head;
      })());
      sec.appendChild(el('div', 'hub-annual-body'));
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

  hookPrint();
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
