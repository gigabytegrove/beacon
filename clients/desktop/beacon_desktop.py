"""Beacon buddy-list desktop client: Windows / Linux, Python 3 Tkinter."""
import base64
import io
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

from win_integration import clear_session, load_session, save_session, system_notice, tray_icon, is_windows

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None


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
        self.loaded_once = False
        self.sound_alerts = True
        self.auto_open_im = True
        self.groups = []
        self.avatar_cache = {}
        self.tray = None
        self.protocol("WM_DELETE_WINDOW", self.close_window)
        self.login_view()
        self.after(100, self.drain)
        self.restore_windows_session()

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
        self.polling = False
        self.old_presence = None
        self.loaded_once = False
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
        self.remember_device = tk.BooleanVar(value=is_windows())
        if is_windows():
            ttk.Checkbutton(root, text="Keep me signed in on this Windows account",
                            variable=self.remember_device).pack(anchor="w", pady=6)

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
                if is_windows() and self.remember_device.get():
                    if not save_session(self.api.base, self.api.token):
                        messagebox.showwarning("Beacon", "Windows could not securely save this device session.")
                else:
                    clear_session()
                self.roster_view()
                self.ensure_tray()
        self.background(work, complete)

    def restore_windows_session(self):
        if not is_windows():
            return
        prior = load_session()
        if not prior:
            return
        self.api.base = prior["server"]
        self.api.token = prior["token"]
        self.error_label.configure(text="Restoring protected Windows session…")
        def finished(result, error):
            if error:
                self.api.token = None
                clear_session()
                self.error_label.configure(text="Please sign in again.")
                return
            self.me = result
            self.roster_view()
            self.ensure_tray()
        self.background(lambda: self.api.call("/me"), finished)

    def ensure_tray(self):
        if not is_windows() or self.tray is not None:
            return
        def queue_gui(callback):
            self.jobs.put((self.generation, lambda *_: callback(), None, None))
        self.tray = tray_icon(
            lambda: queue_gui(self.show_window),
            lambda: queue_gui(self.shutdown)
        )

    def show_window(self):
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def close_window(self):
        if self.tray is not None and self.api.token:
            self.withdraw()
        else:
            self.shutdown()

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
        actions = ttk.Frame(self, padding=(10, 6))
        actions.pack(fill="x")
        ttk.Button(actions, text="+ Group", command=self.add_group).pack(side="left")
        ttk.Button(actions, text="Alerts", command=self.toggle_alerts).pack(side="left", padx=5)
        ttk.Button(actions, text="IM pop-ups", command=self.toggle_popups).pack(side="left")
        self.list = ttk.Treeview(self, show="tree", selectmode="browse")
        self.list.pack(fill="both", expand=True, padx=10, pady=10)
        self.list.bind("<Double-Button-1>", self.open_selected)
        self.list.bind("<Return>", self.open_selected)
        self.list.bind("<Button-3>", self.context_menu)
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

    def toggle_alerts(self):
        self.sound_alerts = not self.sound_alerts
        self.toast("Notification sounds " + ("enabled" if self.sound_alerts else "disabled"))

    def toggle_popups(self):
        self.auto_open_im = not self.auto_open_im
        self.toast("Incoming IM pop-ups " + ("enabled" if self.auto_open_im else "disabled"))

    def group_action(self, path, method="POST", payload=None):
        def completed(_result, error):
            if error:
                messagebox.showerror("Beacon", error, parent=self)
            else:
                self.refresh()
        self.background(lambda: self.api.call(path, method, payload), completed)

    def add_group(self):
        name = simpledialog.askstring("Beacon", "New buddy group name:", parent=self)
        if name and name.strip():
            self.group_action("/groups", "POST", {"name": name.strip()})

    def context_menu(self, event):
        row = self.list.identify_row(event.y)
        if not row:
            return
        self.list.selection_set(row)
        menu = tk.Menu(self, tearoff=0)
        if row.startswith("g:"):
            gid = int(row[2:])
            if gid:
                group = next((g for g in self.groups if g["id"] == gid), None)
                if group is None:
                    return
                def rename():
                    name = simpledialog.askstring("Rename buddy group", "Group name:", initialvalue=group["name"], parent=self)
                    if name and name.strip():
                        self.group_action("/groups/" + str(gid), "PATCH", {"name": name.strip()})
                def remove_group():
                    if messagebox.askyesno("Delete group", "Move buddies to the default group and delete this group?", parent=self):
                        self.group_action("/groups/" + str(gid), "DELETE")
                menu.add_command(label="Rename group", command=rename)
                menu.add_command(label="Delete group", command=remove_group)
        elif row.startswith("p:"):
            buddy_id = int(row[2:])
            buddy = next((p for p in self.buddies if p["id"] == buddy_id), None)
            if buddy is None:
                return
            menu.add_command(label="Open IM", command=self.open_selected)
            def rename():
                name = simpledialog.askstring("Buddy nickname", "Nickname (blank clears):",
                                              initialvalue=buddy.get("nickname") or "", parent=self)
                if name is not None:
                    self.group_action("/buddies/" + str(buddy_id), "PATCH", {"nickname":name})
            menu.add_command(label="Set nickname…", command=rename)
            groups_menu = tk.Menu(menu, tearoff=0)
            for group in [{"id":None,"name":"Buddies"}] + self.groups:
                groups_menu.add_command(label=group["name"], command=lambda gid=group["id"]:
                    self.group_action("/buddies/" + str(buddy_id), "PATCH", {"group_id": gid}))
            menu.add_cascade(label="Move to group", menu=groups_menu)
            menu.add_command(label="Unmute alerts" if buddy.get("muted") else "Mute alerts",
                command=lambda: self.group_action("/buddies/" + str(buddy_id), "PATCH",
                                                  {"muted":not bool(buddy.get("muted"))}))
            menu.add_separator()
            def remove():
                if messagebox.askyesno("Remove buddy", "Remove " + buddy["display_name"] + " from your buddy list?", parent=self):
                    self.group_action("/buddies/" + str(buddy_id), "DELETE")
            menu.add_command(label="Remove buddy", command=remove)
        else:
            return
        menu.tk_popup(event.x_root, event.y_root)
        menu.grab_release()

    def toast(self, text, sound=False):
        if is_windows() and (self.state() == "withdrawn" or not self.focus_displayof()):
            if system_notice("Beacon", text):
                if sound and self.sound_alerts:
                    try:
                        import winsound
                        winsound.MessageBeep()
                    except (ImportError, RuntimeError):
                        pass
                return
        if sound and self.sound_alerts:
            try:
                self.bell()
            except tk.TclError:
                pass
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
            groups = self.api.call("/groups")
            windows = {}
            for peer in open_ids:
                windows[peer] = (self.api.call("/messages/" + str(peer)),
                                 self.api.call("/typing/" + str(peer))["active"])
            return roster, groups, windows
        def done(result, error):
            self.polling = False
            if error:
                self.connection.configure(text=str(error)[:90])
            else:
                self.connection.configure(text="● Connected")
                people, groups, windows = result
                self.groups = groups
                new = {p["id"]: p["presence"] for p in people}
                if self.old_presence:
                    for p in people:
                        if self.old_presence.get(p["id"]) == "offline" and p["presence"] != "offline" and not p.get("muted"):
                            self.toast((p.get("nickname") or p["display_name"]) + " signed on", sound=True)
                previous_unread = {p["id"]: p["unread_count"] for p in self.buddies}
                if self.loaded_once:
                    for p in people:
                        if p["unread_count"] > previous_unread.get(p["id"], 0) and not p.get("muted"):
                            self.toast("New IM from " + (p.get("nickname") or p["display_name"]), sound=True)
                            if self.auto_open_im and p["id"] not in self.chats:
                                self.chats[p["id"]] = Chat(self, p)
                self.loaded_once = True
                self.old_presence = new
                self.buddies = people
                selected = self.list.selection()
                chosen = selected[0] if selected else None
                for item in self.list.get_children():
                    self.list.delete(item)
                self.avatar_cache.clear()
                group_order = [{"id":None,"name":"Buddies"}] + self.groups
                for group in group_order:
                    gid = "g:" + str(group["id"] or 0)
                    people_in_group = sorted(
                        (p for p in self.buddies if p.get("group_id") == group["id"]),
                        key=lambda p: (p["presence"] == "offline", (p.get("nickname") or p["display_name"]).lower())
                    )
                    online = sum(p["presence"] != "offline" for p in people_in_group)
                    self.list.insert("", "end", iid=gid,
                                     text=group["name"] + " (" + str(online) + "/" + str(len(people_in_group)) + ")",
                                     open=True)
                    for p in people_in_group:
                        state = "●" if p["presence"] != "offline" else "○"
                        label = state + " " + (p.get("nickname") or p["display_name"])
                        if p["unread_count"]:
                            label += " (" + str(p["unread_count"]) + ")"
                        if p.get("muted"):
                            label += " [muted]"
                        self.list.insert(gid, "end", iid="p:" + str(p["id"]),
                                         text=label, image=self.avatar_for(p))
                if chosen and self.list.exists(chosen):
                    self.list.selection_set(chosen)
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

    def avatar_for(self, person):
        data = person.get("avatar") or ""
        if not data.startswith("data:image/") or "," not in data:
            return ""
        try:
            mime, payload = data.split(",", 1)
            if Image is not None:
                image = Image.open(io.BytesIO(base64.b64decode(payload)))
                image.thumbnail((32, 32))
                photo = ImageTk.PhotoImage(image)
            elif mime == "data:image/png;base64":
                photo = tk.PhotoImage(data=payload)
                if photo.width() > 40:
                    step = max(1, photo.width() // 32)
                    photo = photo.subsample(step, step)
            else:
                return ""
            self.avatar_cache[person["id"]] = photo
            return photo
        except (ValueError, OSError, tk.TclError):
            return ""

    def open_selected(self, _event=None):
        selected = self.list.selection()
        if not selected or not selected[0].startswith("p:"):
            return
        buddy = next((p for p in self.buddies if p["id"] == int(selected[0][2:])), None)
        if buddy is None:
            return
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
        clear_session()
        token, base = self.api.token, self.api.base
        self.api.token = None
        self.polling = False
        self.loaded_once = False
        self.old_presence = None
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
        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None
        token, base = self.api.token, self.api.base
        self.api.token = None
        clear_session()
        if token:
            def logout_session():
                api = API()
                api.token, api.base = token, base
                try:
                    api.call("/logout", "POST")
                except Exception:
                    pass
            threading.Thread(target=logout_session, daemon=True).start()
        self.destroy()


if __name__ == "__main__":
    Beacon().mainloop()
