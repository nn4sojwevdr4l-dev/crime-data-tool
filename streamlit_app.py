import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取 (穩定版)", layout="wide")

def clean_summary(summary, title):
    if not summary: return ""
    # 移除 HTML
    text = re.sub(r'<[^>]*>', '', summary)
    # 移除開頭可能重複的標題或日期
    text = text.replace(title, "").strip()
    # 移除常見的 "..." 或前綴
    text = re.sub(r'^.*?[-—]\s*', '', text)
    return text[:100]

def crawl_rss_stable(target_date, exclude_list, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 正在同步類別：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 使用精準日期參數
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count = 0
            
            for entry in feed.entries:
                if count >= final_limit: break
                
                source = entry.source.get('title', '媒體')
                title = entry.title.split(' - ')[0]
                
                if title in seen_titles: continue
                if any(ex in source for ex in exclude_list if ex): continue

                all_results.append({
                    "犯罪類別": kw,
                    "媒體來源": source,
                    "新聞標題": title,
                    "摘要": clean_summary(entry.get('summary', ''), title),
                    "連結": entry.link
                })
                seen_titles.add(title)
                count += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.1) 
            
        except Exception as e:
            st.error(f"解析 {kw} 出錯：{e}")

    return pd.DataFrame(all_results)

# --- UI ---
st.title("⚖️ 犯罪新聞數據同步工具")
st.info("💡 此為 3/26 穩定版：免安裝複雜組件，直接在雲端穩定執行。")

with st.sidebar:
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動提取"):
    df = crawl_rss_stable(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！獲取 {len(df)} 筆。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            ws = writer.sheets['Sheet1']
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            ws.column_dimensions['A'].width = 9
            ws.column_dimensions['B'].width = 14
            
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button("📥 下載 Excel", output.getvalue(), f"News_{target_month}.xlsx")
