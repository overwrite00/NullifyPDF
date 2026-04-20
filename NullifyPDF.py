import os
import sys
import re
import datetime
import tempfile
import fitz
import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")


def resource_path(relative_path):
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

        self.bg_color = "#141526"
        self.panel_color = "#1e1f31"
        self.accent_color = "#1fb2e0"
        self.hover_color = "#178cae"
        self.danger_color = "#e74c3c"
        self.configure(fg_color=self.bg_color)

        # Inizializza l'icona della finestra principale
        self.set_window_icon()

        # --- STATO DELL'APPLICAZIONE ---
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.img = None
        self.img_id = None
        self.rect_id = None
        self.offset_x = 0
        self.offset_y = 0
        self.analyzer = None

        # Dizionari utente
        self.blocklist = ""
        self.allowlist = ""

        self.build_ui()

    # --- GESTIONE ICONE ---
    def set_window_icon(self):
        """Imposta l'icona principale e la prepara per le finestre figlie."""
        icon_path_png = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(icon_path_png):
            try:
                if sys.platform.startswith("win"):
                    # Crea il file .ico temporaneo una sola volta
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
                print(f"Errore icona principale: {e}")

    def apply_child_icon(self, child_window):
        """Applica magicamente l'icona a qualsiasi finestra secondaria."""
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
        except Exception as e:
            print(f"Errore icona figlia: {e}")

    def build_ui(self):
        # Toolbar Principale
        toolbar = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        toolbar.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            toolbar,
            text="Open PDF",
            font=("Roboto", 14, "bold"),
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            command=self.load,
        ).pack(side="left", padx=15, pady=15)

        # Selettore AI
        self.lang_selection = ctk.StringVar(value="EN")
        lang_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        lang_frame.pack(side="left", padx=5)
        ctk.CTkLabel(lang_frame, text="AI Engine:", font=("Roboto", 11, "bold")).pack(
            side="top"
        )

        ctk.CTkRadioButton(
            lang_frame,
            text="EN",
            variable=self.lang_selection,
            value="EN",
            width=50,
            font=("Roboto", 12),
        ).pack(side="left")
        ctk.CTkRadioButton(
            lang_frame,
            text="IT",
            variable=self.lang_selection,
            value="IT",
            width=50,
            font=("Roboto", 12),
        ).pack(side="left")
        ctk.CTkRadioButton(
            lang_frame,
            text="BOTH",
            variable=self.lang_selection,
            value="BOTH",
            width=60,
            font=("Roboto", 12),
        ).pack(side="left")

        # Bottoni Azione
        ctk.CTkButton(
            toolbar,
            text="Dictionary 📖",
            font=("Roboto", 12),
            width=100,
            fg_color="#333344",
            command=self.open_dictionary,
        ).pack(side="left", padx=10)

        ctk.CTkButton(
            toolbar,
            text="Auto Redact (AI)",
            font=("Roboto", 13, "bold"),
            fg_color=self.danger_color,
            hover_color="#c0392b",
            command=self.auto_anon,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="Clear All 🗑️",
            font=("Roboto", 12, "bold"),
            fg_color="transparent",
            border_width=1,
            border_color="#555",
            text_color="#aaa",
            hover_color="#333",
            command=self.clear_all,
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="Export PDF",
            font=("Roboto", 13, "bold"),
            fg_color="transparent",
            border_width=2,
            border_color=self.accent_color,
            text_color=self.accent_color,
            hover_color=self.bg_color,
            command=self.save,
        ).pack(side="left", padx=10)

        # Navigazione
        nav = ctk.CTkFrame(toolbar, fg_color="transparent")
        nav.pack(side="right", padx=15)
        ctk.CTkButton(
            nav,
            text="ⓘ",
            width=35,
            fg_color="transparent",
            text_color=self.accent_color,
            font=("Roboto", 18),
            command=self.show_about,
        ).pack(side="right", padx=(10, 0))
        ctk.CTkButton(
            nav,
            text=">",
            width=35,
            fg_color=self.bg_color,
            command=lambda: self.move_page(1),
        ).pack(side="right", padx=5)
        self.p_lab = ctk.CTkLabel(nav, text="Page: 0 / 0", font=("Roboto", 14, "bold"))
        self.p_lab.pack(side="right", padx=10)
        ctk.CTkButton(
            nav,
            text="<",
            width=35,
            fg_color=self.bg_color,
            command=lambda: self.move_page(-1),
        ).pack(side="right", padx=5)

        # Viewport
        view_frame = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        view_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
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
        self.canvas.bind_all("<MouseWheel>", self.on_mouse_wheel)

        # Footer
        footer = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        footer.pack(fill="x", padx=15, pady=(0, 15))
        self.prog = ctk.CTkProgressBar(
            footer, fg_color=self.bg_color, progress_color=self.accent_color, height=8
        )
        self.prog.pack(fill="x", padx=15, pady=(15, 5))
        self.prog.set(0)
        self.log = ctk.CTkTextbox(
            footer,
            height=90,
            fg_color=self.bg_color,
            text_color="#a1a1aa",
            font=("Consolas", 12),
        )
        self.log.pack(fill="x", padx=15, pady=(5, 15))

    # --- FINESTRE SECONDARIE ---
    def open_dictionary(self):
        dic_win = ctk.CTkToplevel(self)
        dic_win.title("Filter Dictionary")
        dic_win.geometry("500x450")
        dic_win.configure(fg_color=self.panel_color)
        dic_win.transient(self)
        dic_win.grab_set()

        # Applica l'icona!
        self.apply_child_icon(dic_win)

        ctk.CTkLabel(
            dic_win, text="🔴 BLOCKLIST (Censura Sempre)", font=("Roboto", 13, "bold")
        ).pack(pady=(15, 0))
        ctk.CTkLabel(
            dic_win,
            text="Una parola o frase per riga.",
            font=("Roboto", 11),
            text_color="#aaa",
        ).pack()
        block_box = ctk.CTkTextbox(dic_win, height=100, fg_color=self.bg_color)
        block_box.pack(fill="x", padx=20, pady=5)
        block_box.insert("1.0", self.blocklist)

        ctk.CTkLabel(
            dic_win,
            text="🟢 ALLOWLIST (Non censurare mai)",
            font=("Roboto", 13, "bold"),
        ).pack(pady=(15, 0))
        ctk.CTkLabel(
            dic_win,
            text="Ignora l'AI se trova queste parole. Una per riga.",
            font=("Roboto", 11),
            text_color="#aaa",
        ).pack()
        allow_box = ctk.CTkTextbox(dic_win, height=100, fg_color=self.bg_color)
        allow_box.pack(fill="x", padx=20, pady=5)
        allow_box.insert("1.0", self.allowlist)

        def save_dicts():
            self.blocklist = block_box.get("1.0", "end").strip()
            self.allowlist = allow_box.get("1.0", "end").strip()
            self.write_log("Dizionari filtri aggiornati.")
            dic_win.destroy()

        ctk.CTkButton(
            dic_win, text="Save & Close", fg_color=self.accent_color, command=save_dicts
        ).pack(pady=15)

    def show_about(self):
        about = ctk.CTkToplevel(self)
        about.title("About")
        w, h = 340, 440
        self.update_idletasks()
        x, y = self.winfo_x() + (self.winfo_width() // 2) - (w // 2), self.winfo_y() + (
            self.winfo_height() // 2
        ) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        # Applica l'icona!
        self.apply_child_icon(about)

        ctk.CTkLabel(
            about, text="🛡️", font=("Segoe UI Emoji", 70), text_color=self.accent_color
        ).place(relx=0.5, y=80, anchor="center")
        ctk.CTkLabel(
            about, text="NullifyPDF", font=("Roboto", 26, "bold"), text_color="#ffffff"
        ).place(relx=0.5, y=160, anchor="center")
        ctk.CTkLabel(
            about,
            text="v1.3.0 AI-Pro",
            font=("Roboto", 15),
            text_color=self.accent_color,
        ).place(relx=0.5, y=195, anchor="center")
        ctk.CTkLabel(
            about,
            text="AI-Powered Forensic Anonymization.\nWith Smart Review System.",
            font=("Roboto", 13),
            text_color="#a1a1aa",
            justify="center",
        ).place(relx=0.5, y=250, anchor="center")
        ctk.CTkButton(
            about,
            text="Close",
            width=120,
            fg_color=self.bg_color,
            command=about.destroy,
        ).place(relx=0.5, y=395, anchor="center")

    # --- LOGICA CORE AI ---
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

            self.write_log(f"Caricamento modelli AI ({choice})... attendere.")
            self.update_idletasks()

            configuration = {"nlp_engine_name": "spacy", "models": models}
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()

            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine, supported_languages=langs
            )
            self.active_langs = langs
            self.write_log("Motore AI configurato e pronto.")
            return True
        except Exception as e:
            self.write_log(f"Errore caricamento AI: {e}")
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

        self.write_log(f"Avvio scansione intelligente ({choice})...")
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

        allow_set = {w.strip().lower() for w in self.allowlist.split("\n") if w.strip()}
        block_set = {w.strip() for w in self.blocklist.split("\n") if w.strip()}

        for i, page in enumerate(self.doc):
            text = page.get_text()
            found_words = set()

            for lang in self.active_langs:
                results = self.analyzer.analyze(
                    text=text, entities=target_entities, language=lang
                )
                for res in results:
                    word = text[res.start : res.end].strip()
                    if len(word) > 2:
                        found_words.add(word)

            final_words = {w for w in found_words if w.lower() not in allow_set}
            final_words.update(block_set)

            for match in final_words:
                for rect in page.search_for(match):
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            self.prog.set((i + 1) / len(self.doc))
            self.update_idletasks()

        self.render()
        self.write_log(
            "Scansione completata. Censure evidenziate (clicca per rimuovere)."
        )

    def clear_all(self):
        if not self.doc:
            return
        count = 0
        for page in self.doc:
            for annot in page.annots():
                if annot.type[0] == fitz.PDF_ANNOT_REDACT:
                    page.delete_annot(annot)
                    count += 1
        self.render()
        self.write_log(f"Cancellate {count} censure pianificate dal documento.")

    # --- FUNZIONI GUI E INTERAZIONE ---
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
        self.p_lab.configure(text=f"Page: {self.page_num + 1} / {len(self.doc)}")

    def center_image(self):
        if not self.img or not self.img_id:
            return
        self.canvas.update_idletasks()
        cw = self.canvas.winfo_width()
        new_x = max(0, (cw - self.img.width()) // 2)
        self.canvas.coords(self.img_id, new_x, 0)
        self.offset_x, self.offset_y = new_x, 0

    def on_mouse_wheel(self, event):
        if not self.doc:
            return
        if event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")
        else:
            self.canvas.yview_scroll(1, "units")

    def on_mouse_press(self, event):
        if not self.doc:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        pt = fitz.Point(
            (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale
        )

        page = self.doc[self.page_num]
        for annot in page.annots():
            if annot.type[0] == fitz.PDF_ANNOT_REDACT and annot.rect.contains(pt):
                page.delete_annot(annot)
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
            self.doc[self.page_num].add_redact_annot(rect, fill=(0, 0, 0))
            self.render()

        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.start_xy = None

    # --- ESPORTAZIONE ---
    def save(self):
        if not self.doc:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_secured.pdf",
        )
        if fp:
            try:
                self.write_log("Applicazione distruttiva delle censure in corso...")

                for page in self.doc:
                    redact_rects = [
                        annot.rect
                        for annot in page.annots()
                        if annot.type[0] == fitz.PDF_ANNOT_REDACT
                    ]
                    for link in page.get_links():
                        link_rect = fitz.Rect(link["from"])
                        for r_rect in redact_rects:
                            if link_rect.intersects(r_rect):
                                page.delete_link(link)
                                break

                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
                    )

                self.doc.set_metadata({})
                catalog_xref = self.doc.pdf_catalog()
                for key in ["Metadata", "PieceInfo", "Properties"]:
                    self.doc.xref_set_key(catalog_xref, key, "null")

                self.doc.save(fp, garbage=4, deflate=True, clean=True)
                self.write_log(
                    f"Esportazione forense completata: {os.path.basename(fp)}"
                )

                self.doc = fitz.open(fp)
                self.render()

            except Exception as e:
                self.write_log(f"Errore Esportazione: {e}")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.render()
            self.write_log(f"Documento caricato: {os.path.basename(path)}")

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
