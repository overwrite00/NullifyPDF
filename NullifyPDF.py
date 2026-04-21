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

__version__ = "1.3.0"


def resource_path(relative_path):
    """Ottiene il percorso assoluto delle risorse, funziona per dev e per PyInstaller"""
    try:
        # PyInstaller crea una cartella temporanea in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
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
        self.redactions = {}
        self.is_drawing = False
        self.start_x = 0
        self.start_y = 0

        # Dizionari Smart
        self.allowlist = set()
        self.blocklist = set()

        self.setup_ui()
        self.load_models()

    def set_window_icon(self):
        icon_path_png = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        icon_path_ico = resource_path(os.path.join("images", "NullifyPDF_icon.ico"))

        try:
            if sys.platform.startswith("win"):
                if os.path.exists(icon_path_ico):
                    self.iconbitmap(icon_path_ico)
            else:
                if os.path.exists(icon_path_png):
                    img = ImageTk.PhotoImage(Image.open(icon_path_png))
                    self.wm_iconphoto(True, img)
        except Exception as e:
            print(f"Errore caricamento icona principale: {e}")

    def apply_child_icon(self, child_window):
        icon_path_png = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        try:
            if os.path.exists(icon_path_png):
                img = ImageTk.PhotoImage(Image.open(icon_path_png))
                child_window.wm_iconphoto(False, img)
        except:
            pass

    def load_models(self):
        # Placeholder per caricamento Presidio/Spacy
        self.write_log("Inizializzazione Motori AI in corso...")
        # Qui andrebbe la logica di caricamento Presidio

    def setup_ui(self):
        # Toolbar laterale
        self.sidebar = ctk.CTkFrame(
            self, width=280, fg_color=self.panel_color, corner_radius=0
        )
        self.sidebar.pack(side="left", fill="y")

        ctk.CTkLabel(
            self.sidebar,
            text="NullifyPDF",
            font=("Roboto", 24, "bold"),
            text_color=self.accent_color,
        ).pack(pady=20)

        self.btn_load = ctk.CTkButton(
            self.sidebar,
            text="Open PDF",
            command=self.load,
            fg_color=self.bg_color,
            hover_color=self.hover_color,
        )
        self.btn_load.pack(pady=10, padx=20, fill="x")

        self.btn_auto = ctk.CTkButton(
            self.sidebar,
            text="AI Smart Scan",
            command=lambda: self.write_log(
                "Scansione AI non implementata in questo snippet"
            ),
            fg_color=self.accent_color,
            text_color="#000000",
            font=("Roboto", 14, "bold"),
        )
        self.btn_auto.pack(pady=10, padx=20, fill="x")

        self.btn_clear = ctk.CTkButton(
            self.sidebar,
            text="Clear All",
            command=self.clear_redactions,
            fg_color="transparent",
            border_width=1,
        )
        self.btn_clear.pack(pady=10, padx=20, fill="x")

        # Separatore
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#33334d").pack(
            fill="x", pady=20, padx=20
        )

        self.btn_export = ctk.CTkButton(
            self.sidebar,
            text="Forensic Export",
            command=self.export_pdf,
            fg_color=self.danger_color,
            hover_color="#c0392b",
        )
        self.btn_export.pack(side="bottom", pady=20, padx=20, fill="x")

        self.btn_about = ctk.CTkButton(
            self.sidebar, text="About", command=self.show_about, fg_color="transparent"
        )
        self.btn_about.pack(side="bottom", pady=5, padx=20, fill="x")

        # Area Centrale
        self.main_area = ctk.CTkFrame(self, fg_color=self.bg_color)
        self.main_area.pack(side="right", expand=True, fill="both")

        self.canvas = Canvas(self.main_area, bg="#0f0f1a", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both", padx=20, pady=20)

        self.log = ctk.CTkTextbox(
            self.main_area, height=120, fg_color=self.panel_color, font=("Consolas", 12)
        )
        self.log.pack(fill="x", padx=20, pady=(0, 20))

    def show_about(self):
        about = ctk.CTkToplevel(self)
        about.title("About NullifyPDF")
        w, h = 400, 550
        self.update_idletasks()
        x, y = self.winfo_x() + (self.winfo_width() // 2) - (w // 2), self.winfo_y() + (
            self.winfo_height() // 2
        ) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        self.apply_child_icon(about)

        # Immagine Logo Reale
        icon_path = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(icon_path):
            try:
                img_path = Image.open(icon_path)
                img_resized = img_path.resize((100, 100), Image.Resampling.LANCZOS)
                self.about_logo = ImageTk.PhotoImage(img_resized)
                logo_label = ctk.CTkLabel(about, image=self.about_logo, text="")
                logo_label.place(relx=0.5, y=80, anchor="center")
            except:
                pass

        ctk.CTkLabel(
            about, text="NullifyPDF", font=("Roboto", 28, "bold"), text_color="#ffffff"
        ).place(relx=0.5, y=165, anchor="center")
        ctk.CTkLabel(
            about,
            text=f"v{__version__} AI-Forensic",
            font=("Roboto", 16),
            text_color=self.accent_color,
        ).place(relx=0.5, y=200, anchor="center")

        info_text = (
            "Professional Forensic Anonymization Tool.\n\n"
            "Developed by: Graziano Mariella\n"
            "Email: graziano.mariella@carabinieri.it\n\n"
            "License: MIT License\n"
            "Copyright (c) 2026"
        )
        ctk.CTkLabel(
            about,
            text=info_text,
            font=("Roboto", 13),
            text_color="#a1a1aa",
            justify="center",
        ).place(relx=0.5, y=310, anchor="center")

        ctk.CTkLabel(
            about,
            text="github.com/graziano-mariella/NullifyPDF",
            font=("Roboto", 11),
            text_color=self.accent_color,
        ).place(relx=0.5, y=400, anchor="center")

        ctk.CTkButton(
            about,
            text="Close",
            width=150,
            fg_color=self.bg_color,
            command=about.destroy,
        ).place(relx=0.5, y=480, anchor="center")

    def render(self):
        if self.doc:
            page = self.doc[self.page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
            img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            self.img = ImageTk.PhotoImage(img_pil)

            self.canvas.delete("all")
            self.img_id = self.canvas.create_image(
                self.canvas.winfo_width() // 2, 20, anchor="n", image=self.img
            )
            self.write_log(f"Renderizzata pagina {self.page_num + 1}")

    def clear_redactions(self):
        self.redactions = {}
        self.render()
        self.write_log("Tutte le censure pianificate sono state rimosse.")

    def export_pdf(self):
        if not self.doc:
            return
        fp = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")]
        )
        if fp:
            try:
                # Logica di salvataggio forense...
                self.doc.save(fp, garbage=4, deflate=True, clean=True)
                self.write_log(f"Esportazione completata: {os.path.basename(fp)}")
            except Exception as e:
                self.write_log(f"Errore Esportazione: {e}")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.render()
            self.write_log(f"Documento caricato: {os.path.basename(path)}")

    def write_log(self, msg):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {msg}\n")
        self.log.see("end")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
