"""Beacon buddy-list desktop client: Windows / Linux, Python 3 Tkinter."""
import json
import platform
import queue
import threading
import time
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from tkinter import messagebox, simpledialog, ttk


class API:
    def __init__(self):
        self.base = ""
        self.token = None

    def call(self, path, method="GET", data=None):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = json.dumps(data).encode() if data is not None else None
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(self.base + "/api" + path, data=body,
                                         method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                error = json.load(exc).get("detail", "Request failed")
            except (ValueError, AttributeError):
                error = "HTTP " + str(exc.code)
            raise RuntimeError(str(error)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise RuntimeError("Server unavailable: " + str(exc)) from exc


class Chat:
    def __init__(self, application, buddy):
        self.app = application
        self.buddy_id = buddy["id"]
        self.window = tk.Toplevel(application)
        self.window.title("Beacon IM · " + buddy["display_name"])
        self.window.geometry("490x560")
        self.seen = set()
        self.last_typed = 0
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.title = ttk.Label(self.window, text=buddy["display_name"],
                               font=("Segoe UI", 15, "bold"))
        self.title.pack(anchor="w", padx=14, pady=9)
        self.history = tk.Text(self.window, state="disabled", wrap="word", padx=14, pady=12)
        self.history.pack(fill="both", expand=True, padx=8)
        self.typing = ttk.Label(self.window, text="")
        self.typing.pack(anchor="w", padx=15)
        bar = ttk.Frame(self.window, padding=8)
        bar.pack(fill="x")
        self.entry = ttk.Entry(bar)
        self.entry.pack(side="left", expand=True, fill="x")
        self.entry.bind("<Return>", lambda _: self.send())
        self.entry.bind("<KeyRelease>", self.on_type)
        ttk.Button(bar, text="Send", command=self.send).pack(side="left", padx=5)

    def close(self):
        self.app.chats.pop(self.buddy_id, None)
        self.window.destroy()

    def on_type(self, _event):
        now = time.monotonic()
        if now - self.last_typed > 1.8:
            self.last_typed = now
            self.app.background(
                lambda: self.app.api.call("/typing/" + str(self.buddy_id), "POST", {"active": True}),
                lambda *_: None,
            )

    def send(self):
        body = self.entry.get().strip()
        if not body:
            return
        self.entry.delete(0, "end")
        def complete(_result, error):
            if error:
                messagebox.showerror("Beacon", error, parent=self.window)
                self.entry.insert(0, body)
            else:
                self.app.refresh()
        self.app.background(
            lambda: self.app.api.call("/messages", "POST",
                                      {"recipient_id": self.buddy_id, "body": body}), complete)

    def receive(self, messages, typing):
        self.history.configure(state="normal")
        for message in messages:
            if message["id"] in self.seen:
                continue
            self.seen.add(message["id"])
            name = "You" if message["sender_id"] == self.app.me["id"] else self.title.cget("text")
            stamp = datetime.fromtimestamp(message["created_at"]).strftime("%H:%M")
            self.history.insert("end", name + " · " + stamp + "\n" + message["body"] + "\n\n")
        self.history.configure(state="disabled")
        self.history.see("end")
        self.typing.configure(text=self.title.cget("text") + " is typing…" if typing else "")


class Beacon(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Beacon · Buddy List")
        self.geometry("345x660")
        self.minsize(285, 400)
        self.api = API()
        self.jobs = queue.Queue()
        self.generation = 0
        self.running = True
        self.me = None
        self.buddies = []
        self.old_presence = None
        self.chats = {}
        self.status = "available"
        self.polling = False
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.login_view()
        self.after(100, self.drain)

    def background(self, work, completed):
        generation = self.generation
        def job():
            try:
                self.jobs.put((generation, completed, work(), None))
            except Exception as exc:
                self.jobs.put((generation, completed, None, str(exc)))
        threading.Thread(target=job, daemon=True).start()

    def drain(self):
        while True:
            try:
                generation, fn, result, error = self.jobs.get_nowait()
            except queue.Empty:
                break
            if generation == self.generation:
                fn(result, error)
        if self.running:
            self.after(100, self.drain)

    def clear(self):
        for widget in self.winfo_children():
            widget.destroy()

    def login_view(self):
        self.generation += 1
        self.clear()
        root = ttk.Frame(self, padding=25)
        root.pack(expand=True, fill="x")
        ttk.Label(root, text="◉ BEACON", font=("Segoe UI", 24, "bold")).pack(pady=16)
        self.inputs = []
        fields = [("Server", "http://127.0.0.1:8765", False),
                  ("Username", "", False),
                  ("Password", "", True),
                  ("Device name", platform.node()[:80] or "Desktop", False)]
        for name, default, secret in fields:
            ttk.Label(root, text=name).pack(anchor="w")
            field = ttk.Entry(root, show="*" if secret else "")
            field.insert(0, default)
            field.pack(fill="x", pady=(2, 10))
            self.inputs.append(field)
        self.login_button = ttk.Button(root, text="Sign in", command=self.login)
        self.login_button.pack(fill="x", pady=8)
        self.error_label = ttk.Label(root, text="")
        self.error_label.pack()

    def login(self):
        server, username, password, device = [f.get().strip() for f in self.inputs]
        parts = urllib.parse.urlsplit(server)
        if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/") or parts.username or parts.password or parts.query or parts.fragment:
            self.error_label.configure(text="Enter a valid HTTP(S) server URL")
            return
        self.api.base = server.rstrip("/")
        self.login_button.configure(state="disabled")
        self.error_label.configure(text="Signing in…")
        def work():
            result = self.api.call("/login", "POST",
                                   {"username": username, "password": password, "device_name": device})
            self.api.token = result["token"]
            return result["user"]
        def complete(result, error):
            if error:
                self.login_button.configure(state="normal")
                self.error_label.configure(text=error)
            else:
                self.me = result
                self.roster_view()
        self.background(work, complete)

    def roster_view(self):
        self.generation += 1
        self.clear()
        top = ttk.Frame(self, padding=12)
        top.pack(fill="x")
        ttk.Label(top, text="◉ Beacon", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(top, text=self.me["display_name"] + " · your buddy list").pack(anchor="w")
        row = ttk.Frame(self, padding=(10, 0))
        row.pack(fill="x")
        self.status_field = ttk.Combobox(row, values=["available", "away", "busy"], state="readonly", width=12)
        self.status_field.set("available")
        self.status_field.pack(side="left")
        self.status_field.bind("<<ComboboxSelected>>", self.status_change)
        ttk.Button(row, text="+ Buddy", command=self.add_buddy).pack(side="right")
        self.list = tk.Listbox(self, font=("Segoe UI", 11), exportselection=False)
        self.list.pack(fill="both", expand=True, padx=10, pady=10)
        self.list.bind("<Double-Button-1>", self.open_selected)
        self.list.bind("<Return>", self.open_selected)
        footer = ttk.Frame(self, padding=10)
        footer.pack(fill="x")
        ttk.Button(footer, text="IM", command=self.open_selected).pack(side="left")
        ttk.Button(footer, text="Sign out", command=self.logout).pack(side="right")
        self.connection = ttk.Label(self, text="Connecting…", padding=10)
        self.connection.pack(anchor="w")
        self.refresh()

    def status_change(self, _event):
        self.status = self.status_field.get()
        self.background(lambda: self.api.call("/presence", "POST", {"status": self.status}),
                        lambda *_: None)

    def toast(self, text):
        tip = tk.Toplevel(self)
        tip.title("Beacon")
        tip.geometry("320x80")
        tip.transient(self)
        ttk.Label(tip, text=text, padding=14, wraplength=290).pack(fill="both", expand=True)
        tip.after(4500, lambda: tip.destroy() if tip.winfo_exists() else None)

    def refresh(self):
        if not self.api.token or self.polling:
            return
        self.polling = True
        open_ids = list(self.chats)
        def work():
            self.api.call("/presence", "POST", {"status": self.status})
            roster = self.api.call("/buddies")
            windows = {}
            for peer in open_ids:
                windows[peer] = (self.api.call("/messages/" + str(peer)),
                                 self.api.call("/typing/" + str(peer))["active"])
            return roster, windows
        def done(result, error):
            self.polling = False
            if error:
                self.connection.configure(text=str(error)[:90])
            else:
                self.connection.configure(text="● Connected")
                people, windows = result
                new = {p["id"]: p["presence"] for p in people}
                if self.old_presence:
                    for p in people:
                        if self.old_presence.get(p["id"]) == "offline" and p["presence"] != "offline":
                            self.toast(p["display_name"] + " signed on")
                previous_unread = {p["id"]: p["unread_count"] for p in self.buddies}
                for p in people:
                    if p["unread_count"] > previous_unread.get(p["id"], 0):
                        self.toast("New message from " + p["display_name"])
                self.old_presence = new
                self.buddies = people
                selected = self.list.curselection()
                chosen = self.buddies[selected[0]]["id"] if selected and selected[0] < len(self.buddies) else None
                self.list.delete(0, "end")
                for p in self.buddies:
                    state = "●" if p["presence"] != "offline" else "○"
                    label = state + " " + p["display_name"] + (" (" + str(p["unread_count"]) + ")" if p["unread_count"] else "")
                    self.list.insert("end", label)
                    if p["id"] == chosen:
                        self.list.selection_set("end")
                for peer, (msgs, typing) in windows.items():
                    if peer not in self.chats:
                        continue
                    self.chats[peer].receive(msgs, typing)
                    incoming = [m for m in msgs if m["sender_id"] == peer]
                    if incoming:
                        self.background(
                            lambda p=peer, n=incoming[-1]["id"]: self.api.call(
                                "/conversations/" + str(p) + "/read", "POST", {"through_id": n}
                            ), lambda *_: None)
            if self.api.token:
                self.after(3000, self.refresh)
        self.background(work, done)

    def open_selected(self, _event=None):
        selected = self.list.curselection()
        if not selected:
            return
        buddy = self.buddies[selected[0]]
        if buddy["id"] in self.chats:
            self.chats[buddy["id"]].window.lift()
            self.chats[buddy["id"]].entry.focus_set()
            return
        chat = Chat(self, buddy)
        self.chats[buddy["id"]] = chat
        chat.entry.focus_set()
        self.refresh()

    def add_buddy(self):
        def work():
            return self.api.call("/directory")
        def complete(people, error):
            if error:
                self.toast(error)
                return
            names = {p["username"].lower(): p["id"] for p in people}
            name = simpledialog.askstring("Beacon", "Username to add:", parent=self)
            if not name:
                return
            buddy = names.get(name.lower())
            if not buddy:
                messagebox.showerror("Beacon", "No matching user", parent=self)
                return
            self.background(lambda: self.api.call("/buddies/" + str(buddy), "POST"),
                            lambda _result, err: self.toast(err or "Buddy added"))
        self.background(work, complete)

    def logout(self):
        token, base = self.api.token, self.api.base
        self.api.token = None
        for window in list(self.chats.values()):
            window.close()
        self.chats.clear()
        if token:
            def work():
                api = API()
                api.base, api.token = base, token
                try:
                    api.call("/logout", "POST")
                except Exception:
                    pass
            threading.Thread(target=work, daemon=True).start()
        self.login_view()

    def shutdown(self):
        self.running = False
        self.api.token = None
        self.destroy()


if __name__ == "__main__":
    Beacon().mainloop()
