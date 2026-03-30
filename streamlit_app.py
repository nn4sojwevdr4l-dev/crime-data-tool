import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import io
import re
import time

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪數據全自動提取 (穩定版)", layout="wide")

def clean_html(text):
    if not text: return ""
    # 移除 HTML 標籤
    clean = re.compile('<.*?>')
    text = re.sub(clean, '', text)
    # 移除多餘空格與換行
    text = text.replace('\n', ' ').replace('\r', ' ').strip()
    return text[:100]

def crawl_rss_news(target_date, final_limit, ex_list):
    KEYWORDS = [
        "洗錢"
    ]

    all_data = []
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"📡 正在處理：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 構建搜尋語句：包含日期區間
            # 例如：詐欺 after:2025-01-01 before:2025-01-31
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            # 使用 Google News RSS 接口 (這個接口在雲端不會被封鎖)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            
            count = 0
            for entry in feed.entries:
                if count >= final_limit: break
                
                source = entry.source.get('title', '新聞媒體')
                
                # 排除媒體過濾
                if any(ex in source for ex in ex_list if ex): continue

                all_data.append({
                    "犯罪類別": kw,
                    "來源": source,
                    "標題": entry.title.split(' - ')[0],
                    "摘要": clean_html(entry.summary if 'summary' in entry else entry.title),
                    "連結": entry.link,
                    "發布日期": entry.get('published', '')
                })
                count += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.1) # 稍微停頓
            
        except Exception as e:
            st.warning(f"⚠️ {kw} 抓取略過")

    return pd.DataFrame(all_data)

# --- UI 介面 ---
st.title("⚖️ 犯罪新聞數據提取 (雲端穩定版)")
st.info("此版本使用 RSS 接口，解決了 Google 搜尋被封鎖的問題。")

with st.sidebar:
    st.header("⚙️ 設定參數")
    user_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    user_limit = st.number_input("每個類別數量", 1, 50, 10)
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    ex_text = st.text_area("例如: Yahoo, LINE TODAY (逗號隔開)")
    ex_list = [x.strip() for x in ex_text.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動執行任務"):
    if not user_date:
        st.error("請輸入日期！")
    else:
        with st.spinner('數據提取中，請稍候...'):
            df = crawl_rss_news(user_date, user_limit, ex_list)
            
            if not df.empty:
                st.success(f"✅ 完成！共計 {len(df)} 筆資料。")
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
            else:
                st.error("❌ 依然抓不到東西。這通常是因為 Google RSS 暫時限制了該主機的訪問，請 5 分鐘後再試。")

st.markdown("---")
st.caption("提示：若需要與手動搜尋結果完全一致，建議下載此代碼並在本地電腦執行 Selenium 版本。")
