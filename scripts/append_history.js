#!/usr/bin/env node
/**
 * 把「當天一筆」寫進時間序列檔（幂等：同日期覆蓋、不同日期累加）。
 *
 * 用法：
 *   node scripts/append_history.js <檔案> <全域變數名> <日期> <JSON 值>
 * 例：
 *   node scripts/append_history.js data/rates-history.js __RATES_HISTORY__ "09/09/2026" '{"USD":"7.8459"}'
 *   node scripts/append_history.js data/hibor-history.js __HIBOR_HISTORY__ "2026/09/02" '{"hibor":2.8626,"prime":5.25}'
 *
 * 設計重點：
 *  1. 日期一律以「來源的資料日期」為準（匯率用 AIA 的 asOf、HIBOR 用大新的 updated），
 *     不是 commit 日期 —— cron 延遲時兩者可能差一天。
 *  2. 接受 MM/DD/YYYY（AIA）與 YYYY/MM/DD（大新）兩種格式，統一轉 ISO。
 *  3. 每天一行輸出：git diff 只多一行，日後查歷史也好看。
 *  4. 只存「原始值」，不做任何換算（例如 USD/RMB 交叉匯率等要用時才算），
 *     避免舍入誤差累積到檔案裡。
 *  5. 缺值取值規則（給未來的分析程式用，不是這裡負責）：
 *     取「不晚於目標日的最近一筆」。
 */
const fs = require('fs');
const path = require('path');

const [, , file, globalName, dateRaw, jsonValue] = process.argv;

function fail(msg) { console.error('[append_history] ' + msg); process.exit(1); }

if (!file || !globalName || !dateRaw || !jsonValue) {
  fail('參數不足：node scripts/append_history.js <檔案> <全域變數名> <日期> <JSON 值>');
}

// ---- 日期正規化 -> YYYY-MM-DD ----
const parts = String(dateRaw).trim().split('/');
let iso;
if (parts.length === 3) {
  if (parts[0].length === 4) {            // YYYY/MM/DD（大新）
    iso = `${parts[0]}-${parts[1].padStart(2, '0')}-${parts[2].padStart(2, '0')}`;
  } else {                                 // MM/DD/YYYY（AIA）
    iso = `${parts[2]}-${parts[0].padStart(2, '0')}-${parts[1].padStart(2, '0')}`;
  }
} else if (/^\d{4}-\d{2}-\d{2}$/.test(String(dateRaw).trim())) {
  iso = String(dateRaw).trim();
} else {
  fail('無法解析日期：' + dateRaw);
}
if (!/^\d{4}-\d{2}-\d{2}$/.test(iso)) fail('日期格式異常：' + dateRaw + ' -> ' + iso);

// ---- 值 ----
let value;
try { value = JSON.parse(jsonValue); }
catch (e) { fail('JSON 值解析失敗：' + e.message); }
if (value === null || typeof value !== 'object' || !Object.keys(value).length) {
  fail('值必須是非空物件');
}

// ---- 讀既有 ----
let obj = {};
if (fs.existsSync(file)) {
  const src = fs.readFileSync(file, 'utf8');
  const m = src.match(/window\.[A-Za-z0-9_]+\s*=\s*([\s\S]*?);\s*$/);
  if (!m) fail('既有檔案格式異常（找不到 window.xxx = {...};）：' + file);
  try { obj = JSON.parse(m[1]); }
  catch (e) { fail('既有檔案 JSON 解析失敗：' + e.message); }
}

const before = JSON.stringify(obj[iso] || null);
obj[iso] = value;                       // 同日覆蓋（一天跑兩次也不會重複）

// ---- 排序後輸出（每天一行）----
const keys = Object.keys(obj).sort();
const body = keys.map(k => JSON.stringify(k) + ': ' + JSON.stringify(obj[k])).join(',\n');
const out = `window.${globalName} = {\n${body}\n};\n`;

fs.mkdirSync(path.dirname(file), { recursive: true });
fs.writeFileSync(file, out);

const changed = before !== JSON.stringify(value);
console.log(`[append_history] ${file} <- ${iso}` +
            (changed ? '（新增/更新）' : '（內容相同）') +
            `　共 ${keys.length} 天　${keys[0]} ~ ${keys[keys.length - 1]}`);
