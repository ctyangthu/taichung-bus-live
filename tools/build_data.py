#!/usr/bin/env python3
"""把 raw/ 的 TDX 臺中市公車資料整理成 data/bus.json。

每條路線每個方向：站序（含各站在線形上的里程與推估行車秒數）、簡化後的線形、
平日與假日的發車時刻。TDX 的臺中市班表只有起點站發車時刻，各站時間為推估。
"""
import json, math, pathlib, re, datetime

ROOT = pathlib.Path(__file__).resolve().parent.parent
RAW, OUT = ROOT / "raw", ROOT / "data" / "bus.json"
KX = 111320 * math.cos(math.radians(24.15))  # 公尺／經度
KY = 110540
# 由 TDX 預估到站資料回歸而得：相鄰兩站行車秒數 ≈ SEG_BASE + SEG_PER_M × 距離
SEG_BASE, SEG_PER_M = 60, 0.085
SIMPLIFY_M = 4
LAYOVER_MIN = 10


def load(name):
    return json.loads((RAW / f"{name}.json").read_text())


def parse_wkt(g):
    pts = []
    for part in re.findall(r"\(([^()]+)\)", g):
        for p in part.split(","):
            x, y = p.split()[:2]
            pts.append((float(x), float(y)))
    return pts


def xy(p):
    return (p[0] * KX, p[1] * KY)


def simplify(pts, tol):
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    m = [xy(p) for p in pts]
    while stack:
        a, b = stack.pop()
        ax, ay = m[a]
        bx, by = m[b]
        dx, dy = bx - ax, by - ay
        L = dx * dx + dy * dy
        best, bi = 0, -1
        for i in range(a + 1, b):
            px, py = m[i]
            if L == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                t = max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
                d = math.hypot(px - ax - t * dx, py - ay - t * dy)
            if d > best:
                best, bi = d, i
        if best > tol:
            keep[bi] = True
            stack += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]


def encode(pts):
    out, px, py = [], 0, 0
    for lon, lat in pts:
        y, x = round(lat * 1e5), round(lon * 1e5)
        for v in (y - py, x - px):
            v = ~(v << 1) if v < 0 else v << 1
            while v >= 0x20:
                out.append(chr((0x20 | (v & 0x1F)) + 63))
                v >>= 5
            out.append(chr(v + 63))
        px, py = x, y
    return "".join(out)


