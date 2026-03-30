# --- Selenium 初始化 (針對 Streamlit Cloud 環境修復版) ---
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    
    # 強制指定 Linux 系統中 Chromium 的路徑
    chrome_options.binary_location = "/usr/bin/chromium" 

    try:
        # 直接調用系統安裝的 chromedriver，不需要安裝器
        service = Service("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(10) 
    except Exception as e:
        # 如果路徑失敗，嘗試後備方案 (給本地測試用)
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            st.error(f"瀏覽器啟動失敗: {e}")
            return pd.DataFrame()
