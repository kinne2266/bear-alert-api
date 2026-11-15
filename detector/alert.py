import time
from collections import deque

LEVELS = {"注意": 1, "警戒": 2, "緊急": 3}
COOLDOWN_S = {"注意": 600, "警戒": 300, "緊急": 30}


def inside(point, polygon):
    """点が多角形の中にあるか（レイキャスティング法）"""
    x, y = point
    hit = False
    for (x1, y1), (x2, y2) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def zone_of(point, zones):
    """点が入っているエリアのうち、いちばん危険度の高いものを返す"""
    hits = [z for z in zones if inside(point, z["polygon"])]
    return max(hits, key=lambda z: LEVELS[z["level"]], default=None)


class AlertGate:
    """追跡IDごとに、直近 window フレームのうち min_hits フレーム以上で熊なら確定する"""

    def __init__(self, window=25, min_hits=15):
        self.window = window
        self.min_hits = min_hits
        self.history = {}    # 追跡ID -> 直近の判定（熊なら True）
        self.last_sent = {}  # (追跡ID, 危険度) -> 最後に通知した時刻

    def observe(self, track_id, is_bear):
        """このフレームの判定を記録し、熊として確定したかを返す"""
        h = self.history.setdefault(track_id, deque(maxlen=self.window))
        h.append(is_bear)
        return sum(h) >= self.min_hits

    def should_notify(self, track_id, level, now=None):
        """同じ熊・同じ危険度の通知は、一定時間あける"""
        now = time.time() if now is None else now
        last = self.last_sent.get((track_id, level))
        if last is not None and now - last < COOLDOWN_S[level]:
            return False
        self.last_sent[(track_id, level)] = now
        return True

    def tick(self, seen_ids):
        """このフレームで見えなかった追跡IDには「熊なし」を記録し、しばらく見えなければ消す"""
        for tid, h in list(self.history.items()):
            if tid not in seen_ids:
                h.append(False)
                if len(h) == self.window and not any(h):
                    del self.history[tid]