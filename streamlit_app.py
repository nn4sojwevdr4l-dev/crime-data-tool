import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞爬蟲工具", layout="wide")

def clean_content(text):
    """ 整理新聞內文格式 """
    if not text: return ""
    # 移除 HTML 標籤
    text = re.sub(re.compile('<.*?>'), '', text)
    # 刷掉摘要開頭的日期 (例如 2026年1月16日 — )
    date_pattern = r'^\d{4}年\d{1,2}月\d{1,2}日\s*[-—]\s*'
    text = re.sub(date_pattern, '', text).strip()
    # 統一換行符號並去除多餘空格
    text = text.replace('\n', ' ').replace('\r', '')
    # 只取前 100 字
    return text[:100].strip()

def get_news_content(driver, url):
    """ 前往新聞網址撈取前 100 字內容 """
    try:
        driver.get(url)
        # 設定短暫等待，讓內容載入
        time.sleep(1.5) 
        
        # 優先嘗試抓取 Meta Description
        try:
            meta_desc = driver.find_element(By.XPATH, "//meta[@name='description']").get_attribute("content")
            if meta_desc and len(meta_desc) > 40:
                return clean_content(meta_desc)
        except:
            pass
            
        # 若 Meta 不理想，抓取頁面中的段落標籤
        paragraphs = driver.find_elements(By.TAG_NAME, "p")
        combined_text = ""
        for p in paragraphs:
            txt = p.text.strip()
            if len(txt) > 20: 
                combined_text += txt
            if len(combined_text) >= 100:
                break
        
        return clean_content(combined_text) if combined_text else "無法讀取內容"
    except:
        return "網頁讀取失敗"

def crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "洗錢"
    ]
    
    # --- Selenium 初始化 (針對 Streamlit Cloud 環境優化) ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false") # 速度優化
    
    # 指定系統中 Chromium 的路徑
    chrome_options.binary_location = "/usr/bin/chromium"

    try:
        # 在 Streamlit Cloud 上，packages.txt 會安裝驅動到此路徑
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(15) 
    except Exception as e:
        st.error(f"瀏覽器啟動失敗: {e}")
        return pd.DataFrame()

    all_results = []
    seen_titles = set() 
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 正在分析：{kw} (進度: {idx+1}/{len(KEYWORDS)})")
            
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count_for_this_kw = 0 
            
            for entry in feed.entries:
                if count_for_this_kw >= buffer_limit:
                    break
                
                source = entry.source.get('title', '未知媒體')
                title = entry.title.split(' - ')[0]
                
                # 去重與過濾
                if title in seen_titles: continue
                if any(ex in source for ex in exclude_list if ex): continue
                
                is_included = True
                if include_list and any(inc for inc in include_list if inc):
                    is_included = any(inc in source for inc in include_list if inc)
                
                if not is_included: continue

                # 進入網頁抓取內容
                link = entry.link
                real_content = get_news_content(driver, link)

                all_results.append({
                    "犯罪類別": kw,
                    "來源": source,
                    "標題": title,
                    "摘要": real_content,
                    "連結": link,
                    "發布日期": entry.get('published', '')
                })
                seen_titles.add(title)
                count_for_this_kw += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.error(f"搜尋 {kw} 時發生錯誤: {e}")

    driver.quit()

    if all_results:
        full_df = pd.DataFrame(all_results)
        final_df = full_df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
        return final_df
    return pd.DataFrame()

# --- UI 介面 ---
st.title("🔍 犯罪新聞爬蟲工具")
st.info("運作邏輯：系統會透過 RSS 鎖定名單，並進入新聞頁面提取前 100 字精準摘要。")

with st.sidebar:
    st.header("⚙️ 篩選設定")
    target_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    exclude_input = st.text_area("輸入要排除的媒體 (要用逗號分隔,不要笨!)", placeholder="例如: Yahoo, LINE TODAY")
    exclude_list = [x.strip() for x in exclude_input.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體")
    include_input = st.text_area("只抓取這些媒體 (要用逗號分隔,不要笨!)", placeholder="例如: 自由時報, 聯合報")
    include_list = [x.strip() for x in include_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始執行深度爬蟲任務"):
    with st.spinner('正在精選數據並讀取網頁內容，請稍候...'):
        df = crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10)
        
        if not df.empty:
            st.success(f"任務完成！每個類別已精選前 10 筆，總計 {len(df)} 筆。")
            st.dataframe(df, width='stretch') # 修正 Container 警告
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 下載精選數據總表.xlsx",
                data=output.getvalue(),
                file_name=f"犯罪新聞_{target_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ 查無資料，請檢查關鍵字或篩選條件。")
