import streamlit as st
import pandas as pd
import urllib.parse
import time
import re
import io
import os

# 核心爬蟲套件
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By

# --- 基礎頁面設定 ---
st.set_page_config(page_title="犯罪數據全自動提取工具 V2.1", layout="wide")

def clean_text(text):
    if not text: return ""
    # 移除 HTML 標籤與特殊換行
    text = re.sub(r'<[^>]*>', '', text)
    text = text.replace('\n', ' ').replace('\r', ' ').strip()
    # 移除 Google 摘要常見的日期前綴
    text = re.sub(r'^\d{4}年\d{1,2}月\d{1,2}日\s*[-—]\s*', '', text)
    return text[:100]

def get_driver():
    """ 初始化 Selenium Driver (相容本地與雲端) """
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    try:
        # 使用 webdriver-manager 自動下載與管理 Chrome Driver
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(20)
        return driver
    except Exception as e:
        st.error(f"❌ 瀏覽器啟動失敗！原因：{e}")
        st.info("💡 如果在雲端執行失敗，建議下載此 .py 檔在本地電腦執行 (需先執行 pip install 指令)。")
        return None

def crawl_task(target_date, final_limit, inc_list, ex_list):
    KEYWORDS = [
        "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", 
        "違反證券交易", "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", 
        "行賄", "仿冒", "盜版", "侵害營業秘密", "第三方洗錢", "洗錢", 
        "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", "偽造", "綁架", "拘禁", "妨害自由"
    ]

    driver = get_driver()
    if not driver: return pd.DataFrame()

    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在同步 Google 搜尋：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 直接模擬 Google 「新聞」分頁搜尋
            query = f"{kw} {target_date}"
            encoded_query = urllib.parse.quote(query)
            # tbm=nws 確保進入新聞模式
            url = f"https://www.google.com/search?q={encoded_query}&hl=zh-TW&gl=tw&tbm=nws"
            
            driver.get(url)
            time.sleep(2) # 確保頁面渲染完成

            # 抓取 Google 新聞容器
            items = driver.find_elements(By.CSS_SELECTOR, "div.SoaBEf")
            
            count = 0
            for item in items:
                if count >= final_limit: break
                
                try:
                    title = item.find_element(By.CSS_SELECTOR, "[role='heading']").text
                    link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                    source = item.find_element(By.CSS_SELECTOR, "div.MgUUmf").text
                    snippet = item.find_element(By.CSS_SELECTOR, "div.UqSP2b").text
                    
                    # 媒體過濾邏輯
                    if any(ex in source for ex in ex_list if ex): continue
                    if inc_list and not any(inc in source for inc in inc_list if inc): continue

                    all_data.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title.split(' - ')[0],
                        "摘要": clean_text(snippet),
                        "連結": link
                    })
                    count += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.warning(f"⚠️ {kw} 抓取略過: {e}")

    driver.quit()
    return pd.DataFrame(all_data)

# --- 介面設計 ---
st.title("⚖️ 犯罪新聞數據全自動提取工具")
st.caption("同步 Google 實時搜尋結果，自動彙整 29 個犯罪類別。")

with st.sidebar:
    st.header("⚙️ 設定參數")
    user_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    user_limit = st.number_input("每個類別抓取數量", min_value=1, max_value=50, value=10)
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    ex_text = st.text_area("例如: Yahoo, LINE TODAY (以逗號隔開)", "")
    ex_list = [x.strip() for x in ex_text.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體")
    inc_text = st.text_area("只看這些媒體 (留空則抓取全部)", "")
    inc_list = [x.strip() for x in inc_text.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動提取任務"):
    if not user_date:
        st.error("請輸入日期！")
    else:
        with st.spinner('模擬真人搜尋中，請勿關閉視窗...'):
            df = crawl_task(user_date, user_limit, inc_list, ex_list)
            
            if not df.empty:
                st.success(f"✅ 任務完成！共計 {len(df)} 筆數據。")
                st.dataframe(df, use_container_width=True)
                
                # 產生 Excel 檔案供下載
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 下載完整數據總表 (.xlsx)",
                    data=output.getvalue(),
                    file_name=f"犯罪數據總表_{user_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("❌ 抓取失敗。可能原因：1. 網路環境限制 2. Google 偵測到機器人 3. 查無新聞。")

st.markdown("---")
st.help("提示：若在雲端無法執行，請確保專案目錄有 requirements.txt 檔案且包含 selenium、webdriver-manager 等套件。")
