import os
import sys
import re
import datetime
import tempfile
import pathlib
import string
import fitz
import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")

__version__ = "1.4.0"


def resource_path(relative_path):
    """Gestisce i percorsi delle risorse per PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class NullifyPDF(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURAZIONE FINESTRA ---
        self.title("NullifyPDF - AI Forensic Edition")
        self.geometry("1300x900")
        self.minsize(900, 600)

        try:
            self.wm_class("NullifyPDF", "NullifyPDF")
        except Exception:
            pass

        self.bg_color = "#141526"
        self.panel_color = "#1e1f31"
        self.accent_color = "#1fb2e0"
        self.hover_color = "#178cae"
        self.danger_color = "#e74c3c"
        self.configure(fg_color=self.bg_color)

        self.set_window_icon()

        # --- STATO APPLICAZIONE ---
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.img = None
        self.img_id = None
        self.rect_id = None
        self.offset_x = 0
        self.offset_y = 0
        self.start_xy = None
        self.analyzer = None
        self.active_langs = []

        # --- PERSISTENZA DIZIONARI ---
        self.config_dir = pathlib.Path.home() / ".nullifypdf"
        try:
            self.config_dir.mkdir(exist_ok=True)
        except Exception as e:
            print(f"Errore creazione cartella config: {e}")

        self.blocklist_file = self.config_dir / "blocklist.txt"
        self.allowlist_file = self.config_dir / "allowlist.txt"
        self.blocklist = self.load_list(self.blocklist_file)
        self.allowlist = self.load_list(self.allowlist_file)

        self.build_ui()

        # OS-Level Drag & Drop (Apertura tramite trascinamento sull'eseguibile)
        self.after(200, self.check_sys_args)

    def check_sys_args(self):
        """Verifica se l'app è stata aperta trascinando un file sull'eseguibile"""
        if len(sys.argv) > 1:
            file_path = sys.argv[1]
            if os.path.exists(file_path) and file_path.lower().endswith(".pdf"):
                self.load_path(file_path)

    def load_list(self, filepath):
        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                return {line.strip().lower() for line in f if line.strip()}
        return set()

    def save_list(self, filepath, data_set):
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for item in sorted(data_set):
                    f.write(f"{item}\n")
        except Exception as e:
            self.write_log(f"Errore salvataggio dizionario: {e}")

    def set_window_icon(self):
        icon_path_png = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(icon_path_png):
            try:
                if sys.platform.startswith("win"):
                    ico_path = os.path.join(
                        tempfile.gettempdir(), "NullifyPDF_icon.ico"
                    )
                    img = Image.open(icon_path_png)
                    img.save(ico_path, format="ICO", sizes=[(256, 256)])
                    self.after(200, lambda: self.iconbitmap(ico_path))
                else:
                    img = Image.open(icon_path_png)
                    self.icon_photo = ImageTk.PhotoImage(img)
                    self.after(200, lambda: self.wm_iconphoto(True, self.icon_photo))
            except Exception as e:
                pass

    def apply_child_icon(self, child_window):
        try:
            if sys.platform.startswith("win"):
                ico_path = os.path.join(tempfile.gettempdir(), "NullifyPDF_icon.ico")
                if os.path.exists(ico_path):
                    child_window.after(200, lambda: child_window.iconbitmap(ico_path))
            else:
                if hasattr(self, "icon_photo"):
                    child_window.after(
                        200, lambda: child_window.wm_iconphoto(False, self.icon_photo)
                    )
        except Exception:
            pass

    def build_ui(self):
        # ==========================================
        # 1. SIDEBAR (Sinistra)
        # ==========================================
        self.sidebar = ctk.CTkFrame(
            self, width=240, corner_radius=0, fg_color=self.panel_color
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo / Titolo
        ctk.CTkLabel(
            self.sidebar,
            text="NullifyPDF",
            font=("Roboto", 22, "bold"),
            text_color=self.accent_color,
        ).pack(pady=(25, 5))
        ctk.CTkLabel(
            self.sidebar,
            text="AI Forensic Edition",
            font=("Roboto", 12),
            text_color="#aaa",
        ).pack(pady=(0, 25))

        # Core Actions
        ctk.CTkButton(
            self.sidebar,
            text="Open PDF",
            font=("Roboto", 14, "bold"),
            height=40,
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            command=self.load,
        ).pack(fill="x", padx=20, pady=10)

        # Separator
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333344").pack(
            fill="x", padx=20, pady=15
        )

        # AI Engine Settings
        ctk.CTkLabel(
            self.sidebar, text="AI Language Model:", font=("Roboto", 12, "bold")
        ).pack(anchor="w", padx=25)
        self.lang_selection = ctk.StringVar(value="EN")
        lang_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        lang_frame.pack(fill="x", padx=20, pady=5)
        ctk.CTkRadioButton(
            lang_frame, text="EN", variable=self.lang_selection, value="EN", width=50
        ).pack(side="left")
        ctk.CTkRadioButton(
            lang_frame, text="IT", variable=self.lang_selection, value="IT", width=50
        ).pack(side="left")
        ctk.CTkRadioButton(
            lang_frame,
            text="BOTH",
            variable=self.lang_selection,
            value="BOTH",
            width=60,
        ).pack(side="left")

        # Tool Buttons
        ctk.CTkButton(
            self.sidebar,
            text="Dictionary 📖",
            fg_color="#333344",
            command=self.open_dictionary,
        ).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(
            self.sidebar,
            text="Auto Redact (AI)",
            font=("Roboto", 13, "bold"),
            fg_color=self.danger_color,
            hover_color="#c0392b",
            command=self.auto_anon,
        ).pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(
            self.sidebar,
            text="Clear Page 🗑️",
            fg_color="transparent",
            border_width=1,
            border_color="#555",
            text_color="#aaa",
            hover_color="#333",
            command=self.clear_all,
        ).pack(fill="x", padx=20, pady=10)

        # Export
        ctk.CTkButton(
            self.sidebar,
            text="Export Secured PDF",
            font=("Roboto", 13, "bold"),
            fg_color="transparent",
            border_width=2,
            border_color=self.accent_color,
            text_color=self.accent_color,
            hover_color=self.bg_color,
            command=self.save,
        ).pack(fill="x", padx=20, pady=(20, 10))

        # Bottom Area of Sidebar (Nav & Exit)
        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=20)

        # Info Button
        ctk.CTkButton(
            bottom_frame,
            text="ⓘ About",
            fg_color="transparent",
            text_color=self.accent_color,
            font=("Roboto", 14),
            command=self.show_about,
        ).pack(pady=10)

        # Exit Button
        ctk.CTkButton(
            bottom_frame,
            text="Exit Application",
            fg_color="transparent",
            text_color="#888",
            hover_color="#333",
            command=self.destroy,
        ).pack()

        # ==========================================
        # 2. MAIN AREA (Destra)
        # ==========================================
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        # -- Top Bar Navigation --
        nav_bar = ctk.CTkFrame(
            self.main_area, fg_color=self.panel_color, corner_radius=8, height=50
        )
        nav_bar.pack(fill="x", pady=(0, 10))
        nav_bar.pack_propagate(False)

        ctk.CTkLabel(
            nav_bar,
            text="Document Viewer",
            font=("Roboto", 14, "bold"),
            text_color="#fff",
        ).pack(side="left", padx=15)

        # Jump to Page Feature
        nav_ctrls = ctk.CTkFrame(nav_bar, fg_color="transparent")
        nav_ctrls.pack(side="right", padx=10)

        ctk.CTkButton(
            nav_ctrls,
            text="<",
            width=30,
            fg_color=self.bg_color,
            command=lambda: self.move_page(-1),
        ).pack(side="left", padx=5)

        self.page_entry_var = ctk.StringVar(value="0")
        self.page_entry = ctk.CTkEntry(
            nav_ctrls,
            textvariable=self.page_entry_var,
            width=40,
            justify="center",
            font=("Roboto", 12, "bold"),
        )
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind(
            "<Return>", self.jump_to_page
        )  # Salto rapido premendo Invio

        self.tot_pages_lab = ctk.CTkLabel(nav_ctrls, text="/ 0", font=("Roboto", 12))
        self.tot_pages_lab.pack(side="left", padx=(2, 10))

        ctk.CTkButton(
            nav_ctrls,
            text=">",
            width=30,
            fg_color=self.bg_color,
            command=lambda: self.move_page(1),
        ).pack(side="left", padx=5)

        # -- Viewport Canvas --
        view_frame = ctk.CTkFrame(
            self.main_area, fg_color=self.panel_color, corner_radius=8
        )
        view_frame.pack(fill="both", expand=True, pady=(0, 10))

        self.canvas = Canvas(
            view_frame, bg="#0d0e1b", highlightthickness=0, cursor="crosshair"
        )
        self.canvas.pack(side="left", fill="both", expand=True, padx=(5, 0), pady=5)

        self.v_scroll = ctk.CTkScrollbar(
            view_frame, orientation="vertical", command=self.canvas.yview
        )
        self.v_scroll.pack(side="right", fill="y", padx=(0, 5), pady=5)
        self.canvas.configure(yscrollcommand=self.v_scroll.set)

        self.canvas.bind("<Configure>", lambda e: self.center_image())
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.canvas.bind("<Button-4>", self.on_mouse_wheel)
        self.canvas.bind("<Button-5>", self.on_mouse_wheel)

        # -- Footer (Log e Progresso) --
        footer = ctk.CTkFrame(
            self.main_area, fg_color=self.panel_color, corner_radius=8
        )
        footer.pack(fill="x")

        self.prog = ctk.CTkProgressBar(
            footer, fg_color=self.bg_color, progress_color=self.accent_color, height=8
        )
        self.prog.pack(fill="x", padx=15, pady=(15, 5))
        self.prog.set(0)

        self.log = ctk.CTkTextbox(
            footer,
            height=80,
            fg_color=self.bg_color,
            text_color="#a1a1aa",
            font=("Consolas", 12),
        )
        self.log.pack(fill="x", padx=15, pady=(5, 15))

    # --- FUNZIONALITA' COMPONENTI ---

    def jump_to_page(self, event=None):
        if not self.doc:
            return
        try:
            target = int(self.page_entry_var.get()) - 1
            if 0 <= target < len(self.doc):
                self.page_num = target
                self.render()
                self.canvas.yview_moveto(0)
            else:
                self.page_entry_var.set(str(self.page_num + 1))
        except ValueError:
            self.page_entry_var.set(str(self.page_num + 1))
            self.canvas.focus_set()

    def open_dictionary(self):
        dic_win = ctk.CTkToplevel(self)
        dic_win.title("Filter Dictionary")
        dic_win.geometry("500x450")
        dic_win.configure(fg_color=self.panel_color)
        self.apply_child_icon(dic_win)

        ctk.CTkLabel(
            dic_win, text="🔴 BLOCKLIST GLOBALE", font=("Roboto", 13, "bold")
        ).pack(pady=(15, 0))
        block_box = ctk.CTkTextbox(dic_win, height=100, fg_color=self.bg_color)
        block_box.pack(fill="x", padx=20, pady=5)
        block_box.insert("1.0", "\n".join(sorted(self.blocklist)))

        ctk.CTkLabel(
            dic_win, text="🟢 ALLOWLIST GLOBALE", font=("Roboto", 13, "bold")
        ).pack(pady=(15, 0))
        allow_box = ctk.CTkTextbox(dic_win, height=100, fg_color=self.bg_color)
        allow_box.pack(fill="x", padx=20, pady=5)
        allow_box.insert("1.0", "\n".join(sorted(self.allowlist)))

        def save_dicts():
            self.blocklist = {
                w.strip().lower()
                for w in block_box.get("1.0", "end").split("\n")
                if len(w.strip()) > 2
            }
            self.allowlist = {
                w.strip().lower()
                for w in allow_box.get("1.0", "end").split("\n")
                if len(w.strip()) > 2
            }
            self.save_list(self.blocklist_file, self.blocklist)
            self.save_list(self.allowlist_file, self.allowlist)
            self.write_log("Dizionari sincronizzati su disco.")
            dic_win.destroy()

        ctk.CTkButton(
            dic_win, text="Save & Close", fg_color=self.accent_color, command=save_dicts
        ).pack(pady=15)
        dic_win.transient(self)
        dic_win.grab_set()

    def show_about(self):
        about = ctk.CTkToplevel(self)
        about.title("About")
        w, h = 340, 440
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        self.apply_child_icon(about)

        icon_path = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(icon_path):
            try:
                img_file = Image.open(icon_path)
                self.about_logo = ctk.CTkImage(
                    light_image=img_file, dark_image=img_file, size=(100, 100)
                )
                ctk.CTkLabel(about, image=self.about_logo, text="").place(
                    relx=0.5, y=80, anchor="center"
                )
            except Exception:
                pass

        ctk.CTkLabel(
            about, text="NullifyPDF", font=("Roboto", 26, "bold"), text_color="#ffffff"
        ).place(relx=0.5, y=160, anchor="center")
        ctk.CTkLabel(
            about,
            text=f"v{__version__} AI-Pro",
            font=("Roboto", 15),
            text_color=self.accent_color,
        ).place(relx=0.5, y=195, anchor="center")

        info_text = "AI-Powered Forensic Anonymization.\nWith Smart Review System.\n\nDeveloped by: Graziano Mariella\nMIT License"
        ctk.CTkLabel(
            about,
            text=info_text,
            font=("Roboto", 13),
            text_color="#a1a1aa",
            justify="center",
        ).place(relx=0.5, y=270, anchor="center")
        ctk.CTkButton(
            about,
            text="Close",
            width=120,
            fg_color=self.bg_color,
            command=about.destroy,
        ).place(relx=0.5, y=395, anchor="center")
        about.transient(self)
        about.grab_set()

    def init_ai(self, choice):
        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            models, langs = [], []
            if choice in ["EN", "BOTH"]:
                models.append({"lang_code": "en", "model_name": "en_core_web_md"})
                langs.append("en")
            if choice in ["IT", "BOTH"]:
                models.append({"lang_code": "it", "model_name": "it_core_news_md"})
                langs.append("it")

            self.write_log(f"Inizializzazione AI ({choice})...")
            self.update_idletasks()
            configuration = {"nlp_engine_name": "spacy", "models": models}
            provider = NlpEngineProvider(nlp_configuration=configuration)
            self.analyzer = AnalyzerEngine(
                nlp_engine=provider.create_engine(), supported_languages=langs
            )
            self.active_langs = langs
            self.write_log("Motore AI pronto.")
            return True
        except Exception as e:
            self.write_log(f"Errore AI: {e}")
            return False

    def auto_anon(self):
        if not self.doc:
            return
        choice = self.lang_selection.get()
        if not self.analyzer or sorted(self.active_langs) != sorted(
            ["en", "it"] if choice == "BOTH" else [choice.lower()]
        ):
            if not self.init_ai(choice):
                return

        self.write_log("Scansione intelligente in corso...")
        self.prog.set(0)
        target_entities = [
            "PERSON",
            "LOCATION",
            "EMAIL_ADDRESS",
            "PHONE_NUMBER",
            "IBAN_CODE",
            "CREDIT_CARD",
            "CRYPTO",
        ]

        for i, page in enumerate(self.doc):
            text = page.get_text()

            existing_redacts = [
                a.rect for a in page.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT
            ]

            # 1. Blocklist
            for block_word in self.blocklist:
                for rect in page.search_for(block_word):
                    center = fitz.Point(
                        (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
                    )
                    if not any(e_r.contains(center) for e_r in existing_redacts):
                        page.add_redact_annot(rect, fill=(0, 0, 0))
                        existing_redacts.append(rect)

            # 2. Whitelist geometrica
            protected_rects = []
            for allow_word in self.allowlist:
                protected_rects.extend(page.search_for(allow_word))

            # 3. AI
            found_ai_words = set()
            for lang in self.active_langs:
                results = self.analyzer.analyze(
                    text=text, entities=target_entities, language=lang
                )
                for res in results:
                    word = text[res.start : res.end].strip()
                    if len(word) > 2:
                        found_ai_words.add(word)

            # 4. Filtro incrociato
            for match in found_ai_words:
                clean_match = " ".join(match.strip(string.punctuation).lower().split())
                is_protected = False

                for allowed in self.allowlist:
                    if re.search(
                        r"\b" + re.escape(clean_match) + r"\b", allowed
                    ) or re.search(r"\b" + re.escape(allowed) + r"\b", clean_match):
                        is_protected = True
                        break

                if is_protected:
                    continue

                for ai_rect in page.search_for(match):
                    if any(ai_rect.intersects(p_rect) for p_rect in protected_rects):
                        continue

                    center = fitz.Point(
                        (ai_rect.x0 + ai_rect.x1) / 2, (ai_rect.y0 + ai_rect.y1) / 2
                    )
                    if any(e_r.contains(center) for e_r in existing_redacts):
                        continue

                    page.add_redact_annot(ai_rect, fill=(0, 0, 0))
                    existing_redacts.append(ai_rect)

            self.prog.set((i + 1) / len(self.doc))
            self.update_idletasks()

        self.render()
        self.write_log("Anonimizzazione completata senza sovrapposizioni.")

    def clear_all(self):
        if not self.doc:
            return
        count = 0
        page = self.doc[self.page_num]  # Clear current page only come da label UI
        for annot in page.annots():
            if annot.type[0] == fitz.PDF_ANNOT_REDACT:
                page.delete_annot(annot)
                count += 1
        self.render()
        self.write_log(f"Cancellate {count} censure pianificate dalla pagina corrente.")

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
        self.img = ImageTk.PhotoImage(
            Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        )
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor="nw", image=self.img)
        self.canvas.configure(scrollregion=(0, 0, self.img.width(), self.img.height()))
        self.center_image()

        # Aggiorna label navigatore
        self.page_entry_var.set(str(self.page_num + 1))
        self.tot_pages_lab.configure(text=f"/ {len(self.doc)}")

    def center_image(self):
        if not self.img or not self.img_id:
            return
        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width()
        new_x = max(0, (cw - self.img.width()) // 2)
        self.canvas.coords(self.img_id, new_x, 0)
        self.offset_x = new_x

    def on_mouse_wheel(self, event):
        if not self.doc:
            return
        if event.num == 4 or getattr(event, "delta", 0) > 0:
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5 or getattr(event, "delta", 0) < 0:
            self.canvas.yview_scroll(1, "units")

    def on_mouse_press(self, event):
        if not self.doc:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        pt = fitz.Point(
            (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale
        )

        page = self.doc[self.page_num]
        annots_to_delete = [
            annot
            for annot in page.annots()
            if annot.type[0] == fitz.PDF_ANNOT_REDACT and annot.rect.contains(pt)
        ]

        if annots_to_delete:
            extracted_text = page.get_text("text", clip=annots_to_delete[0].rect)
            for annot in annots_to_delete:
                page.delete_annot(annot)

            cleaned = " ".join(extracted_text.split()).lower()
            if len(cleaned) > 2:
                self.blocklist.discard(cleaned)
                self.allowlist.add(cleaned)
                self.save_list(self.blocklist_file, self.blocklist)
                self.save_list(self.allowlist_file, self.allowlist)
                self.write_log(
                    f"Consentito: '{cleaned}' (Spostato in Allowlist e pulito)"
                )
            else:
                self.write_log("Censura rimossa manualmente.")

            self.start_xy = None
            self.render()
            return

        self.start_xy = (cx, cy)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            cx, cy, cx, cy, outline=self.danger_color, width=2
        )

    def on_mouse_drag(self, event):
        if not self.start_xy:
            return
        self.canvas.coords(
            self.rect_id,
            self.start_xy[0],
            self.start_xy[1],
            self.canvas.canvasx(event.x),
            self.canvas.canvasy(event.y),
        )

    def on_mouse_release(self, event):
        if not self.doc or not self.start_xy:
            return
        ex, ey = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        x0, x1 = sorted(
            [
                max(0, min(self.start_xy[0] - self.offset_x, self.img.width())),
                max(0, min(ex - self.offset_x, self.img.width())),
            ]
        )
        y0, y1 = sorted(
            [
                max(0, min(self.start_xy[1] - self.offset_y, self.img.height())),
                max(0, min(ey - self.offset_y, self.img.height())),
            ]
        )

        if (x1 - x0) > 3 and (y1 - y0) > 3:
            rect = fitz.Rect(
                x0 / self.scale, y0 / self.scale, x1 / self.scale, y1 / self.scale
            )
            extracted = self.doc[self.page_num].get_text("text", clip=rect)
            self.doc[self.page_num].add_redact_annot(rect, fill=(0, 0, 0))

            cleaned = " ".join(extracted.split()).lower()
            if len(cleaned) > 2:
                self.allowlist.discard(cleaned)
                self.blocklist.add(cleaned)
                self.save_list(self.blocklist_file, self.blocklist)
                self.save_list(self.allowlist_file, self.allowlist)
                self.write_log(f"Censurato: '{cleaned}' (Spostato in Blocklist)")
            else:
                self.write_log("Area oscurata manualmente.")
            self.render()

        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.start_xy = None

    def save(self):
        if not self.doc:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_secured.pdf",
        )
        if fp:
            try:
                for page in self.doc:
                    redact_rects = [
                        a.rect
                        for a in page.annots()
                        if a.type[0] == fitz.PDF_ANNOT_REDACT
                    ]
                    for link in page.get_links():
                        if any(
                            fitz.Rect(link["from"]).intersects(r) for r in redact_rects
                        ):
                            page.delete_link(link)
                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
                    )

                self.doc.set_metadata({})
                self.doc.save(fp, garbage=4, deflate=True, clean=True)
                self.write_log(f"Salvato: {os.path.basename(fp)}")
                self.doc = fitz.open(fp)
                self.render()
            except Exception as e:
                self.write_log(f"Errore export: {e}")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.load_path(path)

    def load_path(self, path):
        try:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.render()
            self.write_log(f"Documento caricato: {os.path.basename(path)}")
        except Exception as e:
            self.write_log(f"Errore caricamento PDF: {e}")

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()
            self.canvas.yview_moveto(0)

    def write_log(self, msg):
        self.log.insert(
            "end", f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        )
        self.log.see("end")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
