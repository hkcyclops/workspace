#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金月榜 2.0 產生器 → fund-ranking.html（繁）／fund-ranking-sc.html（簡）／fund-ranking-YYYY-MM*.html（月份存檔）
（2026-09-15 起**取代 v1 月榜**，沿用舊版檔名：舊分享連結與 06 FAB 都指向 fund-ranking.html）
資料：data/rank2.js（由 build_rank2_data.py 產生；口徑與正式月榜完全相同）

功能：
  · 分頁 派息／非派息　· 檢視 跨期比較／明細　· 類別 chips　· 期間 chips（決定排名基準，固定 Top 10）
  · 名次含與上月同榜的 ▲▼ 變化　· 基準欄金色高亮
  · hover 基金名 → 資訊卡（幣種／類別／風險指標／走勢）；hover 期間數值 → 該期間走勢與指標
  · 點基金名 → 06 走勢圖（?fund=CODE&y=期間）；代號僅為標籤、不可點
  · 手機（≤700px）：只留 名次／基金／基準期間 三欄＋tap 展開明細，表頭 sticky、不再橫向捲動
  · 繁簡雙版、語言跟隨 06（localStorage: calculator-hub-language）、漲跌色依語言（繁綠漲紅跌／簡紅漲綠跌）
  · URL 狀態：?tab=div|nav&cat=&basis=&view=
