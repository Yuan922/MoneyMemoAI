import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import requests
from io import BytesIO

# Constants
CURRENCIES = {"JPY": "日圓 ¥", "TWD": "新台幣 NT$", "USD": "美元 $"}
PAYMENT_METHODS = ["現金", "信用卡", "樂天Pay", "PayPay"]
VALID_CATEGORIES = ["早餐", "午餐", "晚餐", "點心", "交通", "娛樂", "儲值", "其他"]

# Configuration Functions
def setup_page_config():
    st.set_page_config(page_title="打字記帳", page_icon="💰", layout="wide", initial_sidebar_state="collapsed")

def inject_custom_css():
    st.markdown("""
    <style>
        .main-container {padding: 1rem;}
        .card {
            background-color: #ffffff;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .main-content {display: flex; flex-direction: column; gap: 1.5rem;}
        .action-area {width: 100%;}
        .stTabs [data-baseweb="tab-list"] {gap: 8px;}
        .stTabs [data-baseweb="tab"] {padding: 8px 16px; border-radius: 4px;}
        .stTabs [data-baseweb="tab-list"] button {font-size: 16px;}
        .stDataFrame td, .stDataFrame th {padding: 8px;}
        .total-amount {
            text-align: right;
            padding: 16px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 1.1em;
            background-color: #f8f9fa;
            border: 1px solid #e9ecef;
        }
        .analysis-section {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 1rem;
            margin-top: 1rem;
        }
        .chart-container {
            background-color: white;
            border-radius: 8px;
            padding: 1rem;
            margin: 0.5rem 0;
        }
    </style>
    """, unsafe_allow_html=True)

def initialize_session_state():
    if 'username' not in st.session_state:
        st.session_state.username = 'yuan'
    os.makedirs('data', exist_ok=True)
    return f'data/expenses_{st.session_state.username}.csv'

# Data Management Functions
def load_data(file_path):
    try:
        df = pd.read_csv(file_path)
        df['日期'] = pd.to_datetime(df['日期'], errors='coerce').dt.strftime('%Y-%m-%d')
        return df.astype({'日期': 'str', '類別': 'str', '名稱': 'str', '價格': 'float', '支付方式': 'str'})
    except FileNotFoundError:
        return pd.DataFrame(columns=['日期', '類別', '名稱', '價格', '支付方式'])
    except Exception as e:
        st.error(f"載入資料時發生錯誤: {str(e)}")
        return pd.DataFrame(columns=['日期', '類別', '名稱', '價格', '支付方式'])

def save_data(df, file_path):
    df.to_csv(file_path, index=False)

# API and Model Setup
def initialize_gemini():
    load_dotenv()
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    return genai.GenerativeModel('gemini-pro')

def get_exchange_rates(base_currency="JPY"):
    rates = {'TWD': 0.23, 'USD': 0.0067}
    try:
        response = requests.get(f"https://open.er-api.com/v6/latest/{base_currency}")
        if response.status_code == 200:
            data = response.json()
            for currency in CURRENCIES.keys():
                if currency != base_currency and currency in data['rates']:
                    rates[currency] = data['rates'][currency]
        else:
            st.warning("無法取得即時匯率，使用預設匯率")
    except Exception:
        st.warning("無法取得即時匯率，使用預設匯率")
    return rates

# Input Processing Functions
def process_new_record(input_text, model):
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
    return [results] if not isinstance(results, list) else results

