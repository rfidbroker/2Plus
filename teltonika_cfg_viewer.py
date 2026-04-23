from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

KNOWN_FIELDS = {
    "2000": "gprs_enabled",
    "2001": "apn",
    "2002": "apn_username",
    "2003": "apn_password",
    "2004": "primary_server_domain",
    "2005": "primary_server_port",
    "2006": "primary_server_protocol",
    "2007": "secondary_server_domain_or_ip",
    "2008": "secondary_server_port",
    "2009": "secondary_server_protocol",
    "2010": "server_mode",
    "2011": "apn_authentication",
    "2015": "imei",
    "2016": "ack_type",
    "2017": "sort_order",
    "2020": "auto_apn",
    "2022": "limit_connection_errors",
    "1000": "open_link_timeout_s",
    "1001": "response_timeout_s",
    "1002": "network_ping_timeout_s",
    "1003": "network_ping_period_s",
    "902": "ntp_server_1",
    "903": "ntp_server_2",
    "13000": "fota_domain",
    "13001": "fota_port",
    "13002": "fota_period_min",
    "13003": "fota_enabled",
}

PROTOCOL_MAP = {"0": "TCP", "1": "UDP", "2": "MQTT"}
BOOL_MAP = {"0": "False", "1": "True"}
SERVER_MODE_MAP = {"0": "Disabled", "1": "Backup", "2": "Duplicate"}
ACK_TYPE_MAP = {"0": "TCP/IP", "1": "AVL", "2": "Unknown(2)"}
SORT_ORDER_MAP = {"0": "Oldest", "1": "Newest", "2": "Unknown(2)"}
AUTH_MAP = {"0": "None", "1": "Normal(PAP)", "2": "Secured(CHAP)"}


def read_cfg(path: Path) -> str:
    raw = path.read_bytes()
    try:
        return gzip.decompress(raw).decode("utf-8", errors="replace")
    except OSError:
        return raw.decode("utf-8", errors="replace")


def parse_cfg(text: str):
    header = {}
    numeric = {}
    for token in text.split(";"):
        token = token.strip()
        if not token or ":" not in token:
            continue
        key, value = token.split(":", 1)
        key, value = key.strip(), value.strip()
        if key.isdigit():
            numeric[key] = value
        else:
            header[key] = value
    return header, numeric