def stop_offsets(shape, stops):
    """各站投影到線形上的里程（公尺），並保持遞增以處理繞行、折返路段。"""
    m = [xy(p) for p in shape]
    cum = [0.0]
    for a, b in zip(m, m[1:]):
        cum.append(cum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    total = cum[-1]
    offs, prev = [], 0.0
    for s in stops:
        px, py = xy(s)
        cands = []
        for i in range(len(m) - 1):
            ax, ay = m[i]
            bx, by = m[i + 1]
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            t = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            o = cum[i] + t * math.sqrt(L)
            if o >= prev - 1:
                cands.append((math.hypot(px - ax - t * dx, py - ay - t * dy), o))
        if not cands:
            offs.append(prev)
            continue
        dmin = min(c[0] for c in cands)
        # 距離差不多時取里程最前面的，避免在折返路段跳到回程
        o = min(c[1] for c in cands if c[0] <= dmin + 25)
        prev = max(prev, o)
        offs.append(prev)
    return offs, total


def hm(s):
    h, m = s.split(":")[:2]
    return int(h) * 60 + int(m)


def departures(sched):
    """回傳 ([平日分鐘...], [假日分鐘...], 是否由班距推估)。"""
    wk, we, est = set(), set(), False
    for t in sched.get("Timetables") or []:
        st = t.get("StopTimes") or []
        if not st:
            continue
        first = min(st, key=lambda x: x.get("StopSequence", 0))
        v = hm(first.get("DepartureTime") or first.get("ArrivalTime"))
        d = t["ServiceDay"]
        if any(d.get(k) for k in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")):
            wk.add(v)
        if d.get("Saturday") or d.get("Sunday"):
            we.add(v)
    for f in sched.get("Frequencys") or []:
        est = True
        a, b = hm(f["StartTime"]), hm(f["EndTime"])
        if b < a:
            b += 1440
        step = max(1, round((f["MinHeadwayMins"] + f["MaxHeadwayMins"]) / 2))
        d = f["ServiceDay"]
        v = a
        while v < b:
            if any(d.get(k) for k in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")):
                wk.add(v)
            if d.get("Saturday") or d.get("Sunday"):
                we.add(v)
            v += step
    return sorted(wk), sorted(we), est


def natural(name):
    # 數字開頭的路線在前，同一段先比數字再比文字
    return [(0, int(t), "") if t.isdigit() else (1, 0, t) for t in re.findall(r"\d+|\D+", name)]


def main():
    routes = load("Route")
    sor = {(s["SubRouteUID"], s["Direction"]): s for s in load("StopOfRoute")}
    shapes = {(s.get("SubRouteUID", s["RouteUID"]), s.get("Direction", 0)): s for s in load("Shape")}
    scheds = {(s["SubRouteUID"], s["Direction"]): s for s in load("Schedule")}

    stops, stop_ix = [], {}
    out = []
    for r in sorted(routes, key=lambda r: natural(r["RouteName"]["Zh_tw"])):
        uid = r["RouteUID"]
        dirs = []
        for d in (0, 1):
            s = sor.get((uid, d))
            if not s or not s["Stops"]:
                continue
            seq = sorted(s["Stops"], key=lambda x: x["StopSequence"])
            pts = [(x["StopPosition"]["PositionLon"], x["StopPosition"]["PositionLat"]) for x in seq]
            sh = shapes.get((uid, d))
            shape = simplify(parse_wkt(sh["Geometry"]), SIMPLIFY_M) if sh else pts
            if len(shape) < 2:
                shape = pts
            offs, total = stop_offsets(shape, pts)
            tt, ids = [0], []
            for i, x in enumerate(seq):
                key = x["StopUID"]
                if key not in stop_ix:
                    stop_ix[key] = len(stops)
                    stops.append([x["StopName"]["Zh_tw"], round(pts[i][0], 5), round(pts[i][1], 5)])
                ids.append(stop_ix[key])
                if i:
                    tt.append(tt[-1] + round(SEG_BASE + SEG_PER_M * (offs[i] - offs[i - 1])))
            wk, we, est = departures(scheds.get((uid, d), {}))
            dirs.append({
                "d": d,
                "s": ids,
                "q": [x["StopSequence"] for x in seq],
                "o": [round(o) for o in offs],
                "t": tt,
                "len": round(total),
                "p": encode(shape),
                "wk": wk,
                "we": we,
                **({"est": 1} if est else {}),
            })
        if not dirs:
            continue
        # TDX 有些路線只公布去程班表。返程以「去程發車 + 去程行車時間 + 休息」推估，並標記 mir
        if len(dirs) == 2:
            for a, b in ((dirs[0], dirs[1]), (dirs[1], dirs[0])):
                if not (a["wk"] or a["we"]) and (b["wk"] or b["we"]):
                    lag = round(b["t"][-1] / 60) + LAYOVER_MIN
                    a["wk"] = [v + lag for v in b["wk"]]
                    a["we"] = [v + lag for v in b["we"]]
                    a["mir"] = 1
        out.append({
            "id": uid,
            "n": r["RouteName"]["Zh_tw"],
            "from": r.get("DepartureStopNameZh", ""),
            "to": r.get("DestinationStopNameZh", ""),
            "ops": [o["OperatorName"]["Zh_tw"] for o in r.get("Operators", [])],
            "dirs": dirs,
        })

    src_time = max(r["UpdateTime"] for r in routes)
    data = {
        "built": datetime.date.today().isoformat(),
        "source": src_time[:10],
        "stops": stops,
        "routes": out,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    nd = sum(len(r["dirs"]) for r in out)
    print(f"{len(out)} routes, {nd} directions, {len(stops)} stops, "
          f"{sum(len(d['wk']) for r in out for d in r['dirs'])} weekday / "
          f"{sum(len(d['we']) for r in out for d in r['dirs'])} weekend departures, "
          f"{OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
