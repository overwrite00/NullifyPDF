import os
import re
import datetime
import fitz
import customtkinter as ctk
from tkinter import filedialog, Canvas
from PIL import Image, ImageTk


class NullifyPDF(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NullifyPDF - Secure Anonymization Tool")
        self.geometry("1200x900")

        # Color Palette (Dark Professional Style)
        self.bg_color = "#141526"
        self.panel_color = "#1e1f31"
        self.accent_color = "#1fb2e0"
        self.hover_color = "#178cae"
        self.danger_color = "#e74c3c"

        self.configure(fg_color=self.bg_color)

        # Document state variables
        self.doc = None
        self.page_num = 0
        self.scale = 1.5
        self.start_xy = None
        self.img_id = None
        self.offset_x = 0
        self.offset_y = 0
        self.rect_id = None  # ID for the visual selection rectangle

        self.build_ui()

    def build_ui(self):
        # --- TOP TOOLBAR ---
        toolbar = ctk.CTkFrame(self, fg_color=self.panel_color, corner_radius=8)
        toolbar.pack(fill="x", padx=15, pady=15)

        ctk.CTkButton(
            toolbar,
            text="Open Document",
            font=("Roboto", 14, "bold"),
            fg_color=self.accent_color,
            hover_color=self.hover_color,
            text_color="#ffffff",
            command=self.load,
        ).pack(side="left", padx=15, pady=15)
        self.kw = ctk.CTkEntry(
            toolbar,
            placeholder_text="Specific word to redact...",
            width=220,
            fg_color=self.bg_color,
            border_color="#333344",
        )
        self.kw.pack(side="left", padx=5)
        ctk.CTkButton(
            toolbar,
            text="Redact Data (Auto)",
            font=("Roboto", 13, "bold"),
            fg_color=self.danger_color,
            hover_color="#c0392b",
            text_color="#ffffff",
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

        # Navigation
        nav = ctk.CTkFrame(toolbar, fg_color="transparent")
        nav.pack(side="right", padx=15)
        ctk.CTkButton(
            nav,
            text="<",
            width=35,
            fg_color=self.bg_color,
            hover_color="#333344",
            command=lambda: self.move_page(-1),
        ).pack(side="left", padx=5)
        self.p_lab = ctk.CTkLabel(
            nav, text="Page: 0 / 0", font=("Roboto", 14, "bold"), text_color="#ffffff"
        )
        self.p_lab.pack(side="left", padx=10)
        ctk.CTkButton(
            nav,
            text=">",
            width=35,
            fg_color=self.bg_color,
            hover_color="#333344",
            command=lambda: self.move_page(1),
        ).pack(side="left", padx=5)

        # --- SCROLLABLE VIEWPORT ---
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

        # Canvas with crosshair cursor
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

        # Event binding
        self.canvas.bind("<Configure>", self.center_image)
        self.canvas.bind("<ButtonPress-1>", self.on_mouse_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_release)
        self.canvas.bind_all(
            "<MouseWheel>",
            lambda e: self.canvas.yview_scroll(int(-1 * (e.delta / 120)), "units"),
        )

        # --- FOOTER ---
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
        self.write_log("System initialized. Waiting for a document...")

    def write_log(self, msg):
        """Adds messages to the terminal log with a timestamp."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log.insert("end", f"[{timestamp}] {msg}\n")
        self.log.see("end")

    def load(self):
        """Loads the PDF and initializes the first page."""
        path = filedialog.askopenfilename(filetypes=[("PDF Documents", "*.pdf")])
        if path:
            self.doc = fitz.open(path)
            self.page_num = 0
            self.render()
            self.write_log(f"Document loaded: {os.path.basename(path)}")

    def render(self):
        """Extracts the page, converts it to an image, and displays it on the Canvas."""
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
        """Calculates document centering and offsets for mouse coordinates."""
        if not self.doc or not hasattr(self, "img"):
            return
        self.canvas.update_idletasks()
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        iw, ih = self.img.width(), self.img.height()

        x = cw // 2 if cw > iw else iw // 2
        y = ch // 2 if ch > ih else ih // 2

        self.canvas.coords(self.img_id, x, y)
        self.canvas.config(scrollregion=self.canvas.bbox("all"))

        self.offset_x = x - (iw // 2)
        self.offset_y = y - (ih // 2)

    def move_page(self, direction):
        """Changes page while preventing out-of-bounds navigation."""
        if self.doc and 0 <= self.page_num + direction < len(self.doc):
            self.page_num += direction
            self.render()

    def auto_anon(self):
        """Automatic redaction via Regex (Email, SSN/Tax ID) and manual keyword."""
        if not self.doc:
            return
        patterns = [r"[\w\.-]+@[\w\.-]+", r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]"]
        self.write_log("Analysis and redaction in progress...")

        for i, page in enumerate(self.doc):
            matches = set(
                re.findall(patterns[0], page.get_text())
                + re.findall(patterns[1], page.get_text())
            )
            if self.kw.get():
                matches.add(self.kw.get())
            for match in matches:
                [
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    for rect in page.search_for(match)
                ]
            page.apply_redactions()
            self.prog.set((i + 1) / len(self.doc))
            self.update_idletasks()

        self.render()
        self.write_log("Operation completed. Data irreversibly redacted.")

    def on_mouse_press(self, event):
        """Saves the starting point and creates an empty selection rectangle."""
        if not self.doc:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.start_xy = (x, y)

        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            x, y, x, y, outline=self.danger_color, width=2, dash=(4, 4)
        )

    def on_mouse_drag(self, event):
        """Updates the rectangle coordinates while the user drags the mouse."""
        if not self.doc or not self.start_xy or not self.rect_id:
            return
        x, y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.canvas.coords(self.rect_id, self.start_xy[0], self.start_xy[1], x, y)

    def on_mouse_release(self, event):
        """Applies the actual redaction when the user releases the button."""
        if not self.doc or not self.start_xy:
            return

        end_x, end_y = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # Prevent accidental clicks (selections that are too small)
        if abs(end_x - self.start_xy[0]) < 5 or abs(end_y - self.start_xy[1]) < 5:
            if self.rect_id:
                self.canvas.delete(self.rect_id)
            self.start_xy = None
            return

        sx_rel, sy_rel = (
            self.start_xy[0] - self.offset_x,
            self.start_xy[1] - self.offset_y,
        )
        ex_rel, ey_rel = end_x - self.offset_x, end_y - self.offset_y

        x0, x1 = sorted([sx_rel, ex_rel])
        y0, y1 = sorted([sy_rel, ey_rel])

        rect = fitz.Rect(
            x0 / self.scale, y0 / self.scale, x1 / self.scale, y1 / self.scale
        )
        self.doc[self.page_num].add_redact_annot(rect, fill=(0, 0, 0))
        self.doc[self.page_num].apply_redactions()

        self.start_xy = None
        self.render()
        self.write_log(f"Manual redaction applied to page {self.page_num + 1}.")

    def save(self):
        """Exports the file, stripping metadata and compressing the PDF."""
        if not self.doc:
            self.write_log("Error: No document loaded.")
            return

        suggested_name = (
            f"{os.path.splitext(os.path.basename(self.doc.name))[0]}_nullified.pdf"
        )
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=suggested_name,
            filetypes=[("PDF Document", "*.pdf")],
        )
        if file_path:
            try:
                self.doc.save(file_path, garbage=4, deflate=True)
                self.write_log(f"Success: File saved as {os.path.basename(file_path)}")
            except Exception as e:
                self.write_log(f"Error during saving: {e}")


if __name__ == "__main__":
    app = NullifyPDF()
    app.mainloop()
