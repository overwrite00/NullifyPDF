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

__version__ = "1.5.5"


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


class NullifyPDF(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NullifyPDF - AI Forensic Edition")
        self.geometry("1350x950")
        self.minsize(1000, 700)

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

        # STATO APPLICAZIONE
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.min_scale = 0.5
        self.max_scale = 4.0
        self.img = None
        self.img_id = None
        self.rect_id = None
        self.offset_x = 0
        self.offset_y = 0
        self.start_xy = None
        self.analyzer = None
        self.active_langs = []

        # MUTEX LOCK (Previene accavallamenti e crash silenziosi)
        self.is_processing = False

        # PERSISTENZA DIZIONARI
        self.config_dir = pathlib.Path.home() / ".nullifypdf"
        try:
            self.config_dir.mkdir(exist_ok=True)
        except:
            pass

        self.blocklist_file = self.config_dir / "blocklist.txt"
        self.allowlist_file = self.config_dir / "allowlist.txt"
        self.blocklist = self.load_list(self.blocklist_file)
        self.allowlist = self.load_list(self.allowlist_file)

        self.build_ui()
        self.after(200, self.check_sys_args)

    def check_sys_args(self):
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
        except:
            pass

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
            except:
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
        except:
            pass

    def build_ui(self):
        # SIDEBAR
        self.sidebar = ctk.CTkFrame(
            self, width=260, corner_radius=0, fg_color=self.panel_color
        )
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(
            self.sidebar,
            text="NullifyPDF",
            font=("Roboto", 24, "bold"),
            text_color=self.accent_color,
        ).pack(pady=(30, 5))
        ctk.CTkLabel(
            self.sidebar,
            text="AI Forensic Edition",
            font=("Roboto", 12),
            text_color="#aaa",
        ).pack(pady=(0, 30))

        ctk.CTkButton(
            self.sidebar,
            text="Apri PDF",
            font=("Roboto", 14, "bold"),
            height=45,
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            command=self.load,
        ).pack(fill="x", padx=20, pady=10)

        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333344").pack(
            fill="x", padx=20, pady=15
        )

        ctk.CTkLabel(
            self.sidebar, text="Modello Lingua AI:", font=("Roboto", 12, "bold")
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

        ctk.CTkFrame(self.sidebar, height=1, fg_color="#333344").pack(
            fill="x", padx=25, pady=10
        )
        self.redact_images_var = ctk.BooleanVar(value=False)
        self.img_switch = ctk.CTkSwitch(
            self.sidebar,
            text="Oscura Immagini",
            font=("Roboto", 12),
            variable=self.redact_images_var,
            progress_color=self.accent_color,
        )
        self.img_switch.pack(anchor="w", padx=25, pady=5)
        ctk.CTkLabel(
            self.sidebar,
            text="Segnaposto professionale",
            font=("Roboto", 10),
            text_color="#777",
        ).pack(anchor="w", padx=25)

        ctk.CTkButton(
            self.sidebar,
            text="Dizionario 📖",
            fg_color="#333344",
            command=self.open_dictionary,
        ).pack(fill="x", padx=20, pady=15)
        ctk.CTkButton(
            self.sidebar,
            text="Auto Redact (AI)",
            font=("Roboto", 13, "bold"),
            height=40,
            fg_color=self.danger_color,
            hover_color="#c0392b",
            command=self.auto_anon,
        ).pack(fill="x", padx=20, pady=5)
        ctk.CTkButton(
            self.sidebar,
            text="Pulisci Pagina 🗑️",
            fg_color="transparent",
            border_width=1,
            border_color="#555",
            text_color="#aaa",
            command=self.clear_page,
        ).pack(fill="x", padx=20, pady=10)

        ctk.CTkButton(
            self.sidebar,
            text="Esporta PDF Sicuro",
            font=("Roboto", 14, "bold"),
            height=45,
            fg_color="transparent",
            border_width=2,
            border_color=self.accent_color,
            text_color=self.accent_color,
            command=self.save,
        ).pack(fill="x", padx=20, pady=(25, 10))

        bottom_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        bottom_frame.pack(side="bottom", fill="x", pady=20)
        ctk.CTkButton(
            bottom_frame,
            text="ⓘ About",
            fg_color="transparent",
            text_color=self.accent_color,
            command=self.show_about,
        ).pack(pady=5)
        ctk.CTkButton(
            bottom_frame,
            text="Esci",
            fg_color="transparent",
            text_color="#888",
            hover_color="#333",
            command=self.destroy,
        ).pack()

        # MAIN AREA
        self.main_area = ctk.CTkFrame(self, fg_color="transparent")
        self.main_area.pack(side="right", fill="both", expand=True, padx=15, pady=15)

        nav_bar = ctk.CTkFrame(
            self.main_area, fg_color=self.panel_color, corner_radius=8, height=50
        )
        nav_bar.pack(fill="x", pady=(0, 10))
        nav_bar.pack_propagate(False)

        ctk.CTkLabel(
            nav_bar, text="Visualizzatore Documento", font=("Roboto", 14, "bold")
        ).pack(side="left", padx=15)

        zoom_frame = ctk.CTkFrame(nav_bar, fg_color="transparent")
        zoom_frame.pack(side="left", padx=15)
        ctk.CTkButton(
            zoom_frame,
            text="-",
            width=28,
            height=28,
            fg_color="#333344",
            command=self.zoom_out,
        ).pack(side="left", padx=2)
        self.zoom_var = ctk.StringVar(value=f"{int(self.scale * 100)}%")
        ctk.CTkLabel(
            zoom_frame, textvariable=self.zoom_var, width=45, font=("Roboto", 12)
        ).pack(side="left", padx=2)
        ctk.CTkButton(
            zoom_frame,
            text="+",
            width=28,
            height=28,
            fg_color="#333344",
            command=self.zoom_in,
        ).pack(side="left", padx=2)

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
            nav_ctrls, textvariable=self.page_entry_var, width=40, justify="center"
        )
        self.page_entry.pack(side="left", padx=2)
        self.page_entry.bind("<Return>", self.jump_to_page)
        self.tot_pages_lab = ctk.CTkLabel(nav_ctrls, text="/ 0", font=("Roboto", 12))
        self.tot_pages_lab.pack(side="left", padx=(2, 10))
        ctk.CTkButton(
            nav_ctrls,
            text=">",
            width=30,
            fg_color=self.bg_color,
            command=lambda: self.move_page(1),
        ).pack(side="left", padx=5)

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
        self.canvas.bind("<Control-MouseWheel>", self.on_ctrl_mouse_wheel)

        footer = ctk.CTkFrame(
            self.main_area, fg_color=self.panel_color, corner_radius=8
        )
        footer.pack(fill="x")
        self.prog = ctk.CTkProgressBar(
            footer, fg_color=self.bg_color, progress_color=self.accent_color, height=8
        )
        self.prog.pack(fill="x", padx=15, pady=(15, 5))
        self.log = ctk.CTkTextbox(
            footer,
            height=80,
            fg_color=self.bg_color,
            text_color="#a1a1aa",
            font=("Consolas", 12),
        )
        self.log.pack(fill="x", padx=15, pady=(5, 15))

    # --- LOGICA CORE ---

    def add_professional_redaction(self, page, rect):
        """Segnaposto professionale per le immagini rimosse"""
        page.add_redact_annot(
            rect,
            text="[ IMMAGINE RIMOSSA ]",
            align=fitz.TEXT_ALIGN_CENTER,
            fill=(0.92, 0.92, 0.92),
            fontname="helv",
            fontsize=8,
        )

    def init_ai(self, choice):
        try:
            self.write_log(f"Caricamento AI ({choice}) in corso... Attendere prego.")
            self.update()  # FORZA IL RENDERING DELLA UI PRIMA DEL BLOCCO CPU

            from presidio_analyzer import AnalyzerEngine
            from presidio_analyzer.nlp_engine import NlpEngineProvider

            models = []
            if choice in ["EN", "BOTH"]:
                models.append({"lang_code": "en", "model_name": "en_core_web_md"})
            if choice in ["IT", "BOTH"]:
                models.append({"lang_code": "it", "model_name": "it_core_news_md"})
            configuration = {"nlp_engine_name": "spacy", "models": models}
            provider = NlpEngineProvider(nlp_configuration=configuration)
            self.analyzer = AnalyzerEngine(
                nlp_engine=provider.create_engine(),
                supported_languages=[m["lang_code"] for m in models],
            )
            self.active_langs = [m["lang_code"] for m in models]

            self.write_log("Motore AI inizializzato con successo.")
            self.update()
            return True
        except Exception as e:
            self.write_log(f"ERRORE Inizializzazione AI: {str(e)}")
            return False

    def auto_anon(self):
        if not self.doc:
            return

        # MUTEX LOCK: Previene l'accavallamento dei thread se l'utente clicca più volte
        if getattr(self, "is_processing", False):
            return

        self.is_processing = True

        try:
            choice = self.lang_selection.get()
            if not self.analyzer or sorted(self.active_langs) != sorted(
                ["en", "it"] if choice == "BOTH" else [choice.lower()]
            ):
                if not self.init_ai(choice):
                    self.is_processing = False
                    return

            self.write_log("Scansione forense intelligente (in corso)...")
            self.prog.set(0)
            self.update()  # AGGIORNA LA UI PER MOSTRARE IL MESSAGGIO

            target_entities = [
                "PERSON",
                "LOCATION",
                "EMAIL_ADDRESS",
                "PHONE_NUMBER",
                "IBAN_CODE",
                "CREDIT_CARD",
                "CRYPTO",
            ]

            compiled_allowlist = []
            for allowed in self.allowlist:
                compiled_allowlist.append(
                    (allowed, re.compile(r"\b" + re.escape(allowed) + r"\b"))
                )

            for i, page in enumerate(self.doc):
                text = page.get_text()
                existing_redacts = [
                    a.rect for a in page.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT
                ]

                if self.redact_images_var.get():
                    for img_info in page.get_image_info(hashes=False):
                        img_rect = fitz.Rect(img_info["bbox"])
                        self.add_professional_redaction(page, img_rect)
                        existing_redacts.append(img_rect)

                for block_word in self.blocklist:
                    for rect in page.search_for(block_word):
                        center = fitz.Point(
                            (rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2
                        )
                        if not any(e_r.contains(center) for e_r in existing_redacts):
                            page.add_redact_annot(rect, fill=(0, 0, 0))
                            existing_redacts.append(rect)

                protected_rects = [
                    r
                    for allow_word in self.allowlist
                    for r in page.search_for(allow_word)
                ]

                found_ai_words = set()
                for lang in self.active_langs:
                    try:
                        # Scudo di protezione interno contro errori di Parsing di Presidio/Spacy
                        results = self.analyzer.analyze(
                            text=text, entities=target_entities, language=lang
                        )
                        for res in results:
                            word = text[res.start : res.end].strip()
                            if len(word) > 2:
                                found_ai_words.add(word)
                    except Exception as ai_err:
                        self.write_log(f"Avviso AI su Pagina {i+1}: {ai_err}")

                for match in found_ai_words:
                    clean_match = " ".join(
                        match.strip(string.punctuation).lower().split()
                    )
                    is_protected = False

                    # Ottimizzazione Estrema: Niente doppia Regex. Usiamo l'operatore 'in' nativo.
                    for allowed_str, forward_regex in compiled_allowlist:
                        if (
                            forward_regex.search(clean_match)
                            or clean_match in allowed_str
                        ):
                            is_protected = True
                            break

                    if is_protected:
                        continue

                    for ai_rect in page.search_for(match):
                        if any(
                            ai_rect.intersects(p_rect) for p_rect in protected_rects
                        ):
                            continue

                        center = fitz.Point(
                            (ai_rect.x0 + ai_rect.x1) / 2, (ai_rect.y0 + ai_rect.y1) / 2
                        )
                        if not any(e_r.contains(center) for e_r in existing_redacts):
                            page.add_redact_annot(ai_rect, fill=(0, 0, 0))
                            existing_redacts.append(ai_rect)

                self.prog.set((i + 1) / len(self.doc))
                self.update()  # Mantiene la GUI fluida e responsiva pagina per pagina

            self.render()
            self.write_log("Anonimizzazione completata in tempo record.")

        except Exception as e:
            # INTERCETTAZIONE CRITICA: Niente più crash silenziosi
            self.write_log(f"ERRORE CRITICO DURANTE LA SCANSIONE: {str(e)}")
        finally:
            # SBLOCCO DEL MUTEX
            self.is_processing = False

    def save(self):
        if not self.doc:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_secured.pdf",
        )
        if fp:
            try:
                self.write_log("Sanificazione forense (Scrubbing) in corso...")
                self.update()

                pdf_bytes = self.doc.write()
                export_doc = fitz.open("pdf", pdf_bytes)

                for page in export_doc:
                    redact_rects = [
                        a.rect
                        for a in page.annots()
                        if a.type[0] == fitz.PDF_ANNOT_REDACT
                    ]

                    try:
                        for link in page.get_links():
                            if any(
                                fitz.Rect(link["from"]).intersects(r)
                                for r in redact_rects
                            ):
                                page.delete_link(link)
                    except:
                        pass

                    page.apply_redactions(
                        images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
                    )

                    try:
                        for widget in page.widgets():
                            page.delete_widget(widget)
                    except:
                        pass

                export_doc.set_metadata({})
                catalog_xref = export_doc.pdf_catalog()
                for key in ["Metadata", "PieceInfo", "Properties", "AcroForm"]:
                    export_doc.xref_set_key(catalog_xref, key, "null")

                export_doc.save(fp, garbage=4, deflate=True, clean=True)
                export_doc.close()
                self.write_log(f"ESPORTAZIONE COMPLETATA: {os.path.basename(fp)}")
            except Exception as e:
                self.write_log(f"Errore Esportazione: {e}")

    # --- METODI GUI E UTILITY ---

    def load_path(self, path):
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(path)
            self.page_num = 0
            self.scale = 1.5
            self.update_zoom_ui()
            self.write_log(f"Caricato: {os.path.basename(path)}")
        except:
            pass

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
        self.page_entry_var.set(str(self.page_num + 1))
        self.tot_pages_lab.configure(text=f"/ {len(self.doc)}")

    def center_image(self):
        if self.img:
            cw = self.canvas.winfo_width()
            nx = max(0, (cw - self.img.width()) // 2)
            self.canvas.coords(self.img_id, nx, 0)
            self.offset_x = nx

    def zoom_in(self):
        if self.scale < self.max_scale:
            self.scale += 0.25
            self.update_zoom_ui()

    def zoom_out(self):
        if self.scale > self.min_scale:
            self.scale -= 0.25
            self.update_zoom_ui()

    def update_zoom_ui(self):
        self.zoom_var.set(f"{int(self.scale * 100)}%")
        self.render()

    def jump_to_page(self, e=None):
        try:
            t = int(self.page_entry_var.get()) - 1
            if 0 <= t < len(self.doc):
                self.page_num = t
                self.render()
                self.canvas.yview_moveto(0)
            else:
                self.page_entry_var.set(str(self.page_num + 1))
        except:
            pass

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()
            self.canvas.yview_moveto(0)

    def on_mouse_press(self, event):
        if not self.doc:
            return
        cx, cy = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        pt = fitz.Point(
            (cx - self.offset_x) / self.scale, (cy - self.offset_y) / self.scale
        )
        p = self.doc[self.page_num]
        ans = [
            a
            for a in p.annots()
            if a.type[0] == fitz.PDF_ANNOT_REDACT and a.rect.contains(pt)
        ]
        if ans:
            txt = p.get_text("text", clip=ans[0].rect)
            for a in ans:
                p.delete_annot(a)
            cl = " ".join(txt.split()).lower()
            if len(cl) > 2:
                self.blocklist.discard(cl)
                self.allowlist.add(cl)
                self.save_list(self.blocklist_file, self.blocklist)
                self.save_list(self.allowlist_file, self.allowlist)
            self.render()
            return
        self.start_xy = (cx, cy)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            cx, cy, cx, cy, outline=self.danger_color, width=2
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
        if (x1 - x0) > 3:
            rect = fitz.Rect(
                x0 / self.scale, y0 / self.scale, x1 / self.scale, y1 / self.scale
            )
            txt = self.doc[self.page_num].get_text("text", clip=rect)

            if not txt.strip():
                self.add_professional_redaction(self.doc[self.page_num], rect)
            else:
                self.doc[self.page_num].add_redact_annot(rect, fill=(0, 0, 0))
                cl = " ".join(txt.split()).lower()
                if len(cl) > 2:
                    self.allowlist.discard(cl)
                    self.blocklist.add(cl)
                    self.save_list(self.blocklist_file, self.blocklist)
                    self.save_list(self.allowlist_file, self.allowlist)
            self.render()
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.start_xy = None

    def on_mouse_drag(self, e):
        if not self.doc or not self.start_xy:
            return
        self.canvas.coords(
            self.rect_id,
            self.start_xy[0],
            self.start_xy[1],
            self.canvas.canvasx(e.x),
            self.canvas.canvasy(e.y),
        )

    def on_mouse_wheel(self, e):
        if not (e.state & 0x0004) and self.doc:
            if e.num == 4 or e.delta > 0:
                self.canvas.yview_scroll(-1, "units")
            else:
                self.canvas.yview_scroll(1, "units")

    def on_ctrl_mouse_wheel(self, e):
        if self.doc:
            if e.num == 4 or e.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()

    def clear_page(self):
        if not self.doc:
            return
        p = self.doc[self.page_num]

        annots_to_delete = [a for a in p.annots() if a.type[0] == fitz.PDF_ANNOT_REDACT]
        for a in annots_to_delete:
            p.delete_annot(a)

        self.render()
        self.write_log(f"Pulite {len(annots_to_delete)} censure.")

    def open_dictionary(self):
        dic_win = ctk.CTkToplevel(self)
        dic_win.title("Dizionari")

        w, h = 500, 450
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        dic_win.geometry(f"{w}x{h}+{x}+{y}")
        dic_win.resizable(False, False)

        self.apply_child_icon(dic_win)

        ctk.CTkLabel(
            dic_win, text="🔴 BLOCKLIST GLOBALE", font=("Roboto", 13, "bold")
        ).pack(pady=(15, 5))
        bx = ctk.CTkTextbox(dic_win, height=120)
        bx.pack(fill="x", padx=20)
        bx.insert("1.0", "\n".join(sorted(self.blocklist)))

        ctk.CTkLabel(
            dic_win, text="🟢 ALLOWLIST GLOBALE", font=("Roboto", 13, "bold")
        ).pack(pady=(15, 5))
        ax = ctk.CTkTextbox(dic_win, height=120)
        ax.pack(fill="x", padx=20)
        ax.insert("1.0", "\n".join(sorted(self.allowlist)))

        def save_dicts():
            self.blocklist = {
                l.strip().lower()
                for l in bx.get("1.0", "end").split("\n")
                if len(l.strip()) > 2
            }
            self.allowlist = {
                l.strip().lower()
                for l in ax.get("1.0", "end").split("\n")
                if len(l.strip()) > 2
            }
            self.save_list(self.blocklist_file, self.blocklist)
            self.save_list(self.allowlist_file, self.allowlist)
            dic_win.destroy()

        ctk.CTkButton(
            dic_win,
            text="Salva e Chiudi",
            fg_color=self.accent_color,
            command=save_dicts,
        ).pack(pady=15)
        dic_win.transient(self)
        dic_win.grab_set()

    def show_about(self):
        about = ctk.CTkToplevel(self)
        about.title("Info")

        w, h = 340, 440
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.resizable(False, False)

        self.apply_child_icon(about)

        ip = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(ip):
            img = Image.open(ip)
            self.alogo = ctk.CTkImage(light_image=img, dark_image=img, size=(100, 100))
            ctk.CTkLabel(about, image=self.alogo, text="").pack(pady=20)

        ctk.CTkLabel(about, text="NullifyPDF", font=("Roboto", 24, "bold")).pack()
        ctk.CTkLabel(
            about, text=f"v{__version__} AI Forensic", text_color=self.accent_color
        ).pack()
        ctk.CTkLabel(
            about,
            text="\nAnonimizzazione PDF Professionale Offline.\n\nSviluppato da: Graziano Mariella\nLicenza MIT",
            justify="center",
        ).pack(pady=10)
        ctk.CTkButton(
            about, text="Chiudi", fg_color=self.bg_color, command=about.destroy
        ).pack(pady=20)

        about.transient(self)
        about.grab_set()

    def load(self):
        p = filedialog.askopenfilename(filetypes=[("PDF", "*.pdf")])
        if p:
            self.load_path(p)

    def write_log(self, m):
        self.log.insert(
            "end", f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {m}\n"
        )
        self.log.see("end")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
