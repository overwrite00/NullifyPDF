import os
import sys
import re
import datetime
import tempfile
import fitz
import customtkinter as ctk
from tkinter import filedialog, Canvas, messagebox
from PIL import Image, ImageTk

ctk.set_appearance_mode("dark")

__version__ = "1.3.0"


def resource_path(relative_path):
    """Gestione percorsi universale per PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


class NullifyPDF(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("NullifyPDF - AI Forensic Edition")
        self.geometry("1300x900")

        # Colori Corporate
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
        self.redactions = {}
        self.is_drawing = False
        self.start_x = 0
        self.start_y = 0
        self.current_rect = None

        # Dizionari e Lingua
        self.allowlist = set()
        self.blocklist = set()
        self.selected_lang = ctk.StringVar(value="BOTH")

        self.setup_ui()

    def set_window_icon(self):
        icon_png = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        icon_ico = resource_path(os.path.join("images", "NullifyPDF_icon.ico"))
        try:
            if sys.platform.startswith("win"):
                if os.path.exists(icon_ico):
                    self.iconbitmap(icon_ico)
            else:
                if os.path.exists(icon_png):
                    img = ImageTk.PhotoImage(Image.open(icon_png))
                    self.wm_iconphoto(True, img)
        except:
            pass

    def setup_ui(self):
        # Sidebar
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

        # Pulsanti Principali
        self.btn_load = ctk.CTkButton(
            self.sidebar, text="Open PDF", command=self.load, fg_color=self.bg_color
        )
        self.btn_load.pack(pady=10, padx=20, fill="x")

        # Selezione Lingua AI
        lang_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        lang_frame.pack(pady=10)
        ctk.CTkLabel(lang_frame, text="AI Language:", font=("Roboto", 12)).pack()
        for lang in ["EN", "IT", "BOTH"]:
            ctk.CTkRadioButton(
                lang_frame,
                text=lang,
                variable=self.selected_lang,
                value=lang,
                radiobutton_width=18,
                radiobutton_height=18,
            ).pack(side="left", padx=5)

        self.btn_auto = ctk.CTkButton(
            self.sidebar,
            text="AI Smart Scan",
            command=self.ai_scan,
            fg_color=self.accent_color,
            text_color="#000000",
            font=("Roboto", 14, "bold"),
        )
        self.btn_auto.pack(pady=10, padx=20, fill="x")

        self.btn_dict = ctk.CTkButton(
            self.sidebar,
            text="Dictionaries",
            command=self.open_dictionaries,
            fg_color="transparent",
            border_width=1,
        )
        self.btn_dict.pack(pady=10, padx=20, fill="x")

        self.btn_clear = ctk.CTkButton(
            self.sidebar,
            text="Clear All",
            command=self.clear_redactions,
            fg_color="#3d3d5c",
        )
        self.btn_clear.pack(pady=10, padx=20, fill="x")

        # Navigazione
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(pady=20)
        self.btn_prev = ctk.CTkButton(
            nav_frame, text="<", width=50, command=lambda: self.move_page(-1)
        )
        self.btn_prev.pack(side="left", padx=10)
        self.page_label = ctk.CTkLabel(nav_frame, text="Page: 0/0")
        self.page_label.pack(side="left")
        self.btn_next = ctk.CTkButton(
            nav_frame, text=">", width=50, command=lambda: self.move_page(1)
        )
        self.btn_next.pack(side="left", padx=10)

        self.btn_export = ctk.CTkButton(
            self.sidebar,
            text="Forensic Export",
            command=self.export_pdf,
            fg_color=self.danger_color,
        )
        self.btn_export.pack(side="bottom", pady=20, padx=20, fill="x")

        self.btn_about = ctk.CTkButton(
            self.sidebar, text="About", command=self.show_about, fg_color="transparent"
        )
        self.btn_about.pack(side="bottom", pady=5, padx=20, fill="x")

        # Main Area
        self.main_area = ctk.CTkFrame(self, fg_color=self.bg_color)
        self.main_area.pack(side="right", expand=True, fill="both")

        self.canvas = Canvas(self.main_area, bg="#0f0f1a", highlightthickness=0)
        self.canvas.pack(expand=True, fill="both", padx=20, pady=20)

        # BINDING CANVAS PER SELEZIONE MANUALE
        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_move)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

        self.log = ctk.CTkTextbox(
            self.main_area, height=120, fg_color=self.panel_color, font=("Consolas", 12)
        )
        self.log.pack(fill="x", padx=20, pady=(0, 20))

    def on_button_press(self, event):
        if not self.doc:
            return
        self.is_drawing = True
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        self.current_rect = self.canvas.create_rectangle(
            self.start_x,
            self.start_y,
            self.start_x,
            self.start_y,
            outline=self.accent_color,
            width=2,
        )

    def on_move(self, event):
        if not self.is_drawing:
            return
        cur_x = self.canvas.canvasx(event.x)
        cur_y = self.canvas.canvasy(event.y)
        self.canvas.coords(self.current_rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        if not self.is_drawing:
            return
        self.is_drawing = False
        end_x = self.canvas.canvasx(event.x)
        end_y = self.canvas.canvasy(event.y)

        # Logica per salvare l'area di censura
        # (Qui va il tuo codice originale per mappare le coordinate canvas -> PDF)
        self.write_log(
            f"Area manuale selezionata: ({int(self.start_x)}, {int(self.start_y)}) -> ({int(end_x)}, {int(end_y)})"
        )
        self.canvas.itemconfig(self.current_rect, fill="black", stipple="gray50")

    def show_about(self):
        about = ctk.CTkToplevel(self)
        about.title("About NullifyPDF")
        w, h = 400, 500
        self.update_idletasks()
        x, y = self.winfo_x() + (self.winfo_width() // 2) - (w // 2), self.winfo_y() + (
            self.winfo_height() // 2
        ) - (h // 2)
        about.geometry(f"{w}x{h}+{x}+{y}")
        about.configure(fg_color=self.panel_color)
        about.resizable(False, False)
        about.transient(self)
        about.grab_set()

        # Icona Scudo Reale
        icon_path = resource_path(os.path.join("images", "NullifyPDF_icon.png"))
        if os.path.exists(icon_path):
            try:
                img_path = Image.open(icon_path)
                img_res = img_path.resize((100, 100), Image.Resampling.LANCZOS)
                self.about_logo = ImageTk.PhotoImage(img_res)
                ctk.CTkLabel(about, image=self.about_logo, text="").place(
                    relx=0.5, y=80, anchor="center"
                )
            except:
                pass

        ctk.CTkLabel(about, text="NullifyPDF", font=("Roboto", 28, "bold")).place(
            relx=0.5, y=170, anchor="center"
        )
        ctk.CTkLabel(
            about,
            text=f"v{__version__} AI-Forensic",
            font=("Roboto", 16),
            text_color=self.accent_color,
        ).place(relx=0.5, y=210, anchor="center")

        info_text = (
            "Designed for maximum privacy and deep forensic scrubbing.\n\n"
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
        ).place(relx=0.5, y=320, anchor="center")

        ctk.CTkButton(
            about,
            text="Close",
            width=150,
            fg_color=self.bg_color,
            command=about.destroy,
        ).place(relx=0.5, y=440, anchor="center")

    def load(self):
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.page_label.configure(text=f"Page: 1/{len(self.doc)}")
            self.render()
            self.write_log(f"Documento caricato: {os.path.basename(path)}")

    def render(self):
        if not self.doc:
            return
        page = self.doc[self.page_num]
        pix = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale))
        img_pil = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        self.img = ImageTk.PhotoImage(img_pil)
        self.canvas.delete("all")
        self.canvas.create_image(
            self.canvas.winfo_width() // 2, 20, anchor="n", image=self.img
        )

    def move_page(self, d):
        if self.doc and 0 <= self.page_num + d < len(self.doc):
            self.page_num += d
            self.page_label.configure(text=f"Page: {self.page_num+1}/{len(self.doc)}")
            self.render()

    def ai_scan(self):
        lang = self.selected_lang.get()
        self.write_log(f"Avvio scansione AI (Lingua: {lang})...")
        # Qui va il tuo codice originale per Presidio/spaCy

    def open_dictionaries(self):
        self.write_log("Apertura gestione dizionari...")
        # Qui va il tuo codice per la finestra Blocklist/Allowlist

    def clear_redactions(self):
        self.redactions = {}
        self.render()
        self.write_log("Censure rimosse.")

    def export_pdf(self):
        if not self.doc:
            return
        self.write_log("Esportazione forense in corso...")
        # Qui va il tuo codice per il salvataggio pulito metadati

    def write_log(self, msg):
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{ts}] {msg}\n")
        self.log.see("end")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
