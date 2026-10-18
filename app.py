import asyncio
import socket
from urllib.parse import quote

import pandas as pd
from nicegui import run, ui

import data
import sorting

DARK = "#1b5e20"
LIGHT = "#c8e6c9"
PALE = "#f1f8e9"
BENCH_SIZES = [500, 1000, 2000, 5000, 10000, 15000]


def header():
    ui.colors(primary=DARK)
    ui.query("body").style("background-color: white")
    with ui.header().style(f"background-color: white !important; color: {DARK} !important; border-bottom: 4px solid {LIGHT}"):
        with ui.row().classes("w-full items-center justify-between"):
            ui.label("💊 MEDSHELF — Pharmacy Management System").classes("text-xl font-bold")
            with ui.row():
                ui.button("Dashboard", on_click=lambda: ui.navigate.to("/")).props("flat")
                ui.button("All Medicines", on_click=lambda: ui.navigate.to("/medicines")).props("flat")
                ui.button("About", on_click=lambda: ui.navigate.to("/about")).props("flat")


def stat_card(parent, title, value):
    with parent:
        with ui.card().style(f"background-color: {PALE}; min-width: 200px; border: 1px solid {LIGHT}"):
            ui.label(title).classes("text-sm").style(f"color: {DARK}")
            ui.label(str(value)).classes("text-2xl font-bold").style(f"color: {DARK}")


def show_error(message):
    with ui.card().style("background-color: #ffebee; border: 1px solid #ef9a9a"):
        ui.label(message).style("color: #b71c1c")


def format_price(value):
    if pd.isna(value):
        return "N/A"
    return f"{value:,.2f}".rstrip("0").rstrip(".")


def rows_from(df, columns):
    rows = []
    for index, record in df[columns].iterrows():
        row = {"id": int(index)}
        for column in columns:
            row[column] = format_price(record[column]) if column == "price" else str(record[column])
        rows.append(row)
    return rows


@ui.page("/")
def dashboard_page():
    header()
    df, error = data.load_medicines()
    with ui.column().classes("w-full items-center p-6 gap-4"):
        ui.label("Dashboard").classes("text-2xl font-bold").style(f"color: {DARK}")
        if error:
            show_error(error)
            return
        info = data.summary(df)
        cards = ui.row().classes("gap-4")
        stat_card(cards, "Total Medicines", info["total"])
        stat_card(cards, "Available Medicines", info["available"])
        stat_card(cards, "Total Categories", info["categories"])
        if info["available"] == "N/A":
            ui.label("Availability is empty. Run 'python scraper.py details' to fill it.").classes("text-sm text-gray-600")

        def go():
            ui.navigate.to("/medicines?q=" + quote(search.value or ""))

        with ui.row().classes("items-center gap-2 mt-4"):
            search = ui.input("Search medicine by name").props("outlined dense clearable").classes("w-80")
            search.on("keydown.enter", go)
            ui.button("Search", on_click=go)


