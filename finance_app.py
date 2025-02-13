import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import speech_recognition as sr
import google.generativeai as genai
import os

# TODO List:
# 增加修改現有記錄功能
#    - 判斷輸入文字是否包含"修改紀錄"關鍵字
#    - 如果是修改請求，尋找符合的記錄進行更新
#    - 避免重複新增相同記錄
#    - 考慮增加時間範圍限制，例如只能修改最近一週的記錄

# 初始化 Gemini
gemini_api_key = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=gemini_api_key)

model = genai.GenerativeModel('gemini-pro')

# 資料儲存結構
if 'df' not in st.session_state:
    try:
        st.session_state.df = pd.read_csv('data/expenses.csv')
        # 將日期欄位轉換為 datetime 格式
        st.session_state.df['日期'] = pd.to_datetime(st.session_state.df['日期'])
    except FileNotFoundError:
        st.session_state.df = pd.DataFrame(columns=[
            '日期', '類別', '名稱', '價格', '支付方式'
        ])

#TODO 語音辨識函式

# Gemini解析函式
def parse_expense(text, is_modify=False):
    if is_modify:
        prompt = f"""
        請將以下修改請求轉換為JSON格式，包含以下欄位：
        original_amount(要修改的金額),
        date(自動填寫今天日期{datetime.now().strftime('%Y-%m-%d')}),
        category(限：早餐/午餐/晚餐/交通/娛樂/儲值/其他),
        name(商品名稱),
        amount(只保留數字),
        payment(限：現金/信用卡/電子支付/行動支付)

        注意：
        1. 如果是儲值行為（例如：為 mobile suica 加值），類別請標示為「儲值」
        2. 如果是使用已儲值的支付方式消費（例如：使用 mobile suica 搭車），類別請標示為「交通」，支付方式標示為「行動支付」
        3. 請從輸入文字中提取要修改的原始金額

        輸入內容：{text}

        範例輸出格式：
        {{"original_amount": 5000, "date": "2025-02-13", "category": "儲值", "name": "suica儲值", "amount": 3000, "payment": "信用卡"}}
        """
    else:
        prompt = f"""
        請將以下消費記錄轉換為JSON格式，包含以下欄位：
        date(自動填寫今天日期{datetime.now().strftime('%Y-%m-%d')}),
        category(限：早餐/午餐/晚餐/交通/娛樂/儲值/其他),
        name(商品名稱),
        amount(只保留數字),
        payment(限：現金/信用卡/電子支付/行動支付)

    注意：
    1. 如果是儲值行為（例如：為 mobile suica 加值），類別請標示為「儲值」
    2. 如果是使用已儲值的支付方式消費（例如：使用 mobile suica 搭車），類別請標示為「交通」，支付方式標示為「行動支付」

    輸入內容：{text}

    範例輸出格式：
    {{"date": "2025-02-13", "category": "晚餐", "name": "炒麵", "amount": 1150, "payment": "信用卡"}}
    """

    try:
        response = model.generate_content(prompt)
        return eval(response.text)
    except Exception as e:
        st.error(f"解析錯誤: {str(e)}")
        return None

# 新增修改記錄函式
def modify_expense(original_amount, new_data):
    # 找到最近一筆符合金額的記錄
    mask = st.session_state.df['價格'] == original_amount
    if not mask.any():
        st.error(f"找不到金額為 {original_amount} 的記錄")
        return False
    
    # 取得最後一筆符合的記錄索引
    idx = mask.iloc[::-1].idxmax()
    
    # 更新記錄
    st.session_state.df.loc[idx, '日期'] = new_data['date']
    st.session_state.df.loc[idx, '類別'] = new_data['category']
    st.session_state.df.loc[idx, '名稱'] = new_data['name']
    st.session_state.df.loc[idx, '價格'] = new_data['amount']
    st.session_state.df.loc[idx, '支付方式'] = new_data['payment']
    
    # 儲存更新後的資料
    st.session_state.df.to_csv('data/expenses.csv', index=False)
    return True

# 主界面
st.title("AI智能記帳系統 💵")
tab1, tab2 = st.tabs(["📝 記帳界面", "📊 分析報表"])

with tab1:
    with st.form("input_form"):
        input_text = st.text_input("文字輸入（範例：晚餐吃拉麵用現金支付980日幣）")
        submit_button = st.form_submit_button("💾 儲存記錄")
        
        if submit_button and input_text:
            # 判斷是否為修改請求
            is_modify = "修改紀錄" in input_text or "修改記錄" in input_text
            
            parsed = parse_expense(input_text, is_modify)
            if parsed:
                if is_modify:
                    if modify_expense(parsed['original_amount'], parsed):
                        st.success("記錄已更新！")
                else:
                    new_row = {
                        '日期': parsed['date'],
                        '類別': parsed['category'],
                        '名稱': parsed['name'],
                        '價格': int(parsed['amount']),
                        '支付方式': parsed['payment']
                    }
                    st.session_state.df = pd.concat(
                        [st.session_state.df, pd.DataFrame([new_row])],
                        ignore_index=True
                    )
                    st.session_state.df.to_csv('data/expenses.csv', index=False)
                    st.success("已儲存！")

    # 確保編輯前資料類型正確
    df_for_editing = st.session_state.df.copy()
    if not df_for_editing.empty:
        df_for_editing['日期'] = pd.to_datetime(df_for_editing['日期'])

    # 使用 data_editor
    edited_df = st.data_editor(
        df_for_editing,
        use_container_width=True,
        num_rows="dynamic",
        column_config={
            "日期": st.column_config.DateColumn(
                "日期",
                min_value=datetime(2020, 1, 1),
                max_value=datetime(2030, 12, 31),
                format="YYYY-MM-DD",
                required=True
            ),
            "類別": st.column_config.SelectboxColumn(
                "類別",
                options=["早餐", "午餐", "晚餐", "交通", "娛樂", "儲值", "其他"],
                required=True
            ),
            "名稱": st.column_config.TextColumn(
                "名稱",
                required=True
            ),
            "價格": st.column_config.NumberColumn(
                "價格",
                min_value=0,
                required=True
            ),
            "支付方式": st.column_config.SelectboxColumn(
                "支付方式",
                options=["現金", "信用卡", "電子支付", "行動支付"],
                required=True
            )
        },
        hide_index=True,
    )

    # 檢查表格是否有變更並儲存
    if not edited_df.equals(st.session_state.df):
        st.session_state.df = edited_df.copy()
        # 儲存時將日期轉換為字串格式
        st.session_state.df.to_csv('data/expenses.csv', index=False, date_format='%Y-%m-%d')
        st.success("表格已更新！")

    # 匯出按鈕
    if not st.session_state.df.empty:
        csv = st.session_state.df.to_csv(index=False, date_format='%Y-%m-%d').encode('utf-8')
        st.download_button(
            label="📥 下載 CSV",
            data=csv,
            file_name='expenses.csv',
            mime='text/csv',
        )

with tab2:
    analysis_type = st.selectbox("分析類型", ['類別', '支付方式'])
    include_deposit = st.checkbox("包含儲值金額", value=False)

    if not st.session_state.df.empty:
        # 根據選擇決定是否過濾儲值記錄
        df_analysis = st.session_state.df
        if not include_deposit:
            df_analysis = df_analysis[df_analysis['類別'] != '儲值']

        fig = px.pie(
            df_analysis,
            names=analysis_type,
            values='價格',
            title=f'{analysis_type}占比分析 {"(不含儲值)" if not include_deposit else ""}',
            hole=0.3
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("尚未有消費記錄")
