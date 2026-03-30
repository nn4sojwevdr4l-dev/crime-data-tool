import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪數據精選工具 (測試版 V1.1)", layout="wide")

def clean_html(text):
    if not text: return ""
    return re.sub(re.compile('<.*?>'), '', text)

def crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", 
        "違反證券交易", "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", 
        "行賄", "仿冒", "盜版", "侵害營業秘密", "第三方洗錢", "洗錢", 
        "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", "偽造", "綁架", "拘禁", "妨害自由"
    ]
    
    all_results = []
    seen_titles = set() 
    
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 正在分析：{kw} (進度: {idx+1}/{len(KEYWORDS)})")
            
            # 格式化日期查詢
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count_for_this_kw = 0 
            
            # 1. 緩衝抓取階段
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

                all_results.append({
                    "犯罪類別": kw,
                    "來源": source,
                    "標題": title,
                    "摘要": clean_html(entry.get('summary', '')),
                    "連結": entry.link,
                    "發布日期": entry.get('published', '')
                })
                seen_titles.add(title)
                count_for_this_kw += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.05)
            
        except Exception as e:
            st.error(f"搜尋 {kw} 時發生錯誤: {e}")

    if all_results:
        full_df = pd.DataFrame(all_results)
        # 依照「犯罪類別」分組，每組取前 10 筆
        final_df = full_df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
        return final_df
    return pd.DataFrame()

# --- UI 介面 ---
st.title("🔍 犯罪數據精選工具 (30取10版)")
st.info("運作邏輯：系統會先篩選出最多 30 筆符合條件的新聞，最後精選「前 10 筆」寫入 Excel。")

with st.sidebar:
    st.header("⚙️ 篩選設定")
    target_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    exclude_input = st.text_area("輸入要排除的媒體（用逗號分隔）", placeholder="例如: Yahoo, LINE TODAY")
    exclude_list = [x.strip() for x in exclude_input.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體")
    include_input = st.text_area("只抓取這些媒體（用逗號分隔）", placeholder="例如: 自由時報, 聯合報")
    include_list = [x.strip() for x in include_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 開始執行精選任務"):
    with st.spinner('正在從海量新聞中精選數據...'):
        df = crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10)
        
        if not df.empty:
            st.success(f"任務完成！每個類別已精選最多 10 筆，總計 {len(df)} 筆。")
            st.dataframe(df, use_container_width=True)
            
            output = io.BytesIO()
            # 使用 openpyxl 作為引擎
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 下載精選數據總表.xlsx",
                data=output.getvalue(),
                file_name=f"犯罪數據精選_{target_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.warning("⚠️ 查無資料，請放寬篩選條件。")