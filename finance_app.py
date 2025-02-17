import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import google.generativeai as genai
import os
from dotenv import load_dotenv
import json
import random

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
st.set_page_config(page_title="AI智能記帳", page_icon="💰", layout="wide")
st.title("AI智能記帳 💰")

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
                    today = datetime.now().strftime("%Y-%m-%d")
                    prompt = f"""
                    請從以下文字中提取消費資訊，並以JSON格式回傳，包含以下欄位：
                    日期（如果沒提到就用 {today}）、類別（早餐/午餐/晚餐/點心/交通/娛樂/儲值/其他）、
                    名稱、價格、支付方式（現金/信用卡/樂天Pay/PayPay）
                    
                    請確保回傳的格式完全符合以下範例：
                    {{"日期": "{today}", "類別": "晚餐", "名稱": "拉麵", "價格": 980, "支付方式": "現金"}}
                    
                    注意：
                    1. 日期必須是 YYYY-MM-DD 格式
                    2. 如果是下午茶、咖啡廳、飲料店等非正餐的飲食消費，請歸類為「點心」
                    3. 請保持支付方式的原始名稱（如：樂天Pay、PayPay）
                    
                    文字：{input_text}
                    """
                    
                    response = model.generate_content(prompt)
                    result = json.loads(response.text)
                    
                    # 將 JSON 轉換成自然語言回應
                    responses = [
                        f"好的！記下來了～在{result['名稱']}花了{result['價格']}元，用{result['支付方式']}付款的！",
                        f"收到！{result['類別']}吃{result['名稱']}，花了{result['價格']}元，用{result['支付方式']}付款，已經記錄下來囉！",
                        f"了解！{result['名稱']}花了{result['價格']}元，用{result['支付方式']}付款，已經幫你記下來了～",
                        f"Got it！在{result['名稱']}消費{result['價格']}元，使用{result['支付方式']}，已經記錄好了！"
                    ]
                    
                    # 隨機選擇一個回應
                    st.write(random.choice(responses))
                    
                    new_row = pd.DataFrame([result])
                    st.session_state.df = pd.concat([st.session_state.df, new_row], ignore_index=True)
                    st.session_state.df.to_csv('data/expenses.csv', index=False)
                    st.success("已新增記錄！")
                    
                except Exception as e:
                    st.error(f"處理錯誤: {str(e)}")
                    st.error("AI 回應內容：" + response.text)
    else:
        with st.form("edit_form"):
            input_text = st.text_input("請輸入要修改的內容（例如：今天subway的價格是1050、今天下午去komeda的花費是用樂天Pay）")
            submit_button = st.form_submit_button("✏️ 修改記錄")
            
            if submit_button and input_text:
                try:
                    prompt = f"""
                    請從以下文字中提取修改資訊。這是一個修改請求，需要先找到對應的記錄再進行修改。
                    請回傳兩個部分的資訊：
                    1. 搜尋條件：用來找到要修改的記錄（可包含：日期、名稱、類別等資訊）
                    2. 修改內容：要更新的欄位和值
                    
                    可修改的欄位包括：
                    - 日期（YYYY-MM-DD格式）
                    - 類別（早餐/午餐/晚餐/點心/交通/娛樂/儲值/其他）
                    - 名稱
                    - 價格（數字）
                    - 支付方式（現金/信用卡/樂天Pay/PayPay）
                    
                    請以以下格式回傳：
                    {{"search": {{"名稱": "Subway", "日期": "今天"}}, "update": {{"價格": 1050}}}}
                    
                    注意：
                    1. 搜尋條件要盡可能明確，以避免修改到錯誤的記錄
                    2. 如果提到"今天"，請使用今天的日期
                    3. 價格必須是數字
                    
                    文字：{input_text}
                    """
                    
                    response = model.generate_content(prompt)
                    result = json.loads(response.text)
                    
                    # 處理搜尋條件中的"今天"
                    if "日期" in result["search"] and result["search"]["日期"] == "今天":
                        result["search"]["日期"] = datetime.now().strftime("%Y-%m-%d")
                    
                    # 尋找符合條件的記錄
                    mask = pd.Series(True, index=st.session_state.df.index)
                    for key, value in result["search"].items():
                        mask &= st.session_state.df[key].astype(str) == str(value)
                    
                    if mask.any():
                        # 更新符合條件的記錄
                        for key, value in result["update"].items():
                            st.session_state.df.loc[mask, key] = value
                        
                        # 儲存更新後的資料
                        st.session_state.df.to_csv('data/expenses.csv', index=False)
                        
                        # 只顯示一個成功訊息
                        st.success("已更新記錄！")
                        
                    else:
                        st.error("找不到符合的記錄！請確認搜尋條件是否正確。")
                    
                except Exception as e:
                    st.error(f"處理錯誤: {str(e)}")
                    st.error("AI 回應內容：" + response.text)

    # 顯示表格
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
    
    if not edited_df.equals(st.session_state.df):
        st.session_state.df = edited_df.copy()
        st.session_state.df.to_csv('data/expenses.csv', index=False)
        st.success("表格已更新！")

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
        st.metric("總支出", f"${total_expense:,.0f}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # 類別分析
            category_sum = df_analysis.groupby('類別')['價格'].sum()
            fig1 = px.pie(
                values=category_sum.values,
                names=category_sum.index,
                title='類別佔比'
            )
            st.plotly_chart(fig1)
            
        with col2:
            # 支付方式分析
            payment_sum = df_analysis.groupby('支付方式')['價格'].sum()
            fig2 = px.pie(
                values=payment_sum.values,
                names=payment_sum.index,
                title='支付方式佔比'
            )
            st.plotly_chart(fig2)
    else:
        st.info('還沒有任何記錄，請先新增支出！')
