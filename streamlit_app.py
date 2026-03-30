import google.generativeai as genai
import pandas as pd
import time
import json
import re
import urllib.parse
from google.colab import files
from openpyxl.styles import Font, Alignment

# ================= 配置區域 =================
API_KEYS = [
    "第一組_API_KEY", 
    "第二組_API_KEY"
]

CRIME_TYPES = [
    "販毒", "吸金", "詐欺", "詐貸", "走私", "逃稅", "犯罪集團", "內線交易", "違反證券交易", 
    "侵占", "背信", "地下通匯", "賭博", "博弈", "貪污", "行賄", "仿冒", "盜版", 
    "侵害營業秘密", "第三方洗錢", "洗錢", "槍砲彈藥刀械", "贓物", "竊盜", "環保犯罪", 
    "偽造", "綁架", "拘禁", "妨害自由"
]

def start_full_task():
    all_results = []
    # 鎖定 2.5-Flash 路徑
    target_model = 'models/gemini-2.5-flash'
    
    print(f"🚀 啟動全量任務！共有 {len(CRIME_TYPES)} 個類別，預計耗時約 40 分鐘...")

    for i, crime in enumerate(CRIME_TYPES):
        current_idx = i % len(API_KEYS)
        current_key = API_KEYS[current_idx].strip()
        
        genai.configure(api_key=current_key)
        model = genai.GenerativeModel(target_model)
        
        print(f"📡 [Key {current_idx+1}] ({i+1}/{len(CRIME_TYPES)}) 處理中：{crime}...")
        
        try:
            # Prompt 強調台灣寫實新聞
            prompt = f"請提供 10 則 2025 年 1 月關於「{crime}」的台灣真實新聞。格式 JSON Array: [{{'標題': '...', '來源': '...', '摘要': '...'}}]. 摘要長度 70-90 字。"
            response = model.generate_content(prompt)
            
            # 解析 JSON
            json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
            if json_match:
                news_list = json.loads(json_match.group())
                for item in news_list:
                    title = item.get('標題', crime)
                    
                    # --- 搜尋連結優化 (關鍵！) ---
                    search_query = f'"{title}"'
                    encoded_query = urllib.parse.quote(search_query)
                    
                    # lr=lang_zh-TW: 指定搜尋繁體中文網頁
                    # tbs=cdr...: 指定 2025/01/01 - 2025/01/31
                    search_url = (
                        f"https://www.google.com/search?q={encoded_query}"
                        f"&lr=lang_zh-TW" 
                        f"&tbs=cdr:1,cd_min:1/1/2025,cd_max:1/31/2025"
                    )
                    
                    all_results.append({
                        "犯罪": crime,
                        "來源": item.get('來源', '媒體'),
                        "標題": title,
                        "摘要": item.get('摘要', '')[:90],
                        "連結": search_url
                    })
                print(f"✅ {crime} 處理成功！")
            
            # 為了避開 2.5 版嚴格的 429 限制，每類強制休息 80 秒
            if i < len(CRIME_TYPES) - 1:
                print("🕒 深度冷卻 80 秒以維持 API 穩定...")
                time.sleep(80)

        except Exception as e:
            print(f"❌ {crime} 失敗：{str(e)}")
            if "429" in str(e):
                print("🚨 觸發配額限制，強制休息 120 秒後嘗試下一類...")
                time.sleep(120)

    # --- Excel 格式鎖死 (A9, B14, 行高 16, 微軟正黑體 12) ---
    file_name = "2025_01_新聞全量彙整_繁體中文版.xlsx"
    df = pd.DataFrame(all_results)
    with pd.ExcelWriter(file_name, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
        ws = writer.sheets['Sheet1']
        font_style = Font(name='Microsoft JhengHei', size=12)
        
        # 欄寬：A=9, B=14
        ws.column_dimensions['A'].width = 9
        ws.column_dimensions['B'].width = 14
        ws.column_dimensions['C'].width = 45
        ws.column_dimensions['D'].width = 65
        ws.column_dimensions['E'].width = 40

        # 行高鎖死 16
        for r_idx in range(1, ws.max_row + 1):
            ws.row_dimensions[r_idx].height = 16
            for cell in ws[r_idx]:
                cell.font = font_style
                cell.alignment = Alignment(vertical='center', wrap_text=False)

    print(f"🎉 全部任務完成！檔案已生成：{file_name}")
    files.download(file_name)

if __name__ == "__main__":
    start_task()
