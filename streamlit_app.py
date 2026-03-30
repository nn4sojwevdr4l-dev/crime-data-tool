import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞 RSS 精準提取", layout="wide")

def clean_html(text):
    if not text: return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]*>', '', text)
    return text.strip()[:100]

def crawl_rss(target_date, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 正在提取 RSS 數據：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 使用 RSS 模擬手動搜尋語法
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count_for_kw = 0
            
            for entry in feed.entries:
                if count_for_kw >= buffer_limit: break
                
                source = entry.source.get('title', '媒體')
                title = entry.title.split(' - ')[0]
                
                # 去重與排除媒體
                if title in seen_titles: continue
                if any(ex in source for ex in exclude_list if ex): continue

                all_results.append({
                    "犯罪類別": kw,
                    "媒體來源": source,
                    "新聞標題": title,
                    "摘要(可能會重複標題)": clean_html(entry.get('summary', '')),
                    "原始連結": entry.link
                })
                seen_titles.add(title)
                count_for_kw += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.1) # RSS 速度極快，不用等太久
            
        except Exception as e:
            st.error(f"解析 {kw} 出錯：{e}")

    if all_results:
        df = pd.DataFrame(all_results)
        # 30 取 10
        return df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
    return pd.DataFrame()

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞精準提取 (RSS 穩定版)")
st.info("💡 說明：此版本在雲端環境最穩定，結果與手動搜尋高度對齊。")

with st.sidebar:
    st.header("⚙️ 設定")
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    ex_input = st.text_area("🚫 排除媒體")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動執行任務"):
    df = crawl_rss(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 任務完成！共獲取 {len(df)} 筆精選資料。")
        st.dataframe(df)

        # --- Excel 格式鎖死輸出 (A9, B14, 行高 16, 微軟正黑體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='精選數據')
            ws = writer.sheets['精選數據']
            
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            # 欄寬設定
            ws.column_dimensions['A'].width = 9   # 犯罪類別
            ws.column_dimensions['B'].width = 14  # 媒體來源
            ws.column_dimensions['C'].width = 40  # 新聞標題
            ws.column_dimensions['D'].width = 60  # 摘要
            ws.column_dimensions['E'].width = 30  # 連結

            # 行高與全表格式套用
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button(
            label="📥 下載 Excel 總表",
            data=output.getvalue(),
            file_name=f"CrimeNews_{target_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("查無資料，請檢查搜尋日期。")
