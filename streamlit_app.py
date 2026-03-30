import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import io
import time

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪數據全自動提取 (雲端穩定版)", layout="wide")

def crawl_google_news(target_date, final_limit, inc_list, ex_list):
    KEYWORDS = [
        "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", 
        "違反證券交易", "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", 
        "行賄", "仿冒", "盜版", "侵害營業秘密", "第三方洗錢", "洗錢", 
        "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", "偽造", "綁架", "拘禁", "妨害自由"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    all_data = []
    progress_bar = st.progress(0)
    
    for idx, kw in enumerate(KEYWORDS):
        try:
            # 構建搜尋網址
            query = f"{kw} {target_date}"
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=zh-TW&gl=tw"
            
            response = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")
            
            # Google 新聞搜尋結果的容器
            items = soup.select("div.SoaBEf")
            
            count = 0
            for item in items:
                if count >= final_limit: break
                
                try:
                    title = item.select_one("[role='heading']").text
                    link = item.select_one("a")["href"]
                    source = item.select_one("div.MgUUmf").text
                    snippet = item.select_one("div.UqSP2b").text
                    
                    # 過濾媒體
                    if any(ex in source for ex in ex_list if ex): continue
                    if inc_list and not any(inc in source for inc in inc_list if inc): continue

                    all_data.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title.split(' - ')[0],
                        "摘要": snippet[:100],
                        "連結": link
                    })
                    count += 1
                except:
                    continue
            
            time.sleep(0.5) # 避免被 Google 暫時封鎖
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.warning(f"⚠️ {kw} 抓取略過")

    return pd.DataFrame(all_data)

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞數據提取 (雲端穩定版)")
st.info("此版本專為 Streamlit Cloud 優化，無需安裝 Chrome 瀏覽器。")

with st.sidebar:
    st.header("⚙️ 設定參數")
    user_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    user_limit = st.number_input("每個類別數量", 1, 50, 10)
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    ex_text = st.text_area("例如: Yahoo, LINE TODAY (逗號隔開)")
    ex_list = [x.strip() for x in ex_text.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動執行"):
    with st.spinner('數據提取中...'):
        df = crawl_google_news(user_date, user_limit, [], ex_list)
        
        if not df.empty:
            st.success(f"✅ 完成！共計 {len(df)} 筆。")
            st.dataframe(df, use_container_width=True)
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 下載 Excel 總表",
                data=output.getvalue(),
                file_name=f"犯罪數據_{user_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
