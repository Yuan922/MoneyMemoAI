import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import random
from io import BytesIO
import requests
import yaml
from yaml.loader import SafeLoader
import extra_streamlit_components as stx

# 設定頁面
st.set_page_config(
    page_title="打字記帳",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 設定預設用戶
if 'username' not in st.session_state:
    st.session_state.username = 'yuan'

# 確保資料目錄存在
os.makedirs('data', exist_ok=True)

# 設定用戶資料路徑
USER_DATA_PATH = f'data/expenses_{st.session_state.username}.csv'

# 初始化資料框架
if 'df' not in st.session_state:
    try:
        st.session_state.df = pd.read_csv(USER_DATA_PATH,
            dtype={'日期': str, '類別': str, '名稱': str, '價格': float, '支付方式': str})
    except FileNotFoundError:
        st.session_state.df = pd.DataFrame(columns=[
            '日期', '類別', '名稱', '價格', '支付方式'
        ])

# 初始化 Gemini
load_dotenv()
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

# 設定支援的幣別
CURRENCIES = {
    "JPY": "日圓 ¥",
    "TWD": "新台幣 NT$",
    "USD": "美元 $"
}

# 取得即時匯率
def get_exchange_rates(base_currency="JPY"):
    rates = {
        'TWD': 0.23,  # 預設匯率，1日圓約0.23新台幣
        'USD': 0.0067  # 預設匯率，1日圓約0.0067美元
    }
    
    try:
        # 使用 ExchangeRate-API 的免費端點
        response = requests.get(f"https://open.er-api.com/v6/latest/{base_currency}")
        if response.status_code == 200:
            data = response.json()
            for currency in CURRENCIES.keys():
                if currency != base_currency and currency in data['rates']:
                    rates[currency] = data['rates'][currency]
        else:
            st.warning("無法取得即時匯率，使用預設匯率")
    except Exception as e:
        st.warning(f"無法取得即時匯率，使用預設匯率")
    
    return rates

# 自定義 CSS 樣式
st.markdown("""
<style>
    /* 主要容器樣式 */
    .main-container {
        padding: 1rem;
        max-width: 1200px;
        margin: 0 auto;
    }
    
    /* 卡片樣式 */
    .card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        border: 1px solid #f0f0f0;
    }
    
    /* 卡片標題樣式 */
    .card-title {
        color: #1f1f1f;
        font-size: 1.2rem;
        font-weight: 600;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #f0f0f0;
    }
    
    /* 分析區塊樣式 */
    .analysis-section {
        background-color: #f8f9fa;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
    }
    
    /* 圖表容器樣式 */
    .chart-container {
        background-color: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #f0f0f0;
    }
    
    /* 總計金額樣式 */
    .total-amount {
        background-color: #f8f9fa;
        padding: 1.2rem;
        border-radius: 12px;
        margin: 1rem 0;
        border: 1px solid #e9ecef;
    }
    
    .total-amount strong {
        color: #1f1f1f;
        font-size: 1.1rem;
    }
    
    /* 操作按鈕樣式 */
    .stButton > button {
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: 500;
    }
    
    /* 表格樣式優化 */
    .stDataFrame {
        background-color: white;
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #f0f0f0;
    }
    
    .stDataFrame td, .stDataFrame th {
        padding: 8px 12px;
    }
    
    /* Tabs 樣式優化 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 8px 16px;
        border-radius: 8px;
    }
    
    /* 指標卡片樣式 */
    div[data-testid="metric-container"] {
        background-color: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #f0f0f0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# 移除分頁，直接使用主要介面
# 定義支付方式選項
PAYMENT_METHODS = ["現金", "信用卡", "樂天Pay", "PayPay"]

# 檢查是否在嘗試存取其他使用者的資料
current_user = st.session_state.username

# 更新：每次都重新設定當前使用者的資料路徑
if current_user == 'admin':
    selected_user = st.selectbox(
        "選擇要查看的使用者",
        options=[user for user in USERS.keys()],
        index=list(USERS.keys()).index(current_user)
    )
    USER_DATA_PATH = f'data/expenses_{selected_user}.csv'
else:
    USER_DATA_PATH = f'data/expenses_{current_user}.csv'

# 重新載入當前使用者的資料
try:
    st.session_state.df = pd.read_csv(USER_DATA_PATH,
        dtype={'日期': str, '類別': str, '名稱': str, '價格': float, '支付方式': str})
except FileNotFoundError:
    st.session_state.df = pd.DataFrame(columns=[
        '日期', '類別', '名稱', '價格', '支付方式'
    ])

# 將操作模式放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📝 記帳模式</div>', unsafe_allow_html=True)
operation_mode = st.radio(
    "選擇操作模式",
    ["新增記錄", "修改記錄"],
    horizontal=True
)
st.markdown('</div>', unsafe_allow_html=True)

# 將輸入表單放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
if operation_mode == "新增記錄":
    st.markdown('<div class="card-title">✨ 新增記錄</div>', unsafe_allow_html=True)
    with st.form("input_form"):
        input_text = st.text_input("文字輸入（範例：晚餐吃拉麵用現金支付980日幣）")
        submit_button = st.form_submit_button("💾 儲存記錄")
        
        if submit_button and input_text:
            try:
                # 設定時區為日本時間
                JST = timezone(timedelta(hours=9))
                current_time = datetime.now(JST)
                
                prompt = f"""
                請從以下文字中提取記帳資訊，並以 JSON 格式回傳。
                如果包含多筆消費，請分別提取並以陣列形式回傳。
                
                當前時間：{current_time.strftime("%Y-%m-%d")}
                如果沒有提到具體日期，請使用上述日期。
                
                請從以下文字中提取消費資訊，並以JSON格式回傳，包含以下欄位：
                日期（如果沒提到就用 {current_time.strftime("%Y-%m-%d")}）、類別（早餐/午餐/晚餐/點心/交通/娛樂/儲值/其他）、
                名稱、價格、支付方式（現金/信用卡/樂天Pay/PayPay）
                
                請確保回傳的格式完全符合以下範例：
                [
                    {{"日期": "{current_time.strftime("%Y-%m-%d")}", "類別": "晚餐", "名稱": "拉麵", "價格": 980, "支付方式": "現金"}},
                    {{"日期": "{current_time.strftime("%Y-%m-%d")}", "類別": "點心", "名稱": "飲料", "價格": 150, "支付方式": "現金"}}
                ]
                
                注意：
                1. 日期必須是 YYYY-MM-DD 格式
                2. 如果是下午茶、咖啡廳、飲料店等非正餐的飲食消費，請歸類為「點心」
                3. 請保持支付方式的原始名稱（如：樂天Pay、PayPay）
                4. 即使只有一筆消費，也請使用陣列格式回傳
                
                文字：{input_text}
                """
                
                response = model.generate_content(prompt)
                results = json.loads(response.text)
                
                # 確保 results 是列表
                if not isinstance(results, list):
                    results = [results]
                
                # 將每筆記錄加入 DataFrame
                for result in results:
                    new_row = pd.DataFrame([result])
                    st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                
                # 儲存更新後的資料
                st.session_state.df.to_csv(USER_DATA_PATH, index=False)
                
                # 顯示成功訊息
                st.success(f"已新增 {len(results)} 筆記錄！")
                
                # 顯示每筆記錄的詳細資訊
                for result in results:
                    st.write(f"✅ {result['名稱']}：{result['價格']}元（{result['支付方式']}）")
                
            except Exception as e:
                st.error(f"處理錯誤: {str(e)}")
                st.error("AI 回應內容：" + response.text)
else:
    st.markdown('<div class="card-title">✏️ 修改記錄</div>', unsafe_allow_html=True)
    with st.form("edit_form"):
        input_text = st.text_input("請輸入要修改的內容（例如：一顆奇異果花150，然後買了章魚生魚片花350是昨天晚上！不是2-20）")
        submit_button = st.form_submit_button("✏️ 修改記錄")
        
        if submit_button and input_text:
            try:
                # 設定時區為日本時間
                JST = timezone(timedelta(hours=9))
                current_time = datetime.now(JST)
                yesterday = current_time - timedelta(days=1)
                
                prompt = f"""
                你是一個資料庫搜尋專家。請從用戶的修改請求中，提取要修改的記錄資訊。
                如果包含多筆記錄，請分別提取並以陣列形式回傳。
                
                當前時間：{current_time.strftime("%Y-%m-%d")}
                昨天日期：{yesterday.strftime("%Y-%m-%d")}
                
                請回傳以下格式的 JSON：
                [
                    {{
                        "search": {{
                            "名稱": "商品名稱",  // 用於搜尋的關鍵字
                            "價格": 數字  // 可選，用於確認是否為同一筆記錄
                        }},
                        "update": {{
                            "日期": "YYYY-MM-DD",  // 如果要修改日期
                            "價格": 數字,  // 如果要修改價格
                            "支付方式": "付款方式",  // 如果要修改支付方式
                            "類別": "分類"  // 如果要修改分類
                        }}
                    }}
                ]

                範例：
                輸入："奇異果150元和章魚生魚片350元是昨天買的"
                輸出：[
                    {{"search": {{"名稱": "奇異果", "價格": 150}}, "update": {{"日期": "{yesterday.strftime('%Y-%m-%d')}"}}}},
                    {{"search": {{"名稱": "章魚生魚片", "價格": 350}}, "update": {{"日期": "{yesterday.strftime('%Y-%m-%d')}"}}}}
                ]

                請處理以下修改請求：
                {input_text}
                """
                
                response = model.generate_content(prompt)
                # 清理 AI 回應中可能的格式標記
                cleaned_response = response.text.strip()
                if cleaned_response.startswith('```') and cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[cleaned_response.find('{'):cleaned_response.rfind('}')+1]
                
                results = json.loads(cleaned_response)
                
                # 確保 results 是列表
                if not isinstance(results, list):
                    results = [results]
                
                # 記錄成功修改的數量
                success_count = 0
                
                # 處理每筆修改請求
                for result in results:
                    # 尋找符合條件的記錄
                    mask = pd.Series(True, index=st.session_state.df.index)
                    for key, value in result["search"].items():
                        if pd.isna(value):  # 處理空值的情況
                            mask &= pd.isna(st.session_state.df[key])
                        else:
                            # 將 DataFrame 中的值和搜尋值都轉換為小寫並去除空白
                            df_values = st.session_state.df[key].astype(str).str.strip().str.lower()
                            search_value = str(value).strip().lower()
                            # 使用 contains 而不是完全匹配
                            mask &= df_values.str.contains(search_value, case=False, na=False)
                    
                    if mask.any():
                        # 更新符合條件的記錄
                        for key, value in result["update"].items():
                            st.session_state.df.loc[mask, key] = value
                        success_count += 1
                
                if success_count > 0:
                    # 儲存更新後的資料
                    st.session_state.df.to_csv(USER_DATA_PATH, index=False)
                    st.success(f"已更新 {success_count} 筆記錄！")
                else:
                    st.error("找不到符合的記錄！請試著簡化搜尋條件。")
                
            except Exception as e:
                st.error(f"處理錯誤: {str(e)}")
                st.error("AI 回應內容：" + response.text)
st.markdown('</div>', unsafe_allow_html=True)

# 將匯入功能放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📤 匯入資料</div>', unsafe_allow_html=True)
with st.expander("選擇檔案", expanded=False):
    uploaded_file = st.file_uploader(
        "選擇要匯入的 Excel 或 CSV 檔案",
        type=['xlsx', 'csv'],
        help="支援 .xlsx 或 .csv 格式的檔案"
    )
    
    if uploaded_file is not None:
        try:
            # 根據檔案類型讀取資料
            if uploaded_file.name.endswith('.csv'):
                imported_df = pd.read_csv(uploaded_file)
            else:  # Excel 檔案
                imported_df = pd.read_excel(uploaded_file)
            
            # 驗證欄位
            required_columns = ['日期', '類別', '名稱', '價格', '支付方式']
            if not all(col in imported_df.columns for col in required_columns):
                st.error("檔案格式錯誤！必須包含以下欄位：日期、類別、名稱、價格、支付方式")
                st.stop()
            
            # 驗證資料類型
            try:
                # 確保日期格式正確
                imported_df['日期'] = pd.to_datetime(imported_df['日期']).dt.strftime('%Y-%m-%d')
                # 確保價格為數值
                imported_df['價格'] = pd.to_numeric(imported_df['價格'])
                
                # 驗證類別
                valid_categories = ["早餐", "午餐", "晚餐", "點心", "交通", "娛樂", "儲值", "其他"]
                if not imported_df['類別'].isin(valid_categories).all():
                    invalid_categories = imported_df[~imported_df['類別'].isin(valid_categories)]['類別'].unique()
                    st.error(f"發現無效的類別：{', '.join(invalid_categories)}")
                    st.stop()
                
                # 驗證支付方式
                if not imported_df['支付方式'].isin(PAYMENT_METHODS).all():
                    invalid_methods = imported_df[~imported_df['支付方式'].isin(PAYMENT_METHODS)]['支付方式'].unique()
                    st.error(f"發現無效的支付方式：{', '.join(invalid_methods)}")
                    st.stop()
                
            except Exception as e:
                st.error(f"資料格式錯誤：{str(e)}")
                st.stop()
            
            col1, col2 = st.columns(2)
            with col1:
                import_mode = st.radio(
                    "選擇匯入模式",
                    ["附加到現有資料", "覆蓋現有資料"],
                    help="附加：將新資料加到現有資料後面\n覆蓋：用新資料取代所有現有資料"
                )
            
            with col2:
                if st.button("確認匯入", type="primary"):
                    if import_mode == "附加到現有資料":
                        # 附加模式
                        st.session_state.df = pd.concat([st.session_state.df, imported_df], ignore_index=True)
                    else:
                        # 覆蓋模式
                        st.session_state.df = imported_df.copy()
                    
                    # 儲存更新後的資料
                    st.session_state.df.to_csv(USER_DATA_PATH, index=False)
                    st.success(f"成功匯入 {len(imported_df)} 筆資料！")
                    st.rerun()
            
            # 預覽匯入的資料
            st.subheader("預覽匯入資料")
            st.dataframe(
                imported_df,
                use_container_width=True,
                hide_index=True
            )
            
        except Exception as e:
            st.error(f"匯入失敗：{str(e)}")
st.markdown('</div>', unsafe_allow_html=True)

# 將支出記錄表格放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📊 支出記錄</div>', unsafe_allow_html=True)
edited_df = st.data_editor(
    st.session_state.df,
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "日期": st.column_config.TextColumn(
            "日期",
            help="請使用 YYYY-MM-DD 格式",
            required=True,
            validate="^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
        ),
        "類別": st.column_config.SelectboxColumn(
            "類別",
            options=["早餐", "午餐", "晚餐", "點心", "交通", "娛樂", "儲值", "其他"],
            required=True
        ),
        "名稱": st.column_config.TextColumn(
            "名稱",
            required=True
        ),
        "價格": st.column_config.NumberColumn(
            "價格 (JPY)",
            min_value=0,
            required=True,
            format="%.0f"
        ),
        "支付方式": st.column_config.SelectboxColumn(
            "支付方式",
            options=PAYMENT_METHODS,
            required=True
        )
    },
    hide_index=True,
    column_order=["日期", "類別", "名稱", "支付方式", "價格"],
    key="expense_editor"
)

# 如果資料有變更，更新 session state 和檔案
if not edited_df.equals(st.session_state.df):
    st.session_state.df = edited_df.copy()
    st.session_state.df.to_csv(USER_DATA_PATH, index=False)
st.markdown('</div>', unsafe_allow_html=True)

# 將匯出功能放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📥 匯出資料</div>', unsafe_allow_html=True)
# ... existing export code ...
st.markdown('</div>', unsafe_allow_html=True)

# 將每日合計圖表放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📈 每日支出趨勢</div>', unsafe_allow_html=True)
# ... existing daily totals and charts code ...
st.markdown('</div>', unsafe_allow_html=True)

# 將支出分析放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">📊 支出分析</div>', unsafe_allow_html=True)
include_deposit = st.checkbox('包含儲值金額', value=False)
# ... existing analysis code ...
st.markdown('</div>', unsafe_allow_html=True)

# 將匯率資訊放入卡片中
st.markdown('<div class="card">', unsafe_allow_html=True)
st.markdown('<div class="card-title">💱 即時匯率</div>', unsafe_allow_html=True)
# ... existing exchange rate code ...
st.markdown('</div>', unsafe_allow_html=True)
