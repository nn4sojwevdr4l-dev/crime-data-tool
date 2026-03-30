import io
import time
import re
import urllib.parse
import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from openpyxl.styles import Font, Alignment

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞雲端對位工具 (Proxy 版)", layout="wide")

def clean_text(text):
    if not text: return ""
    text = re.sub(r'<[^>]*>', '', text)
    return text.replace('\n', ' ').strip()

def crawl_via_proxy(target_date, exclude_list, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set()
    progress_bar = st.progress(0)
    
    # 模擬真實瀏覽器
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    for idx, kw in enumerate(KEYWORDS):
        try:
            # 原始搜尋網址
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            target_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&tbm=nws&hl=zh-TW&gl=tw"
            
            # --- 黑科技：透過 Google 翻譯代理請求 ---
            proxy_url = f"https://translate.google.com/translate?sl=en&tl=zh-TW&u={urllib.parse.quote(target_url)}"
            
            response = requests.get(proxy_url, headers=headers, timeout=20)
            if response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            
            # 在翻譯模式下，標籤可能會被包裝，我們改用更廣泛的搜尋方式
            # 優先找 SoaBEf，找不到就找一般的新聞容器
            items = soup.select("div.SoaBEf") or soup.select("div.g") or soup.find_all("div", class_=re.compile("n0W69e|card"))
            
            count = 0
            for item in items:
                if count >= final_limit: break
                
                try:
                    # 嘗試多種可能的標題與連結標籤
                    link_elem = item.find("a")
                    title_elem = item.find("div", {"role": "heading"}) or item.find("h3")
                    source_elem = item.select_one("div.MgUUmf") or item.find("span")
                    
                    if not title_elem or not link_elem: continue
                    
                    title = title_elem.text
                    # 處理 Google 翻譯包裝過的連結
                    raw_link = link_elem["href"]
                    if "url?q=" in raw_link:
                        link = raw_link.split("url?q=")[1].split("&")[0]
                    else:
                        link = raw_link
                    
                    source = source_elem.text if source_elem else "新聞媒體"
                    
                    if title in seen_titles: continue
                    if any(ex in source for ex in exclude_list if ex): continue

                    all_results.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title,
                        "連結": link
                    })
                    seen_titles.add(title)
                    count += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(2) # 代理請求建議慢一點
            
        except Exception as e:
            continue

    return pd.DataFrame(all_results)

# --- UI ---
st.title("⚖️ 犯罪新聞數據全自動提取 (雲端代理版)")
st.info("💡 採用 Google 代理繞道技術，專為解決 Streamlit Cloud 被封鎖 IP 問題設計。")

with st.sidebar:
    target_month = st.text_input("📅 月份 (YYYY-MM)", "2025-01")
    ex_input = st.text_area("🚫 排除媒體 (逗號分隔)")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 啟動代理同步任務"):
    with st.spinner("正在透過代理伺服器繞道抓取..."):
        df = crawl_via_proxy(target_month, ex_list)
    
    if not df.empty:
        st.success(f"✅ 完成！成功繞過封鎖，獲取 {len(df)} 筆資料。")
        st.dataframe(df)

        # --- Excel 格式鎖死 (A9, B14, 行高 16, 字體 12) ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
            ws = writer.sheets['Sheet1']
            font_style = Font(name='Microsoft JhengHei', size=12)
            
            # 欄寬鎖死
            ws.column_dimensions['A'].width = 9   # 犯罪類別
            ws.column_dimensions['B'].width = 14  # 來源
            ws.column_dimensions['C'].width = 45  # 標題
            ws.column_dimensions['D'].width = 40  # 連結
            
            for r_idx in range(1, ws.max_row + 1):
                ws.row_dimensions[r_idx].height = 16 # 行高 16
                for cell in ws[r_idx]:
                    cell.font = font_style
                    cell.alignment = Alignment(vertical='center', wrap_text=False)

        st.download_button("📥 下載 Excel", output.getvalue(), f"Proxy_News_{target_month}.xlsx")
    else:
        st.error("❌ 代理模式依然失敗。這代表 Google 對此類繞道也進行了限制。")
        st.markdown("---")
        st.warning("⚠️ **最後的建議：** 既然雲端 IP 被封死，請務必考慮在本地電腦執行 3/26 那個穩定版，那樣 100% 會成功且對位。")