def process_edit_request(input_text, model):
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
                "名稱": "商品名稱",
                "價格": 數字
            }},
            "update": {{
                "日期": "YYYY-MM-DD",
                "價格": 數字,
                "支付方式": "付款方式",
                "類別": "分類"
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
    cleaned_response = response.text.strip()
    if cleaned_response.startswith('```') and cleaned_response.endswith('```'):
        cleaned_response = cleaned_response[cleaned_response.find('{'):cleaned_response.rfind('}')+1]
    results = json.loads(cleaned_response)
    return [results] if not isinstance(results, list) else results

# UI Components
def display_input_form(model, df, file_path):
    operation_mode = st.radio("選擇操作模式", ["新增記錄", "修改記錄"], horizontal=True)
    
    if operation_mode == "新增記錄":
        with st.form("input_form"):
            input_text = st.text_input("文字輸入（範例：晚餐吃拉麵用現金支付980日幣）")
            if st.form_submit_button("💾 儲存記錄") and input_text:
                try:
                    results = process_new_record(input_text, model)
                    for result in results:
                        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
                    save_data(df, file_path)
                    st.session_state.df = df
                    st.success(f"已新增 {len(results)} 筆記錄！")
                    for result in results:
                        st.write(f"✅ {result['名稱']}：{result['價格']}元（{result['支付方式']}）")
                except Exception as e:
                    st.error(f"處理錯誤: {str(e)}")
    else:
        with st.form("edit_form"):
            input_text = st.text_input("請輸入要修改的內容（例如：一顆奇異果花150，然後買了章魚生魚片花350是昨天晚上！不是2-20）")
            if st.form_submit_button("✏️ 修改記錄") and input_text:
                try:
                    results = process_edit_request(input_text, model)
                    success_count = 0
                    for result in results:
                        mask = (df['名稱'].str.lower().str.contains(str(result["search"]["名稱"]).lower(), na=False) & 
                                (df['價格'] == result["search"]["價格"]))
                        if mask.any():
                            df.loc[mask, result["update"].keys()] = result["update"].values()
                            success_count += 1
                    if success_count > 0:
                        save_data(df, file_path)
                        st.session_state.df = df
                        st.success(f"已更新 {success_count} 筆記錄！")
                    else:
                        st.error("找不到符合的記錄！")
                except Exception as e:
                    st.error(f"處理錯誤: {str(e)}")

def display_import_section(df, file_path):
    with st.expander("📤 匯入資料", expanded=False):
        uploaded_file = st.file_uploader(
            "選擇要匯入的 Excel 或 CSV 檔案",
            type=['xlsx', 'csv'],
            help="支援 .xlsx 或 .csv 格式的檔案"
        )
        
        if uploaded_file is not None:
            try:
                if uploaded_file.name.endswith('.csv'):
                    imported_df = pd.read_csv(uploaded_file)
                else:
                    imported_df = pd.read_excel(uploaded_file)
                
                required_columns = ['日期', '類別', '名稱', '價格', '支付方式']
                if not all(col in imported_df.columns for col in required_columns):
                    st.error("檔案格式錯誤！必須包含以下欄位：日期、類別、名稱、價格、支付方式")
                    return df
                
                imported_df['日期'] = pd.to_datetime(imported_df['日期'], errors='coerce').dt.strftime('%Y-%m-%d')
                imported_df['價格'] = pd.to_numeric(imported_df['價格'], errors='coerce')
                
                if not imported_df['類別'].isin(VALID_CATEGORIES).all():
                    invalid_categories = imported_df[~imported_df['類別'].isin(VALID_CATEGORIES)]['類別'].unique()
                    st.error(f"發現無效的類別：{', '.join(map(str, invalid_categories))}")
                    return df
                
                if not imported_df['支付方式'].isin(PAYMENT_METHODS).all():
                    invalid_methods = imported_df[~imported_df['支付方式'].isin(PAYMENT_METHODS)]['支付方式'].unique()
                    st.error(f"發現無效的支付方式：{', '.join(map(str, invalid_methods))}")
                    return df
                
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
                            df = pd.concat([df, imported_df], ignore_index=True)
                        else:
                            df = imported_df.copy()
                        save_data(df, file_path)
                        st.session_state.df = df
                        st.success(f"成功匯入 {len(imported_df)} 筆資料！")
                        st.rerun()
                
                st.subheader("預覽匯入資料")
                st.dataframe(imported_df, use_container_width=True, hide_index=True)
                
            except Exception as e:
                st.error(f"匯入失敗：{str(e)}")
    return df

def display_data_editor(df, file_path):
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "日期": st.column_config.TextColumn("日期", required=True, validate="^[0-9]{4}-[0-9]{2}-[0-9]{2}$"),
            "類別": st.column_config.SelectboxColumn("類別", options=VALID_CATEGORIES, required=True),
            "名稱": st.column_config.TextColumn("名稱", required=True),
            "價格": st.column_config.NumberColumn("價格 (JPY)", min_value=0, required=True, format="%.0f"),
            "支付方式": st.column_config.SelectboxColumn("支付方式", options=PAYMENT_METHODS, required=True)
        },
        hide_index=True,
        column_order=["日期", "類別", "名稱", "支付方式", "價格"]
    )
    if not edited_df.equals(df):
        save_data(edited_df, file_path)
        st.session_state.df = edited_df
    return edited_df

