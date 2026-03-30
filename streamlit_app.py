import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
import io
import random
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取 (原始碼修正版)", layout="wide")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace('\n', ' ').strip()

def crawl_raw_precise(target_date, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "洗錢"
    ]

    # 多組 User-Agent 輪替，降低被封鎖機率
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ]

    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在抓取：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 使用手動搜尋 URL 結構
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=zh-TW&gl=tw"
            
            headers = {
                "User-Agent": random.choice(ua_list),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
                "Referer": "https://www.google.com/"
            }

            response = requests.get(url, headers=headers, timeout=15)
            
            if response.status_code != 200:
                st.warning(f"⚠️ {kw} 請求受阻 (HTTP {response.status_code})")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            # 鎖定手動搜尋對齊標籤 SoaBEf
            items = soup.select("div.SoaBEf")
            
            count_for_kw = 0
            for item in items:
                if count_for_kw >= buffer_limit: break
                
                try:
                    title_elem = item.select_one("div[role='heading']")
                    link_elem = item.select_one("a")
                    source_elem = item.select_one("div.MgUUmf")
                    snippet_elem = item.select_one("div.VwiC3b")
                    
                    if not title_elem or not link_elem: continue
                    
                    title = title_elem.text
                    link = link_elem["href"]
                    source = source_elem.text if source_elem else "媒體"
                    snippet = snippet_elem.text if snippet_elem else ""
                    
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
                    count_for_kw += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(random.uniform(1.0, 2.0)) # 隨機延遲
            
        except Exception as e:
            st.error(f"❌ {kw} 異常：{e}")

    if all_results:
        df = pd.DataFrame(all_results)
        return df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
    return pd.DataFrame()

# --- UI ---
st.title("⚖️ 犯罪新聞精準對位工具 (30取10)")

with st.sidebar:
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全量同步任務"):
    df = crawl_raw_precise(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！獲取 {len(df)} 筆。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            ws = writer.sheets['Sheet1']
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            # A 欄寬 9, B 欄寬 14
            ws.column_dimensions['A'].width = 9
            ws.column_dimensions['B'].width = 14
            ws.column_dimensions['C'].width = 40
            ws.column_dimensions['D'].width = 60
            ws.column_dimensions['E'].width = 30
            
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16 # 行高 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button("📥 下載 Excel", output.getvalue(), f"CrimeData_{target_month}.xlsx")
    else:
        st.error("提取失敗：雲端 IP 依然被 Google 阻擋。")
