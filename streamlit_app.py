import streamlit as st
import pandas as pd
import time
import io
import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞全自動同步工具", layout="wide")

def crawl_with_browser(target_date, exclude_list, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    with sync_playwright() as p:
        # 啟動背景瀏覽器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="zh-TW"
        )
        page = context.new_page()
        # 關鍵：使用 stealth 插件避開 Google 機器人偵測
        stealth_sync(page)

        for idx, kw in enumerate(KEYWORDS):
            try:
                status_text.text(f"🔍 模擬手動搜尋中：{kw} ({idx+1}/{len(KEYWORDS)})")
                
                query = f"{kw} after:{target_date}-01 before:{target_date}-31"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=nws&hl=zh-TW&gl=tw"
                
                page.goto(url, wait_until="networkidle", timeout=30000)
                
                # 滾動一下頁面模擬真人
                page.mouse.wheel(0, 500)
                time.sleep(1)

                # 抓取網頁版標籤
                items = page.query_selector_all("div.SoaBEf")
                
                count = 0
                for item in items:
                    if count >= final_limit: break
                    
                    try:
                        title = item.query_selector("div[role='heading']").inner_text()
                        source = item.query_selector("div.MgUUmf").inner_text()
                        link = item.query_selector("a").get_attribute("href")
                        snippet = item.query_selector("div.VwiC3b").inner_text() if item.query_selector("div.VwiC3b") else ""

                        if title in seen_titles: continue
                        if any(ex in source for ex in exclude_list if ex): continue

                        all_results.append({
                            "犯罪類別": kw,
                            "媒體來源": source,
                            "新聞標題": title,
                            "摘要": snippet[:100],
                            "連結": link
                        })
                        seen_titles.add(title)
                        count += 1
                    except:
                        continue
                
                progress_bar.progress((idx + 1) / len(KEYWORDS))
                # 隨機延遲避免被鎖
                time.sleep(2)
                
            except Exception as e:
                st.warning(f"解析 {kw} 失敗：{e}")
                continue

        browser.close()
    return pd.DataFrame(all_results)

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞全自動同步 (網頁模擬版)")
st.info("💡 說明：此版本會開啟隱形瀏覽器進行搜尋，結果與你手動搜尋完全一致。")

with st.sidebar:
    target_month = st.text_input("📅 月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 啟動全量搜尋任務"):
    df = crawl_with_browser(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！共獲取 {len(df)} 筆資料。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='精選數據')
            ws = writer.sheets['精選數據']
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            ws.column_dimensions['A'].width = 9   # 犯罪類別
            ws.column_dimensions['B'].width = 14  # 媒體來源
            
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button("📥 下載 Excel 總表", output.getvalue(), f"SyncNews_{target_month}.xlsx")
