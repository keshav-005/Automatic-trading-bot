"""
Compatibility Layer for NumPy and Pandas with pure-Python fallback.
Author: Computer Science Student Project

Ensures the trading engine, technical indicators, and backtesting runner
execute smoothly across any platform (including Windows with Application Control,
lightweight serverless runtimes, and newer Python releases) even if binary C-extensions
encounter environment restrictions.
"""

import math
import random
from typing import Any, Dict, List, Optional, Union

# Attempt to load native numpy and pandas
HAS_NATIVE = False
try:
    import numpy as _real_np
    import pandas as _real_pd
    # Validate that compiled C-extensions actually run without permission faults
    _test = _real_np.array([1.0, 2.0]).mean()
    _test_df = _real_pd.DataFrame({'a': [1.0, 2.0]})
    HAS_NATIVE = True
    np = _real_np
    pd = _real_pd
except Exception:
    HAS_NATIVE = False

if not HAS_NATIVE:
    class PureSeries:
        def __init__(self, data: Any = None, index: Optional[Any] = None):
            if data is None:
                self._data = []
            elif isinstance(data, PureSeries):
                self._data = list(data._data)
            elif isinstance(data, (list, tuple)):
                self._data = [float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else x for x in data]
            elif isinstance(data, dict):
                self._data = list(data.values())
            else:
                self._data = [data]
            self.index = list(index) if index is not None else list(range(len(self._data)))

        def __len__(self) -> int:
            return len(self._data)

        def __iter__(self):
            return iter(self._data)

        @property
        def values(self) -> list:
            return self._data

        def tolist(self) -> list:
            return list(self._data)

        def __getitem__(self, item: Any) -> Any:
            if isinstance(item, slice):
                sub_data = self._data[item]
                sub_index = self.index[item]
                return PureSeries(sub_data, index=sub_index)
            elif isinstance(item, (PureSeries, list, tuple)):
                mask = item._data if isinstance(item, PureSeries) else item
                res_data = [x for x, m in zip(self._data, mask) if m]
                res_idx = [i for i, m in zip(self.index, mask) if m]
                return PureSeries(res_data, index=res_idx)
            return self._data[item]

        def __setitem__(self, key: Any, value: Any):
            self._data[key] = value

        @property
        def iloc(self):
            return self

        def diff(self, periods: int = 1) -> "PureSeries":
            res = []
            for i in range(len(self._data)):
                if i < periods:
                    res.append(float('nan'))
                else:
                    a = self._data[i]
                    b = self._data[i - periods]
                    if (isinstance(a, float) and math.isnan(a)) or (isinstance(b, float) and math.isnan(b)):
                        res.append(float('nan'))
                    else:
                        res.append(a - b)
            return PureSeries(res, index=self.index)

        def shift(self, periods: int = 1) -> "PureSeries":
            res = []
            for i in range(len(self._data)):
                if i < periods:
                    res.append(float('nan'))
                else:
                    res.append(self._data[i - periods])
            return PureSeries(res, index=self.index)

        def clip(self, lower: Optional[float] = None, upper: Optional[float] = None) -> "PureSeries":
            res = []
            for x in self._data:
                if isinstance(x, float) and math.isnan(x):
                    res.append(x)
                else:
                    val = x
                    if lower is not None and val < lower:
                        val = lower
                    if upper is not None and val > upper:
                        val = upper
                    res.append(val)
            return PureSeries(res, index=self.index)

        def replace(self, to_replace: float, value: float) -> "PureSeries":
            res = []
            for x in self._data:
                if (x == to_replace) or (isinstance(x, float) and math.isnan(x) and isinstance(to_replace, float) and math.isnan(to_replace)):
                    res.append(value)
                else:
                    res.append(x)
            return PureSeries(res, index=self.index)

        def fillna(self, value: Union[float, "PureSeries"]) -> "PureSeries":
            res = []
            val_list = value._data if isinstance(value, PureSeries) else None
            for i, x in enumerate(self._data):
                if isinstance(x, float) and math.isnan(x):
                    replacement = val_list[i] if val_list is not None else float(value)
                    res.append(replacement)
                else:
                    res.append(x)
            return PureSeries(res, index=self.index)

        def isna(self) -> "PureSeries":
            return PureSeries([isinstance(x, float) and math.isnan(x) for x in self._data], index=self.index)

        def isnull(self) -> "PureSeries":
            return self.isna()

        def any(self) -> bool:
            return any(bool(x) for x in self._data)

        def all(self) -> bool:
            return all(bool(x) for x in self._data)

        def abs(self) -> "PureSeries":
            return PureSeries([abs(x) if not (isinstance(x, float) and math.isnan(x)) else x for x in self._data], index=self.index)

        def mean(self) -> float:
            valid = [x for x in self._data if isinstance(x, (int, float)) and not math.isnan(x)]
            return sum(valid) / len(valid) if valid else 0.0

        def std(self, ddof: int = 0) -> float:
            valid = [x for x in self._data if isinstance(x, (int, float)) and not math.isnan(x)]
            if len(valid) <= ddof:
                return 0.0
            m = sum(valid) / len(valid)
            var = sum((x - m) ** 2 for x in valid) / (len(valid) - ddof)
            return math.sqrt(max(0.0, var))

        def rolling(self, window: int, min_periods: int = 1):
            class Rolling:
                def __init__(self, data: list, index: list, w: int, mp: int):
                    self.data = data
                    self.index = index
                    self.w = w
                    self.mp = mp

                def mean(self) -> "PureSeries":
                    res = []
                    for i in range(len(self.data)):
                        start = max(0, i - self.w + 1)
                        sub = [x for x in self.data[start : i + 1] if not (isinstance(x, float) and math.isnan(x))]
                        if len(sub) >= self.mp:
                            res.append(sum(sub) / len(sub))
                        else:
                            res.append(float('nan'))
                    return PureSeries(res, index=self.index)

                def std(self, ddof: int = 0) -> "PureSeries":
                    res = []
                    for i in range(len(self.data)):
                        start = max(0, i - self.w + 1)
                        sub = [x for x in self.data[start : i + 1] if not (isinstance(x, float) and math.isnan(x))]
                        if len(sub) > ddof and len(sub) >= self.mp:
                            m = sum(sub) / len(sub)
                            var = sum((x - m) ** 2 for x in sub) / (len(sub) - ddof)
                            res.append(math.sqrt(max(0.0, var)))
                        else:
                            res.append(0.0)
                    return PureSeries(res, index=self.index)

            return Rolling(self._data, self.index, window, min_periods)

        def ewm(self, span: Optional[int] = None, alpha: Optional[float] = None, adjust: bool = False, min_periods: int = 0):
            a = alpha if alpha is not None else (2.0 / (span + 1.0) if span is not None else 0.5)
            class EWM:
                def __init__(self, data: list, index: list, a_factor: float, min_p: int):
                    self.data = data
                    self.index = index
                    self.a = a_factor
                    self.min_p = min_p

                def mean(self) -> "PureSeries":
                    res = []
                    val = None
                    valid_count = 0
                    for x in self.data:
                        if isinstance(x, float) and math.isnan(x):
                            res.append(float('nan'))
                            continue
                        valid_count += 1
                        if val is None:
                            val = x
                        else:
                            val = self.a * x + (1.0 - self.a) * val
                        if valid_count >= self.min_p:
                            res.append(val)
                        else:
                            res.append(float('nan'))
                    return PureSeries(res, index=self.index)

            return EWM(self._data, self.index, a, min_periods)

        # Mathematical and Logical Dunder Operations
        def __add__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                return PureSeries([a + b for a, b in zip(self._data, o_data)], index=self.index)
            return PureSeries([a + other for a in self._data], index=self.index)

        def __radd__(self, other: Any) -> "PureSeries":
            return self.__add__(other)

        def __sub__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                return PureSeries([a - b for a, b in zip(self._data, o_data)], index=self.index)
            return PureSeries([a - other for a in self._data], index=self.index)

        def __rsub__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                return PureSeries([b - a for a, b in zip(self._data, o_data)], index=self.index)
            return PureSeries([other - a for a in self._data], index=self.index)

        def __mul__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                return PureSeries([a * b for a, b in zip(self._data, o_data)], index=self.index)
            return PureSeries([a * other for a in self._data], index=self.index)

        def __rmul__(self, other: Any) -> "PureSeries":
            return self.__mul__(other)

        def __truediv__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                res = []
                for a, b in zip(self._data, o_data):
                    if b == 0.0 or (isinstance(b, float) and math.isnan(b)):
                        res.append(float('nan'))
                    else:
                        res.append(a / b)
                return PureSeries(res, index=self.index)
            res = [a / other if other != 0 else float('nan') for a in self._data]
            return PureSeries(res, index=self.index)

        def __rtruediv__(self, other: Any) -> "PureSeries":
            if isinstance(other, (PureSeries, list, tuple)):
                o_data = other._data if isinstance(other, PureSeries) else other
                res = []
                for a, b in zip(self._data, o_data):
                    if a == 0.0 or (isinstance(a, float) and math.isnan(a)):
                        res.append(float('nan'))
                    else:
                        res.append(b / a)
                return PureSeries(res, index=self.index)
            res = []
            for a in self._data:
                if a == 0.0 or (isinstance(a, float) and math.isnan(a)):
                    res.append(float('nan'))
                else:
                    res.append(other / a)
            return PureSeries(res, index=self.index)

        def __neg__(self) -> "PureSeries":
            return PureSeries([-x if not (isinstance(x, float) and math.isnan(x)) else x for x in self._data], index=self.index)

        def __pow__(self, power: Any) -> "PureSeries":
            if isinstance(power, (int, float)):
                return PureSeries([x ** power if not (isinstance(x, float) and math.isnan(x)) else float('nan') for x in self._data], index=self.index)
            elif isinstance(power, (PureSeries, list, tuple)):
                p_data = power._data if isinstance(power, PureSeries) else power
                return PureSeries([x ** p for x, p in zip(self._data, p_data)], index=self.index)
            return self

        def __gt__(self, other: Any) -> "PureSeries":
            if isinstance(other, PureSeries):
                return PureSeries([a > b for a, b in zip(self._data, other._data)], index=self.index)
            return PureSeries([a > other for a in self._data], index=self.index)

        def __lt__(self, other: Any) -> "PureSeries":
            if isinstance(other, PureSeries):
                return PureSeries([a < b for a, b in zip(self._data, other._data)], index=self.index)
            return PureSeries([a < other for a in self._data], index=self.index)

        def __ge__(self, other: Any) -> "PureSeries":
            if isinstance(other, PureSeries):
                return PureSeries([a >= b for a, b in zip(self._data, other._data)], index=self.index)
            return PureSeries([a >= other for a in self._data], index=self.index)

        def __le__(self, other: Any) -> "PureSeries":
            if isinstance(other, PureSeries):
                return PureSeries([a <= b for a, b in zip(self._data, other._data)], index=self.index)
            return PureSeries([a <= other for a in self._data], index=self.index)

        def __and__(self, other: Any) -> "PureSeries":
            if isinstance(other, PureSeries):
                return PureSeries([bool(a and b) for a, b in zip(self._data, other._data)], index=self.index)
            return PureSeries([bool(a and other) for a in self._data], index=self.index)

    class PureDataFrame:
        def __init__(self, data: Optional[Dict[str, Any]] = None, index: Optional[Any] = None):
            self._columns: Dict[str, PureSeries] = {}
            if data:
                n_len = None
                for k, v in data.items():
                    s = PureSeries(v)
                    self._columns[k] = s
                    if n_len is None:
                        n_len = len(s)
                self.index = list(index) if index is not None else list(range(n_len or 0))
            else:
                self.index = []

        def __getitem__(self, item: Any) -> Any:
            if isinstance(item, str):
                return self._columns[item]
            elif isinstance(item, list):
                sub = {k: self._columns[k] for k in item}
                return PureDataFrame(sub, index=self.index)
            raise KeyError(item)

        def __setitem__(self, key: str, value: Any):
            self._columns[key] = PureSeries(value, index=self.index) if not isinstance(value, PureSeries) else value

        def __contains__(self, item: str) -> bool:
            return item in self._columns

        def __len__(self) -> int:
            if not self._columns:
                return 0
            first_col = next(iter(self._columns.values()))
            return len(first_col)

        @property
        def iloc(self):
            class ILoc:
                def __init__(self, df: "PureDataFrame"):
                    self.df = df

                def __getitem__(self, item: Any) -> Any:
                    if isinstance(item, slice):
                        new_cols = {k: v[item] for k, v in self.df._columns.items()}
                        return PureDataFrame(new_cols, index=self.df.index[item])
                    elif isinstance(item, int):
                        return {k: v[item] for k, v in self.df._columns.items()}
            return ILoc(self)

        @property
        def loc(self):
            class Loc:
                def __init__(self, df: "PureDataFrame"):
                    self.df = df

                def __getitem__(self, item: Any) -> Any:
                    if isinstance(item, tuple):
                        row_idx, col_name = item
                        pos = self.df.index.index(row_idx) if row_idx in self.df.index else int(row_idx)
                        return self.df._columns[col_name][pos]
                    elif isinstance(item, str):
                        return self.df._columns[item]
                    raise KeyError(item)

                def __setitem__(self, item: Any, value: Any):
                    if isinstance(item, tuple):
                        row_idx, col_name = item
                        pos = self.df.index.index(row_idx) if row_idx in self.df.index else int(row_idx)
                        self.df._columns[col_name][pos] = value
                    else:
                        raise KeyError(item)
            return Loc(self)

        def copy(self) -> "PureDataFrame":
            return PureDataFrame({k: PureSeries(v.tolist()) for k, v in self._columns.items()}, index=list(self.index))

    class PureConcatResult:
        def __init__(self, series_list: List[PureSeries]):
            self.series_list = series_list

        def max(self, axis: int = 1) -> PureSeries:
            n = len(self.series_list[0])
            res = []
            for i in range(n):
                vals = [s[i] for s in self.series_list if not (isinstance(s[i], float) and math.isnan(s[i]))]
                res.append(max(vals) if vals else float('nan'))
            return PureSeries(res)

    class PurePandas:
        Series = PureSeries
        DataFrame = PureDataFrame

        @staticmethod
        def concat(objs: List[PureSeries], axis: int = 1) -> Any:
            return PureConcatResult(objs)

        @staticmethod
        def date_range(start: Any, periods: Optional[int] = None, freq: str = "5min") -> List[Any]:
            from datetime import datetime, timedelta
            if isinstance(start, str):
                try:
                    dt = datetime.fromisoformat(start)
                except Exception:
                    dt = datetime(2026, 1, 1, 0, 0, 0)
            else:
                dt = start
            minutes = 5
            if "min" in freq:
                try:
                    minutes = int(freq.replace("min", "").strip() or 5)
                except Exception:
                    minutes = 5
            count = periods or 100
            return [dt + timedelta(minutes=i * minutes) for i in range(count)]

    class PureNumpyRandom:
        @staticmethod
        def seed(s: int):
            random.seed(s)

        @staticmethod
        def normal(loc: float = 0.0, scale: float = 1.0, size: Optional[int] = None) -> Any:
            if size is not None:
                return [random.gauss(loc, scale) for _ in range(size)]
            return random.gauss(loc, scale)

        @staticmethod
        def exponential(scale: float = 1.0, size: Optional[int] = None) -> Any:
            if size is not None:
                return [random.expovariate(1.0 / scale) if scale > 0 else 0.0 for _ in range(size)]
            return random.expovariate(1.0 / scale) if scale > 0 else 0.0

        @staticmethod
        def uniform(low: float = 0.0, high: float = 1.0, size: Optional[int] = None) -> Any:
            if size is not None:
                return [random.uniform(low, high) for _ in range(size)]
            return random.uniform(low, high)

        @staticmethod
        def randint(low: int, high: int, size: Optional[int] = None) -> Any:
            if size is not None:
                return [random.randint(low, high) for _ in range(size)]
            return random.randint(low, high)

    class PureMaximum:
        def __call__(self, a: Any, b: Any) -> PureSeries:
            a_lst = a.tolist() if hasattr(a, 'tolist') else list(a)
            b_lst = b.tolist() if hasattr(b, 'tolist') else list(b)
            return PureSeries([max(x, y) for x, y in zip(a_lst, b_lst)])

        def accumulate(self, a: Any) -> PureSeries:
            lst = a.tolist() if hasattr(a, 'tolist') else list(a)
            res = []
            curr_max = float('-inf')
            for x in lst:
                val = float(x)
                if val > curr_max:
                    curr_max = val
                res.append(curr_max)
            return PureSeries(res)

    class PureNumpy:
        nan = float('nan')
        random = PureNumpyRandom

        @staticmethod
        def isnan(x: Any) -> bool:
            return isinstance(x, float) and math.isnan(x)

        @staticmethod
        def sqrt(x: Any) -> float:
            return math.sqrt(float(x))

        @staticmethod
        def max(data: Any) -> float:
            lst = data.tolist() if hasattr(data, 'tolist') else list(data)
            return max(float(x) for x in lst) if lst else 0.0

        @staticmethod
        def min(data: Any) -> float:
            lst = data.tolist() if hasattr(data, 'tolist') else list(data)
            return min(float(x) for x in lst) if lst else 0.0

        @staticmethod
        def mean(data: Any) -> float:
            lst = data.tolist() if hasattr(data, 'tolist') else list(data)
            valid = [x for x in lst if isinstance(x, (int, float)) and not math.isnan(x)]
            return sum(valid) / len(valid) if valid else 0.0

        @staticmethod
        def std(data: Any, ddof: int = 0) -> float:
            lst = data.tolist() if hasattr(data, 'tolist') else list(data)
            valid = [x for x in lst if isinstance(x, (int, float)) and not math.isnan(x)]
            if len(valid) <= ddof:
                return 0.0
            m = sum(valid) / len(valid)
            var = sum((x - m) ** 2 for x in valid) / (len(valid) - ddof)
            return math.sqrt(max(0.0, var))

        @staticmethod
        def cumsum(a: Any) -> PureSeries:
            lst = a.tolist() if hasattr(a, 'tolist') else list(a)
            total = 0.0
            res = []
            for x in lst:
                total += float(x)
                res.append(total)
            return PureSeries(res)

        @staticmethod
        def where(cond: Any, x: Any, y: Any) -> PureSeries:
            c_list = cond.tolist() if hasattr(cond, 'tolist') else list(cond)
            x_list = x.tolist() if hasattr(x, 'tolist') else ([x] * len(c_list))
            y_list = y.tolist() if hasattr(y, 'tolist') else ([y] * len(c_list))
            return PureSeries([xv if cv else yv for cv, xv, yv in zip(c_list, x_list, y_list)])

        @staticmethod
        def diff(a: Any) -> PureSeries:
            lst = a.tolist() if hasattr(a, 'tolist') else list(a)
            return PureSeries([lst[i] - lst[i-1] for i in range(1, len(lst))])

        maximum = PureMaximum()

        @staticmethod
        def minimum(a: Any, b: Any) -> PureSeries:
            a_lst = a.tolist() if hasattr(a, 'tolist') else list(a)
            b_lst = b.tolist() if hasattr(b, 'tolist') else list(b)
            return PureSeries([min(x, y) for x, y in zip(a_lst, b_lst)])

        @staticmethod
        def array(data: Any) -> PureSeries:
            return PureSeries(data)

    np = PureNumpy()
    pd = PurePandas()
