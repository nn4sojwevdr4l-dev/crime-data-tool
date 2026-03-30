import streamlit as st
import pandas as pd
import os
import time
import io
import urllib.parse
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from openpyxl.styles import Font, Alignment

# --- 自動安裝瀏覽器驅動 (雲端執行關鍵) ---
if not os.path.exists("/home/appuser/.cache/ms-playwright"):
    os.system("playwright install chromium")

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準對位工具 (雲端模擬版)", layout="wide")

def crawl_with_playwright(target_date, exclude_list, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    with sync_playwright() as p:
        # 啟動背景瀏覽器 (Headless 模式)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        stealth_sync(page) # 隱藏自動化特徵

        for idx, kw in enumerate(KEYWORDS):
            try:
                status_text.text(f"📡 正在模擬手動抓取：{kw} ({idx+1}/{len(KEYWORDS)})")
                
                # 關鍵：完全模擬手動搜尋 URL
                query = f"{kw} after:{target_date}-01 before:{target_date}-31"
                url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=nws&hl=zh-TW&gl=tw"
                
                page.goto(url, wait_until="networkidle", timeout=45000)
                
                # 取得所有 SoaBEf 區塊 (網頁版專屬標籤)
                items = page.query_selector_all("div.SoaBEf")
                
                count = 0
                for item in items:
                    if count >= final_limit: break
                    
                    try:
                        title = item.query_selector("div[role='heading']").inner_text()
                        source = item.query_selector("div.MgUUmf").inner_text()
                        link = item.query_selector("a").get_attribute("href")
                        # 摘要抓取
                        snippet_elem = item.query_selector("div.VwiC3b")
                        snippet = snippet_elem.inner_text() if snippet_elem else ""

                        if title in seen_titles: continue
                        if any(ex in source for ex in exclude_list if ex): continue

                        all_results.append({
                            "犯罪類別": kw,
                            "來源": source,
                            "標題": title,
                            "摘要": snippet[:100].replace('\n', ' '),
                            "連結": link
                        })
                        seen_titles.add(title)
                        count += 1
                    except:
                        continue
                
                progress_bar.progress((idx + 1) / len(KEYWORDS))
                time.sleep(1.5) # 稍微喘息
                
            except Exception as e:
                st.warning(f"⚠️ {kw} 解析受阻，原因：{str(e)[:50]}")
                continue

        browser.close()
    return pd.DataFrame(all_results)

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞手動對位版 (Playwright)")
st.info("💡 說明：本版本模擬真實瀏覽器行為，抓取的結果與您手動點擊 Google 新聞一致。")

with st.sidebar:
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全同步提取任務"):
    if not target_month:
        st.error("請輸入月份")
    else:
        with st.spinner('環境部署與抓取中，請稍候...'):
            df = crawl_with_playwright(target_month, ex_list)
            
            if not df.empty:
                st.success(f"✅ 成功！共獲取 {len(df)} 筆與手動搜尋同步的數據。")
                st.dataframe(df)

                # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='新聞清單')
                    ws = writer.sheets['新聞清單']
                    font_style = Font(name='Microsoft JhengHei', size=12)
                    
                    ws.column_dimensions['A'].width = 9   # A 欄寬 9
                    ws.column_dimensions['B'].width = 14  # B 欄寬 14
                    
                    for r_idx in range(1, ws.max_row + 1):
                        ws.row_dimensions[r_idx].height = 16 # 行高 16
                        for cell in ws[r_idx]:
                            cell.font = font_style
                            cell.alignment = Alignment(vertical='center', wrap_text=False)

                st.download_button("📥 下載對位 Excel 總表", output.getvalue(), f"Sync_{target_month}.xlsx")
            else:
                st.error("❌ 依然抓不到資料。請確認 GitHub 上是否有 packages.txt 並重新啟動 Streamlit App。")
