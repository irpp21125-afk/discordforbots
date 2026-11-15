"""Десктоп-панель управления Support Bot (Windows).

Подключается к HTTP API на сервере (FadeHost).
Приложение НЕ требует MySQL локально — только доступ к API-серверу.

Запуск:
    python desktop/app.py

Сборка в .exe:
    pyinstaller desktop/app.spec
"""

import json
import os
import sys
import tkinter as tk
import urllib.error
import urllib.request
from tkinter import messagebox, ttk

# ---------- настройки по умолчанию ----------

DEFAULT_SERVER = os.getenv("PANEL_SERVER", "http://localhost:5000")
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

# ---------- HTTP-клиент ----------


class APIClient:
    """Клиент к API бота (HTTP + X-API-Key)."""

    def __init__(self, server_url: str = "", api_key: str = ""):
        self.server = server_url.rstrip("/")
        self.key = api_key

    def _request(self, method: str, path: str, data: dict = None):
        url = f"{self.server}{path}"
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json")
        if self.key:
            req.add_header("X-API-Key", self.key)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                err = json.loads(e.read().decode())
                raise ConnectionError(err.get("error", str(e)))
            except Exception:
                raise ConnectionError(f"HTTP {e.code}: {e.reason}")
        except Exception as e:
            raise ConnectionError(f"Сервер недоступен: {e}")

    def ping(self):
        return self._request("GET", "/api/ping")

    def login(self, login: str, password: str):
        return self._request(
            "POST", "/api/login", {"login": login, "password": password}
        )

    def stats(self):
        return self._request("GET", "/api/stats")

    def tickets(self, status: str = "", limit: int = 50):
        path = f"/api/tickets?limit={limit}"
        if status:
            path += f"&status={status}"
        return self._request("GET", path)

    def ticket_detail(self, tid: int):
        return self._request("GET", f"/api/ticket?id={tid}")

    def ticket_answer(self, tid: int, text: str):
        return self._request(
            "POST", "/api/ticket/answer", {"ticket_id": tid, "text": text}
        )

    def ticket_close(self, tid: int):
        return self._request(
            "POST", "/api/ticket/close", {"ticket_id": tid}
        )

    def users(self, search: str = "", limit: int = 50):
        path = f"/api/users?limit={limit}"
        if search:
            path += f"&search={search}"
        return self._request("GET", path)

    def money(self, uid: int, amount: int, mode: str):
        return self._request(
            "POST", "/api/money",
            {"user_id": uid, "amount": amount, "mode": mode},
        )

    def privilege(self, uid: int, priv: str):
        return self._request(
            "POST", "/api/privilege", {"user_id": uid, "privilege": priv}
        )

    def punishments(self, uid: int = None, limit: int = 50):
        path = f"/api/punishments?limit={limit}"
        if uid:
            path += f"&user_id={uid}"
        return self._request("GET", path)

    def punish(self, uid: int, ptype: str, reason: str, guild_id: int):
        return self._request(
            "POST", "/api/punish",
            {
                "user_id": uid, "type": ptype,
                "reason": reason, "guild_id": guild_id,
            },
        )

    def activity(self, limit: int = 30):
        return self._request("GET", f"/api/activity?limit={limit}")

    def faq(self):
        return self._request("GET", "/api/faq")

    def faq_add(self, question: str, answer: str):
        return self._request(
            "POST", "/api/faq", {"question": question, "answer": answer}
        )

    def faq_delete(self, fid: int):
        return self._request("DELETE", f"/api/faq?id={fid}")

    def settings(self):
        return self._request("GET", "/api/settings")

    def settings_set(self, key: str, value: str):
        return self._request(
            "POST", "/api/settings", {"key": key, "value": value}
        )

    def broadcast(self, text: str):
        return self._request("POST", "/api/broadcast", {"text": text})


# ---------- GUI ----------


