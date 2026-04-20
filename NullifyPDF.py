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
        self.title("NullifyPDF - Secure Anonymization Tool")
        self.geometry("1200x900")

        # Palette Colori (Stile MetaLens/Dark Professional)
        self.bg_color = "#141526"
        self.panel_color = "#1e1f31"
        self.accent_color = "#1fb2e0"
        self.hover_color = "#178cae"
        self.danger_color = "#e74c3c"

        self.configure(fg_color=self.bg_color)

        # --- STATO DELL'APPLICAZIONE ---
        self.doc = None
        self.page_num = 0
        self.scale = 1.5  # Zoom di rendering
        self.start_xy = None  # Punto iniziale selezione manuale
        self.img = None  # Referenza immagine per evitare Garbage Collection
        self.img_id = None  # ID dell'immagine sul Canvas
        self.rect_id = None  # ID del rettangolo di selezione elastico
        self.offset_x = 0  # Offset per centratura PDF
        self.offset_y = 0

        self.build_ui()

    def build_ui(self):
        """Costruisce l'interfaccia principale."""

        # --- TOOLBAR SUPERIORE ---
        toolbar = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        toolbar.pack(fill="x", padx=15, pady=15)

        # Azioni File
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

        # Navigazione e Info
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

        # --- VIEWPORT (Area Visualizzazione PDF) ---
        view_frame = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        view_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.v_scr = ctk.CTkScrollbar(
            view_frame, orientation="vertical", button_color=self.accent_color
        )
        self.v_scr.pack(side="right", fill="y", padx=(0, 5), pady=5)

        self.h_scr = ctk.CTkScrollbar(
            view_frame, orientation="horizontal", button_color=self.accent_color
        )
        self.h_scr.pack(side="bottom", fill="x", padx=5, pady=(0, 5))

        self.canvas = Canvas(
            view_frame,
            bg="#0d0e1b",
            highlightthickness=0,
            cursor="crosshair",
            yscrollcommand=self.v_scr.set,
            xscrollcommand=self.h_scr.set,
        )
        self.canvas.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.v_scr.configure(command=self.canvas.yview)
        self.h_scr.configure(command=self.canvas.xview)

        # Bindings per interazione
        self.canvas.bind("<Configure>", self.center_image)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)

        # Controllo Scroll (attivo solo se il mouse è sopra il PDF)
        self.canvas.bind(
            "<Enter>", lambda _: self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        )
        self.canvas.bind("<Leave>", lambda _: self.canvas.unbind_all("<MouseWheel>"))

        # --- FOOTER (Log e Progresso) ---
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

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

    def write_log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {msg}\n")
        self.log.see("end")

    def show_about(self):
        """Finestra informativa centrata e simmetrica."""
        about = ctk.CTkToplevel(self)
        about.title("About")
        w, h = 340, 440

        # Centratura dinamica rispetto alla finestra principale
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_y() + (self.winfo_height() // 2) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")

        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        # Elementi UI (Precisione Millimetrica con place)
        ctk.CTkLabel(
            about, text="🛡️", font=("Segoe UI Emoji", 70), text_color=self.accent_color
        ).place(relx=0.5, y=80, anchor="center")

        ctk.CTkLabel(
            about, text="NullifyPDF", font=("Roboto", 26, "bold"), text_color="#ffffff"
        ).place(relx=0.5, y=160, anchor="center")

        ctk.CTkLabel(
            about, text="v1.2.0", font=("Roboto", 15), text_color=self.accent_color
        ).place(relx=0.5, y=195, anchor="center")

        desc = "Universal PDF Anonymization Tool.\nIrreversible redaction & forensic cleaning."
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
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
        self.offset_x, self.offset_y = x - (iw // 2), y - (ih // 2)

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.render()

    def auto_anon(self):
        if not self.doc:
            return
        # Regex per Email e Codice Fiscale Italiano
        patterns = [r"[\w\.-]+@[\w\.-]+", r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"]
        self.write_log("Running deep scan and auto-redaction...")

        for i, page in enumerate(self.doc):
            found = set(
                re.findall(patterns[0], page.get_text())
                | re.findall(patterns[1], page.get_text())
            )
            if self.kw.get():
                found.add(self.kw.get())

            for match in found:
                for rect in page.search_for(match):
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            page.apply_redactions()
            self.prog.set((i + 1) / len(self.doc))
            self.update_idletasks()

        self.render()
        self.write_log("Auto-redaction completed. Verify results.")

    # --- SELEZIONE MANUALE CON CLIPPING ---

    def on_mouse_press(self, event):
        if not self.doc or self.img is None:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.start_xy = (x, y)
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x, y, x, y, outline=self.danger_color, width=2, dash=(4, 4)
        )

    def on_mouse_drag(self, event):
        if not self.start_xy or not self.rect_id:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_xy[0], self.start_xy[1], x, y)

    def on_mouse_release(self, event):
        if not self.doc or not self.start_xy:
            return
        ex, ey = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Clipping delle coordinate per evitare crash fuori dai bordi del PDF
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

        # Se il rettangolo ha una dimensione minima, applica la censura
        if (x1 - x0) > 3 and (y1 - y0) > 3:
            rect = fitz.Rect(
                x0 / self.scale, y0 / self.scale, x1 / self.scale, y1 / self.scale
            )
            self.doc[self.page_num].add_redact_annot(rect, fill=(0, 0, 0))
            self.doc[self.page_num].apply_redactions()
            self.render()

        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.start_xy = None

    def save(self):
        if not self.doc:
            return
        suggested = (
            f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_redacted.pdf"
        )
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", initialfile=suggested
        )
        if fp:
            try:
                # Salvataggio con pulizia profonda dei metadati e garbage collection
                self.doc.save(fp, garbage=4, deflate=True, clean=True)
                self.write_log(f"Successfully exported: {os.path.basename(fp)}")
            except Exception as e:
                self.write_log(f"Export Error: {e}")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