用法：python build_rank2.py
"""
import io, os, sys, json

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPLOY = os.path.join(HERE, "_deploy-workspace")
D2 = os.path.join(HERE, "scripts")

raw = io.open(os.path.join(DEPLOY, "data", "rank2.js"), encoding="utf-8").read()
DATA = raw.split("=", 1)[1].rstrip(";\n")

CSS = """
:root{--page:#f4efe5;--surface:#fffdf8;--surface-3:#f9f2e7;--head:#f0e8dc;--gold:#c8a85b;
 --line:#e1d6c4;--line-2:#eee3d4;--line-3:#d8c8b3;--ink:#342d28;--ink-2:#5e5145;--th-ink:#49372f;
 --red:#8f0d25;--gray:#8c7d70;--up:#347558;--down:#b13446}
html[data-lang="tr"]{--up:#347558;--down:#b13446}
html[data-lang="sc"]{--up:#b13446;--down:#347558}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);
 font:14.5px/1.5 "Noto Sans TC", ui-sans-serif, system-ui, "Segoe UI", sans-serif}
.wrap{max-width:1200px;margin:0 auto;padding:30px clamp(14px,2.2vw,44px) 64px}
.masthead{border-bottom:2px solid var(--red);padding-bottom:14px;margin-bottom:16px;position:relative}
.eyebrow{margin:0;font-size:11.5px;letter-spacing:.16em;font-weight:800;color:var(--gray)}
h1{margin:6px 0 0;font-family:Georgia,"Noto Serif TC",serif;font-size:32px;font-weight:500;line-height:1.35}
.sub{margin:8px 0 0;font-size:14px;line-height:1.8;color:var(--ink-2)}
.langsw{position:absolute;right:0;top:0;display:inline-flex;align-items:center;background:#fff;
 border:1px solid #202124;border-radius:0;padding:2px}
.langsw-lbl{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:8px;font-weight:800;
 letter-spacing:.04em;color:#77797c;padding:0 5px 0 4px}
.langbtn{font-size:12px;font-weight:800;line-height:1.25;padding:4px 5px;min-width:28px;text-align:center;
 text-decoration:none;color:#6b6d70}
.langbtn:hover{color:var(--red)}
.langbtn.is-on{background:#202124;color:#fff}
.shotctx{display:none}
.mh-break{display:none}
.shotbar{display:flex;justify-content:flex-end;margin:9px 3px -5px}
.shotbtn{appearance:none;border:0;background:transparent;font:inherit;font-size:12.5px;color:var(--gray);
 cursor:pointer;padding:0 0 1px;border-bottom:1px dotted var(--line-3);white-space:nowrap}
.shotbtn:hover{color:var(--red);border-bottom-color:var(--red)}
.backlink{margin:8px 0 0;font-size:13.5px;line-height:1.6}
.backlink a{color:var(--red);text-decoration:none}
.tabs{display:flex;gap:0;border-bottom:2px solid var(--line-3);margin:22px 0 0;flex-wrap:wrap}
.tab{appearance:none;border:0;background:transparent;cursor:pointer;font:inherit;font-weight:700;
 color:var(--ink-2);padding:11px 18px;border-bottom:2px solid transparent;margin-bottom:-2px}
.tab b{font-family:Georgia,serif;color:var(--gray);font-weight:700;margin-left:6px}
.tab:hover{color:var(--red)}
.tab.is-on{color:var(--red);border-bottom-color:var(--red)}
/* 月份導覽（與 v1 一致） */
.monthnav{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:16px 0 0}
.mnav{border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);
 padding:7px 11px;font-size:13px;font-weight:700;text-decoration:none;display:inline-flex;align-items:center;gap:6px;line-height:1.4}
.mnav:hover{border-color:var(--red);color:var(--red)}
.mnav.off{opacity:.42;pointer-events:none}
.mnav-sel span{color:var(--gray);font-size:11.5px;font-weight:800;letter-spacing:.08em}
.mnav-sel select{border:0;background:transparent;color:inherit;font:inherit;font-weight:700;cursor:pointer;padding:0 2px}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px}
.row .lbl{font-size:11.5px;letter-spacing:.08em;color:var(--gray);font-weight:700;white-space:nowrap}
.chip{border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);border-radius:0;
 padding:6px 12px;font:inherit;font-size:13px;font-weight:700;cursor:pointer}
.chip b{font-family:Georgia,serif;font-weight:700;margin-left:5px;color:var(--red)}
.chip.on{background:var(--ink);border-color:var(--ink);color:#fff}
.chip.on b{color:inherit}
.chip.vw.on{background:var(--gold);border-color:var(--gold);color:#3b2c10}
.chip.period.on{background:var(--red);border-color:var(--red);color:#fff}
.card{background:var(--surface);border:1px solid var(--line);box-shadow:inset 0 2px var(--gold);margin:14px 0 0}
.wrapx{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14.5px}
th,td{border-bottom:1px solid var(--line-2);padding:10px 12px;text-align:right;white-space:nowrap;line-height:1.4}
th:nth-child(-n+3),td:nth-child(-n+3){text-align:left}
thead th{background:var(--head);color:var(--th-ink);font-size:13px;font-weight:700;position:sticky;top:0;z-index:2;
 font-family:Georgia,"Noto Serif TC",serif}
thead th.basis{background:var(--gold);color:#3b2c10}
tbody tr{cursor:default}
/* 只有真的掛了 hover 的格（JS 加 .hv）才有提示：游標 help ＋ 單格高亮（桌機限定，.hv 只在 !TOUCH 時加） */
td.hv{cursor:help}
td.hv:hover{background:#fdfaf3;box-shadow:inset 0 0 0 1px rgba(200,168,91,.7)}
/* ③B 表頭小折線：提示「這欄可 hover 看走勢」。預設隱藏，只在有滑鼠的裝置顯示；
   顏色用 currentColor → 在金色基準表頭上自動變深色；截圖模式隱藏（保持乾淨） */
.hicon{display:none;width:15px;height:9px;margin-left:5px;vertical-align:-1px;opacity:.55}
@media (hover:hover) and (pointer:fine){ .hicon{display:inline-block} }
html.shot .hicon{display:none}
/* 臨時：圖示對照列（?iconcompare=1，定案後連同 ICONS 多餘項一起移除） */
.iconcmp{display:flex;align-items:center;gap:6px;margin:9px 3px 0;flex-wrap:wrap}
.iconcmp .lbl{font-size:11.5px;letter-spacing:.08em;color:var(--gray);font-weight:700}
.iconcmp button{appearance:none;border:1px solid var(--line-3);background:var(--surface);color:var(--ink-2);
 font:inherit;font-size:11.5px;font-weight:700;padding:3px 7px;cursor:pointer;display:inline-flex;align-items:center;gap:5px}
.iconcmp button:hover{border-color:var(--red);color:var(--red)}
.iconcmp button.on{border-color:var(--red);color:var(--red);background:#fdf6e6}
.iconcmp .hicon{display:inline-block}   /* 對照列裡一律畫出來，不受 hover 媒體查詢限制 */
/* 觸控維持原狀：tap 時整列高亮（用戶決定不做 ②b，故保留這個模擬 hover 的殘留） */
html.touch tbody tr:hover td{background:#fdfaf3}
td.rank{white-space:nowrap}
td.rank .rk{font-family:Georgia,serif;font-weight:700}
td.rank .mv{font-size:11.5px;margin-left:5px}
td.rank .mv.up{color:var(--up)}td.rank .mv.down{color:var(--down)}
td.rank .mv.flat{color:var(--gray)}
td.rank .mv.new{color:#8a6a1f;background:#f7eed8;border-radius:4px;padding:1px 4px;font-size:10.5px}
td.name{white-space:normal;min-width:230px;font-size:13.5px;line-height:1.45}
td.name a{color:inherit;text-decoration:none}
td.cell-code{width:56px}
td.cell-code .code{font-family:Georgia,serif;font-weight:700;font-size:14.5px;color:var(--ink)}
td.cell-code a{color:inherit;text-decoration:none}
td.name .code{font-family:Georgia,serif;font-weight:700;font-size:14.5px;margin-right:5px;color:var(--ink)}
td.name .tag{color:var(--gray);font-size:11.5px;margin-left:4px}
td.num{font-family:Georgia,serif;font-weight:700;font-variant-numeric:tabular-nums}
.up{color:var(--up)}.down{color:var(--down)}.na{color:var(--gray)}
td.basis{background:#fbf6ea;font-weight:700}
.note{margin:10px 2px 0;font-size:12.5px;line-height:1.8;color:var(--gray)}
.foot{margin-top:26px;font-size:12.5px;line-height:1.9;color:var(--gray)}
/* hover 資訊卡 */
#hcard{position:fixed;z-index:60;width:296px;background:var(--surface);border:1px solid var(--line);
 border-radius:10px;box-shadow:0 10px 26px rgba(52,45,40,.16);padding:12px 14px;display:none}
#hcard .hc-t{font-size:13.5px;font-weight:700;line-height:1.4}
#hcard .hc-t .code{font-family:Georgia,serif;margin-right:5px}
#hcard .hc-m{margin-top:4px;font-size:11.5px;color:var(--gray)}
#hcard .hc-k{margin-top:8px;font-size:12px;line-height:1.7;color:var(--ink-2);
 display:grid;grid-template-columns:auto 1fr;gap:2px 10px}
#hcard .hc-k b{color:var(--gray);font-weight:400}
#hcard .hc-sp{margin-top:8px}
#hcard .hc-sp svg{display:block;width:100%;height:44px}
#hcard .hc-cap{margin-top:3px;font-size:11px;color:var(--gray)}
.spark{display:block;width:100%;height:100%}
.sp-bg{stroke:#e6dccd;stroke-width:1}
.sp-line{fill:none;stroke:#8f0d25;stroke-width:1.4}
.sp-dd{fill:rgba(143,13,37,.13)}
.sp-rc{fill:rgba(143,13,37,.06)}
.sp-pt{fill:#8f0d25}
.mrow{display:none}
html.touch tr.mrow{display:table-row}      /* 觸控（手機/平板含橫屏）點列可展開 */
html.touch tbody tr{cursor:pointer}
tr.mrow td{text-align:left;white-space:normal;background:var(--surface-3);
 border-bottom:2px solid var(--gold);font-size:12px;line-height:1.7;padding:9px 10px}
tr.mrow .cell.on{color:var(--red);font-weight:700}
.sp-cap{margin-top:3px;font-size:11.5px;line-height:1.4;color:var(--gray)}
.ms{white-space:nowrap;letter-spacing:.5px}
.ms .f{color:var(--gold)}      /* 實心星 */
.ms .e{color:var(--line-3)}    /* 空心星 */
.ms .na{color:var(--gray)}
/* 截圖模式（?shot=1 或按「截圖模式」）：隱藏工具列，讓 Top 10 在一張橫屏裡截完
   幾何前提：390px 高 ÷ (表頭+表頭列) 後每列只剩 ~23px → 基金名必須單行省略（table-layout:fixed） */
html.shot .eyebrow,html.shot .backlink,html.shot .monthnav,html.shot .tabs,
html.shot .row,html.shot .note,html.shot .foot,html.shot .langsw{display:none}
html.shot .wrap{position:relative;padding:6px 8px 6px}
html.shot .masthead{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:12px;padding-right:0;
 padding-bottom:5px;margin-bottom:5px;cursor:pointer}
html.shot .shotbar{position:absolute;right:8px;top:4px;margin:0}
html.shot .mh-break{display:none}   /* 截圖模式維持「標題+基準日+脈絡」單行 */
html.shot h1{font-size:18px;line-height:1.25;margin:0}
html.shot .sub{margin:0;font-size:12px;line-height:1.4}
html.shot .shotctx{display:inline;font-size:12px;color:var(--ink-2);font-weight:700}
html.shot .card{margin:0}
html.shot table{table-layout:fixed;font-size:12px}
html.shot th,html.shot td{padding:4px 8px;line-height:1.3}
html.shot thead th{font-size:11.5px}
html.shot thead th:nth-child(1),html.shot tbody tr:not(.mrow) td:nth-child(1){width:56px}
html.shot thead th:nth-child(2),html.shot tbody tr:not(.mrow) td:nth-child(2){width:48px}
html.shot thead th:nth-child(3),html.shot tbody tr:not(.mrow) td:nth-child(3){width:29%}
html.shot td.name{font-size:11.5px;line-height:1.3;min-width:0;display:table-cell;
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
html.shot td.cell-code .code{font-size:12px}
html.shot td.rank .rk{font-size:12.5px}
html.shot td.rank .mv{font-size:10.5px}
@media (max-width:700px){
 .wrap{padding:8px 8px 90px}
 .masthead{padding-bottom:8px;margin-bottom:8px}
 h1{font-size:19px}
  .eyebrow{font-size:10px;letter-spacing:.1em}
  .sub{margin:6px 0 0;font-size:12.5px;line-height:1.5}
  .foot{display:none}
  .tabs .tab{font-size:12.5px;padding:6px 11px}
 .row{margin-top:8px;gap:5px}
 .chip{font-size:11.5px;padding:4px 9px}
 .card{margin:8px 0 0}
 .wrapx{overflow:visible}
 table{min-width:0;table-layout:auto;font-size:12.5px}
 th,td{padding:7px 6px}
 thead th:first-child,tbody tr:not(.mrow) td:first-child{width:52px}
 thead th:nth-child(2),tbody tr:not(.mrow) td:nth-child(2){width:42px}
 td.cell-code{width:42px}
 tr.mrow td{width:auto !important}
 td.name{min-width:0;font-size:12.5px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
 td.name .tag{display:none}
 .mcol{display:none}
 tbody tr{cursor:pointer}
 tr.mrow{display:table-row}
 tr.mrow td{text-align:left;white-space:normal;background:var(--surface-3);
  border-bottom:2px solid var(--gold);font-size:12px;line-height:1.7;padding:9px 10px}
 tr.mrow .k{color:var(--gray);display:inline-block;min-width:52px}
 tr.mrow .g3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:3px 8px;margin-bottom:5px}
 tr.mrow .cell{white-space:nowrap}
 tr.mrow .line{margin-top:2px}
 tr.mrow .sp-wrap{height:34px;margin-top:4px}
}
@media (orientation:landscape) and (min-width:701px) and (max-width:1100px) and (max-height:600px){
 .wrap{padding:8px 8px 24px}
 .masthead{display:flex;flex-wrap:wrap;align-items:baseline;column-gap:14px;row-gap:1px;
  padding-right:100px;padding-bottom:6px;margin-bottom:8px}
 .mh-break{display:block;flex-basis:100%;height:0;margin:0}   /* 眉標+標題一行，返回/基準日/月份導覽換第二行 */
 .eyebrow{font-size:10.5px;letter-spacing:.12em}
 h1{font-size:19px;line-height:1.2;margin:0}
 .backlink{margin:0;font-size:12.5px}
 .sub{margin:0;font-size:12.5px;line-height:1.5}
 .monthnav{margin:0;gap:6px}
 .mnav{padding:5px 9px;font-size:12.5px}
 .mnav-sel span{font-size:10.5px}
 .tabs{margin:8px 0 0}
 .tab{padding:7px 13px}
 .row{display:inline-flex;margin:6px 16px 0 0;gap:5px;vertical-align:middle}
 .chip{font-size:11.5px;padding:4px 9px}
 .card{margin:6px 0 0}
 table{font-size:13px}
 th,td{padding:6px 8px}
 thead th{font-size:12px}
 td.name{min-width:150px;font-size:12.5px;line-height:1.35}
 .note{margin-top:8px;font-size:12px;line-height:1.6}
}
"""

JS = r"""
(function(){
  var D = window.__RANK2__, PL = {'YTD':'YTD','1':'1 年','3':'3 年','5':'5 年','10':'10 年'};
  var PAGE_LANG = '__LANGVAL__', OTHER_URL = '__OTHER__', SELF_URL = '__SELF__';
  /* 觸控判定：用手上有沒有滑鼠，不用寬度（iPad 橫屏 1024×768 也是觸控） */
  var TOUCH = !(window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)').matches);
  document.documentElement.classList.toggle('touch', TOUCH);
  var qs = new URLSearchParams(location.search);
  var S = {
    panel: (qs.get('tab')==='div'||qs.get('tab')==='nav') ? qs.get('tab') : 'div',
    cat:   qs.get('cat') || 'all',
    basis: qs.get('basis') || 'YTD',
    view:  qs.get('view') || 'cross',
    shot:  qs.get('shot') === '1',
    icon:  (qs.get('icon')||'').toUpperCase(),
    cmp:   qs.get('iconcompare') === '1'
  };
  var CURR = {'USD':'美元','HKD':'港元','RMB':'人民幣','CNY':'人民幣','AUD':'澳元','EUR':'歐元','GBP':'英鎊','JPY':'日圓','SGD':'新加坡元','NZD':'紐元','CAD':'加元','TWD':'新台幣'};
  var CATNAME = {}; D.cats.forEach(function(x){ CATNAME[x[0]] = x[1]; });

  function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function pct(v){ return (v===null||v===undefined||isNaN(v)) ? 'N/A' : (v>=0?'+':'-')+Math.abs(v).toFixed(1)+'%'; }
  function cls(v){ return (v===null||v===undefined||isNaN(v)) ? 'na' : (v>=0?'up':'down'); }
  function el(t,c,h){ var e=document.createElement(t); if(c) e.className=c; if(h!==undefined) e.innerHTML=h; return e; }
  function tag06(p){ return (p==='YTD') ? 'YTD' : String(p); }

  function pd(){ return D.panels[S.panel].p; }
  function periods(){ return D.panels[S.panel].periods; }
  function today(){ return pd()[S.basis] || pd()[periods()[0]]; }
  function codesOf(cat){
    var out=[], p=today();
    Object.keys(p).forEach(function(c){ if(cat==='all' || D.funds[c].cat===cat) out.push(c); });
    return out;
  }
  function rows(){
    var p=today(), list=codesOf(S.cat);
    list.sort(function(a,b){ return (p[b]?p[b].t:-1e9)-(p[a]?p[a].t:-1e9); });
    return list.slice(0, D.panels[S.panel].top[S.basis] || 10);
  }
  function prevRank(code){
    var P = D.prev && D.prev[S.panel] && D.prev[S.panel][S.basis];
    if(!P) return undefined;
    var m = P[S.cat] || P.all || {};
    return m[code];
  }
  function rankHTML(i, code){
    var r=i+1, pv=prevRank(code), mv;
    if(pv===undefined) mv='<span class="mv new">新進</span>';
    else if(pv>r) mv='<span class="mv up">▲'+(pv-r)+'</span>';
    else if(pv<r) mv='<span class="mv down">▼'+(r-pv)+'</span>';
    else mv='<span class="mv flat">–</span>';
    return '<span class="rk">'+r+'</span>'+mv;
  }
  /* ③B 表頭圖示：候選 A–E。?icon=X 指定；?iconcompare=1 顯示臨時對照列（定案後移除對照機制） */
  function svgI(inner){ return '<svg class="hicon" viewBox="0 0 16 9" aria-hidden="true">'+inner+'</svg>'; }
  var ICONS = {
    A: svgI('<polyline points="1,7.5 5,4 9,6 15,1.5" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'),
    B: svgI('<path d="M1.5 1 V8.5 H15" fill="none" stroke="currentColor" stroke-width="1" opacity=".6"/>'+
            '<polyline points="3,7 7,4.5 11,5.5 15,2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'),
    C: svgI('<rect x="1.5" y="6" width="3" height="4" fill="currentColor" opacity=".55"/>'+
            '<rect x="6.5" y="3.5" width="3" height="6.5" fill="currentColor" opacity=".55"/>'+
            '<rect x="11.5" y="1" width="3" height="9" fill="currentColor"/>'),
    D: svgI('<rect x="0.6" y="0.6" width="14.8" height="7.8" rx="1.5" fill="none" stroke="currentColor" stroke-width="1" opacity=".6"/>'+
            '<polyline points="2.5,7 6,4 10,5.5 14,2" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>'),
    E: svgI('<path d="M2 8 L13 2" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>'+
            '<path d="M13 2 L8.2 2.9 L9.1 7.7 Z" fill="currentColor"/>')
  };
  function hIcon(){ return ICONS[S.icon] || ICONS.A; }
  function linkURL(code){ return './06-fund-portfolio-workbench.html?fund='+code+'&y='+tag06(S.basis); }
  /* Morningstar 星級（0＝無評級 → 顯示「—」，與 06 的規則一致） */
  function starsHTML(code){
    var m=(D.funds[code]||{}).m||0;
    if(!m) return '<span class="ms" title="Morningstar 無評級"><span class="na">—</span></span>';
    var s='';
    for(var i=1;i<=5;i++) s+=(i<=m?'<span class="f">★</span>':'<span class="e">☆</span>');
    return '<span class="ms" title="Morningstar '+m+' 星">'+s+'</span>';
  }
  function codeHTML(code){
    /* 代號只是標籤，不可點（只有基金名才連到 06） */
    return '<span class="code">'+code+'</span>';
  }
  function nameHTML(code){
    var f=D.funds[code];
    var inner = esc(f.n)+(f.h?'<span class="tag">（對沖）</span>':'');
    /* 觸控上名稱不包連結：點名稱＝展開明細，進 06 走展開列裡的連結（避免誤觸跳走） */
    return TOUCH ? inner
      : '<a href="'+linkURL(code)+'" title="在 06 開啟 '+code+' 走勢圖（'+PL[S.basis]+'）">'+inner+'</a>';
  }

  /* ── 走勢圖（0–100 序列 + 回撤深/收復淺兩段）── */
  function sparkSVG(key, w, h){
    var d=D.spark[key]; if(!d||!d.v||d.v.length<2) return null;
    var v=d.v, n=v.length, W=w||300, H=h||44, pad=2;
    var X=function(i){ return pad + i*(W-2*pad)/(n-1); }, Y=function(x){ return H-pad - x*(H-2*pad)/100; };
    var pts=v.map(function(x,i){ return X(i)+','+Y(x); }).join(' ');
    var x0=X(Math.round((d.pk||0)*(n-1))), x1=X(Math.round((d.tr||0)*(n-1)));
    var x2=X(Math.round((d.rec!==null&&d.rec!==undefined?d.rec:1)*(n-1)));
    var dd='<rect class="sp-dd" x="'+x0+'" y="0" width="'+Math.max(0,x1-x0)+'" height="'+H+'"/>';
    var rc=(x2>x1)?'<rect class="sp-rc" x="'+x1+'" y="0" width="'+(x2-x1)+'" height="'+H+'"/>':'';
    return '<svg class="spark" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img" aria-label="期間走勢">'+
      '<line class="sp-bg" x1="0" y1="'+(H-pad)+'" x2="'+W+'" y2="'+(H-pad)+'"/>'+dd+rc+
      '<polyline class="sp-line" points="'+pts+'"/>'+
      '<circle class="sp-pt" cx="'+X(n-1)+'" cy="'+Y(v[n-1])+'" r="2.4"/></svg>';
  }
  function sparkCard(code, period){
    var d=D.spark[code+'|'+period];
    if(!d) return {svg:'', cap:'此期間無走勢資料'};
    var note = d.recd ? ('高點 '+d.pkd+' → 低點 '+d.trd+' → 收復 '+d.recd)
                      : ('高點 '+d.pkd+' → 低點 '+d.trd+'（未收復）');
    return {svg:sparkSVG(code+'|'+period, 268, 44)||'', cap:note};
  }

  /* ── hover 資訊卡 ── */
  var HC=null;
  function hcard(){ if(!HC){ HC=el('div'); HC.id='hcard'; document.body.appendChild(HC);} return HC; }
  function showCard(code, period, anchorEl){
    var f=D.funds[code], m=(pd()[period]||{})[code]||{}, sc=sparkCard(code, period);
    var hc=hcard();
    var risk = (S.panel==='nav')
      ? '<b>波動率</b><span>'+(m.vol!==null&&m.vol!==undefined?m.vol.toFixed(1)+'%':'N/A')+'</span>'+
        '<b>最大回撤</b><span>'+(m.mdd!==null&&m.mdd!==undefined?m.mdd.toFixed(1)+'%':'N/A')+'</span>'+
        '<b>收復時間</b><span>'+esc(m.rec||'N/A')+'</span>'
      : '<b>年化派息率</b><span>'+(f.r?f.r.toFixed(2)+'%':'—')+'</span>'+
        '<b>派息貢獻</b><span>+'+(m.dv!==null&&m.dv!==undefined?m.dv.toFixed(1)+'%':'N/A')+'</span>'+
        '<b>NAV 貢獻</b><span>'+pct(m.nv)+'</span>';
    hc.innerHTML =
      '<div class="hc-t"><span class="code">'+code+'</span>'+esc(f.n)+'</div>'+
      '<div class="hc-m">'+(CURR[f.c]||esc(f.c)||'—')+' · '+esc(CATNAME[f.cat]||f.cat)+(f.h?' ·（對沖）':'')+
        ' · '+PL[period]+' 回報 <b class="'+cls(m.t)+'">'+pct(m.t)+'</b>　'+starsHTML(code)+'</div>'+
      '<div class="hc-k">'+risk+'</div>'+
      '<div class="hc-sp">'+sc.svg+'</div>'+
      '<div class="hc-cap">'+sc.cap+
        '　·　<span style="color:#b13446">深色＝回撤期</span>、<span style="color:#c9a3ab">淺色＝收復期</span></div>';
    hc.style.display='block';
    /* 放在「該列下方」，避免蓋住正在比較的那一列；空間不足則改放列上方 */
    var cell=anchorEl.getBoundingClientRect();
    var row=anchorEl.closest('tr').getBoundingClientRect();
    var w=hc.offsetWidth, h=hc.offsetHeight;
    var left=cell.left;
    if(left + w > window.innerWidth - 12) left = window.innerWidth - w - 12;
    if(left < 12) left = 12;
    var top = row.bottom + 6;
    if(top + h > window.innerHeight - 12){
      var above = row.top - h - 6;
      top = (above >= 12) ? above : Math.max(12, window.innerHeight - h - 12);
    }
    hc.style.left=Math.round(left)+'px'; hc.style.top=Math.round(top)+'px';
  }
  function hideCard(){ if(HC) HC.style.display='none'; }

  /* ── 渲染 ── */
  function renderTabs(){
    var box=document.getElementById('tabs'); box.innerHTML='';
    [['div','派息基金'],['nav','非派息基金']].forEach(function(x){
      var n=Object.keys(D.panels[x[0]].p[D.panels[x[0]].periods[0]]||{}).length;
      var b=el('button','tab'+(S.panel===x[0]?' is-on':''),x[1]+' <b>'+n+'</b>');
      b.onclick=function(){ S.panel=x[0];
        if(periods().indexOf(S.basis)<0) S.basis=periods()[0];
        if(S.cat!=='all' && !hasCat(S.cat)) S.cat='all';
        render(); };
      box.appendChild(b);
    });
    var vb=document.getElementById('views'); vb.innerHTML='';
    [['cross','基本'],['detail','明細']].forEach(function(x){
      var b=el('button','chip vw'+(S.view===x[0]?' on':''),x[1]);
      b.onclick=function(){ S.view=x[0]; render(); };
      vb.appendChild(b);
    });
  }
  function catCount(cat){
    var n=0, p=today();
    Object.keys(p).forEach(function(c){ if(cat==='all'||D.funds[c].cat===cat) n++; });
    return n;
  }
  function hasCat(cat){ return cat==='all'||catCount(cat)>0; }
  function renderCats(){
    var box=document.getElementById('cats'); box.innerHTML='';
    D.cats.forEach(function(x){
      var n=catCount(x[0]);
      if(n===0 && S.cat!==x[0]) return;
      var b=el('button','chip'+(S.cat===x[0]?' on':''),esc(x[1])+'<b>'+n+'</b>');
      b.onclick=function(){ S.cat=x[0]; render(); };
      box.appendChild(b);
    });
  }
  function renderPeriods(){
    var box=document.getElementById('periods'); box.innerHTML='';
    periods().forEach(function(p){
      var b=el('button','chip period'+(S.basis===p?' on':''),(PL[p]||p));
      b.onclick=function(){ S.basis=p; render(); };
      box.appendChild(b);
    });
  }
  function renderTable(){
    var host=document.getElementById('table'); host.innerHTML='';
    var PS=periods(), pdd=pd(), list=rows();
    var table=el('table'), thead=el('thead'), tr=el('tr');
    tr.appendChild(el('th','','名次'));
    tr.appendChild(el('th','','代號'));
    tr.appendChild(el('th','','基金'));
    if(S.view==='cross'){
      PS.forEach(function(p){ tr.appendChild(el('th',(p===S.basis?'basis':'mcol'),(PL[p]||p)+hIcon())); });
    } else {
      tr.appendChild(el('th','basis',(PL[S.basis]||S.basis)+hIcon()));
      if(S.panel==='nav'){
        if(S.basis!=='YTD') tr.appendChild(el('th','num mcol','年化回報'));
        tr.appendChild(el('th','num mcol','波動率'));
        tr.appendChild(el('th','num mcol','最大回撤'));
        tr.appendChild(el('th','num mcol','收復時間'));
      } else {
        tr.appendChild(el('th','num mcol','年化派息率'));
        if(S.basis!=='YTD') tr.appendChild(el('th','num mcol','年化回報'));
        tr.appendChild(el('th','num mcol','派息貢獻'));
        tr.appendChild(el('th','num mcol','NAV 貢獻'));
        tr.appendChild(el('th','num mcol','紀錄日'));
      }
    }
    thead.appendChild(tr); table.appendChild(thead);

    var tbody=el('tbody');
    if(!list.length){ tbody.appendChild(el('tr','','<td colspan="9" class="na">此類別在此期間沒有足夠資料</td>')); }
    list.forEach(function(code,i){
      var f=D.funds[code], r=pdd[S.basis][code], row=el('tr');
      row.setAttribute('data-code',code);
      row.appendChild(el('td','rank',rankHTML(i,code)));
      row.appendChild(el('td','cell-code',codeHTML(code)));
      row.appendChild(el('td','name',nameHTML(code)));
      if(S.view==='cross'){
        PS.forEach(function(p){
          var o=(pdd[p]||{})[code], v=o?o.t:null;
          var td=el('td','num '+cls(v)+((p===S.basis)?' basis':' mcol'),pct(v));
          if(p!==S.basis) td.setAttribute('data-period',p);
          row.appendChild(td);
        });
      } else {
        var tdB=el('td','num '+cls(r.t)+' basis',pct(r.t)); row.appendChild(tdB);
        if(S.panel==='nav'){
          if(S.basis!=='YTD') row.appendChild(el('td','num mcol '+((r.a===null)?'na':''),(r.a===null?'N/A':pct(r.a)+'/年')));
          row.appendChild(el('td','num mcol',(r.vol===null||r.vol===undefined?'N/A':r.vol.toFixed(1)+'%')));
          row.appendChild(el('td','num mcol '+cls(r.mdd),(r.mdd===null||r.mdd===undefined?'N/A':r.mdd.toFixed(1)+'%')));
          row.appendChild(el('td','num mcol',esc(r.rec)));
        } else {
          row.appendChild(el('td','num mcol',f.r?f.r.toFixed(2)+'%':'—'));
          if(S.basis!=='YTD') row.appendChild(el('td','num mcol '+((r.a===null)?'na':''),(r.a===null?'N/A':pct(r.a))));
          row.appendChild(el('td','num mcol','+'+(r.dv!==null&&r.dv!==undefined?r.dv.toFixed(1):'0.0')+'%'));
          row.appendChild(el('td','num mcol '+cls(r.nv),pct(r.nv)));
          row.appendChild(el('td','num mcol',esc(r.b)));
        }
      }
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    var tw=el('div','wrapx'); tw.appendChild(table); host.appendChild(tw);

    /* hover（桌機）／tap（手機）：代號格與基金名格都顯示資訊卡 */
    Array.prototype.forEach.call(tbody.querySelectorAll('tr'), function(row){
      var code=row.getAttribute('data-code'); if(!code) return;
      /* hover 只掛「期間欄」——
         跨期：每一期都可 hover；明細：只留「年期」那一欄（其餘指標欄都是同一張基準期卡，重複）
         代號／基金名不掛（它們給的也是基準期卡，與基準欄重複） */
      if(!TOUCH) Array.prototype.forEach.call(row.children, function(td){
        if(!td.classList.contains('num')) return;
        if(S.view!=='cross' && !td.classList.contains('basis')) return;
        td.classList.add('hv');                 // 標記「這格可 hover」→ CSS 給 cursor:help 與單格高亮
        var per=td.getAttribute('data-period')||S.basis;
        td.addEventListener('mouseenter', function(){ showCard(code, per, td); });
        td.addEventListener('mouseleave', hideCard);
      });
      row.addEventListener('click', function(e){
        if(e.target.closest && e.target.closest('a')) return;   // 桌機點基金名 → 06
        /* 觸控：點某一期數值格 → 展開「那一期」；點名次/代號/名稱 → 展開當前排名基準期 */
        var per=S.basis;
        if(TOUCH){
          var cell=e.target.closest?e.target.closest('td'):null;
          if(cell && cell.getAttribute) per = cell.getAttribute('data-period') || per;
        }
        var nx=row.nextElementSibling;
        if(nx && nx.classList.contains('mrow')){
          var same = (nx.getAttribute('data-per')===per);
          nx.remove();
          if(same) return;                                     // 點同一期 → 收合
        }
        var det=buildDetail(code, per); if(det) row.after(det);
      });
    });

    /* 截圖模式用的一行脈絡（一般模式隱藏） */
    var ctx=document.getElementById('shotctx');
    if(ctx) ctx.textContent=' · '+(S.panel==='div'?'派息基金':'非派息基金')+' · '+(CATNAME[S.cat]||'全部')
      +' · 排名基準 '+(PL[S.basis]||S.basis)+' · Top '+list.length;

    var cov=D.cov[S.panel][S.basis];
    document.getElementById('note').innerHTML =
      (S.view==='cross'
        ? '依 <b>'+(PL[S.basis]||S.basis)+'</b> 排名，固定取前 10；列內可同時比較其他期間（基準欄以金色標示）。'
        : '明細：只顯示 <b>'+(PL[S.basis]||S.basis)+'</b> 這一期的完整欄位。')
      + ' 該期間共 '+cov+' 檔有完整資料（本表 '+list.length+' 檔）。'
      + (D.prev ? ' 名次旁 ▲▼ 為與上月同一榜（'+D.prev.asof.slice(0,7)+'）的名次變化。' : '')
      ;
  }

  /* 手機用的展開列（同時也是桌機點列的明細） */
  function buildDetail(code, per){
    per = per || S.basis;
    var f=D.funds[code], PS=periods(), pdd=pd();
    var det=el('tr','mrow'), td=el('td'); td.colSpan=99;
    det.setAttribute('data-per', per); det.setAttribute('data-code', code);
    var html='<div class="g3">';
    PS.forEach(function(p){
      var o=(pdd[p]||{})[code];
      html+='<span class="cell'+(p===per?' on':'')+'"><span class="k">'+(PL[p]||p)+'</span>'+pct(o?o.t:null)+'</span>';
    });
    html+='</div><div class="line"><span class="k">幣種</span>'+(CURR[f.c]||esc(f.c)||'—')+
          '　<span class="k">類別</span>'+esc(CATNAME[f.cat]||f.cat)+
          '　<span class="k">評級</span>'+starsHTML(code)+'</div>';
    var m=(pdd[per]||{})[code]||{};
    if(S.panel==='nav'){
      html+='<div class="line"><span class="k">波動率</span>'+(m.vol===null||m.vol===undefined?'N/A':m.vol.toFixed(1)+'%')+
            '　<span class="k">最大回撤</span>'+(m.mdd===null||m.mdd===undefined?'N/A':m.mdd.toFixed(1)+'%')+
            '　<span class="k">收復時間</span>'+esc(m.rec||'N/A')+'</div>';
    } else {
      html+='<div class="line"><span class="k">年化派息率</span>'+(f.r?f.r.toFixed(2)+'%':'—')+
            '　<span class="k">派息貢獻</span>+'+(m.dv!==null&&m.dv!==undefined?m.dv.toFixed(1):'0.0')+'%'+
            '　<span class="k">NAV 貢獻</span>'+pct(m.nv)+'</div>';
    }
    var sv=sparkSVG(code+'|'+per, 320, 34);
    if(sv){
      html+='<div class="sp-wrap">'+sv+'</div>'+
            '<div class="sp-cap"><span style="color:#8f0d25">深色＝回撤期</span>、'+
            '<span style="color:#c9a3ab">淺色＝收復期</span></div>';
    } else {
      html+='<div class="sp-cap">此期間無內嵌走勢圖（僅各期前 10 名基金有圖）</div>';
    }
    html+='<div style="margin-top:6px"><a href="./06-fund-portfolio-workbench.html?fund='+code+'&y='+tag06(per)+
          '" style="color:#8f0d25">在 06 開啟 '+code+' 走勢圖（'+PL[per]+'）→</a></div>';
    td.innerHTML='<div class="inner">'+html+'</div>'; det.appendChild(td);
    return det;
  }

  function syncURL(){
    var q=new URLSearchParams();
    q.set('tab',S.panel); q.set('cat',S.cat); q.set('basis',S.basis); q.set('view',S.view);
    if(S.shot) q.set('shot','1');
    if(S.icon) q.set('icon', S.icon);
    if(S.cmp) q.set('iconcompare','1');
    if(history.replaceState) history.replaceState(null,'',location.pathname+'?'+q.toString());
  }
  function renderIconCmp(){
    var box=document.getElementById('iconcmp'); if(!box) return;
    if(!S.cmp){ box.style.display='none'; box.innerHTML=''; return; }
    box.style.display='flex'; box.innerHTML='';
    box.appendChild(el('span','lbl','圖示對照'));
    ['A','B','C','D','E'].forEach(function(k){
      var cur=(S.icon||'A')===k;
      var b=el('button', cur?'on':'', k+' '+ICONS[k]);
      b.title='套用 '+k+' 圖示';
      b.onclick=function(){ S.icon=k; renderTable(); renderIconCmp(); syncURL(); };
      box.appendChild(b);
    });
  }
  function render(){ hideCard(); document.body.style.cursor=''; renderTabs(); renderCats(); renderPeriods(); renderTable(); renderIconCmp(); syncURL(); }
  render();
  window.addEventListener('scroll', hideCard, true);

  /* 截圖模式：只切換 html.shot 這個 class（工具列隱藏、基金名單行省略），資料完全不動
     開啟後網址會帶 ?shot=1，可直接加入手機主畫面當「一張截完 Top 10」的書籤 */
  var shotBtn=document.getElementById('shotbtn');
  function applyShot(on){
    S.shot=!!on;
    document.documentElement.classList.toggle('shot', S.shot);
    if(shotBtn){
      shotBtn.textContent = S.shot ? '✕ 退出' : '截圖模式';
      shotBtn.title = S.shot ? '退出截圖模式（也可點標題列或按 Esc）' : '截圖模式：隱藏工具列，一張截完 Top 10';
    }
    var mh=document.querySelector('.masthead');
    if(mh) mh.title = S.shot ? '點此退出截圖模式' : '';
    try{ localStorage.setItem('calculator-hub-rank-shot', S.shot ? '1' : '0'); }catch(e){}
    syncURL();
  }
  if(shotBtn) shotBtn.addEventListener('click', function(e){ e.stopPropagation(); applyShot(!S.shot); });
  var MH=document.querySelector('.masthead');   /* 截圖模式下點標題列也能退出 */
  if(MH) MH.addEventListener('click', function(){ if(S.shot) applyShot(false); });
  document.addEventListener('keydown', function(e){ if(e.key==='Escape' && S.shot) applyShot(false); });
  if(!qs.get('shot')){            /* 網址沒指定就跟隨本機上次的選擇 */
    try{ if(localStorage.getItem('calculator-hub-rank-shot')==='1') S.shot=true; }catch(e){}
  }
  applyShot(S.shot);

  /* 語言：跟隨 06（同源 localStorage）＋ 本頁切換寫回同一鍵 */
  function swapTo(url){
    try{ if(history.replaceState) history.replaceState(null,'',location.pathname+location.search); }catch(e){}
    try{ location.replace(url+location.search); }catch(e){}
  }
  try{
    var want=localStorage.getItem('calculator-hub-language');
    if(want==='traditional' && PAGE_LANG!=='tr') swapTo(OTHER_URL);
    else if(want==='simplified' && PAGE_LANG!=='sc') swapTo(OTHER_URL);
  }catch(e){}
  Array.prototype.forEach.call(document.querySelectorAll('.langbtn'), function(a){
    a.addEventListener('click', function(){
      try{ localStorage.setItem('calculator-hub-language', a.getAttribute('data-lang')); }catch(e){}
    });
  });
})();
"""

TPL = """<!doctype html>
<html lang="__LANGTAG__" data-lang="__LANGVAL__" data-rank2="1">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>基金月榜｜AIA TMP2</title>
<style>__CSS__</style>
</head>
<body>
<div class="wrap">
  <header class="masthead">
    <p class="eyebrow">AIA · TMP2 / FUND MONTHLY RANKING</p>
    <h1 id="h1">基金月榜</h1>
    <span class="mh-break"></span>
    <p class="backlink"><a href="./06-fund-portfolio-workbench.html">← 返回 06 基金組合測算</a></p>
    <p class="sub">基準日 <b id="anchor"></b><span id="shotctx" class="shotctx"></span></p>
    __MONTHNAV__
    <div class="langsw" role="group" aria-label="切換中文顯示">
      <span class="langsw-lbl">LANG</span>
      <a class="langbtn__TR_ON__" data-lang="traditional" href="__SELF__">繁</a>
      <a class="langbtn__SC_ON__" data-lang="simplified" href="__OTHER__">简</a>
    </div>
  </header>

  <div class="tabs" id="tabs"></div>
  <div class="row"><span class="lbl">檢視</span><span id="views" style="display:flex;gap:8px"></span></div>
  <div class="row"><span class="lbl">類別</span><span id="cats" style="display:flex;gap:8px;flex-wrap:wrap"></span></div>
  <div class="row"><span class="lbl">排名基準</span><span id="periods" style="display:flex;gap:8px;flex-wrap:wrap"></span></div>

  <div class="iconcmp" id="iconcmp" style="display:none"></div>
  <div class="shotbar"><button type="button" id="shotbtn" class="shotbtn">截圖模式</button></div>
  <div class="card" id="table"></div>
  <p class="note" id="note"></p>

  <p class="foot">資料來源：AIA 官方日頻 NAV 與派息紀錄（與月榜同一套計算）。<br>
    非派息基金回報以各基金自身幣別計，<b>不含匯率影響</b>；名稱後標「（對沖）」者為對沖股份類別。<br>
    漲跌色跟隨語言：繁體版<b>綠漲紅跌</b>、簡體版<b>紅漲綠跌</b>。歷史資料不代表未來表現，非投資建議。</p>
</div>
<script>window.__RANK2__=__DATA__;</script>
<script>
(function(){ var M=window.__RANK2__.meta;
  document.getElementById('anchor').textContent=M.anchor;
  var ym=(M.month||M.anchor.slice(0,7)).split('-'), t=(ym[1]? parseInt(ym[1],10)+'月' : M.anchor.slice(0,7));
  var h='基金月榜 - '+t; document.getElementById('h1').textContent=h; document.title=h+'｜AIA TMP2';
})();
</script>
<script>__JS__</script>
</body>
</html>
"""


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_rankings as B
import build_rank2_data as P


def fname(y, m, lang):
    """最新月份 → fund-ranking(.html/-sc.html)；其餘 → fund-ranking-YYYY-MM...
    （2026-09-15 起取代 v1 月榜，故沿用舊版檔名：舊分享連結與 06 FAB 都指向 fund-ranking.html）"""
    latest = (y, m) == tuple(B.MONTHS[0])
    base = "fund-ranking" if latest else f"fund-ranking-{y}-{m:02d}"
    return base + (".html" if lang == "tr" else "-sc.html")


def month_nav(y, m):
    """月份導覽（placeholders __URL_YYYY-MM__ / __URL_LATEST__ 由 localize 依語言替換）"""
    opts = []
    for (yy, mm) in B.MONTHS:
        sel = " selected" if (yy, mm) == (y, m) else ""
        opts.append(f"<option value='__URL_{yy}-{mm:02d}__'{sel}>{yy}-{mm:02d}</option>")
    idx = B.MONTHS.index((y, m))
    if idx + 1 < len(B.MONTHS):
        oy, om = B.MONTHS[idx + 1]
        prev_html = f"<a class='mnav' href='__URL_{oy}-{om:02d}__'>&lsaquo; 前一月</a>"
    else:
        prev_html = "<span class='mnav off'>&lsaquo; 前一月</span>"
    next_html = ("<span class='mnav off'>最新月份 &rsaquo;</span>" if idx == 0
                 else "<a class='mnav' href='__URL_LATEST__'>最新月份 &rsaquo;</a>")
    return (f"<nav class='monthnav' aria-label='月份切換'>{prev_html}"
            f"<label class='mnav mnav-sel'><span>月份</span>"
            f"<select aria-label='選擇月份' onchange=\"if(this.value) location.href=this.value\">"
            f"{''.join(opts)}</select></label>{next_html}</nav>")


def localize(y, m, lang, data):
    html = TPL.replace("__MONTHNAV__", month_nav(y, m))
    html = html.replace("__CSS__", CSS).replace("__JS__", JS).replace("__DATA__", data)
    other = "sc" if lang == "tr" else "tr"
    out = (html
           .replace("__URL_LATEST__", fname(B.MONTHS[0][0], B.MONTHS[0][1], lang))
           .replace("__SELF__", fname(y, m, lang))
           .replace("__OTHER__", fname(y, m, other))
           .replace("__LANGTAG__", "zh-HK" if lang == "tr" else "zh-Hans")
           .replace("__LANGVAL__", lang)
           .replace("__TR_ON__", " is-on" if lang == "tr" else "")
           .replace("__SC_ON__", " is-on" if lang == "sc" else ""))
    for (yy, mm) in B.MONTHS:
        out = out.replace(f"__URL_{yy}-{mm:02d}__", fname(yy, mm, lang))
    return out


def check_no_ph(txt, name):
    import re as _re
    ALLOW = {'__RANK2__'}   # 頁面自己的 JS 變數，非佔位符
    left = sorted(set(_re.findall(r"__[A-Z_][A-Z0-9_-]*__", txt)) - ALLOW)
    if left:
        raise SystemExit(f"{name} 仍有未替換的佔位符：{left}")


def main():
    try:
        from opencc import OpenCC
        cc = OpenCC("t2s")
    except Exception as e:
        cc = None
        print("opencc 不可用，只產出繁體版：", e)
    for (y, m) in B.MONTHS:
        data = P.pack(y, m)
        for lang in ("tr", "sc"):
            if lang == "sc" and cc is None:
                continue
            out = localize(y, m, lang, data)
            if lang == "sc":
                out = cc.convert(out)
            check_no_ph(out, f"{y}-{m:02d} {lang}")
            name = fname(y, m, lang)
            io.open(os.path.join(DEPLOY, name), "w", encoding="utf-8", newline="").write(out)
            print(f"{name}（{lang}，{len(out.encode())/1024:.0f} KB）")


if __name__ == "__main__":
    main()