class SupportPanel:
    """Главное окно панели."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Support Bot — Панель управления")
        self.root.geometry("1000x650")
        self.client = None

        self._load_config()
        self._build_ui()
        if self.client and self.api_key:
            self.root.after(100, self._auto_login)

    def _load_config(self):
        """Читаем сохранённые настройки сервера."""
        self.server_url = DEFAULT_SERVER
        self.api_key = ""
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.server_url = cfg.get("server", DEFAULT_SERVER)
                self.api_key = cfg.get("api_key", "")
        except Exception:
            pass

    def _save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "server": self.server_url,
                        "api_key": self.api_key,
                    },
                    f,
                )
        except Exception:
            pass

    def _build_ui(self):
        # ---------- верхняя панель: подключение ----------
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Сервер:").pack(side="left")
        self.server_var = tk.StringVar(value=self.server_url)
        ttk.Entry(top, textvariable=self.server_var, width=40).pack(
            side="left", padx=4
        )
        ttk.Label(top, text="API-ключ:").pack(side="left", padx=(12, 0))
        self.key_var = tk.StringVar(value=self.api_key)
        ttk.Entry(top, textvariable=self.key_var, width=28, show="*").pack(
            side="left", padx=4
        )
        ttk.Button(top, text="Подключиться", command=self._connect).pack(
            side="left", padx=8
        )
        self.status_label = ttk.Label(top, text="Не подключено",
                                      foreground="red")
        self.status_label.pack(side="left", padx=8)

        # ---------- вкладки ----------
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)

        self._build_stats_tab()
        self._build_tickets_tab()
        self._build_users_tab()
        self._build_punishments_tab()
        self._build_faq_tab()
        self._build_settings_tab()

        # ---------- статус-бар ----------
        self.sb = ttk.Label(
            self.root, text="Готов", relief="sunken", anchor="w", padding=4
        )
        self.sb.pack(fill="x", side="bottom")

    # ---------- вкладка: статистика ----------

    def _build_stats_tab(self):
        frame = ttk.Frame(self.nb, padding=12)
        self.nb.add(frame, text=" Статистика ")
        self.stats_text = tk.Text(frame, height=20, font=("Segoe UI", 11))
        self.stats_text.pack(fill="both", expand=True)
        ttk.Button(frame, text="Обновить",
                   command=self._refresh_stats).pack(pady=8)

    def _refresh_stats(self):
        if not self._check_client():
            return
        try:
            data = self.client.stats()
            lines = [
                f"Discord-пользователей: {data.get('dc_users', 0)}",
                f"Telegram-пользователей: {data.get('tg_users', 0)}",
                f"Всего обращений: {data.get('tickets', 0)}",
                f"Наказаний: {data.get('punishments', 0)}",
                f"Розыгрышей: {data.get('giveaways', 0)}",
                f"Предложений: {data.get('suggestions', 0)}",
                "",
                "Обращения по статусам:",
            ]
            for k, v in (data.get("tickets_by_status") or {}).items():
                lines.append(f"  {k}: {v}")
            self.stats_text.delete("1.0", "end")
            self.stats_text.insert("1.0", "\n".join(lines))
            self.sb.config(text="Статистика обновлена")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- вкладка: обращения ----------

    def _build_tickets_tab(self):
        frame = ttk.Frame(self.nb, padding=8)
        self.nb.add(frame, text=" Обращения ")
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        ttk.Button(bar, text="Открытые",
                   command=lambda: self._load_tickets("open")).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Отвеченные",
                   command=lambda: self._load_tickets("answered")).pack(
            side="left", padx=2)
        ttk.Button(bar, text="Все",
                   command=lambda: self._load_tickets("")).pack(
            side="left", padx=2)

        cols = ("id", "author", "category", "priority", "status",
                "preview", "created")
        self.tickets_tree = ttk.Treeview(frame, columns=cols,
                                         show="headings", height=10)
        headers = {
            "id": ("№", 50), "author": ("Автор", 110),
            "category": ("Категория", 120), "priority": ("Приоритет", 80),
            "status": ("Статус", 80), "preview": ("Сообщение", 300),
            "created": ("Дата", 120),
        }
        for col, (text, width) in headers.items():
            self.tickets_tree.heading(col, text=text)
            self.tickets_tree.column(col, width=width)
        self.tickets_tree.pack(fill="both", expand=True, pady=6)
        self.tickets_tree.bind("<Double-1>", self._show_ticket)

        # панель ответа
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x")
        ttk.Label(bottom, text="Ответ:").pack(side="left")
        self.answer_var = tk.StringVar()
        ttk.Entry(bottom, textvariable=self.answer_var,
                  width=60).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(bottom, text="Отправить",
                   command=self._send_answer).pack(side="left", padx=2)
        ttk.Button(bottom, text="Закрыть",
                   command=self._close_ticket).pack(side="left", padx=2)

    def _load_tickets(self, status: str):
        if not self._check_client():
            return
        try:
            data = self.client.tickets(status=status)
            for item in self.tickets_tree.get_children():
                self.tickets_tree.delete(item)
            for t in data.get("tickets", []):
                self.tickets_tree.insert(
                    "", "end", values=(
                        t["id"], f"{t['author_type']}:{t['author_ref']}",
                        t["category"], t["priority"], t["status"],
                        t["preview"], t["created_at"],
                    ),
                )
            self.sb.config(text=f"Загружено обращений: "
                                f"{len(data.get('tickets', []))}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _show_ticket(self, event):
        sel = self.tickets_tree.selection()
        if not sel:
            return
        tid = int(self.tickets_tree.item(sel[0])["values"][0])
        try:
            data = self.client.ticket_detail(tid)
            t = data["ticket"]
            text = (f"Обращение #{t['id']}\n"
                    f"Автор: {t['author_type']}:{t['author_ref']}\n"
                    f"Категория: {t['category']} | "
                    f"Приоритет: {t['priority']} | "
                    f"Статус: {t['status']}\n"
                    f"Создан: {t['created_at']}\n\n"
                    f"{t['message']}\n\n--- Ответы ---\n")
            for r in data.get("replies", []):
                who = "👨‍💼" if r["is_admin"] else "👤"
                text += f"{who} {r['author_name']} ({r['created_at']}):\n" \
                        f"{r['text']}\n\n"
            win = tk.Toplevel(self.root)
            win.title(f"Обращение #{tid}")
            win.geometry("600x500")
            txt = tk.Text(win, wrap="word", font=("Segoe UI", 10))
            txt.pack(fill="both", expand=True)
            txt.insert("1.0", text)
            txt.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _send_answer(self):
        sel = self.tickets_tree.selection()
        if not sel:
            messagebox.showwarning("Нет выбора", "Выберите обращение")
            return
        tid = int(self.tickets_tree.item(sel[0])["values"][0])
        text = self.answer_var.get().strip()
        if not text:
            return
        try:
            self.client.ticket_answer(tid, text)
            self.answer_var.set("")
            self.sb.config(text=f"Ответ отправлен в #{tid}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _close_ticket(self):
        sel = self.tickets_tree.selection()
        if not sel:
            return
        tid = int(self.tickets_tree.item(sel[0])["values"][0])
        if not messagebox.askyesno("Подтверждение",
                                   f"Закрыть обращение #{tid}?"):
            return
        try:
            self.client.ticket_close(tid)
            self.sb.config(text=f"Обращение #{tid} закрыто")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- вкладка: пользователи ----------

    def _build_users_tab(self):
        frame = ttk.Frame(self.nb, padding=8)
        self.nb.add(frame, text=" Пользователи ")
        bar = ttk.Frame(frame)
        bar.pack(fill="x")
        ttk.Label(bar, text="Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search_var,
                  width=24).pack(side="left", padx=4)
        ttk.Button(bar, text="Найти",
                   command=self._load_users).pack(side="left", padx=2)

        cols = ("id", "name", "points", "level", "priv", "msgs")
        self.users_tree = ttk.Treeview(frame, columns=cols,
                                       show="headings", height=12)
        headers = {
            "id": ("ID", 110), "name": ("Имя", 150),
            "points": ("XP", 80), "level": ("Уровень", 70),
            "priv": ("Привилегия", 110), "msgs": ("Сообщений", 90),
        }
        for col, (text, width) in headers.items():
            self.users_tree.heading(col, text=text)
            self.users_tree.column(col, width=width)
        self.users_tree.pack(fill="both", expand=True, pady=6)

        ops = ttk.LabelFrame(frame, text="Действия", padding=6)
        ops.pack(fill="x")
        ttk.Label(ops, text="XP:").pack(side="left")
        self.xp_var = tk.StringVar()
        ttk.Entry(ops, textvariable=self.xp_var, width=10).pack(
            side="left", padx=4)
        ttk.Button(ops, text="Выдать",
                   command=lambda: self._set_money("add")).pack(
            side="left", padx=2)
        ttk.Button(ops, text="Снять",
                   command=lambda: self._set_money("remove")).pack(
            side="left", padx=2)
        ttk.Button(ops, text="Установить",
                   command=lambda: self._set_money("set")).pack(
            side="left", padx=2)

        ttk.Label(ops, text="Привилегия:").pack(side="left", padx=(16, 0))
        self.priv_var = tk.StringVar(value="none")
        ttk.Combobox(ops, textvariable=self.priv_var, width=12,
                     values=["none", "starvision", "viaglobal",
                             "gectoring"], state="readonly").pack(
            side="left", padx=4)
        ttk.Button(ops, text="Применить",
                   command=self._set_privilege).pack(side="left", padx=2)

    def _load_users(self):
        if not self._check_client():
            return
        try:
            data = self.client.users(search=self.search_var.get())
            for item in self.users_tree.get_children():
                self.users_tree.delete(item)
            for u in data.get("users", []):
                self.users_tree.insert(
                    "", "end", values=(
                        u["id"], u.get("display_name")
                        or u.get("username") or "—",
                        u["points"], u["level"], u.get("privilege", "none"),
                        u["messages_count"],
                    ),
                )
            self.sb.config(text=f"Найдено: "
                                f"{len(data.get('users', []))}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _selected_user_id(self):
        sel = self.users_tree.selection()
        if not sel:
            messagebox.showwarning("Нет выбора", "Выберите пользователя")
            return None
        return int(self.users_tree.item(sel[0])["values"][0])

    def _set_money(self, mode: str):
        uid = self._selected_user_id()
        if not uid:
            return
        try:
            amount = int(self.xp_var.get())
        except ValueError:
            messagebox.showerror("Ошибка", "XP должно быть числом")
            return
        try:
            self.client.money(uid, amount, mode)
            self.sb.config(text=f"XP обновлены для {uid}")
            self._load_users()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _set_privilege(self):
        uid = self._selected_user_id()
        if not uid:
            return
        try:
            self.client.privilege(uid, self.priv_var.get())
            self.sb.config(text=f"Привилегия для {uid}: "
                                f"{self.priv_var.get()}")
            self._load_users()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- вкладка: наказания ----------

    def _build_punishments_tab(self):
        frame = ttk.Frame(self.nb, padding=8)
        self.nb.add(frame, text=" Наказания ")
        cols = ("id", "guild", "user", "type", "reason", "active", "date")
        self.pun_tree = ttk.Treeview(frame, columns=cols,
                                     show="headings", height=12)
        headers = {
            "id": ("№", 50), "guild": ("Сервер", 110),
            "user": ("Пользователь", 110), "type": ("Тип", 70),
            "reason": ("Причина", 250), "active": ("Активно", 70),
            "date": ("Дата", 120),
        }
        for col, (text, width) in headers.items():
            self.pun_tree.heading(col, text=text)
            self.pun_tree.column(col, width=width)
        self.pun_tree.pack(fill="both", expand=True)
        ttk.Button(frame, text="Обновить",
                   command=self._load_punishments).pack(pady=6)

    def _load_punishments(self):
        if not self._check_client():
            return
        try:
            data = self.client.punishments()
            for item in self.pun_tree.get_children():
                self.pun_tree.delete(item)
            for p in data.get("punishments", []):
                self.pun_tree.insert(
                    "", "end", values=(
                        p["id"], p["guild_id"], p["user_id"],
                        p["type"], (p["reason"] or "")[:50],
                        "да" if p["active"] else "нет", p["created_at"],
                    ),
                )
            self.sb.config(text=f"Наказаний: "
                                f"{len(data.get('punishments', []))}")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- вкладка: FAQ ----------

    def _build_faq_tab(self):
        frame = ttk.Frame(self.nb, padding=8)
        self.nb.add(frame, text=" FAQ ")
        cols = ("id", "question", "answer")
        self.faq_tree = ttk.Treeview(frame, columns=cols,
                                     show="headings", height=10)
        self.faq_tree.heading("id", text="№")
        self.faq_tree.heading("question", text="Вопрос")
        self.faq_tree.heading("answer", text="Ответ")
        self.faq_tree.column("id", width=50)
        self.faq_tree.column("question", width=300)
        self.faq_tree.column("answer", width=420)
        self.faq_tree.pack(fill="both", expand=True)

        add = ttk.LabelFrame(frame, text="Добавить вопрос", padding=6)
        add.pack(fill="x", pady=6)
        ttk.Label(add, text="Вопрос:").grid(row=0, column=0, sticky="w")
        self.faq_q = tk.StringVar()
        ttk.Entry(add, textvariable=self.faq_q,
                  width=60).grid(row=0, column=1, padx=4, pady=2)
        ttk.Label(add, text="Ответ:").grid(row=1, column=0, sticky="w")
        self.faq_a = tk.StringVar()
        ttk.Entry(add, textvariable=self.faq_a,
                  width=60).grid(row=1, column=1, padx=4, pady=2)
        ttk.Button(add, text="Добавить",
                   command=self._faq_add).grid(row=2, column=1, sticky="e")
        ttk.Button(add, text="Удалить выбранный",
                   command=self._faq_delete).grid(row=2, column=0, sticky="w")
        ttk.Button(frame, text="Обновить",
                   command=self._load_faq).pack()

    def _load_faq(self):
        if not self._check_client():
            return
        try:
            data = self.client.faq()
            for item in self.faq_tree.get_children():
                self.faq_tree.delete(item)
            for f in data.get("faq", []):
                self.faq_tree.insert(
                    "", "end", values=(f["id"], f["question"][:70],
                                       f["answer"][:90]),
                )
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _faq_add(self):
        q, a = self.faq_q.get().strip(), self.faq_a.get().strip()
        if not q or not a:
            return
        try:
            self.client.faq_add(q, a)
            self.faq_q.set("")
            self.faq_a.set("")
            self._load_faq()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _faq_delete(self):
        sel = self.faq_tree.selection()
        if not sel:
            return
        fid = int(self.faq_tree.item(sel[0])["values"][0])
        try:
            self.client.faq_delete(fid)
            self._load_faq()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- вкладка: настройки и рассылка ----------

    def _build_settings_tab(self):
        frame = ttk.Frame(self.nb, padding=8)
        self.nb.add(frame, text=" Настройки ")
        cols = ("key", "value")
        self.set_tree = ttk.Treeview(frame, columns=cols,
                                     show="headings", height=8)
        self.set_tree.heading("key", text="Ключ")
        self.set_tree.heading("value", text="Значение")
        self.set_tree.column("key", width=200)
        self.set_tree.column("value", width=500)
        self.set_tree.pack(fill="both", expand=True)

        row = ttk.Frame(frame)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Ключ:").pack(side="left")
        self.set_key = tk.StringVar()
        ttk.Entry(row, textvariable=self.set_key,
                  width=20).pack(side="left", padx=4)
        ttk.Label(row, text="Значение:").pack(side="left")
        self.set_val = tk.StringVar()
        ttk.Entry(row, textvariable=self.set_val,
                  width=40).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(row, text="Сохранить",
                   command=self._save_setting).pack(side="left", padx=4)
        ttk.Button(frame, text="Обновить список",
                   command=self._load_settings).pack(pady=4)

        bc = ttk.LabelFrame(frame, text="Рассылка в Discord (webhook)",
                            padding=6)
        bc.pack(fill="x", pady=6)
        self.bc_text = tk.StringVar()
        ttk.Entry(bc, textvariable=self.bc_text, width=70).pack(
            side="left", padx=4, fill="x", expand=True)
        ttk.Button(bc, text="Отправить",
                   command=self._broadcast).pack(side="left", padx=4)

    def _load_settings(self):
        if not self._check_client():
            return
        try:
            data = self.client.settings()
            for item in self.set_tree.get_children():
                self.set_tree.delete(item)
            for k, v in (data.get("settings") or {}).items():
                self.set_tree.insert("", "end", values=(k, v))
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _save_setting(self):
        k, v = self.set_key.get().strip(), self.set_val.get()
        if not k:
            return
        try:
            self.client.settings_set(k, v)
            self._load_settings()
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def _broadcast(self):
        text = self.bc_text.get().strip()
        if not text:
            return
        try:
            self.client.broadcast(text)
            self.bc_text.set("")
            self.sb.config(text="Сообщение отправлено в Discord")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    # ---------- подключение ----------

    def _connect(self):
        self.server_url = self.server_var.get().strip()
        self.api_key = self.key_var.get().strip()
        self.client = APIClient(self.server_url, self.api_key)
        try:
            self.client.ping()
            self.status_label.config(text="Подключено", foreground="green")
            self._save_config()
            self.sb.config(text=f"Сервер: {self.server_url}")
            self._refresh_stats()
        except Exception as e:
            self.status_label.config(text="Ошибка", foreground="red")
            messagebox.showerror("Не удалось подключиться", str(e))

    def _auto_login(self):
        """Пробуем подключиться с сохранёнными настройками."""
        self.client = APIClient(self.server_url, self.api_key)
        try:
            self.client.ping()
            self.status_label.config(text="Подключено", foreground="green")
            self._refresh_stats()
        except Exception:
            self.status_label.config(text="Нет связи с сервером",
                                     foreground="red")

    def _check_client(self) -> bool:
        if not self.client:
            messagebox.showwarning("Не подключено",
                                   "Сначала подключитесь к серверу")
            return False
        return True

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    SupportPanel().run()
