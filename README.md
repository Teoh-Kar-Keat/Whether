# 🌾 天氣資料下載與農業應用系統 — 完整報告

## 📌 1. 系統簡介

本系統透過中央氣象局 OpenData API，自動下載最新的農業天氣預報資料（資料集代碼：F-A0010-001），解析後存入 SQLite3 資料庫，並以 Streamlit 建立互動式儀表板，讓使用者能快速查詢每日各地天氣資訊。

本系統特別適用於農業領域，使農民能清楚掌握天氣趨勢，協助調整灌溉、施肥、採收、病蟲害防治等重要農務決策。

目前僅部署在本地 Streamlit App

---

# 📦 2. 系統整體架構

```
使用者 ↔ Streamlit 前端介面
              │
              ▼
         SQLite3 資料庫 (data.db)
              │
              ▼
        fetch_to_db.py
  (下載→解析→資料清洗→寫入資料庫)
              │
              ▼
  中央氣象局 CWA OpenData API

```


https://github.com/user-attachments/assets/b35dd9d9-2101-4d9c-a9ff-506bf4c1f167


---

# 🌐 3. 使用資料來源

| 項目 | 連結 |
| --- | --- |
| CWA 官網溫度觀測頁 | https://www.cwa.gov.tw/V8/C/W/OBS_Temp.html |
| CWA OpenData 登入頁 | https://opendata.cwa.gov.tw/userLogin |
| API Key | `請填上私人API` |
| JSON 資料集 | https://opendata.cwa.gov.tw/dataset/forecast/F-A0010-001 |
| 下載 API（本系統使用） | https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-A0010-001?Authorization=CWA-1FFDDAEC-161F-46A3-BE71-93C32C52829F&downloadType=WEB&format=JSON |

---

# 🧩 4. JSON 資料解析流程

下載後的 JSON 結構如下（簡化版）：

```json
{
  "cwaopendata": {
    "resources": {
      "resource": {
        "data": {
          "agrWeatherForecasts": {
            "weatherForecasts": {
              "location": [
                {
                  "locationName": "臺中市",
                  "weatherElements": {
                    "Wx": { "daily": [...] },
                    "MaxT": { "daily": [...] },
                    "MinT": { "daily": [...] }
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

```

本系統會抓取以下欄位：

- 地區名稱（locationName）
- 每日天氣敘述（Wx → daily → weather）
- 每日最低溫（MinT → daily → temperature）
- 每日最高溫（MaxT → daily → temperature）
- 日期（dataDate）

---

# 🗄 5. SQLite3 資料庫設計

## 📌 資料庫名稱

```
data.db

```

## 📌 資料表結構 — weather

```sql
CREATE TABLE IF NOT EXISTS weather (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    location TEXT,
    date TEXT,
    min_temp REAL,
    max_temp REAL,
    description TEXT
);

```

### 欄位解釋

| 欄位 | 說明 |
| --- | --- |
| id | 主鍵 |
| location | 地區名稱，例如「臺中市」 |
| date | 預報日期 |
| min_temp | 最低溫度 |
| max_temp | 最高溫度 |
| description | 天氣敘述，例如「多雲短暫雨」 |

---

# 🧪 6. 資料下載與儲存程式 `fetch_to_db.py`

```python
import requests
import sqlite3

URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-A0010-001?Authorization=CWA-1FFDDAEC-161F-46A3-BE71-93C32C52829F&downloadType=WEB&format=JSON"

def download_data():
    r = requests.get(URL)
    return r.json()

def save_to_db(data):
    try:
        locations = data["cwaopendata"]["resources"]["resource"]["data"] \
                        ["agrWeatherForecasts"]["weatherForecasts"]["location"]
    except KeyError as e:
        print("❌ JSON 結構不符:", e)
        return

    conn = sqlite3.connect("data.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            date TEXT,
            min_temp REAL,
            max_temp REAL,
            description TEXT
        )
    """)

    for loc in locations:
        name = loc["locationName"]
        wx_daily = loc["weatherElements"]["Wx"]["daily"]
        max_daily = loc["weatherElements"]["MaxT"]["daily"]
        min_daily = loc["weatherElements"]["MinT"]["daily"]

        for i in range(len(wx_daily)):
            date = wx_daily[i]["dataDate"]
            weather = wx_daily[i]["weather"]
            t_max = max_daily[i]["temperature"]
            t_min = min_daily[i]["temperature"]

            cur.execute(
                "INSERT INTO weather (location, date, min_temp, max_temp, description) VALUES (?, ?, ?, ?, ?)",
                (name, date, t_min, t_max, weather)
            )

    conn.commit()
    conn.close()
    print("✅ 資料已成功寫入 SQLite3！")

if __name__ == "__main__":
    data = download_data()
    save_to_db(data)

```


https://github.com/user-attachments/assets/90368d59-a1b3-4053-9c02-584c4497ac75


---

# 📊 7. Streamlit 前端介面 `app.py`

以下是可運行的 Streamlit 程式：

```python
import sqlite3
import pandas as pd
import streamlit as st

st.title("🌾 農業氣象查詢系統")

conn = sqlite3.connect("data.db")
df = pd.read_sql_query("SELECT * FROM weather", conn)

locations = df["location"].unique()
selected_loc = st.selectbox("選擇地區", locations)

result = df[df["location"] == selected_loc]

st.subheader(f"📍 {selected_loc} 的天氣預報")
st.table(result)

```

---

# 🌱 8. 系統對農業的實際應用價值

## ⭐ 1. **協助灌溉排程**

透過每日最高、最低溫及天氣狀態，農民可判斷是否需加強或減少灌溉，避免因降雨或高溫造成作物水分失衡。

## ⭐ 2. **病蟲害預警**

潮濕、多雨天氣容易引起病害（如真菌感染），系統提供的每日天氣能協助農民提前施作防治措施。

## ⭐ 3. **採收與作業規劃**

農民可依預測的晴雨狀況安排：

- 採收作業
- 除草
- 施肥
- 農藥噴灑

降低因天候不佳造成的損失。

## ⭐ 4. **作物生長模型與智慧農業整合**

資料庫格式化後，可進一步與：

- 自動化溫室控制
- AI 生長模型
- 遙測資料

整合成智慧農業決策系統。

## ⭐ 5. **區域農業風險評估**

提供不同縣市的溫度差異，協助農民選擇適作作物品種、安排播種期。

---

# 📘 9. 結論

本系統成功整合中央氣象局資料 API，使用 SQLite3 儲存並可視化天氣資訊。透過 Streamlit，使用者可快速查詢各地天氣，對農業決策具有高度實用價值。

未來可加入：

- 氣象圖表（折線圖、熱力圖）
- 自動排程每天更新
- 與農機 IoT 整合
- 氣象災害告警功能

以強化完整的智慧農業生態系統。
