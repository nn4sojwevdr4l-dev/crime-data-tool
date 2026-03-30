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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪數據自動化提取工具 V2.0", layout="wide")

def clean_text(text):
    if not text: return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]*>', '', text)
    # 移除常見的日期前綴 (例如: 2025年1月5日 — )
    text = re.sub(r'^\d{4}年\d{1,2}月\d{1,2}日\s*[-—]\s*', '', text)
    # 移除換行與多餘空格
    text = text.replace('\n', ' ').replace('\r', ' ').strip()
    return text[:100] # 嚴格限制 100 字

def get_deep_content(driver, url):
    """ 當 Google 摘要不夠時，進入內文抓取前 100 字 """
    try:
        driver.get(url)
        time.sleep(1.5)
        # 優先抓 Meta Description
        try:
            meta = driver.find_element(By.XPATH, "//meta[@name='description']").get_attribute("content")
            if meta and len(meta) > 40:
                return clean_text(meta)
        except:
            pass
        # 次之抓取前幾個 P 標籤
        paragraphs = driver.find_elements(By.TAG_NAME, "p")
        content = "".join([p.text for p in paragraphs[:3]])
        return clean_text(content) if content else "無法讀取內文"
    except:
        return "連結讀取失敗"

def crawl_google_news(target_date, include_list, exclude_list, final_limit=10):
    KEYWORDS = [
        "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", 
        "違反證券交易", "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", 
        "行賄", "仿冒", "盜版", "侵害營業秘密", "第三方洗錢", "洗錢", 
        "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", "偽造", "綁架", "拘禁", "妨害自由"
    ]

    # --- Selenium 初始化 ---
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--blink-settings=imagesEnabled=false")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(15)
    except Exception as e:
        st.error(f"瀏覽器啟動失敗: {e}")
        return pd.DataFrame()

    all_results = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在同步 Google 搜尋結果：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 模擬手動「新聞」標籤搜尋
            query = f"{kw} {target_date}"
            encoded_query = urllib.parse.quote(query)
            search_url = f"https://www.google.com/search?q={encoded_query}&hl=zh-TW&gl=tw&tbm=nws"
            
            driver.get(search_url)
            time.sleep(2) # 等待 Google 渲染

            # 定位新聞容器 (SoaBEf)
            items = driver.find_elements(By.CSS_SELECTOR, "div.SoaBEf")
            
            count_for_kw = 0
            for item in items:
                if count_for_kw >= final_limit: break
                
                try:
                    title = item.find_element(By.CSS_SELECTOR, "[role='heading']").text
                    link = item.find_element(By.CSS_SELECTOR, "a").get_attribute("href")
                    source = item.find_element(By.CSS_SELECTOR, "div.MgUUmf").text
                    google_snippet = item.find_element(By.CSS_SELECTOR, "div.UqSP2b").text
                    
                    # 排除媒體過濾
                    if any(ex in source for ex in exclude_list if ex): continue
                    # 指定媒體過濾
                    if include_list and not any(inc in source for inc in include_list if inc): continue

                    # 摘要處理：如果 Google 給的摘要太短，就深入網頁抓取
                    final_snippet = clean_text(google_snippet)
                    if len(final_snippet) < 30:
                        final_snippet = get_deep_content(driver, link)
                        # 抓完深層內容要跳回搜尋頁，否則下一個 item 找不到
                        driver.back()
                        time.sleep(1)

                    all_results.append({
                        "犯罪類別": kw,
                        "來源": source,
                        "標題": title.split(' - ')[0],
                        "摘要": final_snippet,
                        "連結": link
                    })
                    count_for_kw += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            
        except Exception as e:
            st.warning(f"⚠️ 關鍵字 {kw} 搜尋中斷: {e}")

    driver.quit()
    return pd.DataFrame(all_results)

# --- Streamlit UI ---
st.title("⚖️ 犯罪新聞數據全自動提取工具")
st.markdown("本工具直接模擬 **Google 網頁搜尋**，結果與手動搜尋完全一致。")

with st.sidebar:
    st.header("⚙️ 搜尋設定")
    user_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    limit = st.slider("每個類別抓取數量", 1, 20, 10)
    
    st.markdown("---")
    st.subheader("🚫 排除媒體 (逗號隔開)")
    ex_input = st.text_area("例如: Yahoo, LINE TODAY", "")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體 (逗號隔開)")
    inc_input = st.text_area("不填則抓取全部", "")
    inc_list = [x.strip() for x in inc_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始執行 29 類別全自動任務"):
    if not user_date:
        st.error("請輸入日期！")
    else:
        with st.spinner('正在模擬真人搜尋並提取數據，請稍候...'):
            df = crawl_google_news(user_date, inc_list, ex_list, final_limit=limit)
            
            if not df.empty:
                st.success(f"任務完成！共抓取 {len(df)} 筆資料。")
                st.dataframe(df, use_container_width=True)
                
                # 下載 Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 下載完整 Excel 總表",
                    data=output.getvalue(),
                    file_name=f"犯罪數據總表_{user_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.error("❌ 抓取失敗，可能是被 Google 暫時封鎖 IP，請稍後再試或檢查網路。")

st.info("💡 提示：若出現抓取不到的情況，請嘗試切換日期格式或確認網路是否可正常開啟 Google。")
