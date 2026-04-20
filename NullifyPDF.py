import os
import re
import datetime
import fitz
import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk

# Configurazione tema globale
ctk.set_appearance_mode("dark")


class NullifyPDF(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- CONFIGURAZIONE FINESTRA PRINCIPALE ---
        self.title("NullifyPDF - Forensic Edition")
        self.geometry("1200x900")

        # Palette Colori
        self.bg_color = "#141526"
        self.panel_color = "#1e1f31"
        self.accent_color = "#1fb2e0"
        self.hover_color = "#178cae"
        self.danger_color = "#e74c3c"

        self.configure(fg_color=self.bg_color)

        # --- STATO DELL'APPLICAZIONE ---
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.start_xy = None
        self.img = None
        self.img_id = None
        self.rect_id = None
        self.offset_x = 0
        self.offset_y = 0

        self.build_ui()

    def build_ui(self):
        """Costruisce l'interfaccia principale."""
        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        toolbar.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            toolbar,
            text="Open Document",
            font=("Roboto", 14, "bold"),
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            command=self.load,
        ).pack(side="left", padx=15, pady=15)

        self.kw = ctk.CTkEntry(
            toolbar,
            placeholder_text="Specific word...",
            width=200,
            fg_color=self.bg_color,
            border_color="#333344",
        )
        self.kw.pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar,
            text="Auto Redact",
            font=("Roboto", 13, "bold"),
            fg_color=self.danger_color,
            hover_color="#c0392b",
            command=self.auto_anon,
        ).pack(side="left", padx=10)

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
        self.canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.canvas.bind("<Configure>", self.center_image)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

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

    # --- LOGICA CORE ---

    def write_log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {msg}\n")
        self.log.see("end")

    def show_about(self):
        """Finestra informativa con posizionamento place simmetrico."""
        about = ctk.CTkToplevel(self)
        about.title("About")
        w, h = 340, 440
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        ctk.CTkLabel(
            about, text="🛡️", font=("Segoe UI Emoji", 70), text_color=self.accent_color
        ).place(relx=0.5, y=80, anchor="center")
        ctk.CTkLabel(
            about, text="NullifyPDF", font=("Roboto", 26, "bold"), text_color="#ffffff"
        ).place(relx=0.5, y=160, anchor="center")
        ctk.CTkLabel(
            about,
            text="v1.2.5 [Forensic Edition]",
            font=("Roboto", 15),
            text_color=self.accent_color,
        ).place(relx=0.5, y=195, anchor="center")

        desc = "Universal PDF Anonymization Tool.\nIrreversible redaction & forensic scrubbing."
        ctk.CTkLabel(
            about,
            text=desc,
            font=("Roboto", 13),
            text_color="#a1a1aa",
            justify="center",
        ).place(relx=0.5, y=250, anchor="center")
        ctk.CTkFrame(about, height=1, fg_color="#333344", width=240).place(
            relx=0.5, y=310, anchor="center"
        )
        ctk.CTkLabel(
            about,
            text="© 2026 Graziano Mariella",
            font=("Roboto", 12),
            text_color="#ffffff",
        ).place(relx=0.5, y=345, anchor="center")

        ctk.CTkButton(
            about,
            text="Close",
            width=120,
            fg_color=self.bg_color,
            hover_color="#333344",
            command=about.destroy,
        ).place(relx=0.5, y=395, anchor="center")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.render()
            self.write_log(f"Document loaded: {os.path.basename(path)}")

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
        self.img = ImageTk.PhotoImage(
            Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        )
        self.canvas.delete("all")
        self.img_id = self.canvas.create_image(0, 0, anchor="center", image=self.img)
        self.center_image()
        self.p_lab.configure(text=f"Page: {self.page_num + 1} / {len(self.doc)}")

    def center_image(self, event=None):
        if not self.doc or self.img is None:
            return
        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.img.width(), self.img.height()
        x, y = (cw // 2 if cw > iw else iw // 2), (ch // 2 if ch > ih else ih // 2)
        if self.img_id:
            self.canvas.coords(self.img_id, x, y)
        self.offset_x, self.offset_y = x - (iw // 2), y - (ih // 2)

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()

    def auto_anon(self):
        if not self.doc:
            return

        # Regex robuste e case-insensitive
        email_pattern = r"[a-zA-Z0-9-_.]+@[a-zA-Z0-9-_.]+\.[a-zA-Z]{2,5}"
        cf_pattern = r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"

        self.write_log("Starting Forensic Scan (Text & Hyperlinks)...")
        self.prog.set(0)

        for i, page in enumerate(self.doc):
            text = page.get_text()

            # Utilizzo corretto di union() per i set
            found_emails = set(re.findall(email_pattern, text, re.IGNORECASE))
            found_cf = set(re.findall(cf_pattern, text, re.IGNORECASE))
            found = found_emails.union(found_cf)

            kw_val = self.kw.get().strip()
            if kw_val:
                found.add(kw_val)

            for match in found:
                match_lower = match.lower()

                # 1. DISTRUZIONE LINK IPERTESTUALI (La causa del binario fallito)
                for link in page.get_links():
                    uri = link.get("uri", "").lower()
                    # Se il link contiene l'email/parola (es: mailto:graziano...), cancellalo
                    if uri and match_lower in uri:
                        page.delete_link(link)

                # 2. CENSURA VISIVA DEL TESTO
                for rect in page.search_for(match):
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            # Redazione profonda anche su grafica e immagini
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True)
            self.prog.set((i + 1) / len(self.doc))
            self.update_idletasks()

        self.render()
        self.write_log("Auto-redaction applied to visual text and interactive links.")

    def on_mouse_press(self, event):
        if not self.doc or self.img is None:
            return
        x, y = event.x, event.y
        self.start_xy = (x, y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x, y, x, y, outline=self.danger_color, width=2
        )

    def on_mouse_drag(self, event):
        if not self.start_xy:
            return
        self.canvas.coords(
            self.rect_id, self.start_xy[0], self.start_xy[1], event.x, event.y
        )

    def on_mouse_release(self, event):
        if not self.doc or not self.start_xy:
            return
        ex, ey = event.x, event.y
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
            self.doc[self.page_num].apply_redactions(
                images=fitz.PDF_REDACT_IMAGE_REMOVE, graphics=True
            )
            self.render()

        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.start_xy = None

    def save(self):
        if not self.doc:
            return

        suggested = (
            f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_secured.pdf"
        )
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=suggested
        )

        if fp:
            try:
                self.write_log("Executing structural deep-clean...")

                # 1. SVUOTAMENTO METADATI STANDARD
                self.doc.set_metadata({})

                # 2. RIMOZIONE XML METADATA (XMP)
                if hasattr(self.doc, "del_xml_metadata"):
                    self.doc.del_xml_metadata()

                # 3. INTERVENTO CHIRURGICO SUL CATALOGO (XREF)
                # Eliminiamo manualmente i puntatori a metadati e dati applicativi
                try:
                    catalog_xref = self.doc.pdf_catalog()
                    # Rimuoviamo il riferimento all'oggetto Metadata
                    self.doc.xref_set_key(catalog_xref, "Metadata", "null")
                    # Rimuoviamo PieceInfo (spesso usato da Adobe/MS Word per nascondere tracce)
                    self.doc.xref_set_key(catalog_xref, "PieceInfo", "null")
                    # Rimuoviamo Proprietà Custom
                    self.doc.xref_set_key(catalog_xref, "Properties", "null")
                except Exception as e:
                    self.write_log(f"Catalog cleanup notice: {e}")

                # 4. SALVATAGGIO CON RIGENERAZIONE TOTALE
                # Usiamo 'expand_incremental=False' implicito salvando su nuovo file
                # garbage=4: è fondamentale, distrugge gli oggetti scollegati al punto 3
                self.doc.save(
                    fp,
                    garbage=4,
                    deflate=True,
                    clean=True,
                    pretty=False,  # Evita di rendere il PDF "leggibile" (rimuove spazi bianchi extra)
                )

                self.write_log(f"SUCCESS: {os.path.basename(fp)} is now binary-clean.")

            except Exception as e:
                self.write_log(f"Export Error: {str(e)}")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
