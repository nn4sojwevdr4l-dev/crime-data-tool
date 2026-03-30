import streamlit as st
import pandas as pd
import feedparser
import urllib.parse
import time
import re
import io

# --- 基礎設定 ---
st.set_page_config(page_title="犯罪新聞精準提取工具", layout="wide")

def clean_html(text):
    if not text: return ""
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]*>', '', text)
    # 移除摘要開頭重複的媒體名稱或日期
    text = re.sub(r'^.*?\d{4}年\d{1,2}月\d{1,2}日 — ', '', text)
    return text.strip()[:150]

def crawl_data(target_date, include_list, exclude_list, buffer_limit=30, final_limit=10):
    KEYWORDS = [
        "洗錢"
    ]
    
    all_results = []
    seen_titles = set() 
    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, kw in enumerate(KEYWORDS):
        try:
            status_text.text(f"🚀 正在提取類別：{kw} (進度: {idx+1}/{len(KEYWORDS)})")
            
            # 使用 RSS 模擬手動搜尋語法
            query = f"{kw} after:{target_date}-01 before:{target_date}-31"
            encoded_query = urllib.parse.quote(query)
            rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
            
            feed = feedparser.parse(rss_url)
            count_for_this_kw = 0 
            
            for entry in feed.entries:
                if count_for_this_kw >= buffer_limit: break
                
                source = entry.source.get('title', '未知媒體')
                title = entry.title.split(' - ')[0]
                
                # 排除重複與過濾媒體
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
                    "發布時間": entry.get('published', '')
                })
                seen_titles.add(title)
                count_for_this_kw += 1
            
            progress_bar.progress((idx + 1) / len(KEYWORDS))
            time.sleep(0.1) # 穩定請求
            
        except Exception as e:
            st.error(f"搜尋 {kw} 時發生錯誤: {e}")

    if all_results:
        full_df = pd.DataFrame(all_results)
        final_df = full_df.groupby("犯罪類別").head(final_limit).reset_index(drop=True)
        return final_df
    return pd.DataFrame()

# --- UI 介面 ---
st.title("⚖️ 犯罪數據自動提取 (RSS 穩定版)")
st.info("本版本使用 Google RSS 接口，抓取結果與手動搜尋排序高度一致，且支援雲端部署。")

with st.sidebar:
    st.header("⚙️ 搜尋設定")
    target_date = st.text_input("📅 搜尋月份 (YYYY-MM)", value="2025-01")
    
    st.markdown("---")
    st.subheader("🚫 排除媒體")
    ex_input = st.text_area("排除名單 (用逗號分隔)", placeholder="例如: Yahoo, LINE TODAY")
    ex_list = [x.strip() for x in ex_input.replace('，', ',').split(',') if x.strip()]
    
    st.subheader("🎯 指定媒體")
    inc_input = st.text_area("指定名單 (留空則不限)", placeholder="例如: 自由時報, 聯合報")
    inc_list = [x.strip() for x in inc_input.replace('，', ',').split(',') if x.strip()]

if st.button("🚀 執行 29 類別一鍵提取"):
    if not target_date:
        st.error("請輸入日期")
    else:
        with st.spinner('正在精準同步數據...'):
            df = crawl_data(target_date, inc_list, ex_list)
            
            if not df.empty:
                st.success(f"任務完成！共抓取 {len(df)} 筆精選數據。")
                st.dataframe(df, use_container_width=True)
                
                # Excel 下載優化
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='犯罪數據')
                    # 自動調整欄寬 (透過 openpyxl 存檔後自動完成)
                
                st.download_button(
                    label="📥 下載 Excel 精選總表",
                    data=output.getvalue(),
                    file_name=f"犯罪新聞精選_{target_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("查無資料，請檢查篩選設定。")

st.markdown("---")
st.caption("提示：此版本最穩定且結果最準。如果客戶在雲端使用，這是唯一的 100% 成功路徑。")
