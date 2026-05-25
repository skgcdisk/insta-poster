import os
import threading
from datetime import datetime, timedelta

import customtkinter as ctk
import tkinterdnd2
from tkinterdnd2 import DND_FILES
from PIL import Image, ImageOps

from config_manager import ConfigManager
from image_processor import ImageProcessor
from gemini_client import GeminiClient
from queue_manager import QueueManager
from poster import get_poster
from poster.base import PosterBase


class App(ctk.CTk):
    """
    メインアプリケーションウィンドウ。

    CustomTkinter（ダークUI）をベースにしつつ、tkdnd Tcl パッケージを
    手動でロードしてドラッグ&ドロップを有効化する。
    tkinterdnd2 は import 時に tkinter.BaseWidget へ DnD メソッドを注入するため、
    多重継承は不要で `self.tk.call('package', 'require', 'tkdnd')` だけで動作する。
    """

    WINDOW_TITLE     = "insta-poster"
    WINDOW_SIZE      = "880x780"
    # スケジュール済みジョブの状態変化を確認するポーリング間隔（ミリ秒）
    POLL_INTERVAL_MS = 30_000

    # キューアイテムのステータスに対応する（表示ラベル, 背景色, 文字色）
    STATUS_BADGE = {
        "pending":    ("待機中",        "#2a2a3a", "#778899"),
        "processing": ("処理中...",     "#1a2a3a", "#4488cc"),
        "ready":      ("処理済み",      "#1a3a1a", "#44cc44"),
        "ng":         ("🚫 NG",         "#3a1a1a", "#cc4444"),
        "scheduled":  ("📅 予約済み",   "#1a2a4a", "#6688ff"),
        "posted":     ("✅ 投稿済み",   "#1a2a2a", "#44bbcc"),
        "error":      ("❌ エラー",     "#3a1a1a", "#cc4444"),
        "expired":    ("⌛ 日時経過",   "#2a2a1a", "#aaaa44"),  # アプリ停止中に時刻が過ぎた
    }

    def __init__(self):
        super().__init__()
        self.title(self.WINDOW_TITLE)
        self.geometry(self.WINDOW_SIZE)

        # tkinterdnd2 が同梱する tkdnd ライブラリのパスを Tcl の auto_path に追加してからロードする。
        # ctk.CTk は TkinterDnD.Tk を経由しないためこの手順が必要。
        # sys.maxsize で 64bit/32bit を判定して正しいサブフォルダを選ぶ。
        import sys, platform
        _base = os.path.join(os.path.dirname(tkinterdnd2.__file__), 'tkdnd')
        _is64 = sys.maxsize > 2**32
        _sys  = platform.system()
        if _sys == 'Windows':
            _sub = 'win-x64' if _is64 else 'win-x86'
        elif _sys == 'Darwin':
            _sub = 'osx-arm64' if platform.machine() == 'arm64' else 'osx-x64'
        else:
            _sub = 'linux-arm64' if platform.machine() == 'aarch64' else 'linux-x64'
        tkdnd_lib = os.path.join(_base, _sub)
        self.tk.eval(f'lappend auto_path {{{tkdnd_lib}}}')
        self.tk.call('package', 'require', 'tkdnd')

        # コア部品の初期化
        self.config_mgr      = ConfigManager()
        self.queue_mgr       = QueueManager()
        self.image_processor = ImageProcessor()
        self.gemini: GeminiClient | None = None   # Gemini API キー設定後に初期化
        self.poster: PosterBase | None  = None   # 各種 API キー設定後に初期化

        # 各ジョブの投稿日時を個別管理する StringVar 辞書。
        # _refresh_queue_list でウィジェットを再生成しても値を保持するために使う。
        self._date_vars: dict[str, ctk.StringVar] = {}

        self._init_clients()
        self._build_ui()
        self._refresh_queue_list()

        # スケジュール済みジョブの投稿完了を定期的に確認するポーリングを開始する
        self._start_polling()

        # ウィンドウを閉じるときにスケジューラーを安全に停止する
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ──────────────────────────────────────────
    # 初期化
    # ──────────────────────────────────────────

    def _init_clients(self):
        """APIキーが設定済みであれば GeminiClient と Poster を初期化する。"""
        api_key = self.config_mgr.get("gemini_api_key")
        if api_key:
            self.gemini = GeminiClient(api_key)

        # Instagram 投稿に必要な3つのキーがすべて揃っているか確認
        required = ["instagram_user_id", "instagram_access_token", "imgbb_api_key"]
        if all(self.config_mgr.get(k) for k in required):
            # 既存の Poster が稼働中なら停止してから作り直す
            if self.poster:
                self.poster.shutdown()
            self.poster = get_poster(self.config_mgr, self.queue_mgr, self._on_post_done)

    # ──────────────────────────────────────────
    # UI 構築
    # ──────────────────────────────────────────

    def _build_ui(self):
        """UI レイアウト全体を構築する。"""
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=16, pady=(16, 4))
        self.tabview.add("メイン")
        self.tabview.add("設定")

        self._build_main_tab(self.tabview.tab("メイン"))
        self._build_settings_tab(self.tabview.tab("設定"))

        # ステータスバー（画面下部）
        self.status_label = ctk.CTkLabel(
            self, text="待機中...", font=("", 11), text_color="gray", anchor="w"
        )
        self.status_label.pack(side="bottom", fill="x", padx=16, pady=(0, 8))

    def _build_main_tab(self, parent):
        """メインタブの UI 要素を構築する。"""

        # ── ドロップゾーン ──
        self.drop_zone = ctk.CTkLabel(
            parent,
            text="🖼️   複数の画像をここにドラッグ＆ドロップ\n対応形式：JPG / PNG / WEBP　　複数ファイル同時 OK",
            fg_color="#1e1e2e",
            corner_radius=10,
            height=90,
            font=("", 13),
        )
        self.drop_zone.pack(fill="x", pady=(0, 12))
        # tkinterdnd2 によるドロップイベントを登録
        self.drop_zone.drop_target_register(DND_FILES)  # type: ignore[attr-defined]
        self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)  # type: ignore[attr-defined]

        # ── キュー操作ボタン行 ──
        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", pady=(0, 4))
        ctk.CTkLabel(btn_row, text="投稿キュー", font=("", 12, "bold")).pack(side="left")
        ctk.CTkButton(
            btn_row, text="🗑 完了・NG を削除", width=130,
            fg_color="#3a3a5a", hover_color="#4a4a7a",
            command=self._on_clear_done,
        ).pack(side="right")
        ctk.CTkButton(
            btn_row, text="✨ 一括処理", width=130,
            command=self._on_batch_process,
        ).pack(side="right", padx=(0, 8))

        # ── プログレスバー（一括処理中に進捗を表示） ──
        prog_row = ctk.CTkFrame(parent, fg_color="transparent")
        prog_row.pack(fill="x", pady=(0, 4))
        self.progress_bar = ctk.CTkProgressBar(prog_row, height=10)
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.progress_label = ctk.CTkLabel(
            prog_row, text="", font=("", 10), text_color="gray", width=60, anchor="e"
        )
        self.progress_label.pack(side="left")

        # ── キュー一覧（スクロール可能） ──
        self.queue_frame = ctk.CTkScrollableFrame(parent, height=300)
        self.queue_frame.pack(fill="both", expand=True)

        # ── スケジュール設定バー ──
        sched = ctk.CTkFrame(parent, fg_color="#1e1e2e", corner_radius=10)
        sched.pack(fill="x", pady=(12, 0))

        # 1行目：日時入力 ＋ ボタン類
        sched_row = ctk.CTkFrame(sched, fg_color="transparent")
        sched_row.pack(fill="x", padx=14, pady=(10, 4))

        ctk.CTkLabel(sched_row, text="開始日時", font=("", 12)).pack(side="left", padx=(0, 4))
        self.start_datetime_entry = ctk.CTkEntry(
            sched_row, width=155, placeholder_text="例: 2026/05/10 10:00"
        )
        self.start_datetime_entry.pack(side="left", padx=4)

        ctk.CTkButton(
            sched_row, text="⏹ 停止", width=80,
            fg_color="#553333", hover_color="#774444", text_color="#ffaaaa",
            command=self._on_stop_schedule,
        ).pack(side="right", padx=(4, 0))
        ctk.CTkButton(
            sched_row, text="📅 一日ごと投稿予約", width=160,
            command=self._on_batch_schedule,
        ).pack(side="right", padx=(8, 4))

        # 2行目：注意書き（⑤ Phase1 の制約をユーザーに明示）
        ctk.CTkLabel(
            sched,
            text="※ 本バージョンではアプリ起動中のみ自動投稿が実行されます。"
                 "　個別予約は各カードの「📅 予約」ボタンから設定できます。",
            font=("", 10), text_color="#778899",
        ).pack(anchor="w", padx=14, pady=(0, 8))

    def _build_settings_tab(self, parent):
        """設定タブの UI 要素を構築する。"""

        # ── 各 API キー入力欄 ──
        # (config_key, ラベル, プレースホルダー, ヒント, マスク)
        fields = [
            ("gemini_api_key",          "Gemini API キー",             "AIza...",         "Google AI Studio で取得。キャプション生成・安全チェックに使用します。",  True),
            ("instagram_user_id",       "Instagram ユーザーID",        "17841xxxxxxxxx",  "Instagramビジネスアカウントの数字ID。",                                 False),
            ("instagram_access_token",  "Instagram アクセストークン",  "EAAxxxxxxxx...",  "Facebook Graph API で取得できます。",                                   True),
            ("imgbb_api_key",           "imgbb API キー",              "xxxxxxxx",        "imgbb.com の無料APIキー（投稿時に画像を一時公開するために使用）。",      True),
        ]

        self.entries: dict[str, ctk.CTkEntry] = {}
        scroll = ctk.CTkScrollableFrame(parent)
        scroll.pack(fill="both", expand=True)

        for key, label, placeholder, hint, masked in fields:
            self._add_field(scroll, key, label, placeholder, hint, masked)

        # ── キャプション生成プロンプト編集 ──
        prompt_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        prompt_frame.pack(fill="x", pady=(16, 0))
        ctk.CTkLabel(
            prompt_frame,
            text="キャプション生成の指示文",
            font=("", 12, "bold"),
        ).pack(anchor="w")
        ctk.CTkLabel(
            prompt_frame,
            text="AI にキャプションをどう書いてほしいかを日本語で指示します。\n"
                 "安全チェックの設定はここでは変更できません（内部で固定されています）。\n"
                 "空欄のままにするとデフォルトの指示が使われます。",
            font=("", 10), text_color="gray",
        ).pack(anchor="w", pady=(2, 4))

        # 書き方の例
        example_text = (
            "【書き方の例】\n"
            "この画像に合うInstagramキャプションを日本語で書いてください。\n"
            "・カジュアルで親しみやすいトーンにする\n"
            "・絵文字を3〜5個使う\n"
            "・ハッシュタグを5個つける（日本語と英語を混ぜる）\n"
            "・最後に「いいねやフォローよろしくお願いします！」を入れる"
        )
        ctk.CTkLabel(
            prompt_frame, text=example_text,
            font=("", 10), text_color="#556677",
            justify="left", anchor="w",
            fg_color="#1a1a2a", corner_radius=6,
        ).pack(fill="x", pady=(0, 6), ipady=6, ipadx=8)

        self.prompt_textbox = ctk.CTkTextbox(prompt_frame, height=140, width=480, font=("", 11))
        self.prompt_textbox.pack(anchor="w")
        saved_prompt = self.config_mgr.get("caption_prompt")
        if saved_prompt:
            self.prompt_textbox.insert("0.0", saved_prompt)

        ctk.CTkButton(
            scroll, text="💾 保存する", width=160, command=self._on_save_config
        ).pack(anchor="w", pady=12)

    def _add_field(self, parent, key, label, placeholder, hint, masked):
        """設定タブの入力フィールドを1行追加するヘルパー。"""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=5)
        ctk.CTkLabel(frame, text=label, font=("", 12)).pack(anchor="w")
        entry = ctk.CTkEntry(
            frame,
            placeholder_text=placeholder,
            show="*" if masked else "",
            width=420,
        )
        entry.insert(0, self.config_mgr.get(key))
        entry.pack(anchor="w", pady=2)
        if hint:
            ctk.CTkLabel(frame, text=hint, font=("", 10), text_color="gray").pack(anchor="w")
        self.entries[key] = entry

    # ──────────────────────────────────────────
    # イベントハンドラ
    # ──────────────────────────────────────────

    def _on_drop(self, event):
        """
        ドロップされたファイルをキューに追加する。
        tkinterdnd2 はスペースを含むパスを {} で囲むため splitlist で分割する。
        """
        paths = self.tk.splitlist(event.data)
        supported_ext = {".jpg", ".jpeg", ".png", ".webp"}
        added = 0
        for path in paths:
            if os.path.splitext(path)[1].lower() in supported_ext:
                self.queue_mgr.add(path)
                added += 1

        if added:
            self._set_status(f"{added} 枚の画像をキューに追加しました")
            self._refresh_queue_list()
        else:
            self._set_status("対応していないファイル形式です（JPG / PNG / WEBP のみ）")

    def _on_batch_process(self):
        """一括処理（安全チェック → 補正 → キャプション生成）を開始する。"""
        if not self.gemini:
            self._set_status("❌ Gemini API キーを設定タブで入力してください")
            return
        pending = [j for j in self.queue_mgr.jobs if j["status"] == "pending"]
        if not pending:
            self._set_status("処理対象の画像がありません（待機中の画像をドロップしてください）")
            return
        threading.Thread(
            target=self._batch_process_worker, args=(pending,), daemon=True
        ).start()

    def _batch_process_worker(self, jobs: list[dict]):
        """
        バックグラウンドスレッドで一括処理を実行するワーカー。
        プログレスバーを更新しながら各画像を順番に処理する。
        UI の更新は after() でメインスレッドに委譲する。
        """
        total = len(jobs)
        custom_prompt = self.config_mgr.get("caption_prompt").strip() or None

        for index, job in enumerate(jobs):
            self.after(0, lambda p=index / total, i=index, t=total: self._update_progress(p, i, t))
            self.queue_mgr.update(job["id"], status="processing")
            self.after(0, self._refresh_queue_list)

            try:
                is_safe, ng_reason, caption = self.gemini.analyze_image(
                    job["original_path"], custom_caption_prompt=custom_prompt
                )
                if not is_safe:
                    self.queue_mgr.update(job["id"], status="ng", ng_reason=ng_reason)
                    continue

                corrected_path = self.image_processor.auto_correct(job["original_path"])
                self.queue_mgr.update(
                    job["id"], corrected_path=corrected_path, caption=caption, status="ready"
                )

            except Exception as e:
                import traceback
                traceback.print_exc()
                self.queue_mgr.update(job["id"], status="error", error_message=str(e))

            self.after(0, self._refresh_queue_list)

        self.after(0, lambda: self._update_progress(1.0, total, total))
        self.after(2000, lambda: self._update_progress(0.0, 0, 0))
        self.after(0, lambda: self._set_status("✅ 一括処理が完了しました"))

    def _update_progress(self, value: float, current: int, total: int):
        """プログレスバーと進捗ラベルを更新する（メインスレッドから呼ぶこと）。"""
        self.progress_bar.set(value)
        self.progress_label.configure(text=f"{current}/{total}" if total > 0 else "")

    def _on_batch_schedule(self):
        """
        開始日時から 1 日おきに、全ての処理済みジョブを一括でスケジュール登録する。
        個別に日時を設定したい場合は各カードの「📅 予約」ボタンを使う。
        """
        if not self.poster:
            self._set_status("❌ Instagram / imgbb の API キーを設定してください")
            return

        start_str = self.start_datetime_entry.get().strip()
        try:
            start_dt = datetime.strptime(start_str, "%Y/%m/%d %H:%M")
        except ValueError:
            self._set_status("❌ 日時の形式が正しくありません（例: 2026/05/10 10:00）")
            return

        ready_jobs = self.queue_mgr.get_ready_jobs()
        if not ready_jobs:
            self._set_status("スケジュール登録できる画像がありません（先に一括処理を実行してください）")
            return

        now = datetime.now()
        scheduled_count = 0
        past_names: list[str] = []

        for i, job in enumerate(ready_jobs):
            scheduled_at = start_dt + timedelta(days=i)

            if scheduled_at < now:
                past_names.append(os.path.basename(job["original_path"]))
                continue

            # StringVar を更新して日時エントリの表示を同期する
            formatted = scheduled_at.strftime("%Y/%m/%d %H:%M")
            if job["id"] not in self._date_vars:
                self._date_vars[job["id"]] = ctk.StringVar()
            self._date_vars[job["id"]].set(formatted)

            scheduled_iso = scheduled_at.isoformat()
            self.queue_mgr.update(job["id"], scheduled_at=scheduled_iso)
            self.poster.submit({**job, "scheduled_at": scheduled_iso})
            scheduled_count += 1

        self._refresh_queue_list()

        if past_names:
            names_str = "、".join(past_names)
            self._set_status(f"⚠️ 過去の日時です。修正してください → {names_str}")
        else:
            self._set_status(f"✅ {scheduled_count} 件を一日ごとにスケジュール登録しました")

    def _on_stop_schedule(self):
        """スケジュール済みのジョブをすべてキャンセルして ready に戻す。"""
        if not self.poster:
            return
        scheduled = [j for j in self.queue_mgr.jobs if j["status"] == "scheduled"]
        for job in scheduled:
            self.poster.cancel(job["id"])
        self._refresh_queue_list()
        self._set_status(f"{len(scheduled)} 件のスケジュールを停止しました")

    def _on_clear_done(self):
        """投稿済み・NG・エラー・日時経過のジョブをキューから削除する。"""
        removable = [
            j for j in self.queue_mgr.jobs
            if j["status"] in ("posted", "ng", "error", "expired")
        ]
        for job in removable:
            self._date_vars.pop(job["id"], None)
            self._delete_corrected_file(job)
            self.queue_mgr.remove(job["id"])
        self._refresh_queue_list()

    def _on_save_config(self):
        """設定タブの内容を保存し、クライアントを再初期化する。"""
        for key, entry in self.entries.items():
            self.config_mgr.set(key, entry.get().strip())