@ui.page("/medicines")
def medicines_page(q: str = ""):
    header()
    df, error = data.load_medicines()
    with ui.column().classes("w-full p-4 gap-3"):
        ui.label("All Medicines").classes("text-2xl font-bold").style(f"color: {DARK}")
        if error:
            show_error(error)
            return

        columns = data.visible_columns(df)
        view = {"df": data.apply_filters(df, name=q)}
        busy = {"on": False}

        def current_filters():
            return data.apply_filters(
                df,
                name=name_input.value or "",
                category=category_select.value,
                manufacturer=manufacturer_select.value if manufacturer_select else "All",
                min_price=min_price.value if min_price else None,
                max_price=max_price.value if max_price else None,
            )

        def refresh():
            table.rows = rows_from(view["df"], columns)
            table.update()
            count_label.set_text(f"Showing {len(view['df']):,} of {len(df):,} medicines")

        def apply_filters(_=None):
            if busy["on"]:
                return
            view["df"] = current_filters()
            refresh()

        def clear_filters():
            busy["on"] = True
            name_input.value = ""
            category_select.value = "All"
            if manufacturer_select:
                manufacturer_select.value = "All"
            if min_price:
                min_price.value = None
                max_price.value = None
            busy["on"] = False
            apply_filters()
            metrics_box.clear()

        with ui.card().classes("w-full").style(f"border: 1px solid {LIGHT}"):
            ui.label("Search and Filters").classes("font-bold").style(f"color: {DARK}")
            with ui.row().classes("items-end gap-3"):
                name_input = ui.input("Medicine name", value=q, on_change=apply_filters).props("outlined dense clearable debounce=400")
                category_select = ui.select(["All"] + data.unique_values(df, "category"), value="All", label="Category", with_input=True, on_change=apply_filters).props("outlined dense").classes("w-56")
                manufacturer_select = None
                if "manufacturer" in columns:
                    manufacturer_select = ui.select(["All"] + data.unique_values(df, "manufacturer"), value="All", label="Brand / Manufacturer", with_input=True, on_change=apply_filters).props("outlined dense").classes("w-64")
                min_price = None
                max_price = None
                if "price" in columns:
                    min_price = ui.number("Min price", value=None, min=0, on_change=apply_filters).props("outlined dense").classes("w-28")
                    max_price = ui.number("Max price", value=None, min=0, on_change=apply_filters).props("outlined dense").classes("w-28")
                ui.button("Clear Filters", on_click=clear_filters).props("outline")

        async def run_sort():
            current = view["df"]
            if current.empty:
                ui.notify("There are no medicines to sort.", type="warning")
                return
            name = algorithm_select.value
            ascending = order_select.value == "Ascending"
            items = sorting.make_items(current, sort_select.value)
            sort_button.disable()
            ui.notify(f"Sorting {len(items):,} medicines with {name}. Please wait...", timeout=4000)
            try:
                result, stats = await run.cpu_bound(sorting.run_sort, name, items, ascending)
                view["df"] = current.loc[[pair[1] for pair in result]]
                refresh()
                metrics_box.clear()
                cards = [
                    ("Algorithm", name),
                    ("Rows Sorted", f"{len(result):,}"),
                    ("Execution Time", f"{stats['time_ms']:,} ms"),
                    ("Comparisons", f"{stats['comparisons']:,}"),
                    ("Swaps", f"{stats['swaps']:,}"),
                    ("Moves", f"{stats['moves']:,}"),
                    ("Time Complexity", stats["complexity"]),
                ]
                for title, value in cards:
                    stat_card(metrics_box, title, value)
            except Exception as error:
                try:
                    ui.notify(f"Sorting failed: {error}", type="negative")
                except Exception:
                    pass
            finally:
                try:
                    sort_button.enable()
                except Exception:
                    pass

        def reset_sort():
            apply_filters()
            metrics_box.clear()

        with ui.card().classes("w-full").style(f"border: 1px solid {LIGHT}"):
            ui.label("Sorting").classes("font-bold").style(f"color: {DARK}")
            with ui.row().classes("items-end gap-3"):
                sort_select = ui.select({c: data.LABELS[c] for c in columns}, value=columns[0], label="Column").props("outlined dense").classes("w-48")
                order_select = ui.select(["Ascending", "Descending"], value="Ascending", label="Order").props("outlined dense").classes("w-40")
                algorithm_select = ui.select(list(sorting.ALGORITHMS), value="Merge Sort", label="Algorithm").props("outlined dense").classes("w-48")
                sort_button = ui.button("Sort", on_click=run_sort)
                ui.button("Reset Sort", on_click=reset_sort).props("outline")
            metrics_box = ui.row().classes("gap-3")

        sizes = [n for n in BENCH_SIZES if n < len(df)] + [len(df)]
        size_options = {n: f"{n:,}" for n in sizes}
        size_options[len(df)] = f"All ({len(df):,})"
        default_size = 1000 if 1000 in sizes else sizes[0]

        async def run_benchmark():
            size = min(int(benchmark_size.value), len(df))
            ascending = order_select.value == "Ascending"
            sample = df.sample(n=size, random_state=1)
            items = sorting.make_items(sample, sort_select.value)
            benchmark_button.disable()
            ui.notify(f"Benchmark started on {size:,} medicines. All 6 algorithms run at the same time. Please wait...", timeout=8000)
            try:
                results = await asyncio.gather(*[
                    run.cpu_bound(sorting.benchmark_one, name, items, ascending)
                    for name in sorting.ALGORITHMS
                ])
                results = list(results)
                fastest = min(results, key=lambda r: r["time_ms"])
                benchmark_table.rows = results
                benchmark_table.update()
                benchmark_table.set_visibility(True)
                benchmark_note.set_text(f"Same {size:,} medicines for every algorithm, sorted by {data.LABELS[sort_select.value]} ({order_select.value}). Fastest: {fastest['algorithm']}.")
            except Exception as error:
                try:
                    ui.notify(f"Benchmark failed: {error}", type="negative")
                except Exception:
                    pass
            finally:
                try:
                    benchmark_button.enable()
                except Exception:
                    pass

        with ui.card().classes("w-full").style(f"border: 1px solid {LIGHT}"):
            ui.label("Benchmark").classes("font-bold").style(f"color: {DARK}")
            with ui.row().classes("items-end gap-3"):
                benchmark_size = ui.select(size_options, value=default_size, label="Number of medicines").props("outlined dense").classes("w-56")
                benchmark_button = ui.button("Run Benchmark", on_click=run_benchmark)
            if len(df) > 5000:
                ui.label("Bubble, Selection and Insertion Sort are O(n²), so they take longer on big sizes. All algorithms run in parallel, and the app stays responsive.").classes("text-sm text-gray-600")
            benchmark_note = ui.label("")
            benchmark_columns = [
                {"name": "algorithm", "label": "Algorithm", "field": "algorithm", "align": "left"},
                {"name": "time_ms", "label": "Time (ms)", "field": "time_ms", "align": "right"},
                {"name": "comparisons", "label": "Comparisons", "field": "comparisons", "align": "right"},
                {"name": "swaps", "label": "Swaps", "field": "swaps", "align": "right"},
                {"name": "moves", "label": "Moves", "field": "moves", "align": "right"},
                {"name": "complexity", "label": "Time Complexity", "field": "complexity", "align": "left"},
            ]
            benchmark_table = ui.table(columns=benchmark_columns, rows=[], row_key="algorithm").classes("w-full")
            benchmark_table.set_visibility(False)

        count_label = ui.label("")
        table_columns = [{"name": c, "label": data.LABELS[c], "field": c, "align": "left"} for c in columns]
        table = ui.table(columns=table_columns, rows=[], row_key="id", pagination=15).classes("w-full")
        refresh()