def mapped_value(field_id: str, value: str) -> str:
    if field_id in {"2000", "2020", "2022", "13003"}:
        return BOOL_MAP.get(value, value)
    if field_id in {"2006", "2009"}:
        return PROTOCOL_MAP.get(value, value)
    if field_id == "2010":
        return SERVER_MODE_MAP.get(value, value)
    if field_id == "2011":
        return AUTH_MAP.get(value, value)
    if field_id == "2016":
        return ACK_TYPE_MAP.get(value, value)
    if field_id == "2017":
        return SORT_ORDER_MAP.get(value, value)
    return value


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Teltonika CFG Viewer")
        self.geometry("1180x760")
        self.minsize(980, 620)

        self.current_file: Path | None = None
        self.header = {}
        self.numeric = {}

        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="Open CFG", command=self.open_file).pack(side="left")
        ttk.Button(top, text="Export JSON", command=self.export_json).pack(side="left", padx=(8, 0))
        ttk.Button(top, text="Export CSV", command=self.export_csv).pack(side="left", padx=(8, 0))

        self.file_label = ttk.Label(top, text="No file loaded")
        self.file_label.pack(side="left", padx=(16, 0))

        filter_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Filter:").pack(side="left")
        self.filter_var = tk.StringVar()
        entry = ttk.Entry(filter_frame, textvariable=self.filter_var, width=40)
        entry.pack(side="left", padx=(8, 0))
        entry.bind("<KeyRelease>", lambda e: self.populate_tables())

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Summary tab
        summary_frame = ttk.Frame(notebook, padding=10)
        notebook.add(summary_frame, text="Preview")
        self.summary_text = tk.Text(summary_frame, wrap="word", height=20)
        self.summary_text.pack(fill="both", expand=True)

        # Header tab
        header_frame = ttk.Frame(notebook, padding=10)
        notebook.add(header_frame, text="Header")
        self.header_tree = self._make_tree(header_frame, ["Key", "Value"], [220, 780])

        # Numeric tab
        numeric_frame = ttk.Frame(notebook, padding=10)
        notebook.add(numeric_frame, text="Fields")
        self.numeric_tree = self._make_tree(numeric_frame, ["ID", "Name", "Value", "Mapped"], [100, 260, 360, 360])

    def _make_tree(self, parent, columns, widths):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        tree = ttk.Treeview(frame, columns=columns, show="headings")
        vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        for col, width in zip(columns, widths):
            tree.heading(col, text=col)
            tree.column(col, width=width, anchor="w")
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        return tree

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open Teltonika CFG file",
            filetypes=[("CFG files", "*.cfg"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            self.current_file = Path(path)
            text = read_cfg(self.current_file)
            self.header, self.numeric = parse_cfg(text)
            self.file_label.configure(text=str(self.current_file))
            self.populate_tables()
            self.populate_summary()
        except Exception as exc:
            messagebox.showerror("Load error", f"Failed to load file:\n{exc}")

    def populate_tables(self):
        pattern = self.filter_var.get().strip().lower()

        for item in self.header_tree.get_children():
            self.header_tree.delete(item)
        for item in self.numeric_tree.get_children():
            self.numeric_tree.delete(item)

        for key, value in sorted(self.header.items()):
            blob = f"{key} {value}".lower()
            if pattern and pattern not in blob:
                continue
            self.header_tree.insert("", "end", values=(key, value))

        for key in sorted(self.numeric.keys(), key=lambda x: int(x)):
            name = KNOWN_FIELDS.get(key, "")
            value = self.numeric[key]
            mapped = mapped_value(key, value)
            blob = f"{key} {name} {value} {mapped}".lower()
            if pattern and pattern not in blob:
                continue
            self.numeric_tree.insert("", "end", values=(key, name, value, mapped))

    def populate_summary(self):
        self.summary_text.delete("1.0", "end")
        if not self.current_file:
            return

        lines = [
            f"Loaded file: {self.current_file}",
            f"Header fields: {len(self.header)}",
            f"Numeric fields: {len(self.numeric)}",
            "",
            "Quick preview:",
        ]

        preview_ids = ["2001", "2002", "2004", "2005", "2006", "2007", "2008", "2009", "2010", "13000", "13001", "13002", "13003"]
        for field_id in preview_ids:
            if field_id in self.numeric:
                name = KNOWN_FIELDS.get(field_id, "")
                raw = self.numeric[field_id]
                mapped = mapped_value(field_id, raw)
                lines.append(f"- {field_id} | {name or 'unknown'} = {raw} ({mapped})")

        self.summary_text.insert("1.0", "\n".join(lines))

    def export_json(self):
        if not self.current_file:
            messagebox.showinfo("Export JSON", "Load a CFG file first.")
            return
        out = self.current_file.with_name(self.current_file.stem + "_parsed.json")
        payload = {"header": self.header, "data": self.numeric}
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        messagebox.showinfo("Export JSON", f"Saved:\n{out}")

    def export_csv(self):
        if not self.current_file:
            messagebox.showinfo("Export CSV", "Load a CFG file first.")
            return
        out = self.current_file.with_name(self.current_file.stem + "_parsed.csv")
        with out.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Name", "Value", "Mapped"])
            for key in sorted(self.numeric.keys(), key=lambda x: int(x)):
                writer.writerow([key, KNOWN_FIELDS.get(key, ""), self.numeric[key], mapped_value(key, self.numeric[key])])
        messagebox.showinfo("Export CSV", f"Saved:\n{out}")


if __name__ == "__main__":
    app = App()
    app.mainloop()