prompt = self.prompt_textbox.get("0.0", "end").strip()
        self.config_mgr.set("caption_prompt", prompt)
        self.config_mgr.save()
        self._init_clients()
        self._set_status("✅ 設定を保存しました")

    def _on_post_done(self, job_id: str):
        """投稿完了時コールバック。after() で UI 更新をメインスレッドに委譲する。"""
        self.after(0, self._refresh_queue_list)
        job = self.queue_mgr.get(job_id)
        if job:
            if job["status"] == "posted":
                self.after(0, lambda: self._set_status("✅ 投稿が完了しました"))
            else:
                msg = job.get("error_message", "不明なエラー")
                self.after(0, lambda: self._set_status(f"❌ 投稿エラー: {msg}"))

    def _on_close(self):
        """アプリ終了時にスケジューラーを安全に停止してからウィンドウを閉じる。"""
        if self.poster:
            self.poster.shutdown()
        self.destroy()

    # ──────────────────────────────────────────
    # UI 更新
    # ──────────────────────────────────────────

    def _refresh_queue_list(self):
        """キュー一覧の UI を queue_mgr.jobs の現在状態で再描画する。"""
        for widget in self.queue_frame.winfo_children():
            widget.destroy()

        if not self.queue_mgr.jobs:
            ctk.CTkLabel(
                self.queue_frame,
                text="画像をドロップするとここに表示されます",
                text_color="gray",
                font=("", 12),
            ).pack(pady=20)
            return

        for job in self.queue_mgr.jobs:
            self._render_queue_item(job)

    def _render_queue_item(self, job: dict):
        """キュー1件分の行 UI を描画する。"""
        row = ctk.CTkFrame(self.queue_frame, fg_color="#1e1e2e", corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)

        # ── サムネイル ──
        # EXIF の回転情報（縦向き写真など）を exif_transpose で適用してから表示する。
        # これをしないとドラッグ時点で横向きに表示されてしまう。
        img_path = job.get("corrected_path") or job.get("original_path", "")
        try:
            pil_img = Image.open(img_path)
            pil_img = ImageOps.exif_transpose(pil_img)   # ← EXIF 回転を適用
            pil_img.thumbnail((48, 48))
            thumb = ctk.CTkImage(pil_img, size=(48, 48))
            ctk.CTkLabel(row, image=thumb, text="").pack(side="left", padx=10, pady=8)
        except Exception:
            ctk.CTkLabel(row, text="🖼", font=("", 22), width=48).pack(side="left", padx=10, pady=8)

        # ── 中央の情報エリア ──
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=4)

        ctk.CTkLabel(
            info,
            text=os.path.basename(job.get("original_path", "")),
            font=("", 12, "bold"), anchor="w",
        ).pack(fill="x")

        sub_text = job.get("ng_reason") or job.get("error_message") or job.get("caption") or "─"
        ctk.CTkLabel(
            info, text=sub_text[:80],
            font=("", 10), text_color="gray", anchor="w",
        ).pack(fill="x")

        # 投稿日時エントリ＋個別予約ボタン（処理済み・予約済みのジョブに表示）
        if job["status"] in ("ready", "scheduled"):
            date_row = ctk.CTkFrame(info, fg_color="transparent")
            date_row.pack(fill="x", pady=(2, 0))

            job_id = job["id"]
            if job_id not in self._date_vars:
                initial = ""
                if job.get("scheduled_at"):
                    try:
                        initial = datetime.fromisoformat(
                            job["scheduled_at"]
                        ).strftime("%Y/%m/%d %H:%M")
                    except ValueError:
                        pass
                self._date_vars[job_id] = ctk.StringVar(value=initial)

            ctk.CTkEntry(
                date_row,
                textvariable=self._date_vars[job_id],
                placeholder_text="YYYY/MM/DD HH:MM",
                width=130,
                height=22,
                font=("", 10),
            ).pack(side="left", padx=(0, 4))

            # ② 個別予約ボタン
            ctk.CTkButton(
                date_row, text="📅 予約", width=70, height=22,
                font=("", 10),
                fg_color="#1a2a4a", hover_color="#2a3a6a",
                command=lambda jid=job_id: self._schedule_single_job(jid),
            ).pack(side="left")

        # ── 右側：ステータスバッジ ──
        label, bg, fg = self.STATUS_BADGE.get(job["status"], ("?", "#333", "#aaa"))
        ctk.CTkLabel(
            row, text=label,
            fg_color=bg, text_color=fg,
            corner_radius=6, font=("", 11, "bold"), width=90,
        ).pack(side="right", padx=8)

        job_id = job["id"]

        # 削除ボタン
        ctk.CTkButton(
            row, text="🗑", width=34,
            fg_color="#2a2a4a", hover_color="#3a3a6a",
            command=lambda jid=job_id: self._remove_job(jid),
        ).pack(side="right", padx=(4, 0))

        # 今すぐ投稿ボタン（処理済み・スケジュール済み・エラー状態のときのみ表示）
        if job["status"] in ("ready", "scheduled", "error", "expired"):
            ctk.CTkButton(
                row, text="📤 今すぐ投稿", width=110,
                fg_color="#2a4a2a", hover_color="#3a6a3a",
                command=lambda jid=job_id: self._post_now(jid),
            ).pack(side="right", padx=(4, 0))

        # キャプション編集ボタン
        if job["status"] in ("ready", "scheduled", "posted"):
            ctk.CTkButton(
                row, text="✏️", width=34,
                fg_color="#2a3a4a", hover_color="#3a4a6a",
                command=lambda jid=job_id: self._edit_caption(jid),
            ).pack(side="right", padx=(4, 0))

    def _schedule_single_job(self, job_id: str):
        """
        個別の「📅 予約」ボタンから1件だけスケジュール登録する。
        日時エントリの値を読み取って検証し、問題なければ Poster に登録する。
        """
        if not self.poster:
            self._set_status("❌ Instagram / imgbb の API キーを設定してください")
            return

        job = self.queue_mgr.get(job_id)
        if not job:
            return

        date_str = self._date_vars[job_id].get().strip() if job_id in self._date_vars else ""
        if not date_str:
            self._set_status("❌ 投稿日時を入力してください（YYYY/MM/DD HH:MM 形式）")
            return

        try:
            scheduled_at = datetime.strptime(date_str, "%Y/%m/%d %H:%M")
        except ValueError:
            self._set_status("❌ 日時の形式が正しくありません（例: 2026/05/10 10:00）")
            return

        if scheduled_at < datetime.now():
            self._set_status(f"⚠️ 過去の日時です。修正してください: {date_str}")
            return

        # 既にスケジュール済みの場合はいったんキャンセルしてから再登録する
        if job["status"] == "scheduled":
            self.poster.cancel(job_id)

        scheduled_iso = scheduled_at.isoformat()
        self.queue_mgr.update(job_id, scheduled_at=scheduled_iso)
        success = self.poster.submit({**job, "scheduled_at": scheduled_iso})

        self._refresh_queue_list()
        if success:
            self._set_status(
                f"✅ 予約しました: {os.path.basename(job['original_path'])} → "
                f"{scheduled_at.strftime('%Y/%m/%d %H:%M')}"
            )
        else:
            self._set_status("❌ 予約に失敗しました。エラー詳細はターミナルを確認してください")

    def _edit_caption(self, job_id: str):
        """キャプション編集ダイアログを開く（モーダルウィンドウ）。"""
        job = self.queue_mgr.get(job_id)
        if not job:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("キャプションを編集")
        dialog.geometry("520x360")
        dialog.grab_set()
        dialog.focus_set()

        ctk.CTkLabel(
            dialog,
            text=f"📝 {os.path.basename(job['original_path'])}",
            font=("", 12, "bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        textbox = ctk.CTkTextbox(dialog, font=("", 11), height=220)
        textbox.pack(fill="both", expand=True, padx=16, pady=4)
        textbox.insert("0.0", job.get("caption", ""))
        textbox.focus_set()

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=16, pady=(4, 14))

        def _save():
            new_caption = textbox.get("0.0", "end").strip()
            self.queue_mgr.update(job_id, caption=new_caption)
            self._refresh_queue_list()
            self._set_status("✅ キャプションを保存しました")
            dialog.destroy()

        ctk.CTkButton(btn_row, text="💾 保存", width=120, command=_save).pack(side="right")
        ctk.CTkButton(
            btn_row, text="キャンセル", width=100,
            fg_color="#3a3a5a", hover_color="#4a4a7a",
            command=dialog.destroy,
        ).pack(side="right", padx=(0, 8))

    def _post_now(self, job_id: str):
        """「今すぐ投稿」ボタンから即時投稿する。テスト・手動投稿用。"""
        self._set_status("📤 投稿中...")
        threading.Thread(
            target=self._post_now_worker, args=(job_id,), daemon=True
        ).start()

    def _post_now_worker(self, job_id: str):
        """バックグラウンドで即時投稿を実行するワーカー。"""
        from post_job import execute_post
        execute_post(job_id)
        self.after(0, self._refresh_queue_list)
        job = self.queue_mgr.get(job_id)
        if job and job["status"] == "posted":
            self.after(0, lambda: self._set_status("✅ 投稿完了！"))
        else:
            msg = job.get("error_message", "不明なエラー") if job else "不明なエラー"
            self.after(0, lambda: self._set_status(f"❌ 投稿エラー: {msg}"))

    def _remove_job(self, job_id: str):
        """指定ジョブをキャンセルしてキューから削除する。"""
        if self.poster:
            self.poster.cancel(job_id)
        self._date_vars.pop(job_id, None)
        job = self.queue_mgr.get(job_id)
        if job:
            self._delete_corrected_file(job)
        self.queue_mgr.remove(job_id)
        self._refresh_queue_list()

    def _delete_corrected_file(self, job: dict):
        """
        processed/ フォルダ内の補正済み画像ファイルを削除する。
        ジョブをキューから削除するときに合わせて呼び出す。
        ファイルが存在しない場合やエラーは無視する（元画像には触れない）。
        """
        corrected_path = job.get("corrected_path", "")
        if corrected_path and os.path.exists(corrected_path):
            try:
                os.remove(corrected_path)
                print(f"[app] 補正済みファイルを削除: {corrected_path}")
            except Exception as e:
                print(f"[app] 補正済みファイルの削除に失敗: {e}")

    def _set_status(self, message: str):
        """ステータスバーのメッセージを更新する。"""
        self.status_label.configure(text=message)

    # ──────────────────────────────────────────
    # ポーリング（スケジュール済みジョブの状態監視）
    # ──────────────────────────────────────────

    def _start_polling(self):
        """30 秒ごとに _poll_jobs を呼ぶポーリングループを開始する。"""
        self.after(self.POLL_INTERVAL_MS, self._poll_jobs)

    def _poll_jobs(self):
        """
        queue.json をディスクから再読み込みして状態変化を検出する。

        APScheduler がバックグラウンドで投稿を完了すると queue.json の
        status が "posted" や "error" に更新される。ポーリングでその変化を
        検知して UI を自動更新し、ユーザーに通知する。
        """
        old_statuses = {j["id"]: j["status"] for j in self.queue_mgr.jobs}
        self.queue_mgr.jobs = self.queue_mgr._load()

        changed = False
        for job in self.queue_mgr.jobs:
            old = old_statuses.get(job["id"])
            new = job["status"]
            if old != new:
                changed = True
                filename = os.path.basename(job.get("original_path", ""))
                if new == "posted":
                    self._set_status(f"✅ 投稿完了: {filename}")
                elif new == "error":
                    err = job.get("error_message", "不明なエラー")
                    self._set_status(f"❌ 投稿エラー: {filename} — {err}")

        if changed:
            self._refresh_queue_list()

        self.after(self.POLL_INTERVAL_MS, self._poll_jobs)
