import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import io
import random
from fake_useragent import UserAgent

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞雲端提取器 (原始碼版)", layout="wide")

def get_session():
    """建立一個帶有真實瀏覽器特徵的 Session"""
    session = requests.Session()
    ua = UserAgent()
    session.headers.update({
        "User-Agent": ua.random,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    })
    return session

def crawl_step_1_cloud(target_date, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = ["洗錢"]
    
    all_links = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    session = get_session()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 雲端解析中：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 關鍵語法：tbs=cdr:1... 是 Google 網頁版鎖定日期的原始參數，比 after/before 更能欺騙機器人偵測
            # 假設月份為 2025-01 -> 開始日 1/1, 結束日 1/31
            query = urllib.parse.quote(kw)
            url = f"https://www.google.com/search?q={query}&tbm=nws&hl=zh-TW&gl=tw&tbs=cdr:1,cd_min:{target_date}-01,cd_max:{target_date}-31"
            
            # 隨機延遲，模擬真人翻頁時間
            time.sleep(random.uniform(1.5, 3.0))
            
            response = session.get(url, timeout=20)
            
            if response.status_code != 200:
                st.warning(f"⚠️ {kw} 被攔截 (HTTP {response.status_code})，更換指紋重試...")
                session = get_session() # 重新獲取 Session
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            items = soup.select("div.SoaBEf")
            
            if not items:
                # 雲端有時會被導向簡化版網頁，嘗試另一種標籤
                items = soup.select("div.g") 

            count_for_kw = 0
            for item in items:
                if count_for_kw >= buffer_limit: break 
                
                try:
                    title_elem = item.find("div", {"role": "heading"})
                    link_elem = item.find("a")
                    source_elem = item.select_one("div.MgUUmf")
                    
                    if title_elem and link_elem:
                        title = title_elem.text
                        link = link_elem["href"]
                        source = source_elem.text if source_elem else "媒體"
                        
                        if title in seen_titles: continue
                        if any(ex in source for ex in exclude_list if ex): continue

                        all_links.append({
                            "犯罪類別": kw,
                            "來源": source,
                            "標題": title,
                            "連結": link
                        })
                        seen_titles.add(title)
                        count_for_kw += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.error(f"解析 {kw} 異常：{e}")

    if all_links:
        df = pd.DataFrame(all_links)
        return df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
    return pd.DataFrame()

# --- UI ---
st.title("⚖️ 第一階段：雲端原始碼連結提取 (30取10)")
st.info("此版本採用動態指紋偽裝，嘗試繞過雲端 IP 封鎖。")

with st.sidebar:
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    ex_input = st.text_area("🚫 排除媒體 (逗號隔開)")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 啟動雲端暴力提取任務"):
    df_result = crawl_step_1_cloud(target_month, ex_list)
    if not df_result.empty:
        st.success(f"✅ 成功撈取 {len(df_result)} 筆資料！")
        st.dataframe(df_result, use_container_width=True)
        
        csv = df_result.to_csv(index=False, encoding='utf-8-sig')
        st.download_button("📥 下載第一階段清單 (CSV)", csv, f"Links_{target_month}.csv")
    else:
        st.error("❌ 雲端節點依然被封鎖。")
        st.info("💡 最後絕招：請先在 Google 搜尋隨便找個東西，點開新聞分頁，把網址貼給我。我幫你分析你那邊最新的加密參數。")
