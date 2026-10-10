"""Beacon native desktop client for Windows and Linux (Python 3 + Tkinter)."""
import json
import platform
import queue
import threading
import tkinter as tk
import urllib.error
import urllib.parse
import urllib.request
from tkinter import messagebox, ttk
from datetime import datetime

class BeaconError(Exception):
    pass

class Client:
    def __init__(self):
        self.base = ""
        self.token = None

    def request(self, path, method="GET", data=None):
        url = self.base.rstrip("/") + "/api" + path
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        body = None
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            try:
                detail = json.load(exc).get("detail", "Request failed")
            except Exception:
                detail = str(exc)
            raise BeaconError(str(detail)) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise BeaconError("Unable to reach the Beacon server: " + str(exc)) from exc

class BeaconDesktop(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Beacon")
        self.geometry("860x570")
        self.minsize(570, 390)
        self.configure(bg="#152339")
        self.client = Client()
        self.events = queue.Queue()
        self.generation = 0
        self.people = []
        self.active = None
        self.my_id = None
        self.seen = set()
        self.running = True
        self.protocol("WM_DELETE_WINDOW", self.shutdown)
        self.show_login()
        self.after(100, self.drain)

    def clear(self):
        for child in self.winfo_children():
            child.destroy()

    def show_login(self):
        self.generation += 1
        self.clear()
        pane = ttk.Frame(self, padding=32)
        pane.pack(expand=True)
        ttk.Label(pane, text="BEACON", font=("Segoe UI", 24, "bold")).pack(pady=16)
        ttk.Label(pane, text="Server address (http://LAN-IP:8765 or https://host)").pack(anchor="w")
        self.server = ttk.Entry(pane, width=48)
        self.server.insert(0, "http://127.0.0.1:8765")
        self.server.pack(fill="x", pady=(3, 12))
        ttk.Label(pane, text="Username").pack(anchor="w")
        self.username = ttk.Entry(pane)
        self.username.pack(fill="x", pady=(3, 12))
        ttk.Label(pane, text="Password").pack(anchor="w")
        self.password = ttk.Entry(pane, show="*")
        self.password.pack(fill="x", pady=(3, 12))
        ttk.Label(pane, text="Device name").pack(anchor="w")
        self.device = ttk.Entry(pane)
        self.device.insert(0, platform.node()[:80] or "Desktop")
        self.device.pack(fill="x", pady=(3, 12))
        self.login_button = ttk.Button(pane, text="Sign in", command=self.login)
        self.login_button.pack(fill="x")
        self.notice = ttk.Label(pane, text="")
        self.notice.pack(pady=12)
        self.password.bind("<Return>", lambda _: self.login())

    def run_async(self, fn, callback):
        generation = self.generation
        def worker():
            try:
                result = fn()
                self.events.put((generation, callback, result, None))
            except Exception as exc:
                self.events.put((generation, callback, None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def drain(self):
        while True:
            try:
                generation, callback, result, error = self.events.get_nowait()
            except queue.Empty:
                break
            if generation == self.generation:
                callback(result, error)
        if self.running:
            self.after(100, self.drain)

    def login(self):
        base = self.server.get().strip().rstrip("/")
        parsed = urllib.parse.urlsplit(base)
        if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
            self.notice.configure(text="Enter a valid HTTP(S) server address.")
            return
        self.client.base = base
        username = self.username.get()
        password = self.password.get()
        device = self.device.get().strip()
        if not device:
            self.notice.configure(text="Enter a device name.")
            return
        self.login_button.configure(state="disabled")
        self.notice.configure(text="Connecting…")
        def work():
            data = self.client.request("/login", "POST", {"username": username, "password": password, "device_name": device})
            self.client.token = data["token"]
            users = self.client.request("/users")
            return data["user"], users
        def done(result, error):
            self.login_button.configure(state="normal")
            if error:
                self.notice.configure(text=error)
            else:
                self.my_id = result[0]["id"]
                self.people = [p for p in result[1] if p["id"] != self.my_id]
                self.show_chat()
        self.run_async(work, done)

    def show_chat(self):
        self.generation += 1
        self.clear()
        main = ttk.Frame(self, padding=8)
        main.pack(fill="both", expand=True)
        top = ttk.Frame(main)
        top.pack(fill="x")
        ttk.Label(top, text="◉ BEACON", font=("Segoe UI", 17, "bold")).pack(side="left")
        ttk.Button(top, text="Sign out", command=self.logout).pack(side="right")
        self.status = ttk.Label(top, text="Connected")
        self.status.pack(side="right", padx=18)
        body = ttk.Panedwindow(main, orient="horizontal")
        body.pack(fill="both", expand=True, pady=8)
        left = ttk.Frame(body, width=200)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=4)
        ttk.Label(left, text="People").pack(anchor="w")
        self.people_list = tk.Listbox(left, exportselection=False)
        self.people_list.pack(fill="both", expand=True)
        for person in self.people:
            self.people_list.insert(tk.END, person["display_name"])
        self.people_list.bind("<<ListboxSelect>>", self.select)
        self.chat_title = ttk.Label(right, text="Select someone to chat with")
        self.chat_title.pack(anchor="w", pady=6)
        self.history = tk.Text(right, state="disabled", wrap="word", padx=12, pady=12)
        self.history.pack(fill="both", expand=True)
        composer = ttk.Frame(right)
        composer.pack(fill="x", pady=8)
        self.draft = ttk.Entry(composer)
        self.draft.pack(side="left", fill="x", expand=True)
        self.draft.bind("<Return>", lambda _: self.send())
        ttk.Button(composer, text="Send", command=self.send).pack(side="left", padx=5)
        self.poll()

    def select(self, _event=None):
        indexes = self.people_list.curselection()
        if not indexes:
            return
        self.active = self.people[indexes[0]]["id"]
        self.seen = set()
        self.chat_title.configure(text=self.people[indexes[0]]["display_name"])
        self.history.configure(state="normal")
        self.history.delete("1.0", "end")
        self.history.configure(state="disabled")
        self.refresh_history()

    def show_messages(self, messages):
        self.history.configure(state="normal")
        for m in messages:
            if m["id"] in self.seen:
                continue
            self.seen.add(m["id"])
            label = "You" if m["sender_id"] == self.my_id else next(
                (p["display_name"] for p in self.people if p["id"] == m["sender_id"]), "User"
            )
            stamp = datetime.fromtimestamp(m["created_at"]).strftime("%H:%M")
            self.history.insert("end", f"{label} · {stamp}\n{m['body']}\n\n")
        self.history.configure(state="disabled")
        self.history.see("end")

    def refresh_history(self):
        peer_id = self.active
        if peer_id is None:
            return
        def done(result, error):
            if self.active != peer_id:
                return
            if error:
                self.status.configure(text=error[:70])
            else:
                self.status.configure(text="Connected")
                self.show_messages(result)
        self.run_async(lambda: self.client.request("/messages/" + str(peer_id)), done)

    def send(self):
        if self.active is None:
            return
        body = self.draft.get().strip()
        if not body:
            return
        peer_id = self.active
        self.draft.delete(0, "end")
        def done(_result, error):
            if error:
                messagebox.showerror("Beacon", error)
                self.draft.insert(0, body)
            elif self.active == peer_id:
                self.refresh_history()
        self.run_async(lambda: self.client.request("/messages", "POST", {"recipient_id": peer_id, "body": body}), done)

    def poll(self):
        if not self.running or not self.client.token:
            return
        self.refresh_history()
        self.after(3000, self.poll)

    def logout(self):
        self.generation += 1
        token = self.client.token
        if token:
            self.run_async(lambda: self.client.request("/logout", "POST"), lambda *_: None)
        self.client.token = None
        self.active = None
        self.show_login()

    def shutdown(self):
        self.running = False
        self.destroy()

if __name__ == "__main__":
    BeaconDesktop().mainloop()