def display_export_section(df):
    date_range = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d')
    if not df.empty:
        dates = pd.to_datetime(df['日期'], errors='coerce')
        date_range = f"{dates.min().strftime('%Y%m%d')}-{dates.max().strftime('%Y%m%d')}"
    
    col1, col2 = st.columns(2)
    with col1:
        export_format = st.radio("選擇匯出格式", ["Excel", "CSV"], horizontal=True)
    with col2:
        if export_format == "Excel":
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name='支出記錄', index=False)
            st.download_button(
                label="下載 Excel 檔案",
                data=output.getvalue(),
                file_name=f"支出記錄_{date_range}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            csv = df.to_csv(index=False)
            st.download_button(
                label="下載 CSV 檔案",
                data=csv,
                file_name=f"支出記錄_{date_range}.csv",
                mime="text/csv"
            )

def display_daily_charts(df, exchange_rates):
    daily_totals = df.groupby('日期')['價格'].sum().sort_index()
    daily_df = pd.DataFrame(daily_totals).reset_index()
    daily_df['日期'] = pd.to_datetime(daily_df['日期'], format='%Y-%m-%d', errors='coerce')
    daily_df['TWD'] = daily_df['價格'] * exchange_rates.get('TWD', 0.23)
    daily_df['USD'] = daily_df['價格'] * exchange_rates.get('USD', 0.0067)

    st.subheader("每日合計")
    chart_tab1, chart_tab2 = st.tabs(["折線圖", "長條圖"])

    with chart_tab1:
        fig_line = px.line(
            daily_df,
            x='日期',
            y='價格',
            title='每日支出趨勢',
            labels={'日期': '日期', '價格': '金額 (JPY)'}
        )
        fig_line.update_traces(
            hovertemplate="日期: %{x}<br>JPY: ¥%{y:,.0f}<br>TWD: NT$%{customdata[0]:,.0f}<br>USD: $%{customdata[1]:.2f}",
            customdata=daily_df[['TWD', 'USD']]
        )
        fig_line.update_layout(xaxis_title="日期", yaxis_title="金額 (JPY)", hovermode='x unified')
        st.plotly_chart(fig_line, use_container_width=True)

    with chart_tab2:
        fig_bar = px.bar(
            daily_df,
            x='日期',
            y='價格',
            title='每日支出趨勢',
            labels={'日期': '日期', '價格': '金額 (JPY)'}
        )
        fig_bar.update_traces(
            hovertemplate="日期: %{x}<br>JPY: ¥%{y:,.0f}<br>TWD: NT$%{customdata[0]:,.0f}<br>USD: $%{customdata[1]:.2f}",
            customdata=daily_df[['TWD', 'USD']]
        )
        fig_bar.update_layout(xaxis_title="日期", yaxis_title="金額 (JPY)", hovermode='x unified')
        st.plotly_chart(fig_bar, use_container_width=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("平均每日支出", f"¥{daily_totals.mean():,.0f}")
    with col2:
        st.metric("最高單日支出", f"¥{daily_totals.max():,.0f}")
    with col3:
        st.metric("最低單日支出", f"¥{daily_totals.min():,.0f}")

    total_amount_jpy = df['價格'].sum()
    total_amount_twd = total_amount_jpy * exchange_rates.get('TWD', 0.23)
    total_amount_usd = total_amount_jpy * exchange_rates.get('USD', 0.0067)

    st.markdown(f"""
    <div class="total-amount">
        <strong>總計金額：</strong><br>
        JPY: ¥{total_amount_jpy:,.0f}<br>
        TWD: NT${total_amount_twd:,.0f}<br>
        USD: ${total_amount_usd:,.2f}
    </div>
    """, unsafe_allow_html=True)

def display_analysis(df, exchange_rates):
    include_deposit = st.checkbox('包含儲值金額', value=False)
    df_analysis = df if include_deposit else df[df['類別'] != '儲值']
    
    total_expense = df_analysis['價格'].sum()
    st.markdown('<div class="analysis-section">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("總支出 (JPY)", f"¥{total_expense:,.0f}")
    with col2:
        st.metric("總支出 (TWD)", f"NT${total_expense * exchange_rates.get('TWD', 0.23):,.0f}")
    with col3:
        st.metric("總支出 (USD)", f"${total_expense * exchange_rates.get('USD', 0.0067):,.2f}")
    st.markdown('</div>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        fig1 = px.pie(df_analysis.groupby('類別')['價格'].sum().reset_index(), 
                     values='價格', names='類別', title='類別佔比分析')
        fig1.update_traces(textinfo='percent+label')
        st.plotly_chart(fig1, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        fig2 = px.pie(df_analysis.groupby('支付方式')['價格'].sum().reset_index(), 
                     values='價格', names='支付方式', title='支付方式分析')
        fig2.update_traces(textinfo='percent+label')
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# Main Function
def main():
    setup_page_config()
    inject_custom_css()
    file_path = initialize_session_state()
    st.session_state.df = load_data(file_path)
    model = initialize_gemini()
    exchange_rates = get_exchange_rates()

    st.title("打字記帳")
    
    display_input_form(model, st.session_state.df, file_path)
    st.session_state.df = display_import_section(st.session_state.df, file_path)
    
    st.markdown("### 📝 支出記錄")
    edited_df = display_data_editor(st.session_state.df, file_path)
    
    st.markdown("### 📥 匯出資料")
    display_export_section(edited_df)
    
    display_daily_charts(edited_df, exchange_rates)
    
    st.markdown("### 📊 支出分析")
    display_analysis(edited_df, exchange_rates)

if __name__ == "__main__":
    main()