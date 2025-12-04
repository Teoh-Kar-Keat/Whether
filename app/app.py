import streamlit as st
import sqlite3
import pandas as pd
import requests
import altair as alt
from datetime import datetime

# ---------------------------------------------------------
# 1. 系統設定與美化
# ---------------------------------------------------------
st.set_page_config(
    page_title="智慧農業氣象站",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義 CSS 以美化介面 (卡片效果、字體優化)
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
        border: 1px solid #e0e0e0;
    }
    .big-font {
        font-size: 20px !important;
        font-weight: 600;
        color: #2c3e50;
    }
    .info-box {
        background-color: #e8f5e9;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #66bb6a;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 全域變數與資料庫設置
# ---------------------------------------------------------
CWA_API_KEY = "CWA-8ABBB4CD-9E3A-4B9A-B2CE-3347A4E99473"
API_URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-A0010-001"
DB_NAME = "agri_weather.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS weather (
        location TEXT, date TEXT, min_temp REAL, max_temp REAL, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agri_stats (
        location TEXT, date TEXT, degree_day REAL, accumulated_temp REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS crop_stats (
        location TEXT, crop_breed TEXT, growing_days INTEGER, accumulated_temp REAL, description TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS overview (content TEXT, update_time TEXT)''')
    conn.commit()
    conn.close()

def save_all_data(weather_list, agri_list, crop_list, overview_text):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    
    c.execute("DELETE FROM weather")
    if weather_list: c.executemany('INSERT INTO weather VALUES (?,?,?,?,?)', weather_list)
        
    c.execute("DELETE FROM agri_stats")
    if agri_list: c.executemany('INSERT INTO agri_stats VALUES (?,?,?,?)', agri_list)
        
    c.execute("DELETE FROM crop_stats")
    if crop_list: c.executemany('INSERT INTO crop_stats VALUES (?,?,?,?,?)', crop_list)

    c.execute("DELETE FROM overview")
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if overview_text: c.execute('INSERT INTO overview VALUES (?, ?)', (overview_text, now_str))

    conn.commit()
    conn.close()
    return len(weather_list) + len(agri_list) + len(crop_list)

def load_data(table_name):
    try:
        conn = sqlite3.connect(DB_NAME)
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df
    except:
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. 資料抓取邏輯 (ETL)
# ---------------------------------------------------------
def fetch_and_update_data():
    params = {"Authorization": CWA_API_KEY, "format": "JSON"}
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        
        # 解析路徑
        try:
            root = data['cwaopendata']['resources']['resource']['data']['agrWeatherForecasts']
            weather_profile = root.get('weatherProfile', '目前無概況資料')
            forecast_locs = root['weatherForecasts']['location']
            
            # 農業建議節點
            agr_advices_node = root.get('agrAdvices', {})
            agri_locs = agr_advices_node.get('agrForecasts', {}).get('location', [])
            
            # 作物統計節點 (相容性處理)
            if 'cropStatistics' in root:
                crop_node = root['cropStatistics']
            elif 'cropStatistics' in agr_advices_node:
                crop_node = agr_advices_node['cropStatistics']
            else:
                crop_node = {}
            crop_locs = crop_node.get('crop', {}).get('location', [])
            
        except KeyError:
            return -1 # 解析結構錯誤

        # 1. 天氣預報
        weather_data = []
        for loc in forecast_locs:
            name = loc['locationName']
            elements = loc['weatherElements']
            daily = {}
            
            # 整合 Wx, MinT, MaxT
            wx_list = elements.get('Wx', {}).get('daily', [])
            max_list = elements.get('MaxT', {}).get('daily', [])
            min_list = elements.get('MinT', {}).get('daily', [])
            
            # 建立日期索引字典
            for item in wx_list:
                daily[item['dataDate']] = {'desc': item['weather']}
            for item in max_list:
                if item['dataDate'] in daily: daily[item['dataDate']]['max'] = float(item['temperature'])
            for item in min_list:
                if item['dataDate'] in daily: daily[item['dataDate']]['min'] = float(item['temperature'])
                
            for d, v in daily.items():
                weather_data.append((name, d, v.get('min',0), v.get('max',0), v.get('desc','')))

        # 2. 積溫資料
        agri_data = []
        for loc in agri_locs:
            name = loc['locationName']
            for item in loc['weatherElements']['daily']:
                d, dd, at = item.get('dataDate'), item.get('degreeDay'), item.get('accumulatedTemperature')
                if d: agri_data.append((name, d, float(dd) if dd else 0, float(at) if at else 0))

        # 3. 水稻監測
        crop_data = []
        for loc in crop_locs:
            name = loc['locationName']
            breed = loc.get('cropBreed', '未知品種')
            stats = loc.get('statistics', {}).get('thisYear', {})
            desc = stats.get('description', '無說明')
            period = stats.get('timePeriod', {})
            gd = period.get('growingDays')
            at = period.get('accumulatedTemperature')
            if gd and at:
                crop_data.append((name, breed, int(gd), float(at), desc))

        return save_all_data(weather_data, agri_data, crop_data, weather_profile)

    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return 0

# ---------------------------------------------------------
# 4. UI 介面構建
# ---------------------------------------------------------
init_db()

# --- 側邊欄 ---
with st.sidebar:
    st.image("https://www.cwa.gov.tw/V8/assets/img/logo_CWA.svg", width=150)
    st.header("⚙️ 控制面板")
    
    if st.button("🔄 立即更新資料", type="primary", use_container_width=True):
        with st.spinner("📡 正在連接氣象署衛星資料..."):
            status = fetch_and_update_data()
            if status > 0:
                st.toast("✅ 更新成功！", icon="🎉")
                st.cache_data.clear()
                st.rerun()
            elif status == -1:
                st.error("❌ 資料格式變動，請聯繫管理員。")
            else:
                st.error("❌ 無法取得資料，請稍後再試。")
    
    st.divider()
    
    with st.expander("📖 這是什麼系統？"):
        st.markdown("""
        **智慧農業氣象站** 專為農友設計，整合：
        1. **一般天氣**：未來的晴雨溫度。
        2. **農業積溫**：計算作物「吸收到多少熱量」，判斷生長進度。
        3. **水稻監測**：針對二期稻作的關鍵指標追蹤。
        
        資料來源：交通部中央氣象署
        """)
    
    st.caption("Ver 2.0 | Designed for Farmers")

# --- 主標題區 ---
st.title("🌾 智慧農業氣象儀表板")
st.markdown("讓數據成為您的「巡田水」好幫手。")

# 載入資料
df_overview = load_data('overview')
df_weather = load_data('weather')
df_agri = load_data('agri_stats')
df_crop = load_data('crop_stats')

# --- 若無資料的引導 ---
if df_weather.empty:
    st.warning("⚠️ 系統目前沒有資料")
    st.info("👈 請點擊左側側邊欄的 **「🔄 立即更新資料」** 按鈕來初始化系統。")
    st.stop()

# --- 概況卡片 ---
if not df_overview.empty:
    update_time = df_overview.iloc[0].get('update_time', '剛剛')
    st.markdown(f"<div style='text-align:right; color:gray; font-size:0.8em;'>最後更新：{update_time}</div>", unsafe_allow_html=True)
    
    with st.container():
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown("### 📢 本週農氣概況")
        st.write(df_overview.iloc[0]['content'])
        st.markdown('</div>', unsafe_allow_html=True)

# --- 主要分頁 ---
tab1, tab2, tab3 = st.tabs(["🌤️ 未來天氣預報", "🌱 積溫生長分析", "🌾 水稻專區監測"])

# === Tab 1: 天氣預報 ===
with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.markdown("#### 📍 選擇地區")
        locs = sorted(df_weather['location'].unique())
        sel_loc_t1 = st.selectbox("地區", locs, label_visibility="collapsed", key="t1_loc")
        
        # 顯示該地區今日天氣摘要
        today_weather = df_weather[df_weather['location'] == sel_loc_t1].iloc[0]
        st.metric("今日最高溫", f"{today_weather['max_temp']} °C", delta_color="normal")
        st.metric("今日最低溫", f"{today_weather['min_temp']} °C", delta_color="inverse")
        st.caption(f"天氣現象：{today_weather['description']}")

    with col2:
        st.markdown("#### 📅 未來一週溫度趨勢")
        df_show = df_weather[df_weather['location'] == sel_loc_t1].sort_values('date')
        
        # 美化圖表
        base = alt.Chart(df_show).encode(x=alt.X('date:T', axis=alt.Axis(format='%m/%d', title='日期')))
        
        line_max = base.mark_line(color='#ff7f0e', point=True).encode(
            y=alt.Y('max_temp:Q', scale=alt.Scale(zero=False), title='溫度 (°C)'),
            tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), alt.Tooltip('max_temp', title='最高溫'), 'description']
        )
        
        line_min = base.mark_line(color='#1f77b4', point=True).encode(
            y='min_temp:Q',
            tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), alt.Tooltip('min_temp', title='最低溫')]
        )
        
        band = base.mark_area(opacity=0.3, color='#9ecae1').encode(
            y='max_temp:Q',
            y2='min_temp:Q'
        )
        
        chart = (band + line_max + line_min).properties(height=350)
        st.altair_chart(chart, use_container_width=True)

# === Tab 2: 積溫分析 (科普重點) ===
with tab2:
    st.markdown("### 📈 什麼是「積溫」？ (Accumulated Temperature)")
    with st.expander("💡 科普小教室：植物也需要「熱量存摺」？", expanded=True):
        st.markdown("""
        *   **植物生長不只看天數，更看「溫度」**：如果天氣冷，植物長得慢；天氣熱，長得快。
        *   **GDD (每日生長度日)**：把今天的平均溫度減去植物生長的最低門檻（例如水稻約 10°C），就是今天存進去的「熱量」。
        *   **累積積溫**：把每天的 GDD 加總起來。每個品種開花、結穗需要的積溫是固定的，**農夫可以藉此預測收成日！**
        """)

    if not df_agri.empty:
        col_sel, col_chart = st.columns([1, 3])
        with col_sel:
            st.markdown("#### 觀測站點")
            locs_agri = sorted(df_agri['location'].unique())
            sel_loc_t2 = st.selectbox("選擇站點", locs_agri, key="t2_loc")
        
        with col_chart:
            df_agri_show = df_agri[df_agri['location'] == sel_loc_t2].sort_values('date')
            
            # 雙軸圖表
            base = alt.Chart(df_agri_show).encode(x=alt.X('date:T', axis=alt.Axis(format='%m/%d', title='日期')))
            
            bar = base.mark_bar(color='#a5d6a7', opacity=0.7).encode(
                y=alt.Y('degree_day:Q', title='每日度日 (GDD)'),
                tooltip=['date:T', alt.Tooltip('degree_day', title='GDD')]
            )
            
            line = base.mark_line(color='#2e7d32', strokeWidth=3).encode(
                y=alt.Y('accumulated_temp:Q', title='累積積溫'),
                tooltip=['date:T', alt.Tooltip('accumulated_temp', title='累積積溫')]
            )
            
            c = alt.layer(bar, line).resolve_scale(y='independent').properties(height=350)
            st.altair_chart(c, use_container_width=True)
    else:
        st.info("目前無積溫資料，可能是非產季或資料來源未更新。")

# === Tab 3: 水稻監測 ===
with tab3:
    st.markdown("### 🌾 重點示範區水稻監測 (二期作)")
    st.caption("數據來源：各區農業改良場豐歉試驗")
    
    if not df_crop.empty:
        # 使用 CSS Grid 或多欄位佈局顯示卡片
        cols = st.columns(3)
        for idx, row in df_crop.iterrows():
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"#### 📍 {row['location']}")
                    st.markdown(f"**品種**：`{row['crop_breed']}`")
                    
                    c1, c2 = st.columns(2)
                    c1.metric("已生長", f"{row['growing_days']} 天")
                    c2.metric("累積積溫", f"{row['accumulated_temp']:.0f}")
                    
                    st.markdown("**生長評語：**")
                    if row['description']:
                        st.info(row['description'])
                    else:
                        st.text("尚無詳細評語")
                    
                    # 模擬進度條 (假設二期作約 120-140 天成熟，純示意)
                    progress = min(row['growing_days'] / 140.0, 1.0)
                    st.progress(progress, text=f"預估生長進度: {int(progress*100)}%")
    else:
        st.warning("⚠️ 目前 API 回傳資料中無水稻監測數據。")
        st.markdown("""
        **可能原因：**
        1. 目前非二期稻作的主要觀測期。
        2. 氣象署資料結構暫時調整。
        """)

# Footer
st.markdown("---")
st.markdown("<div style='text-align:center; color:gray;'>© 2025 專業農業氣象儀表板 | 資料僅供參考，實際農務請依現況調整</div>", unsafe_allow_html=True)
