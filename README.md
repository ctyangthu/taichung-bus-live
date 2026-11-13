# 台中公車動態

臺中市 394 條市區公車路線的即時位置與時刻表，資料來自交通部 [TDX 運輸資料流通服務](https://tdx.transportdata.tw/)（與臺中市公車動態系統同一份來源）。

## 功能

- **GPS 即時**：地圖顯示所有回報 GPS 的公車（方向、時速、GPS 時間），點車輛可看資訊並跳到路線。
- **路線**：搜尋路線，看兩個方向的站序、各站到站時間、車輛目前在哪一站，以及起點發車時刻表（平日／假日）。
- **站牌**：搜尋站牌名稱，列出經過的路線方向與下一班車。
- **運行中**：目前各路線的車輛數。
- **時刻表推估**：不用 GPS，依發車時刻推算每一班車的位置，可拖時間軸或加速播放。

## 到站時間怎麼來的

| 標示 | 來源 |
| --- | --- |
| 官方預估 | TDX `EstimatedTimeOfArrival`，需要 TDX 金鑰 |
| GPS 推估 | 把公車 GPS 位置投影到路線上，加上到該站的表定行車時間 |
| 表定推估 | 起點發車時刻加上到該站的行車時間 |

TDX 的臺中市班表只有**起點站發車時刻**，各站行車時間是推估的：相鄰兩站約 60 秒加上每公尺 0.085 秒，係數由 TDX 預估到站資料回歸而得。

## TDX 存取限制

- 未登入的 TDX 每個網路位址一天只能查詢 **20 次**。所以沒有金鑰時，頁面只在開啟時與按「更新 GPS」時讀取一次全市車輛位置（5 分鐘內重新整理會沿用上一次的結果）。
- 在頁面右上角「TDX 金鑰」填入自己的 Client ID／Secret 後，車輛位置每 20 秒自動更新，選取的路線改用官方預估到站。金鑰只存在瀏覽器的 localStorage，只會傳給 TDX。

## 資料限制

- TDX 有 45 條路線只公布單一方向的班表（例如 300 的臺中車站發車方向）。這些方向的班次由對向發車時刻加上行車時間與 10 分鐘休息推估，畫面上會標示。另有 12 條路線完全沒有班表。
- 11 條路線只公布班距，班次依班距排出。
- 班表只分平日與假日，國定假日未另外處理。
- 環狀或折返路線上，GPS 推估可能把車輛對到錯的路段。
- 本系統為非官方展示，實際行車以臺中市政府公告為準。

## 專案結構

```
src/app.html          頁面（Leaflet + OpenStreetMap 圖磚）
data/bus.json         路線、站序、線形、發車時刻（tools/build_data.py 產生）
raw/                  TDX 原始資料（不納入版本控制）
tools/fetch_tdx.py    下載 TDX 的 Route、StopOfRoute、Shape、Schedule
tools/build_data.py   整理成 data/bus.json
tools/build.py        組出 dist/
```

## 建置

```bash
python3 tools/build.py
```

更新路線與班表（未登入一次用掉 4 次查詢額度；可設定 `TDX_CLIENT_ID`、`TDX_CLIENT_SECRET`）：

```bash
python3 tools/fetch_tdx.py --force && python3 tools/build_data.py && python3 tools/build.py
```

開發時可用 `?snapshot=檔名.json` 讀取放在 `dist/` 的 `RealTimeByFrequency` 快照，不消耗 TDX 額度。
