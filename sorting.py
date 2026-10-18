import time
import pandas as pd

THRESHOLD = 10

SLOW_ALGORITHMS = ["Bubble Sort", "Selection Sort", "Insertion Sort"]

COMPLEXITY = {
    "Bubble Sort": "Best O(n), Average O(n²), Worst O(n²)",
    "Selection Sort": "Best O(n²), Average O(n²), Worst O(n²)",
    "Insertion Sort": "Best O(n), Average O(n²), Worst O(n²)",
    "Quick Sort": "Best O(n log n), Average O(n log n), Worst O(n²)",
    "Merge Sort": "Best O(n log n), Average O(n log n), Worst O(n log n)",
    "Hybrid Merge Sort": "Best O(n log n), Average O(n log n), Worst O(n log n)",
}


# Note: run_sort() removes the empty (None) values before sorting and puts them
# at the end afterwards, so every algorithm below only sees real values.


def is_before(a, b, ascending, stats):
    stats["comparisons"] += 1
    if ascending:
        return a < b
    return a > b


def bubble_sort(items, ascending, stats):
    keys = [item[0] for item in items]
    comparisons = 0
    swaps = 0
    end = len(items) - 1  # last index that still needs checking
    while end > 0:
        last_swap = 0
        comparisons += end
        if ascending:
            for j in range(end):
                if keys[j + 1] < keys[j]:
                    keys[j], keys[j + 1] = keys[j + 1], keys[j]
                    items[j], items[j + 1] = items[j + 1], items[j]
                    swaps += 1
                    last_swap = j
        else:
            for j in range(end):
                if keys[j + 1] > keys[j]:
                    keys[j], keys[j + 1] = keys[j + 1], keys[j]
                    items[j], items[j + 1] = items[j + 1], items[j]
                    swaps += 1
                    last_swap = j
        end = last_swap  # everything after the last swap is already sorted
    stats["comparisons"] += comparisons
    stats["swaps"] += swaps
    return items


def selection_sort(items, ascending, stats):
    n = len(items)
    keys = [item[0] for item in items]
    comparisons = 0
    swaps = 0
    for i in range(n - 1):
        best = i
        best_key = keys[i]
        comparisons += n - 1 - i
        if ascending:
            for j in range(i + 1, n):
                key = keys[j]
                if key < best_key:
                    best = j
                    best_key = key
        else:
            for j in range(i + 1, n):
                key = keys[j]
                if key > best_key:
                    best = j
                    best_key = key
        if best != i:
            keys[i], keys[best] = keys[best], keys[i]
            items[i], items[best] = items[best], items[i]
            swaps += 1
    stats["comparisons"] += comparisons
    stats["swaps"] += swaps
    return items


def insertion_sort(items, ascending, stats):
    comparisons = 0
    moves = 0
    for i in range(1, len(items)):
        current = items[i]
        key = current[0]
        j = i - 1
        if ascending:
            while j >= 0 and key < items[j][0]:
                items[j + 1] = items[j]
                j -= 1
        else:
            while j >= 0 and key > items[j][0]:
                items[j + 1] = items[j]
                j -= 1
        shifted = i - 1 - j
        comparisons += shifted + (1 if j >= 0 else 0)
        items[j + 1] = current
        moves += shifted + 1
    stats["comparisons"] += comparisons
    stats["moves"] += moves
    return items


def quick_sort(items, ascending, stats):
    stack = [(0, len(items) - 1)]
    while stack:
        low, high = stack.pop()
        if low >= high:
            continue
        pivot = items[(low + high) // 2][0]
        i = low
        j = high
        while i <= j:
            while is_before(items[i][0], pivot, ascending, stats):
                i += 1
            while is_before(pivot, items[j][0], ascending, stats):
                j -= 1
            if i <= j:
                if i != j:
                    items[i], items[j] = items[j], items[i]
                    stats["swaps"] += 1
                i += 1
                j -= 1
        stack.append((low, j))
        stack.append((i, high))
    return items


def merge(left, right, ascending, stats):
    result = []
    i = 0
    j = 0
    while i < len(left) and j < len(right):
        if is_before(right[j][0], left[i][0], ascending, stats):
            result.append(right[j])
            j += 1
        else:
            result.append(left[i])
            i += 1
        stats["moves"] += 1
    rest = left[i:] + right[j:]
    result.extend(rest)
    stats["moves"] += len(rest)
    return result


def merge_sort(items, ascending, stats):
    if len(items) <= 1:
        return items
    middle = len(items) // 2
    left = merge_sort(items[:middle], ascending, stats)
    right = merge_sort(items[middle:], ascending, stats)
    return merge(left, right, ascending, stats)


def hybrid_merge_sort(items, ascending, stats):
    if len(items) <= THRESHOLD:
        return insertion_sort(items, ascending, stats)
    middle = len(items) // 2
    left = hybrid_merge_sort(items[:middle], ascending, stats)
    right = hybrid_merge_sort(items[middle:], ascending, stats)
    return merge(left, right, ascending, stats)


ALGORITHMS = {
    "Bubble Sort": bubble_sort,
    "Selection Sort": selection_sort,
    "Insertion Sort": insertion_sort,
    "Quick Sort": quick_sort,
    "Merge Sort": merge_sort,
    "Hybrid Merge Sort": hybrid_merge_sort,
}


def make_items(df, column):
    items = []
    is_number = pd.api.types.is_numeric_dtype(df[column])
    for index, value in df[column].items():
        if is_number:
            key = None if pd.isna(value) else float(value)
        else:
            text = str(value).strip().lower()
            key = None if text in ("", "n/a", "nan") else text
        items.append([key, int(index)])
    return items


def run_sort(name, items, ascending):
    """Sort one list. Empty values (None) always go to the end."""
    stats = {"comparisons": 0, "swaps": 0, "moves": 0}
    filled = [item for item in items if item[0] is not None]
    empty = [item for item in items if item[0] is None]
    start = time.perf_counter()
    result = ALGORITHMS[name](filled, ascending, stats) + empty
    stats["time_ms"] = round((time.perf_counter() - start) * 1000, 3)
    stats["complexity"] = COMPLEXITY[name]
    return result, stats


def benchmark_one(name, items, ascending):
    """Run one algorithm and return only the small result row.
    Used so each algorithm can run in its own process at the same time."""
    _, stats = run_sort(name, items, ascending)
    return {
        "algorithm": name,
        "time_ms": stats["time_ms"],
        "comparisons": stats["comparisons"],
        "swaps": stats["swaps"],
        "moves": stats["moves"],
        "complexity": stats["complexity"],
    }


def benchmark(items, ascending):
    return [benchmark_one(name, items, ascending) for name in ALGORITHMS]