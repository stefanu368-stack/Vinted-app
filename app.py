"""
gui_app.py
-----------
Interfata grafica (Tkinter - vine cu Python, nu necesita instalare separata)
care leaga toate modulele:

  1. Tab "Analiza piata" - introduci ce vinzi -> aplicatia cauta pe Vinted
     articole similare, extrage tendinte si genereaza titlu + descriere.
  2. Tab "Poze studio" - alegi poze -> aplicatia le proceseaza (luminozitate,
     eliminare fundal, indreptare, fundal alb) si le salveaza intr-un folder.

Ruleaza cu:
    python gui_app.py
"""

from __future__ import annotations
import os
import threading
import traceback
from pathlib import Path
from tkinter import (
    Tk, StringVar, END, filedialog, messagebox, ttk, Text, BOTH, LEFT, RIGHT,
    Y, X, TOP, BOTTOM, N, S, E, W, DISABLED, NORMAL
)

from vinted_scraper import get_market_trends, TrendReport
from listing_generator import ItemInfo, generate_listing
from image_studio import enhance_photo


CONDITIONS = ["noua cu eticheta", "ca noua", "foarte buna", "buna", "satisfacatoare"]
GENDERS = ["", "barbati", "femei", "unisex", "copii"]


class VintedAssistantApp:
    def __init__(self, root: Tk):
        self.root = root
        self.root.title("Asistent Vinted - analiza piata & poze studio")
        self.root.geometry("880x640")

        self.last_trends: TrendReport | None = None
        self.selected_photos: list[str] = []

        notebook = ttk.Notebook(root)
        notebook.pack(fill=BOTH, expand=True, padx=10, pady=10)

        self.tab_listing = ttk.Frame(notebook)
        self.tab_photos = ttk.Frame(notebook)
        notebook.add(self.tab_listing, text="Analiza piata & Titlu/Descriere")
        notebook.add(self.tab_photos, text="Poze studio")

        self._build_listing_tab()
        self._build_photos_tab()

    # ------------------------------------------------------------------
    # TAB 1: Analiza piata + generare titlu/descriere
    # ------------------------------------------------------------------
    def _build_listing_tab(self):
        frame = self.tab_listing
        pad = {"padx": 8, "pady": 4}

        form = ttk.Frame(frame)
        form.pack(fill=X, **pad)

        self.var_category = StringVar()
        self.var_brand = StringVar()
        self.var_color = StringVar()
        self.var_size = StringVar()
        self.var_material = StringVar()
        self.var_condition = StringVar(value=CONDITIONS[2])
        self.var_gender = StringVar(value="")

        def add_row(label, widget, row):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky=W, **pad)
            widget.grid(row=row, column=1, sticky=W + E, **pad)

        form.columnconfigure(1, weight=1)

        add_row("Ce vinzi (categorie) *", ttk.Entry(form, textvariable=self.var_category), 0)
        add_row("Brand (optional)", ttk.Entry(form, textvariable=self.var_brand), 1)
        add_row("Culoare (optional)", ttk.Entry(form, textvariable=self.var_color), 2)
        add_row("Marime (optional)", ttk.Entry(form, textvariable=self.var_size), 3)
        add_row("Material (optional)", ttk.Entry(form, textvariable=self.var_material), 4)
        add_row("Stare", ttk.Combobox(form, textvariable=self.var_condition, values=CONDITIONS, state="readonly"), 5)
        add_row("Gen (optional)", ttk.Combobox(form, textvariable=self.var_gender, values=GENDERS), 6)

        self.btn_analyze = ttk.Button(frame, text="Analizeaza piata Vinted & genereaza titlu/descriere",
                                       command=self._on_analyze_clicked)
        self.btn_analyze.pack(pady=8)

        self.status_label = ttk.Label(frame, text="", foreground="#555")
        self.status_label.pack()

        results_frame = ttk.LabelFrame(frame, text="Rezultat")
        results_frame.pack(fill=BOTH, expand=True, padx=8, pady=8)

        ttk.Label(results_frame, text="Titlu generat:").pack(anchor=W, padx=6, pady=(6, 0))
        self.title_text = Text(results_frame, height=2, wrap="word")
        self.title_text.pack(fill=X, padx=6, pady=2)

        ttk.Label(results_frame, text="Descriere generata:").pack(anchor=W, padx=6, pady=(6, 0))
        self.desc_text = Text(results_frame, height=10, wrap="word")
        self.desc_text.pack(fill=BOTH, expand=True, padx=6, pady=2)

        self.price_label = ttk.Label(results_frame, text="Pret sugerat: -")
        self.price_label.pack(anchor=W, padx=6, pady=(2, 6))

    def _on_analyze_clicked(self):
        category = self.var_category.get().strip()
        if not category:
            messagebox.showwarning("Lipseste categoria", "Scrie mai intai ce vinzi (ex: 'geaca de piele barbati').")
            return

        self.btn_analyze.config(state=DISABLED)
        self.status_label.config(text="Se cauta pe Vinted si se analizeaza tendintele... (poate dura 5-15 secunde)")

        thread = threading.Thread(target=self._run_analysis, args=(category,), daemon=True)
        thread.start()

    def _run_analysis(self, category: str):
        try:
            trends = get_market_trends(category, per_page=40, max_pages=2)
        except Exception as e:
            self.root.after(0, self._on_analysis_error, e)
            return

        item = ItemInfo(
            category=category,
            brand=self.var_brand.get().strip() or None,
            color=self.var_color.get().strip() or None,
            size=self.var_size.get().strip() or None,
            material=self.var_material.get().strip() or None,
            condition=self.var_condition.get(),
            gender=self.var_gender.get().strip() or None,
        )
        listing = generate_listing(item, trends)
        self.root.after(0, self._on_analysis_done, trends, listing)

    def _on_analysis_done(self, trends: TrendReport, listing: dict):
        self.last_trends = trends
        self.btn_analyze.config(state=NORMAL)

        if trends.sample_size == 0:
            self.status_label.config(
                text="Nu am gasit anunturi (posibil Vinted a blocat cererea automata sau categoria e prea specifica). "
                     "Titlul/descrierea de mai jos sunt generate doar din datele introduse de tine."
            )
        else:
            self.status_label.config(
                text=f"Am analizat {trends.sample_size} anunturi similare. "
                     f"Pret mediu pe piata: {trends.avg_price:.0f} RON."
            )

        self.title_text.delete("1.0", END)
        self.title_text.insert("1.0", listing["title"])

        self.desc_text.delete("1.0", END)
        self.desc_text.insert("1.0", listing["description"])

        price_text = f"{listing['suggested_price']:.0f} RON" if listing["suggested_price"] else "-"
        self.price_label.config(text=f"Pret sugerat: {price_text}")

    def _on_analysis_error(self, error: Exception):
        self.btn_analyze.config(state=NORMAL)
        self.status_label.config(text="Eroare la conectarea cu Vinted (vezi detalii).")
        messagebox.showerror(
            "Eroare",
            f"Nu am putut analiza piata Vinted:\n{error}\n\n"
            "Cauze posibile: Vinted a blocat cererea automata, sau nu exista conexiune la internet.\n"
            "Poti totusi continua - titlul/descrierea se genereaza si fara date de piata."
        )
        print(traceback.format_exc())

    # ------------------------------------------------------------------
    # TAB 2: Procesare poze in stil studio
    # ------------------------------------------------------------------
    def _build_photos_tab(self):
        frame = self.tab_photos
        pad = {"padx": 8, "pady": 6}

        top = ttk.Frame(frame)
        top.pack(fill=X, **pad)

        ttk.Button(top, text="Alege poze...", command=self._choose_photos).pack(side=LEFT)
        self.photos_label = ttk.Label(top, text="Nicio poza selectata.")
        self.photos_label.pack(side=LEFT, padx=10)

        options = ttk.Frame(frame)
        options.pack(fill=X, **pad)
        ttk.Label(options, text="Fundal:").pack(side=LEFT)
        self.bg_choice = StringVar(value="alb")
        ttk.Combobox(
            options, textvariable=self.bg_choice, values=["alb", "gri clar"],
            state="readonly", width=12
        ).pack(side=LEFT, padx=6)

        self.btn_process = ttk.Button(frame, text="Transforma pozele in stil studio",
                                       command=self._on_process_clicked)
        self.btn_process.pack(pady=8)

        self.process_status = ttk.Label(frame, text="", foreground="#555")
        self.process_status.pack()

        info = (
            "Notă: se corectează automat luminozitatea/contrastul, se elimină fundalul, "
            "se îndreaptă și centrează articolul pe un fundal neutru.\n"
            "Repoziționarea completă a hainei (ex: transformare din 'pusă pe pat' în 'pe manechin') "
            "necesită AI generativ și nu este inclusă în acest pas automat."
        )
        ttk.Label(frame, text=info, wraplength=820, foreground="#777", justify=LEFT).pack(padx=8, pady=10)

    def _choose_photos(self):
        paths = filedialog.askopenfilenames(
            title="Alege poze",
            filetypes=[("Imagini", "*.jpg *.jpeg *.png *.webp")]
        )
        if paths:
            self.selected_photos = list(paths)
            self.photos_label.config(text=f"{len(paths)} poza(e) selectata(e).")

    def _on_process_clicked(self):
        if not self.selected_photos:
            messagebox.showwarning("Nicio poza", "Alege mai intai una sau mai multe poze.")
            return

        self.btn_process.config(state=DISABLED)
        self.process_status.config(text="Se proceseaza pozele...")

        thread = threading.Thread(target=self._run_processing, daemon=True)
        thread.start()

    def _run_processing(self):
        bg_color = (255, 255, 255) if self.bg_choice.get() == "alb" else (235, 235, 235)
        out_dir = Path.home() / "Desktop" / "poze_studio_vinted"
        if not out_dir.parent.exists():
            out_dir = Path.cwd() / "poze_studio_vinted"
        out_dir.mkdir(parents=True, exist_ok=True)

        results = []
        errors = []
        for path in self.selected_photos:
            try:
                name = Path(path).stem
                out_path = out_dir / f"{name}_studio.jpg"
                enhance_photo(path, str(out_path), bg_color=bg_color)
                results.append(str(out_path))
            except Exception as e:
                errors.append((path, str(e)))

        self.root.after(0, self._on_processing_done, results, errors, out_dir)

    def _on_processing_done(self, results, errors, out_dir):
        self.btn_process.config(state=NORMAL)
        msg = f"Am salvat {len(results)} poza(e) in:\n{out_dir}"
        if errors:
            msg += f"\n\n{len(errors)} poza(e) au dat eroare:\n"
            msg += "\n".join(f"- {Path(p).name}: {e}" for p, e in errors)
        self.process_status.config(text=f"Terminat. {len(results)} poza(e) salvata(e) in {out_dir}")
        messagebox.showinfo("Terminat", msg)


def main():
    root = Tk()
    app = VintedAssistantApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
