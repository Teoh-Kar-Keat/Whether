import streamlit as st
import sqlite3
import pandas as pd
import requests
import altair as alt
import re
from datetime import datetime

# ---------------------------------------------------------
# 1. 系統設定與視覺優化 (CSS) - 🔥 顯示修復版
# ---------------------------------------------------------
st.set_page_config(
    page_title="智慧農業氣象站",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定義 CSS：針對「舒適排版」、「高對比」、「大字體」
st.markdown("""
    <style>
    /* 1. 全域字體：深色、高對比、無襯線體 */
    html, body, [class*="css"] {
        font-family: "Microsoft JhengHei", "PingFang TC", sans-serif;
        color: #000000 !important; /* 純黑字體 */
    }

    /* 2. 內文優化：字級 22px，行距 1.8 */
    .stMarkdown p, .stMarkdown li, .stText, .stHtml, .stInfo {
        font-size: 22px !important;
        font-weight: 500 !important;
        line-height: 1.8 !important;
        margin-bottom: 12px !important;
    }
    
    /* 3. 標題層級 */
    h1 { font-size: 48px !important; font-weight: 900 !important; color: #1b5e20 !important; letter-spacing: 1.5px; }
    h2 { font-size: 36px !important; font-weight: 800 !important; color: #2e7d32 !important; }
    h3 { font-size: 28px !important; font-weight: 800 !important; color: #388e3c !important; }
    h4 { font-size: 24px !important; font-weight: 700 !important; color: #43a047 !important; }

    /* 4. 概況卡片容器 (Timeline Card) */
    .weather-card {
        background-color: #ffffff;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
        margin-bottom: 25px;
        display: block; /* 確保區塊顯示 */
    }

    /* 每一行的容器 */
    .timeline-row {
        padding-bottom: 15px;
        margin-bottom: 15px;
        border-bottom: 1px dashed #cfd8dc;
        display: flex;
        align-items: flex-start; /* 對齊頂部 */
        flex-wrap: wrap;
    }
    .timeline-row:last-child {
        border-bottom: none;
    }

    /* 日期標籤 (藥丸形狀) */
    .date-pill {
        display: inline-block;
        background-color: #2e7d32;
        color: #ffffff !important;
        font-size: 20px;
        font-weight: bold;
        padding: 5px 15px;
        border-radius: 50px;
        margin-right: 15px;
        white-space: nowrap;
        box-shadow: 0 2px 5px rgba(46, 125, 50, 0.3);
        margin-top: 5px; /* 微調垂直對齊 */
    }

    /* 內容文字區塊 */
    .content-text {
        font-size: 22px;
        line-height: 1.8;
        color: #212121;
        flex: 1; /* 填滿剩餘空間 */
        min-width: 250px; /* 手機版避免過窄 */
    }

    /* 5. 關鍵字高亮 */
    .highlight-cold { color: #b71c1c; font-weight: 900; background-color: #ffcdd2; padding: 0 6px; border-radius: 4px; }
    .highlight-warm { color: #e65100; font-weight: 900; background-color: #ffe0b2; padding: 0 6px; border-radius: 4px; }
    .highlight-warn { color: #4a148c; font-weight: 900; background-color: #e1bee7; padding: 0 6px; border-radius: 4px; }

    /* 6. 數據指標卡片 */
    [data-testid="stMetricValue"] { font-size: 46px !important; font-weight: 900 !important; color: #0277bd; }
    .stMetric { background-color: #ffffff; border: 2px solid #b0bec5; border-radius: 12px; padding: 20px; }
    
    /* 7. Tab 標籤 */
    .stTabs [data-baseweb="tab"] { font-size: 24px !important; font-weight: 700 !important; padding: 15px 30px !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# 2. 全域變數與資料庫
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
# 3. 資料處理工具 (修正 HTML 拼接問題)
# ---------------------------------------------------------
def format_weather_text(text):
    """
    將氣象局長文轉換為「時間軸列表」格式。
    修正：使用緊湊的 HTML 字串，避免 Markdown 解析錯誤。
    """
    if not text: return "⚠️ 暫無概況資料"
    
    # 1. 符號清洗：將分號 (;) 與 (；) 強制換成句號，以便切分
    text = text.replace(";", "。").replace("；", "。").replace(",", "，").replace(":", "：")
    
    # 2. 關鍵字上色
    text = re.sub(r"(東北季風[^,;，；。]*|轉涼|有雨|短暫雨|局部雨)", r"<span class='highlight-cold'>\1</span>", text)
    text = re.sub(r"(氣溫[^,;，；。]*回升|晴)", r"<span class='highlight-warm'>\1</span>", text)
    text = re.sub(r"(日夜溫差[^,;，；。]*)", r"<span class='highlight-warn'>\1</span>", text)

    # 3. 切分句子
    sentences = text.split("。")
    
    # 開始組合 HTML，注意不要有多餘縮排
    html_parts = ["<div class='weather-card'>"]
    
    for sentence in sentences:
        clean_sentence = sentence.strip()
        if not clean_sentence: continue
        
        # 4. 抓取日期
        date_pattern = r"^(\d+日(?:、\d+日)?)"
        match = re.match(date_pattern, clean_sentence)
        
        if match:
            date_str = match.group(1)
            content_str = clean_sentence[len(date_str):].strip()
            if content_str.startswith("，") or content_str.startswith("、"):
                content_str = content_str[1:].strip()
            
            # 使用 f-string 但不換行，防止 Markdown 誤判
            row = f"<div class='timeline-row'><div class='date-pill'>📅 {date_str}</div><div class='content-text'>{content_str}。</div></div>"
            html_parts.append(row)
        else:
            # 沒日期的段落
            if len(clean_sentence) > 3:
                row = f"<div class='timeline-row'><div class='content-text'>{clean_sentence}。</div></div>"
                html_parts.append(row)
            
    html_parts.append("</div>")
    
    # 將陣列接成單一字串
    return "".join(html_parts)

# ---------------------------------------------------------
# 4. API 資料抓取
# ---------------------------------------------------------
def fetch_and_update_data():
    params = {"Authorization": CWA_API_KEY, "format": "JSON"}
    try:
        response = requests.get(API_URL, params=params)
        response.raise_for_status()
        data = response.json()
        try:
            root = data['cwaopendata']['resources']['resource']['data']['agrWeatherForecasts']
            weather_profile = root.get('weatherProfile', '目前無概況資料')
            forecast_locs = root['weatherForecasts']['location']
            agr_advices_node = root.get('agrAdvices', {})
            agri_locs = agr_advices_node.get('agrForecasts', {}).get('location', [])
            
            if 'cropStatistics' in root: crop_node = root['cropStatistics']
            elif 'cropStatistics' in agr_advices_node: crop_node = agr_advices_node['cropStatistics']
            else: crop_node = {}
            crop_locs = crop_node.get('crop', {}).get('location', [])
        except KeyError: return -1

        weather_data = []
        for loc in forecast_locs:
            name = loc['locationName']
            daily = {}
            for item in loc['weatherElements']['Wx']['daily']: daily[item['dataDate']] = {'desc': item['weather']}
            for item in loc['weatherElements']['MaxT']['daily']: 
                if item['dataDate'] in daily: daily[item['dataDate']]['max'] = float(item['temperature'])
            for item in loc['weatherElements']['MinT']['daily']: 
                if item['dataDate'] in daily: daily[item['dataDate']]['min'] = float(item['temperature'])
            for d, v in daily.items(): weather_data.append((name, d, v.get('min',0), v.get('max',0), v.get('desc','')))

        agri_data = []
        for loc in agri_locs:
            name = loc['locationName']
            for item in loc['weatherElements']['daily']:
                d, dd, at = item.get('dataDate'), item.get('degreeDay'), item.get('accumulatedTemperature')
                if d: agri_data.append((name, d, float(dd) if dd else 0, float(at) if at else 0))

        crop_data = []
        for loc in crop_locs:
            name = loc['locationName']
            breed = loc.get('cropBreed', '未知品種')
            stats = loc.get('statistics', {}).get('thisYear', {})
            desc = stats.get('description', '')
            period = stats.get('timePeriod', {})
            gd, at = period.get('growingDays'), period.get('accumulatedTemperature')
            if gd and at: crop_data.append((name, breed, int(gd), float(at), desc))

        return save_all_data(weather_data, agri_data, crop_data, weather_profile)
    except Exception: return 0

# ---------------------------------------------------------
# 5. 主程式 UI
# ---------------------------------------------------------
init_db()

with st.sidebar:
    st.image("https://www.cwa.gov.tw/V8/assets/img/logo_CWA.svg", width=180)
    st.markdown("## ⚙️ 控制面板")
    
    if st.button("🔄 立即更新資料", type="primary", use_container_width=True):
        with st.spinner("📡 資料更新中..."):
            status = fetch_and_update_data()
            if status > 0:
                st.toast("✅ 更新完成！", icon="🎉")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error("更新失敗")
    
    st.divider()
    with st.expander("📖 系統說明"):
        st.markdown("""
        **智慧農業氣象站**
        1. **一週天氣**：降雨、氣溫。
        2. **GDD 積溫**：作物生長進度。
        3. **水稻監測**：產區重點追蹤。
        """)

st.title("🌾 智慧農業氣象儀表板")
st.markdown("**結合氣象預報與作物積溫，科學化管理農田。**")

df_overview = load_data('overview')
df_weather = load_data('weather')
df_agri = load_data('agri_stats')
df_crop = load_data('crop_stats')

if df_weather.empty:
    st.warning("⚠️ 系統目前無資料，請點擊左側「立即更新」按鈕。")
    st.stop()

# --- 天氣概況 (使用新版 Timeline Card) ---
if not df_overview.empty:
    update_time = df_overview.iloc[0].get('update_time', '')
    
    with st.container():
        st.markdown(f"### 📢 本週農氣概況解析 <span style='font-size:18px; color:#555; float:right; font-weight:normal;'>更新：{update_time}</span>", unsafe_allow_html=True)
        
        raw_text = df_overview.iloc[0]['content']
        # 產生純 HTML 字串
        pretty_html = format_weather_text(raw_text)
        # 關鍵：unsafe_allow_html=True 確保 HTML 被渲染而非顯示源碼
        st.markdown(pretty_html, unsafe_allow_html=True)
        
        st.caption("💡 提示：紅色文字 = 轉涼/有雨 (需防寒) | 橘色文字 = 回升/晴天 | 紫色文字 = 溫差大 (注意通風)")
        st.write("") 

# --- 數據分頁 ---
tab1, tab2, tab3 = st.tabs(["🌤️ 未來天氣預報", "🌱 積溫生長分析", "🌾 水稻專區監測"])

# Tab 1: 天氣預報
with tab1:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### 📍 選擇地區")
        locs = sorted(df_weather['location'].unique())
        sel_loc_t1 = st.selectbox("地區", locs, label_visibility="collapsed", key="t1_loc")
        
        today_data = df_weather[df_weather['location'] == sel_loc_t1].iloc[0]
        st.metric("今日最高溫", f"{today_data['max_temp']}°C")
        st.metric("夜間低溫", f"{today_data['min_temp']}°C", delta="-低溫注意" if today_data['min_temp'] < 18 else "off", delta_color="inverse")
        st.info(f"天氣現象：{today_data['description']}")

    with col2:
        st.markdown(f"#### 📅 {sel_loc_t1} - 未來一週溫度趨勢")
        df_show = df_weather[df_weather['location'] == sel_loc_t1].sort_values('date')
        
        # Altair 字體放大
        base = alt.Chart(df_show).encode(
            x=alt.X('date:T', axis=alt.Axis(format='%m/%d', title='日期', labelFontSize=16, titleFontSize=18))
        )
        band = base.mark_area(opacity=0.3, color='#90caf9').encode(
            y=alt.Y('max_temp:Q', title='溫度 (°C)', axis=alt.Axis(labelFontSize=16, titleFontSize=18)),
            y2='min_temp:Q'
        )
        line_max = base.mark_line(color='#d32f2f', point=True, strokeWidth=4).encode(
            y='max_temp:Q', tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), alt.Tooltip('max_temp', title='最高溫')]
        )
        line_min = base.mark_line(color='#1976d2', point=True, strokeWidth=4).encode(
            y='min_temp:Q', tooltip=[alt.Tooltip('date:T', format='%Y-%m-%d'), alt.Tooltip('min_temp', title='最低溫')]
        )
        st.altair_chart((band + line_max + line_min).interactive(), use_container_width=True)

# Tab 2: 積溫分析
with tab2:
    st.markdown("### 📈 積溫趨勢 (GDD)")
    with st.expander("💡 科普：為什麼要看「積溫」？", expanded=False):
        st.markdown("""
        *   **植物只看熱量**：溫度夠高才長得快。
        *   **GDD**：今日均溫減去基礎溫度。
        *   **用途**：預測割稻日子，比看日曆準！
        """)

    if not df_agri.empty:
        col_sel, col_chart = st.columns([1, 3])
        with col_sel:
            st.markdown("#### 觀測站")
            sel_loc_t2 = st.selectbox("觀測站點", sorted(df_agri['location'].unique()), key="t2_loc", label_visibility="collapsed")
        with col_chart:
            df_agri_show = df_agri[df_agri['location'] == sel_loc_t2].sort_values('date')
            
            base = alt.Chart(df_agri_show).encode(
                x=alt.X('date:T', axis=alt.Axis(format='%m/%d', title='日期', labelFontSize=16, titleFontSize=18))
            )
            bar = base.mark_bar(color='#a5d6a7', opacity=0.8).encode(
                y=alt.Y('degree_day:Q', title='每日度日 (GDD)', axis=alt.Axis(labelFontSize=16, titleFontSize=18))
            )
            line = base.mark_line(color='#2e7d32', strokeWidth=5).encode(
                y=alt.Y('accumulated_temp:Q', title='累積積溫', axis=alt.Axis(labelFontSize=16, titleFontSize=18))
            )
            st.altair_chart(alt.layer(bar, line).resolve_scale(y='independent'), use_container_width=True)
    else:
        st.info("目前無積溫資料")

# Tab 3: 水稻監測
with tab3:
    st.markdown("### 🌾 重點示範區水稻監測")
    if not df_crop.empty:
        cols = st.columns(3)
        for idx, row in df_crop.iterrows():
            with cols[idx % 3]:
                with st.container(border=True):
                    st.markdown(f"### 📍 {row['location']}")
                    st.markdown(f"**品種**: {row['crop_breed']}")
                    c1, c2 = st.columns(2)
                    c1.metric("已生長", f"{row['growing_days']} 天")
                    c2.metric("累積積溫", f"{row['accumulated_temp']:.0f}")
                    st.progress(min(row['growing_days']/140.0, 1.0), text="生長進度")
                    st.markdown(f"<div style='background:#f1f8e9; padding:15px; border-radius:8px; border:1px solid #c8e6c9; color:#2e7d32;'>{row['description']}</div>", unsafe_allow_html=True)
    else:
        st.warning("目前無水稻資料")

st.markdown("---")
st.markdown("<div style='text-align:center; font-size:18px; color:gray; font-weight:bold;'>© 2025 智慧農業氣象站</div>", unsafe_allow_html=True)