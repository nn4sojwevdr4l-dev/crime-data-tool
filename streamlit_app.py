import streamlit as st
import pandas as pd
import urllib.parse
import time
import re
import io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪數據精選工具 (手動對應版)", layout="wide")

def clean_content(text):
    if not text: return ""
    text = re.sub(re.compile('<.*?>'), '', text)
    text = text.replace('\n', ' ').replace('\r', '').strip()
    return text[:100]

def crawl_data(target_date, include_list, exclude_list, final_limit=10):
    # 這裡放你的 29 個固定關鍵字
    KEYWORDS = ["販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", "違反證券交易", "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", "行賄", "仿冒", "盜版", "侵害營業秘密", "第三方洗錢", "洗錢", "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", "偽造", "綁架", "拘禁", "妨害自由"]

    chrome_options = Options()
    chrome_options.add_argument("--headless") # 正式跑用 headless
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    # 關鍵：偽裝成真人瀏覽器，否則會被 Google 擋
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception as e:
        st.error(f"瀏覽器啟動失敗: {e}")
        return pd.DataFrame()

    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        status_text.text(f"🚀 正在同步 Google 搜尋結果：{kw} ({idx+1}/{len(KEYWORDS)})")
        
        # 1. 直接構建 Google 搜尋網址 (這就是你手動搜的網址格式)
        query = f"{kw} {target_date}"
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://www.google.com/search?q={encoded_query}&hl=zh-TW&gl=tw&tbm=nws" # tbm=nws 是新聞標籤頁面
        
        try:
            driver.get(search_url)
            time.sleep(2) # 等待頁面載入

            # 2. 抓取新聞容器 (Google 新聞分頁的常見結構)
            # 這裡抓的是 Google 新聞列表中的標題、來源和摘要
            containers = driver.find_elements(By.CSS_SELECTOR, "div.SoaBEf")
            
            count = 0
            for box in containers:
                if count >= final_limit: break
                
                try:
                    title = box.find_element(By.CSS_SELECTOR, "[role='heading']").text
                    link = box.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                    source = box.find_element(By.CSS_SELECTOR, "div.MgUUmf").text
                    # 直接抓取 Google 頁面上的摘要 (這最準，不用進去新聞內頁等它轉圈)
                    snippet = box.find_element(By.CSS_SELECTOR, "div.UqSP2b").text
                    
                    # 篩選邏輯
                    if any(ex in source for ex in exclude_list if ex): continue
                    if include_list and not any(inc in source for inc in include_list if inc): continue

                    all_results.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title,
                        "摘要": clean_content(snippet),
                        "連結": link
                    })
                    count += 1
                except:
                    continue
                    
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.warning(f"{kw} 搜尋失敗: {e}")

    driver.quit()
    return pd.DataFrame(all_results)

# --- UI 部分 (略，維持你原本的 Streamlit UI) ---
# ... 把原本調用 crawl_data 的參數對應好即可 ...
