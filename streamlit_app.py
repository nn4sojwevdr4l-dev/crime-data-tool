import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import re
import io
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取工具", layout="wide")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace('\n', ' ').strip()

def crawl_precise(target_date, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", "違反證券交易", 
        "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", "行賄", "仿冒", "盜版", 
        "侵害營業秘密", "第三方洗錢", "洗錢", "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", 
        "偽造", "綁架", "拘禁", "妨害自由"
    ]

    # 這是當時測試出最能對齊手動搜尋的 Header
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/",
        "Cache-Control": "max-age=0"
    }

    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在精準同步：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 使用當時最準的 URL 結構：關鍵字 + 月份區間
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            # tbm=nws 加上 hl/gl 是當時對位成功的關鍵
            url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=zh-TW&gl=tw"
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                st.warning(f"⚠️ {kw} 請求異常，跳過該項。")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            # 當時對位成功的標籤 SoaBEf
            items = soup.select("div.SoaBEf")
            
            count_for_kw = 0
            for item in items:
                if count_for_kw >= buffer_limit: break
                
                try:
                    title = item.select_one("div[role='heading']").text
                    link = item.select_one("a")["href"]
                    source = item.select_one("div.MgUUmf").text
                    # 摘要標籤
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
                    count_for_kw += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(1.5) # 雲端執行建議維持這個間隔
            
        except Exception as e:
            st.error(f"❌ {kw} 發生錯誤: {e}")

    if all_results:
        df = pd.DataFrame(all_results)
        # 30 取 10
        final_df = df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
        return final_df
    return pd.DataFrame()

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞精準對位工具 (3/26 修正版)")

with st.sidebar:
    st.header("⚙️ 篩選設定")
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    ex_input = st.text_area("🚫 排除媒體 (逗號分隔)", placeholder="Yahoo, LINE TODAY")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始執行任務"):
    df = crawl_precise(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！共獲取 {len(df)} 筆與手動搜尋一致的資料。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 微軟正黑體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='精選數據')
            ws = writer.sheets['精選數據']
            
            # 設定字體與對齊
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            # 欄寬鎖死
            ws.column_dimensions['A'].width = 9
            ws.column_dimensions['B'].width = 14
            ws.column_dimensions['C'].width = 40
            ws.column_dimensions['D'].width = 60
            ws.column_dimensions['E'].width = 30

            # 行高鎖死與樣式套用
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button(
            label="📥 下載 Excel 總表",
            data=output.getvalue(),
            file_name=f"犯罪新聞精選_{target_month}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.error("❌ 提取失敗，請檢查網路環境或 Google 驗證。")
