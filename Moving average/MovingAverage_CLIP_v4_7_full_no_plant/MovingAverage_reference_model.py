"""Floating-point reference model for MovingAverage CLIP node.
Implements an N=16 sliding-window moving average over 0–100 range.
"""

from collections import deque

class MovingAverageRef:
    def __init__(self, N=16):
        self.N = N
        self.buf = deque([0.0] * N, maxlen=N)

    def step(self, x: float) -> float:
        self.buf.append(float(x))
        return sum(self.buf) / len(self.buf)

if __name__ == "__main__":
    m = MovingAverageRef(16)
    for i in range(20):
        y = m.step(100.0 if i >= 4 else 0.0)
        print(i, y)
