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

# 設定頁面
st.set_page_config(
    page_title="打字記帳",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 從 Streamlit secrets 讀取使用者資訊
USERS = {
    "admin": {
        "password": st.secrets["ADMIN_PASSWORD"],
        "name": "admin"
    },
    "yuan": {
        "password": st.secrets["USER_PASSWORD"],
        "name": "yuan"
    }
}

# 如果沒有設定密碼，顯示錯誤訊息
if "ADMIN_PASSWORD" not in st.secrets or "USER_PASSWORD" not in st.secrets:
    st.error("請在 Streamlit Secrets 中設定必要的密碼")
    st.stop()

# 初始化 session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'username' not in st.session_state:
    st.session_state.username = None
if 'df' not in st.session_state:
    st.session_state.df = None

# 登入處理函數
def handle_login(username, password):
    if username in USERS and USERS[username]["password"] == password:
        st.session_state.authenticated = True
        st.session_state.username = username
        # 登入成功後立即載入資料
        try:
            USER_DATA_PATH = f'data/expenses_{username}.csv'
            st.session_state.df = pd.read_csv(USER_DATA_PATH,
                dtype={'日期': str, '類別': str, '名稱': str, '價格': float, '支付方式': str})
        except FileNotFoundError:
            st.session_state.df = pd.DataFrame(columns=[
                '日期', '類別', '名稱', '價格', '支付方式'
            ])
        return True
    return False

# 登出處理函數
def handle_logout():
    st.session_state.authenticated = False
    st.session_state.username = None
    st.session_state.df = None

# 登入介面
if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("登入")
        username = st.text_input("帳號")
        password = st.text_input("密碼", type="password")
        
        if st.button("登入"):
            if handle_login(username, password):
                st.rerun()
            else:
                st.error("帳號或密碼錯誤")
else:
    # 登出按鈕
    with st.sidebar:
        if st.button("登出"):
            handle_logout()
            st.rerun()
    
    # 顯示歡迎訊息
    st.write(f"歡迎回來，{USERS[st.session_state.username]['name']}！")
    
    # 修改資料儲存路徑，加入用戶名稱
    USER_DATA_PATH = f'data/expenses_{st.session_state.username}.csv'
    
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

    # 資料儲存結構
    if st.session_state.df is None:
        try:
            os.makedirs('data', exist_ok=True)
            try:
                st.session_state.df = pd.read_csv(USER_DATA_PATH,
                    dtype={'日期': str, '類別': str, '名稱': str, '價格': float, '支付方式': str})
            except FileNotFoundError:
                st.session_state.df = pd.DataFrame(columns=[
                    '日期', '類別', '名稱', '價格', '支付方式'
                ])
        except Exception as e:
            st.error(f"資料載入錯誤: {str(e)}")
            st.session_state.df = pd.DataFrame(columns=[
                '日期', '類別', '名稱', '價格', '支付方式'
            ])

    # 自定義 CSS 樣式
    st.markdown("""
    <style>
        /* 主要容器樣式 */
        .main-container {
            padding: 1rem;
        }
        
        /* 卡片樣式 */
        .card {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        
        /* 表格和操作區域的佈局 */
        .main-content {
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
        }
        
        .action-area {
            width: 100%;
        }
        
        /* 通用樣式優化 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }
        .stTabs [data-baseweb="tab"] {
            padding: 8px 16px;
            border-radius: 4px;
        }
        .stTabs [data-baseweb="tab-list"] button {
            font-size: 16px;
        }

        /* 表格樣式優化 */
        .stDataFrame td, .stDataFrame th {
            padding: 8px;
        }
        
        /* 總計金額樣式 */
        .total-amount {
            text-align: right;
            padding: 16px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 1.1em;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
        }

        /* 分析區塊樣式 */
        .analysis-section {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }

        /* 圖表容器樣式 */
        .chart-container {
            background-color: white;
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
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

    # 新增一個 radio button 來選擇操作模式
    operation_mode = st.radio(
        "選擇操作模式",
        ["新增記錄", "修改記錄"],
        horizontal=True
    )

    if operation_mode == "新增記錄":
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

    # 新增一個匯入區塊
    with st.expander("📤 匯入資料", expanded=False):
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

    # 修改表格和操作區域的佈局
    with st.container():
        st.markdown("### 📝 支出記錄")
        # 表格區域
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

        # 匯出功能
        st.markdown("### 📥 匯出資料")
        st.markdown('<div class="card">', unsafe_allow_html=True)
        
        # 取得資料的起訖日期
        if not st.session_state.df.empty:
            start_date = pd.to_datetime(st.session_state.df['日期']).min().strftime('%Y%m%d')
            end_date = pd.to_datetime(st.session_state.df['日期']).max().strftime('%Y%m%d')
            date_range = f"{start_date}-{end_date}"
        else:
            date_range = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d')
        
        col1, col2 = st.columns(2)
        with col1:
            export_format = st.radio(
                "選擇匯出格式",
                ["Excel", "CSV"],
                horizontal=True,
                key="export_format"
            )
        
        with col2:
            if export_format == "Excel":
                # 建立 BytesIO 物件
                output = BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    st.session_state.df.to_excel(writer, sheet_name='支出記錄', index=False)
                
                st.download_button(
                    label="下載 Excel 檔案",
                    data=output.getvalue(),
                    file_name=f"支出記錄_{date_range}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            else:
                csv = st.session_state.df.to_csv(index=False)
                st.download_button(
                    label="下載 CSV 檔案",
                    data=csv,
                    file_name=f"支出記錄_{date_range}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        st.markdown('</div>', unsafe_allow_html=True)

        # 取得匯率
        exchange_rates = get_exchange_rates()

        # 計算每日合計
        daily_totals = edited_df.groupby('日期')['價格'].sum().sort_index()
        daily_df = pd.DataFrame(daily_totals).reset_index()
        daily_df['日期'] = pd.to_datetime(daily_df['日期'])

        # 顯示每日合計
        st.subheader("每日合計")

        # 使用 tabs 來切換圖表類型
        chart_tab1, chart_tab2 = st.tabs(["折線圖", "長條圖"])

        # 計算換算金額
        daily_df['TWD'] = daily_df['價格'] * exchange_rates.get('TWD', 0.23)
        daily_df['USD'] = daily_df['價格'] * exchange_rates.get('USD', 0.0067)

        with chart_tab1:
            # 折線圖
            fig_line = px.line(
                daily_df,
                x='日期',
                y='價格',
                title='每日支出趨勢',
                labels={'日期': '日期', '價格': '金額 (JPY)'}
            )
            # 設定互動提示格式
            fig_line.update_traces(
                hovertemplate="日期: %{x}<br>" +
                "JPY: ¥%{y:,.0f}<br>" +
                "TWD: NT$%{customdata[0]:,.0f}<br>" +
                "USD: $%{customdata[1]:.2f}",
                customdata=daily_df[['TWD', 'USD']]
            )
            fig_line.update_layout(
                xaxis_title="日期",
                yaxis_title="金額 (JPY)",
                hovermode='x unified'
            )
            st.plotly_chart(fig_line, use_container_width=True)

        with chart_tab2:
            # 長條圖
            fig_bar = px.bar(
                daily_df,
                x='日期',
                y='價格',
                title='每日支出趨勢',
                labels={'日期': '日期', '價格': '金額 (JPY)'}
            )
            # 設定互動提示格式
            fig_bar.update_traces(
                hovertemplate="日期: %{x}<br>" +
                "JPY: ¥%{y:,.0f}<br>" +
                "TWD: NT$%{customdata[0]:,.0f}<br>" +
                "USD: $%{customdata[1]:.2f}",
                customdata=daily_df[['TWD', 'USD']]
            )
            fig_bar.update_layout(
                xaxis_title="日期",
                yaxis_title="金額 (JPY)",
                hovermode='x unified'
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # 顯示數值摘要
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("平均每日支出", f"¥{daily_totals.mean():,.0f}")
        with col2:
            st.metric("最高單日支出", f"¥{daily_totals.max():,.0f}")
        with col3:
            st.metric("最低單日支出", f"¥{daily_totals.min():,.0f}")

        # 顯示總計金額（多幣別）
        total_amount_jpy = edited_df['價格'].sum()
        total_amount_twd = total_amount_jpy * exchange_rates.get('TWD', 0.23)  # 使用預設值
        total_amount_usd = total_amount_jpy * exchange_rates.get('USD', 0.0067)  # 使用預設值

        st.markdown(f"""
        <div class="total-amount">
            <strong>總計金額：</strong><br>
            JPY: ¥{total_amount_jpy:,.0f}<br>
            TWD: NT${total_amount_twd:,.0f}<br>
            USD: ${total_amount_usd:,.2f}
        </div>
        """, unsafe_allow_html=True)
        
        # 操作區域（刪除功能）
        col1, col2 = st.columns(2)
        
        with col1:
            with st.expander("🗑️ 刪除記錄", expanded=True):
                # 初始化 selected 狀態
                if 'selected' not in st.session_state:
                    st.session_state.selected = [False] * len(st.session_state.df)

                # 確保 selected 列表長度與 DataFrame 相同
                if len(st.session_state.selected) != len(st.session_state.df):
                    st.session_state.selected = [False] * len(st.session_state.df)

                # 刪除選中的記錄
                selected_indices = [i for i, selected in enumerate(st.session_state.selected) if selected]
                if selected_indices and st.button("🗑️ 刪除選中的記錄", type="secondary", use_container_width=True):
                    st.session_state.df = st.session_state.df.drop(selected_indices).reset_index(drop=True)
                    st.session_state.df.to_csv(USER_DATA_PATH, index=False)
                    st.session_state.selected = [False] * len(st.session_state.df)
                    st.success("已刪除選中的記錄！")
                    st.rerun()

    # 在表格區域之後，新增分析區塊
    with st.container():
        st.markdown("### 📊 支出分析")
        
        # 新增篩選選項
        include_deposit = st.checkbox('包含儲值金額', value=False)
        
        # 根據篩選條件準備資料
        if not include_deposit:
            df_analysis = st.session_state.df[st.session_state.df['類別'] != '儲值']
        else:
            df_analysis = st.session_state.df.copy()
        
        # 計算總支出
        total_expense = df_analysis['價格'].sum()
        
        # 顯示多幣別總支出
        st.markdown('<div class="analysis-section">', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("總支出 (JPY)", f"¥{total_expense:,.0f}")
        with col2:
            st.metric("總支出 (TWD)", f"NT${total_expense * exchange_rates.get('TWD', 0.23):,.0f}")
        with col3:
            st.metric("總支出 (USD)", f"${total_expense * exchange_rates.get('USD', 0.0067):,.2f}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # 圖表分析
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            # 類別分析
            category_sum = df_analysis.groupby('類別')['價格'].sum()
            fig1 = px.pie(
                values=category_sum.values,
                names=category_sum.index,
                title='類別佔比分析'
            )
            fig1.update_traces(textinfo='percent+label')
            st.plotly_chart(fig1, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="chart-container">', unsafe_allow_html=True)
            # 支付方式分析
            payment_sum = df_analysis.groupby('支付方式')['價格'].sum()
            fig2 = px.pie(
                values=payment_sum.values,
                names=payment_sum.index,
                title='支付方式分析'
            )
            fig2.update_traces(textinfo='percent+label')
            st.plotly_chart(fig2, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

        # 匯率資訊顯示
        st.markdown("### 💱 即時匯率")
        st.markdown('<div class="analysis-section">', unsafe_allow_html=True)
        rate_cols = st.columns(len(exchange_rates))
        for col, (currency, rate) in zip(rate_cols, exchange_rates.items()):
            with col:
                st.metric(
                    f"JPY → {currency}",
                    f"{CURRENCIES[currency]} {rate:.4f}",
                    help="如果無法取得即時匯率，將使用預設匯率"
                )
        st.markdown('</div>', unsafe_allow_html=True)
