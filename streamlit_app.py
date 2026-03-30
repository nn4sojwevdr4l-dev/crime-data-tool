import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time
import io

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞提取 - 第一階段 (連結撈取)", layout="wide")

def clean_text(text):
    if not text: return ""
    # 移除 HTML 標籤與多餘空格
    text = re.sub(r'<[^>]*>', '', text)
    return text.strip()

def crawl_step_1(target_date, exclude_list, include_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "洗錢"
    ]

    # 關鍵偽裝 Header，模擬真實瀏覽器行為
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.google.com/"
    }

    all_links = []
    seen_titles = set()
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在從 Google 原始碼撈取連結：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 構建手動搜尋網址 (新聞分頁 tbm=nws)
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded_query}&tbm=nws&hl=zh-TW&gl=tw"
            
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                st.warning(f"⚠️ {kw} 請求異常 (HTTP {response.status_code})")
                continue

            soup = BeautifulSoup(response.text, "html.parser")
            # 鎖定 Google 新聞網頁標準容器 SoaBEf
            items = soup.select("div.SoaBEf")
            
            count_for_kw = 0
            for item in items:
                if count_for_kw >= buffer_limit: break 
                
                try:
                    title_elem = item.select_one("div[role='heading']")
                    link_elem = item.select_one("a")
                    source_elem = item.select_one("div.MgUUmf")
                    
                    if not title_elem or not link_elem: continue
                    
                    title = title_elem.text
                    link = link_elem["href"]
                    source = source_elem.text if source_elem else "未知媒體"
                    
                    # 過濾重複與指定/排除媒體
                    if title in seen_titles: continue
                    if any(ex in source for ex in exclude_list if ex): continue
                    if include_list and not any(inc in source for inc in include_list if inc): continue

                    all_links.append({
                        "犯罪類別": kw,
                        "來源媒體": source,
                        "標題": title,
                        "連結": link
                    })
                    seen_titles.add(title)
                    count_for_kw += 1
                except:
                    continue
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(1.2) # 延遲確保不被鎖 IP
            
        except Exception as e:
            st.error(f"解析 {kw} 出錯：{e}")

    if all_links:
        df = pd.DataFrame(all_links)
        # 執行 30 取 10 (每組類別保留前 10 筆)
        final_df = df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
        return final_df
    return pd.DataFrame()

# --- UI 介面 ---
st.title("⚖️ 第一階段：犯罪新聞連結精準提取 (30 取 10)")
st.info("💡 運作說明：本工具直接解析 Google 搜尋原始碼，獲取精確的原始新聞連結清單。")

with st.sidebar:
    st.header("⚙️ 搜尋設定")
    target_month = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    st.markdown("---")
    st.subheader("🚫 排除媒體 (逗號隔開)")
    ex_input = st.text_area("例如: Yahoo, LINE TODAY")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始執行 (一鍵撈取 29 類別連結)"):
    if not target_month:
        st.error("請輸入日期")
    else:
        with st.spinner('正在分析原始數據...'):
            result_df = crawl_step_1(target_month, ex_list, [])
            
            if not result_df.empty:
                st.success(f"✅ 任務完成！共撈取 {len(result_df)} 筆原始連結。")
                st.dataframe(result_df, use_container_width=True)
                
                # 輸出 CSV 供第二階段使用
                output = io.BytesIO()
                result_df.to_csv(output, index=False, encoding='utf-8-sig')
                
                st.download_button(
                    label="📥 下載連結清單 (CSV)",
                    data=output.getvalue(),
                    file_name=f"CrimeLinks_{target_month}.csv",
                    mime="text/csv"
                )
            else:
                st.error("❌ 提取失敗：請檢查 Google 是否彈出驗證碼，或嘗試在本地執行。")

st.markdown("---")
st.caption("完成第一階段後，請保存 CSV 檔案，再進行第二階段的內文提取。")
