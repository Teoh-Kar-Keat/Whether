中央氣象局天氣資料下載、儲存與可視化系統
🧩 一、系統目的與背景

本系統的目的是自動化取得中央氣象局（CWA）開放資料，
將每日各地區天氣預報整理後存進 SQLite 資料庫，
再透過 Streamlit 提供互動式下拉選單與曲線圖，
讓使用者更直觀地查詢未來數日天氣趨勢。

此架構非常適合農業應用，例如農民可以透過曲線圖快速了解溫度變化，協助安排灌溉、防霜、防雨措施。

📡 二、系統流程
整體流程圖
中央氣象局 API(JSON)
        ↓
    Python requests
        ↓
    解析 JSON
        ↓
    SQLite3 (data.db)
        ↓
    Streamlit 前端
  ↓       ↓       ↓
下拉選單  表格    曲線圖

🧱 三、系統功能說明（依區塊拆解）
1️⃣ 下載中央氣象局 JSON 資料
📌 使用 F-A0010-001（農業天氣預報） API

程式碼：

r = requests.get(URL)
data = r.json()

⭐ 功能說明：

向中央氣象局伺服器發出 GET 請求

回傳 JSON 格式資料，包含：

地區名稱（locationName）

天氣現象（Wx）

最高溫（MaxT）

最低溫（MinT）

預報7天資料

2️⃣ JSON 資料解析

CWA 的 JSON 結構如下（實際節錄）：

{
  "cwaopendata": {
    "resources": {
      "resource": {
        "data": {
          "agrWeatherForecasts": {
            "weatherForecasts": {
              "location": [
                {
                  "locationName": "北部地區",
                  "weatherElements": {
                    "Wx": {"daily": [...]},
                    "MaxT": {"daily": [...]},
                    "MinT": {"daily": [...]}
                  }
                }
              ]
            }
          }
        }
      }
    }
  }
}

⭐ 解析程式功能：

找到 location 清單

針對每個地區取得：

地區名（region）

每日日期（date）

每日天氣描述（weather）

最高溫（temp_high）

最低溫（temp_low）

每筆資料最後會變成：

北部地區 | 2025-12-04 | 多雲時晴 | 15~21

3️⃣ 建立 SQLite 資料庫（data.db）

資料庫名稱：

data.db


資料表設計：

CREATE TABLE weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT,
    date TEXT,
    weather TEXT,
    temp_low REAL,
    temp_high REAL
);

⭐ 設計理念：

region：可查詢特定區域

date：可繪製折線圖

weather：可做天氣文字摘要

temp_low / temp_high：可視覺化溫度曲線

SQLite 的優點：

優點	說明
輕量	一個 data.db 就能存所有資料
零配置	不需安裝 MySQL, PostgreSQL
可攜性	系統可直接上課 demo 或跨電腦使用
適合中小型資料	氣象資料量小，非常合適
4️⃣ 將資料寫入 SQLite

核心程式：

conn = sqlite3.connect("data.db")
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO weather (region, date, weather, temp_low, temp_high)
    VALUES (?, ?, ?, ?, ?)
""", (name, date, weather, t_min, t_max))

conn.commit()

⭐ 功能說明：

逐筆將預報資料寫入資料庫

使用 parameterized SQL（安全）

存入後可直接被 Streamlit 讀取

5️⃣ Streamlit 前端介面（app.py）
(1) 下拉式選單
regions = sorted(df["region"].unique())
choice = st.selectbox("選擇地區", regions)


✔ 動態讀取所有地區
✔ 自動提供選擇項

(2) 顯示資料表格
st.dataframe(df_sel, height=300)


✔ 顯示該地區 7 天預報
✔ 使用者可點選排序或放大

(3) 曲線圖（最高/最低溫）
line_chart = alt.Chart(df_sel)...
st.altair_chart(line_chart)


✔ 顯示最高溫/最低溫曲線
✔ 可看到溫度趨勢、是否上升或下降

(4) 天氣摘要
for _, row in df_sel.iterrows():
    st.write(f"{row['date']}：{row['weather']}（{row['temp_low']}~{row['temp_high']}°C）")


✔ 文字描述每日天氣

🌱 六、此系統對農業的實際應用價值

本系統屬於 農業氣象決策輔助平台（Agricultural Weather DSS） 的雛型，
能直接協助農民做以下判斷：

1️⃣ 防止低溫造成作物凍害

溫度曲線圖可看到：

是否接近 霜凍臨界溫度 12°C

檢測 連續低溫天數

協助決定是否啟動防寒措施（覆蓋布、灌溉保溫）

2️⃣ 降雨與病害預測

天氣描述（例如「短暫雨」）可用來預測：

某些作物（例如番茄、瓜類）在濕冷環境病害上升

稻作可能受雨延遲施肥

調整藥劑噴灑時機，避免白噴造成浪費

3️⃣ 協助灌溉排程

透過溫度與天氣變化可以：

判斷是否需要提前灌溉

避免大雨前澆水

減少水資源浪費

4️⃣ 收穫 / 播種時程調整

哪一天溫度最高？
哪一天雨勢較小？

這些都可以從系統清楚看出，農民可決定：

收穫日（避免雨天）

播種日（選擇晴天溫暖時段）

避免低溫或強風日搬運作物

5️⃣ 改善農作業計畫效率

整體來說，本系統讓農民快速得到：

近一週天氣變化

高溫 / 低溫趨勢

雨天或壞天氣提醒

相比傳統看電視、看大量文字預報，
「視覺化曲線 + 下拉選單 + 數據表格」更易於判讀。

📝 七、結論

本系統整合：

中央氣象局開放資料

SQLite 資料庫

Streamlit 互動式網頁

成功提供：

資料自動下載

資料庫化管理

即時視覺化查詢

區域化氣象資訊

並且在農業應用上具有高度價值，
可以有效協助農民做 逐日作業判斷、災害提前應對與田間管理排程。