@ui.page("/about")
def about_page():
    header()
    with ui.column().classes("w-full items-center p-6 gap-3"):
        ui.label("About MEDSHELF").classes("text-2xl font-bold").style(f"color: {DARK}")
        with ui.card().classes("w-full max-w-3xl").style(f"border: 1px solid {LIGHT}"):
            ui.label("MEDSHELF is a student project that shows pharmacy medicines in a simple table and lets you search, filter and sort them.")
            ui.label("Data: medicine records scraped from Medimart Pakistan (medimart.pk) and saved in medicines.csv.")
            ui.label("Sorting algorithms: Bubble Sort, Selection Sort, Insertion Sort, Quick Sort, Merge Sort and Hybrid Merge Sort, all written by hand.")
            ui.label("After each sort the app shows execution time, comparisons, swaps, moves and time complexity.")
            ui.label("Built with Python, NiceGUI, Pandas and CSV files.")
            ui.label("This is a learning project, not medical advice.").classes("text-gray-600")


def find_free_port(start=8080):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as test:
            try:
                test.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


if __name__ in {"__main__", "__mp_main__"}:
    port = find_free_port()
    print(f"Open this link in your browser: http://127.0.0.1:{port}")
    ui.run(title="MEDSHELF — Pharmacy Management System", host="127.0.0.1", port=port, reload=False)