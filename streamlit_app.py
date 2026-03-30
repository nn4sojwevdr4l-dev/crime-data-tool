import io
import time
import re
import random
import urllib.parse
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取 (穩定版)", layout="wide")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace('\n', ' ').strip()

def crawl_task(target_date, exclude_list, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    
    # 模擬真實瀏覽器標頭
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }

    for idx, kw in enumerate(KEYWORDS):
        try:
            # 構建搜尋網址 (與手動搜尋完全一致的參數)
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=nws&hl=zh-TW&gl=tw"
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            # 鎖定網頁版關鍵標籤 SoaBEf
            items = soup.select("div.SoaBEf")
            
            count = 0
            for item in items:
                if count >= final_limit: break
                
                try:
                    title = item.select_one("div[role='heading']").text
                    link = item.select_one("a")["href"]
                    source = item.select_one("div.MgUUmf").text
                    snippet = item.select_one("div.VwiC3b").text if item.select_one("div.VwiC3b") else ""
                    
                    if title in seen_titles: continue
                    if any(ex in source for ex in exclude_list if ex): continue

                    all_results.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title,
                        "摘要": clean_text(snippet)[:90],
                        "連結": link
                    })
                    seen_titles.add(title)
                    count += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(random.uniform(1, 2))
            
        except:
            continue

    return pd.DataFrame(all_results)

# --- UI ---
st.title("⚖️ 犯罪新聞數據全自動提取")

with st.sidebar:
    target_month = st.text_input("📅 月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始同步提取"):
    df = crawl_task(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！獲取 {len(df)} 筆與手動搜尋對位的資料。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            ws = writer.sheets['Sheet1']
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            # 欄寬設定
            ws.column_dimensions['A'].width = 9   # A 欄寬 9
            ws.column_dimensions['B'].width = 14  # B 欄寬 14
            ws.column_dimensions['C'].width = 40
            ws.column_dimensions['D'].width = 60
            ws.column_dimensions['E'].width = 30
            
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16 # 行高 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button("📥 下載對位 Excel", output.getvalue(), f"CrimeData_{target_month}.xlsx")
    else:
        st.error("查無資料，可能是雲端 IP 被 Google 阻擋，請重新整理頁面再試一次。")
