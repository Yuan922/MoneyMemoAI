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

# TODO List:
# 增加修改現有記錄功能
#    - 判斷輸入文字是否包含"修改紀錄"關鍵字
#    - 如果是修改請求，尋找符合的記錄進行更新
#    - 避免重複新增相同記錄
#    - 考慮增加時間範圍限制，例如只能修改最近一週的記錄

# 初始化 Gemini
load_dotenv()
genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
model = genai.GenerativeModel('gemini-pro')

# 資料儲存結構
if 'df' not in st.session_state:
    try:
        os.makedirs('data', exist_ok=True)
        try:
            # 讀取 CSV 時明確指定日期格式
            st.session_state.df = pd.read_csv('data/expenses.csv',
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

# 設定頁面
st.set_page_config(
    page_title="AI智能記帳",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 初始化主題設定
if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

# 自定義 CSS 樣式
st.markdown("""
<style>
    /* 主題切換開關樣式 */
    .theme-toggle {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 1000;
    }
    
    /* 響應式設計 */
    @media (max-width: 768px) {
        .theme-toggle {
            position: relative;
            top: 0;
            right: 0;
            margin-bottom: 1rem;
        }
        
        /* 在手機版將右側欄移到下方 */
        [data-testid="column-right"] {
            width: 100% !important;
            margin-top: 1rem;
        }
        [data-testid="column-left"] {
            width: 100% !important;
        }
    }
    
    /* 深色模式樣式 */
    .dark-mode {
        background-color: #0E1117;
        color: #FAFAFA;
    }
    .dark-mode .total-amount {
        background-color: #1B1F27;
        color: #FAFAFA;
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
        padding: 12px;
        border-radius: 8px;
        margin: 10px 0;
        font-size: 1.1em;
    }
</style>
""", unsafe_allow_html=True)

# 主題切換開關
col_left, col_right = st.columns([3, 1])
with col_right:
    theme_toggle = st.toggle('🌙 深色模式', value=(st.session_state.theme == 'dark'))
    if theme_toggle != (st.session_state.theme == 'dark'):
        st.session_state.theme = 'dark' if theme_toggle else 'light'
        # 使用 JavaScript 動態切換主題
        st.markdown(f"""
        <script>
            const doc = window.parent.document;
            doc.documentElement.setAttribute('data-theme', '{st.session_state.theme}');
        </script>
        """, unsafe_allow_html=True)

# 建立分頁
tab1, tab2 = st.tabs(["記帳", "分析"])

# 定義支付方式選項（移除電子支付）
PAYMENT_METHODS = ["現金", "信用卡", "樂天Pay", "PayPay"]

# 主要記帳介面
with tab1:
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
                    st.session_state.df.to_csv('data/expenses.csv', index=False)
                    
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
                        st.session_state.df.to_csv('data/expenses.csv', index=False)
                        st.success(f"已更新 {success_count} 筆記錄！")
                    else:
                        st.error("找不到符合的記錄！請試著簡化搜尋條件。")
                    
                except Exception as e:
                    st.error(f"處理錯誤: {str(e)}")
                    st.error("AI 回應內容：" + response.text)

    # 修改表格和操作區域的佈局
    container = st.container()
    table_col, action_col = container.columns([2, 1])
    
    with table_col:
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
                    "價格",
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
            column_order=["日期", "類別", "名稱", "支付方式", "價格"]
        )
        
        # 顯示總計金額（在表格下方）
        total_amount = edited_df['價格'].sum()
        st.markdown(f"""
        <div class="total-amount">
            <strong>總計金額：</strong> ¥{total_amount:,.0f}
        </div>
        """, unsafe_allow_html=True)
    
    with action_col:
        # 操作區域（匯出和刪除功能）
        with st.expander("📥 匯出資料", expanded=True):
            # 取得資料的起訖日期
            if not st.session_state.df.empty:
                start_date = pd.to_datetime(st.session_state.df['日期']).min().strftime('%Y%m%d')
                end_date = pd.to_datetime(st.session_state.df['日期']).max().strftime('%Y%m%d')
                date_range = f"{start_date}-{end_date}"
            else:
                date_range = datetime.now(timezone(timedelta(hours=9))).strftime('%Y%m%d')
            
            export_format = st.radio(
                "選擇匯出格式",
                ["Excel", "CSV"],
                horizontal=True,
                key="export_format"
            )
            
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
                st.session_state.df.to_csv('data/expenses.csv', index=False)
                st.session_state.selected = [False] * len(st.session_state.df)
                st.success("已刪除選中的記錄！")
                st.rerun()

# 分析頁面
with tab2:
    if not st.session_state.df.empty:
        # 新增篩選選項
        include_deposit = st.checkbox('包含儲值金額', value=False)
        
        # 根據篩選條件準備資料
        if not include_deposit:
            df_analysis = st.session_state.df[st.session_state.df['類別'] != '儲值']
        else:
            df_analysis = st.session_state.df.copy()
            
        # 計算總支出
        total_expense = df_analysis['價格'].sum()
        st.metric("總支出", f"¥{total_expense:,.0f}")
        
        col1, col2, col3 = st.columns([1, 1, 1])
        
        with col1:
            # 類別分析
            category_sum = df_analysis.groupby('類別')['價格'].sum()
            fig1 = px.pie(
                values=category_sum.values,
                names=category_sum.index,
                title='類別佔比'
            )
            st.plotly_chart(fig1, use_container_width=True)
            
        with col2:
            # 支付方式分析
            payment_sum = df_analysis.groupby('支付方式')['價格'].sum()
            fig2 = px.pie(
                values=payment_sum.values,
                names=payment_sum.index,
                title='支付方式佔比'
            )
            st.plotly_chart(fig2, use_container_width=True)

        # 新增月度趨勢分析
        st.subheader("月度支出趨勢")
        
        # 將日期轉換為 datetime 格式
        df_analysis['日期'] = pd.to_datetime(df_analysis['日期'])
        
        # 計算每月支出
        monthly_expenses = df_analysis.groupby(df_analysis['日期'].dt.strftime('%Y-%m'))[['價格']].sum()
        
        # 繪製月度趨勢圖
        fig3 = px.line(
            monthly_expenses,
            x=monthly_expenses.index,
            y='價格',
            title='月度支出趨勢',
            labels={'價格': '支出金額', '日期': '月份'}
        )
        st.plotly_chart(fig3, use_container_width=True)

        # 顯示每日平均支出
        daily_avg = df_analysis.groupby('日期')['價格'].sum().mean()
        st.metric("每日平均支出", f"¥{daily_avg:,.0f}")
    else:
        st.info('還沒有任何記錄，請先新增支出！')
