import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取 (同步版)", layout="wide")

def clean_html(text):
    if not text: return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]*>', '', text)
    # 移除摘要中常見的重複日期前綴
    text = re.sub(r'^\d{4}年\d{1,2}月\d{1,2}日\s*[-—]\s*', '', text)
    return text.replace('\n', ' ').strip()[:150]

def crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10):
    # 這裡是你那 29 個精準關鍵字
    KEYWORDS = ["洗錢"]
    
    all_results = []
    seen_titles = set() 
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 同步搜尋中：{kw} ({idx+1}/{len(KEYWORDS)})")
            
            # 【關鍵點】: 這裡的日期與關鍵字組合必須與你手動搜尋時輸入的一模一樣
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            
            # 【關鍵強化】: 加入特定參數，強制 Google News 採用台灣本地排序 (GL=TW, HL=zh-TW)
            # ceid=TW:zh-Hant 是讓它與台灣網頁版同步的關鍵標記
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count_for_kw = 0 
            
            for entry in feed.entries:
                if count_for_kw >= buffer_limit: break
                
                source = entry.source.get('title', '未知來源')
                title = entry.title.split(' - ')[0] # 移除標題結尾的來源
                
                if title in seen_titles: continue
                if any(ex in source for ex in exclude_list if ex): continue
                
                is_included = True
                if include_list and any(inc for inc in include_list if inc):
                    is_included = any(inc in source for inc in include_list if inc)
                
                if not is_included: continue

                all_results.append({
                    "犯罪類別": kw,
                    "媒體來源": source,
                    "新聞標題": title,
                    "內容摘要": clean_html(entry.get('summary', '')),
                    "原始連結": entry.link,
                    "發布日期": entry.get('published', '')
                })
                seen_titles.add(title)
                count_for_kw += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.05) # 稍微緩衝避開 API 限制
            
        except Exception as e:
            st.error(f"⚠️ {kw} 提取異常: {e}")

    return pd.DataFrame(all_results)

# --- 介面 ---
st.title("⚖️ 犯罪數據一鍵精選提取")
st.info("運作邏輯：模擬手動進階搜尋語法，透過 RSS 接口抓取與網頁版排序一致的新聞數據。")

with st.sidebar:
    st.header("⚙️ 搜尋設定")
    target_date = st.text_input("📅 月份 (YYYY-MM)", value="2025-01")
    limit = st.slider("每個類別抓取上限", 1, 20, 10)
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    ex_input = st.text_area("排除名單 (逗號分隔)")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體")
    inc_input = st.text_area("只看這些媒體 (留空則不限)")
    inc_list = [x.strip() for x in inc_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始全自動執行任務"):
    with st.spinner('正在與 Google 數據庫同步...'):
        df_full = crawl_data(target_date, inc_list, ex_list, buffer_limit=30, final_limit=limit)
        
        if not df_full.empty:
            # 確保每個類別只取前 10 筆 (與你手動精選的邏輯一致)
            df = df_full.groupby("犯罪類別").head(limit).reset_index(drop=True)
            
            st.success(f"✅ 完成！總計獲取 {len(df)} 筆精選資料。")
            st.dataframe(df, use_container_width=True)
            
            # Excel 匯出
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 下載精選結果 (.xlsx)",
                data=output.getvalue(),
                file_name=f"犯罪新聞精選_{target_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("查無結果，請確認日期格式是否正確。")
