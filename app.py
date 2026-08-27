"""Assinador de PDFs por imagem — Prefeitura de Imperatriz.

Esta aplicação insere uma imagem de assinatura em um ou vários PDFs. Ela não
gera uma assinatura digital criptográfica/certificada (ICP-Brasil).
"""

from __future__ import annotations

import json
import queue
import re
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import Request, urlopen

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image, ImageTk
from tkinter import Canvas, Menu, filedialog, messagebox


APP_DIR = Path(__file__).resolve().parent
# PyInstaller extrai os recursos em uma pasta temporária (_MEIPASS). Em modo
# desenvolvimento, os arquivos continuam sendo lidos diretamente do projeto.
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DEFAULT_OUTPUT_NAME = "pdfs_assinados"
MM_TO_POINTS = 72 / 25.4
APP_VERSION = "1.0.4"
GITHUB_REPOSITORY = "pm-itz/assinapdf"
UPDATE_ASSET_NAME = "AssinaPDF-Setup.exe"
LATEST_RELEASE_API = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"

APP_BACKGROUND = ("#F3F6FA", "#111827")
CARD_BACKGROUND = ("#FFFFFF", "#1F2937")
CARD_BORDER = ("#D9E1EC", "#3A475A")
PRIMARY_TEXT = ("#153B82", "#A9CBFF")
SECONDARY_TEXT = ("#4B5B70", "#CBD5E1")
HELP_TEXT = ("#6A778B", "#AEBACB")
MANUAL_BACKGROUND = ("#EDF3FC", "#263A56")


class AssinadorPMI(ctk.CTk):
    """Janela principal e fluxo de assinatura em lote."""

    def __init__(self) -> None:
        super().__init__()
        # A janela permanece invisível enquanto a interface é montada e já
        # recebe o estado maximizado antes de aparecer na tela.
        self.withdraw()
        self.title("Assinador de PDFs | Prefeitura de Imperatriz")
        self.geometry("1060x760")
        self.minsize(920, 650)
        self.configure(fg_color=APP_BACKGROUND)

        self.pdfs: list[Path] = []
        self.signature_path: Path | None = None
        self.output_dir: Path | None = None
        self.manual_positions: dict[str, tuple[float, float]] = {}
        self.manual_widths: dict[str, float] = {}
        self.shared_manual_position: tuple[float, float] | None = None
        self.shared_manual_width: float | None = None
        self.is_processing = False
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.logo_image: ctk.CTkImage | None = None

        self.position_var = ctk.StringVar(value="Inferior direita")
        self.theme_var = ctk.StringVar(value="Claro")
        self.manual_enabled_var = ctk.BooleanVar(value=False)
        self.shared_manual_var = ctk.BooleanVar(value=True)
        self.pages_var = ctk.StringVar(value="Última página")
        self.width_var = ctk.StringVar(value="45")
        self.margin_var = ctk.StringVar(value="12")
        self.status_var = ctk.StringVar(value="Pronto para selecionar documentos.")
        self.pdf_count_var = ctk.StringVar(value="Nenhum PDF selecionado")
        self.signature_label_var = ctk.StringVar(value="Nenhuma imagem selecionada")
        self.output_label_var = ctk.StringVar(value="Será criada junto aos PDFs")

        self._build_interface()
        self._set_window_icon()
        self._build_menu()
        self._maximize_window()
        self.deiconify()
        self.after(120, self._process_events)

    def _maximize_window(self) -> None:
        """Inicia ocupando toda a área útil da tela e mantém a barra de título."""
        try:
            if sys.platform.startswith("win"):
                self.state("zoomed")
            else:
                self.attributes("-zoomed", True)  # Linux
        except Exception:
            pass

    def _change_theme(self, value: str) -> None:
        ctk.set_appearance_mode("dark" if value == "Escuro" else "light")

    def _build_menu(self) -> None:
        menu_bar = Menu(self)
        help_menu = Menu(menu_bar, tearoff=0)
        help_menu.add_command(label="Verificar atualizações", command=self._check_for_updates)
        help_menu.add_separator()
        help_menu.add_command(
            label="Sobre o AssinaPDF",
            command=lambda: messagebox.showinfo(
                "Sobre o AssinaPDF", f"AssinaPDF\nPrefeitura Municipal de Imperatriz\nVersão {APP_VERSION}", parent=self
            ),
        )
        menu_bar.add_cascade(label="Ajuda", menu=help_menu)
        self.configure(menu=menu_bar)

    def _set_window_icon(self) -> None:
        """Usa a marca institucional tanto no código-fonte quanto no .exe."""
        icon_path = BUNDLE_DIR / "assets" / "imperatriz.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                pass

    def _build_interface(self) -> None:
        header = ctk.CTkFrame(self, height=128, corner_radius=0, fg_color="#153B82")
        header.pack(fill="x")
        header.pack_propagate(False)

        self._add_logo(header)
        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", fill="both", expand=True, padx=(4, 30), pady=22)
        ctk.CTkLabel(
            title_frame,
            text="ASSINADOR DE PDFs",
            font=ctk.CTkFont(size=27, weight="bold"),
            text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text="Prefeitura Municipal de Imperatriz",
            font=ctk.CTkFont(size=15),
            text_color="#DCE7FF",
        ).pack(anchor="w", pady=(3, 0))
        ctk.CTkOptionMenu(
            header,
            values=["Claro", "Escuro"],
            variable=self.theme_var,
            command=self._change_theme,
            width=118,
            height=34,
            fg_color="#0D2F6C",
            button_color="#0A285B",
            button_hover_color="#071E45",
        ).pack(side="right", padx=28, pady=47)

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=28, pady=24)
        main.grid_columnconfigure(0, weight=3)
        main.grid_columnconfigure(1, weight=2)
        main.grid_rowconfigure(1, weight=1)

        documents = self._card(main, "1. Documentos PDF")
        documents.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 12))
        self._build_document_section(documents)

        signature = self._card(main, "2. Imagem da assinatura")
        signature.grid(row=0, column=1, sticky="new", padx=(12, 0), pady=(0, 12))
        self._build_signature_section(signature)

        settings = self._card(main, "3. Posicionamento")
        settings.grid(row=1, column=1, sticky="new", padx=(12, 0))
        self._build_settings_section(settings)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=28, pady=(0, 22))
        ctk.CTkLabel(
            footer,
            textvariable=self.status_var,
            font=ctk.CTkFont(size=13),
            text_color=SECONDARY_TEXT,
        ).pack(side="left")
        self.sign_button = ctk.CTkButton(
            footer,
            text="ASSINAR PDFs",
            height=44,
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#00A650",
            hover_color="#008A42",
            command=self._start_signing,
        )
        self.sign_button.pack(side="right")

    def _add_logo(self, parent: ctk.CTkFrame) -> None:
        logo_path = BUNDLE_DIR / "assets" / "logo_pmi_branca_3.png"
        if not logo_path.exists():
            logo_path = None
        if logo_path:
            try:
                image = Image.open(logo_path)
                self.logo_image = ctk.CTkImage(light_image=image, dark_image=image, size=(245, 88))
                ctk.CTkLabel(parent, text="", image=self.logo_image).pack(side="left", padx=(28, 18), pady=18)
                return
            except OSError:
                pass
        ctk.CTkLabel(
            parent, text="IMPERATRIZ", font=ctk.CTkFont(size=24, weight="bold"), text_color="white"
        ).pack(side="left", padx=(28, 18))

    @staticmethod
    def _card(parent: ctk.CTkFrame, title: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color=CARD_BACKGROUND, border_width=1, border_color=CARD_BORDER)
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color=PRIMARY_TEXT
        ).pack(anchor="w", padx=20, pady=(17, 10))
        return card

    def _build_document_section(self, parent: ctk.CTkFrame) -> None:
        buttons = ctk.CTkFrame(parent, fg_color="transparent")
        buttons.pack(fill="x", padx=20)
        ctk.CTkButton(buttons, text="Selecionar PDFs", command=self._choose_pdfs).pack(side="left")
        ctk.CTkButton(
            buttons, text="Selecionar pasta", fg_color="#5C6B80", hover_color="#475568", command=self._choose_folder
        ).pack(side="left", padx=9)
        ctk.CTkButton(
            buttons, text="Limpar", width=75, fg_color="transparent", text_color=PRIMARY_TEXT, border_width=1,
            border_color=PRIMARY_TEXT, command=self._clear_pdfs
        ).pack(side="right")

        ctk.CTkLabel(parent, textvariable=self.pdf_count_var, text_color=SECONDARY_TEXT).pack(anchor="w", padx=20, pady=(12, 6))
        self.pdf_list = ctk.CTkTextbox(parent, height=310, font=ctk.CTkFont(size=12), wrap="none")
        self.pdf_list.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        self.pdf_list.configure(state="disabled")

        ctk.CTkLabel(parent, text="Pasta de saída", font=ctk.CTkFont(size=13, weight="bold"), text_color=PRIMARY_TEXT).pack(
            anchor="w", padx=20
        )
        output_row = ctk.CTkFrame(parent, fg_color="transparent")
        output_row.pack(fill="x", padx=20, pady=(5, 17))
        ctk.CTkLabel(output_row, textvariable=self.output_label_var, anchor="w", text_color=SECONDARY_TEXT).pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(output_row, text="Alterar", width=84, command=self._choose_output).pack(side="right")

    def _build_signature_section(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            parent,
            text="Escolha PNG, JPG ou JPEG com a assinatura.",
            text_color=SECONDARY_TEXT,
            wraplength=320,
            justify="left",
        ).pack(anchor="w", padx=20)
        ctk.CTkButton(parent, text="Escolher imagem", command=self._choose_signature).pack(anchor="w", padx=20, pady=12)
        ctk.CTkLabel(
            parent, textvariable=self.signature_label_var, text_color=PRIMARY_TEXT, wraplength=320, justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 18))

    def _build_settings_section(self, parent: ctk.CTkFrame) -> None:
        fields = ctk.CTkFrame(parent, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(0, 8))
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(1, weight=1)

        self._option_field(fields, "Posição padrão", self.position_var, [
            "Inferior direita", "Inferior esquerda", "Superior direita", "Superior esquerda", "Centro"
        ], 0, 0)
        self._option_field(fields, "Aplicar em", self.pages_var, ["Última página", "Primeira página", "Todas as páginas"], 0, 1)
        self._entry_field(fields, "Largura (mm)", self.width_var, 1, 0)
        self._entry_field(fields, "Margem (mm)", self.margin_var, 1, 1)

        ctk.CTkButton(
            parent,
            text="Pré-visualizar posição padrão",
            fg_color="transparent",
            text_color=PRIMARY_TEXT,
            border_width=1,
            border_color=PRIMARY_TEXT,
            command=self._open_predefined_preview,
        ).pack(anchor="w", padx=20, pady=(5, 10))

        manual_box = ctk.CTkFrame(parent, fg_color=MANUAL_BACKGROUND, corner_radius=8)
        manual_box.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkSwitch(
            manual_box,
            text="Quero ajustar a posição manualmente",
            variable=self.manual_enabled_var,
            command=self._toggle_manual_controls,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=PRIMARY_TEXT,
        ).pack(anchor="w", padx=12, pady=(10, 4))
        ctk.CTkLabel(
            manual_box,
            text="Use somente quando a posição padrão não for suficiente.",
            text_color=SECONDARY_TEXT,
            font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=12)
        self.manual_controls = ctk.CTkFrame(manual_box, fg_color="transparent")
        ctk.CTkButton(
            self.manual_controls,
            text="Abrir prévia e ajustar",
            fg_color="#5C6B80",
            hover_color="#475568",
            command=self._open_manual_editor,
        ).pack(anchor="w", pady=(8, 3))
        self.manual_controls.pack_forget()
        ctk.CTkLabel(
            parent,
            text="A assinatura é inserida como imagem visível. Para assinaturas certificadas, use um certificado digital apropriado.",
            text_color=HELP_TEXT, justify="left", wraplength=330, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=20, pady=(3, 17))

    @staticmethod
    def _option_field(parent: ctk.CTkFrame, label: str, variable: ctk.StringVar, values: list[str], row: int, column: int) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=6)
        ctk.CTkLabel(holder, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color=SECONDARY_TEXT).pack(anchor="w")
        ctk.CTkOptionMenu(holder, values=values, variable=variable, height=33).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _entry_field(parent: ctk.CTkFrame, label: str, variable: ctk.StringVar, row: int, column: int) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=6)
        ctk.CTkLabel(holder, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color=SECONDARY_TEXT).pack(anchor="w")
        ctk.CTkEntry(holder, textvariable=variable, height=33).pack(fill="x", pady=(4, 0))

    def _choose_pdfs(self) -> None:
        files = filedialog.askopenfilenames(title="Selecione os PDFs", filetypes=[("Arquivos PDF", "*.pdf")])
        self._set_pdfs([Path(file) for file in files])

    def _choose_folder(self) -> None:
        folder = filedialog.askdirectory(title="Selecione a pasta com PDFs")
        if folder:
            self._set_pdfs(sorted(Path(folder).glob("*.pdf"), key=lambda item: item.name.lower()))

    def _set_pdfs(self, paths: Iterable[Path]) -> None:
        self.pdfs = list(dict.fromkeys(path.resolve() for path in paths if path.suffix.lower() == ".pdf"))
        selected = {str(path) for path in self.pdfs}
        self.manual_positions = {path: point for path, point in self.manual_positions.items() if path in selected}
        self.manual_widths = {path: width for path, width in self.manual_widths.items() if path in selected}
        if self.pdfs and self.output_dir is None:
            self.output_label_var.set(str(self.pdfs[0].parent / DEFAULT_OUTPUT_NAME))
        self._update_pdf_list()

    def _clear_pdfs(self) -> None:
        self.pdfs.clear()
        self._update_pdf_list()

    def _update_pdf_list(self) -> None:
        self.pdf_count_var.set(f"{len(self.pdfs)} PDF(s) selecionado(s)")
        self.pdf_list.configure(state="normal")
        self.pdf_list.delete("1.0", "end")
        self.pdf_list.insert("end", "\n".join(path.name for path in self.pdfs) or "A lista de documentos aparecerá aqui.")
        self.pdf_list.configure(state="disabled")

    def _choose_signature(self) -> None:
        filename = filedialog.askopenfilename(
            title="Escolha a imagem da assinatura", filetypes=[("Imagens", "*.png *.jpg *.jpeg"), ("Todos os arquivos", "*.*")]
        )
        if filename:
            self.signature_path = Path(filename)
            self.signature_label_var.set(self.signature_path.name)

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title="Escolha a pasta de saída")
        if folder:
            self.output_dir = Path(folder)
            self.output_label_var.set(str(self.output_dir))

    def _toggle_manual_controls(self) -> None:
        if self.manual_enabled_var.get():
            self.manual_controls.pack(fill="x", padx=12, pady=(0, 10))
        else:
            self.manual_controls.pack_forget()

    def _is_shared_manual_mode(self) -> bool:
        return self.shared_manual_var.get()

    def _start_signing(self) -> None:
        if self.is_processing:
            return
        if not self.pdfs:
            messagebox.showwarning("Documentos", "Selecione pelo menos um arquivo PDF.")
            return
        if not self.signature_path or not self.signature_path.exists():
            messagebox.showwarning("Assinatura", "Selecione uma imagem de assinatura válida.")
            return
        dimensions = self._read_dimensions()
        if dimensions is None:
            return
        width_mm, margin_mm = dimensions

        manual_mode = self.manual_enabled_var.get()
        if manual_mode:
            if self._is_shared_manual_mode():
                missing = [] if self.shared_manual_position is not None else self.pdfs
            else:
                missing = [path for path in self.pdfs if str(path) not in self.manual_positions]
            if missing:
                instructions = (
                    "Escolha uma posição e um tamanho que serão aplicados a todos os PDFs na prévia que será aberta."
                    if self._is_shared_manual_mode()
                    else "Escolha a posição da assinatura para cada PDF na janela que será aberta."
                )
                messagebox.showinfo(
                    "Definir posições",
                    instructions + " Depois, clique em ASSINAR PDFs novamente.",
                )
                self._open_manual_editor()
                return

        if manual_mode and self._is_shared_manual_mode():
            manual_positions = {str(path): self.shared_manual_position for path in self.pdfs}
            manual_widths = {str(path): self.shared_manual_width for path in self.pdfs if self.shared_manual_width}
        else:
            manual_positions = dict(self.manual_positions)
            manual_widths = dict(self.manual_widths)

        output = self.output_dir or (self.pdfs[0].parent / DEFAULT_OUTPUT_NAME)
        self.is_processing = True
        self.sign_button.configure(state="disabled", text="ASSINANDO...")
        self.status_var.set("Processando documentos...")
        config = (
            list(self.pdfs), self.signature_path, output, width_mm, margin_mm,
            "Manual por PDF" if manual_mode else self.position_var.get(), self.pages_var.get(), manual_positions, manual_widths,
        )
        threading.Thread(target=self._sign_batch, args=config, daemon=True).start()

    def _read_dimensions(self) -> tuple[float, float] | None:
        try:
            width_mm = float(self.width_var.get().replace(",", "."))
            margin_mm = float(self.margin_var.get().replace(",", "."))
            if width_mm <= 0 or margin_mm < 0:
                raise ValueError
            return width_mm, margin_mm
        except ValueError:
            messagebox.showwarning("Medidas", "Informe largura maior que zero e margem igual ou maior que zero.")
            return None

    def _open_manual_editor(self) -> None:
        if not self.pdfs:
            messagebox.showwarning("Documentos", "Selecione pelo menos um arquivo PDF antes de definir as posições.")
            return
        if not self.signature_path or not self.signature_path.exists():
            messagebox.showwarning("Assinatura", "Selecione uma imagem de assinatura antes de definir as posições.")
            return
        dimensions = self._read_dimensions()
        if dimensions is None:
            return
        self.manual_enabled_var.set(True)
        self._toggle_manual_controls()
        ManualPositionEditor(self, self.pdfs, self.signature_path, *dimensions, shared=self._is_shared_manual_mode())

    def _open_predefined_preview(self) -> None:
        if not self.pdfs:
            messagebox.showwarning("Documentos", "Selecione pelo menos um arquivo PDF antes de abrir a prévia.")
            return
        if not self.signature_path or not self.signature_path.exists():
            messagebox.showwarning("Assinatura", "Selecione uma imagem de assinatura antes de abrir a prévia.")
            return
        dimensions = self._read_dimensions()
        if dimensions is None:
            return
        PositionPreview(self, self.pdfs, self.signature_path, *dimensions, self.position_var.get())

    def _sign_batch(
        self, pdfs: list[Path], signature: Path, output_dir: Path, width_mm: float, margin_mm: float, position: str,
        pages: str, manual_positions: dict[str, tuple[float, float]], manual_widths: dict[str, float],
    ) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        successes: list[str] = []
        failures: list[str] = []
        try:
            with Image.open(signature) as image:
                image_width, image_height = image.size
            if not image_width or not image_height:
                raise ValueError("A imagem de assinatura está vazia.")
            aspect_ratio = image_height / image_width
            for index, pdf_path in enumerate(pdfs, start=1):
                self.event_queue.put(("progress", f"Assinando {index}/{len(pdfs)}: {pdf_path.name}"))
                try:
                    destination = self._available_destination(pdf_path, output_dir)
                    signature_width = manual_widths.get(str(pdf_path.resolve()), width_mm) if position == "Manual por PDF" else width_mm
                    self._sign_pdf(
                        pdf_path, signature, destination, signature_width, margin_mm, aspect_ratio, position, pages,
                        manual_positions.get(str(pdf_path.resolve())),
                    )
                    successes.append(pdf_path.name)
                except Exception as error:  # continua o lote mesmo se um PDF falhar
                    failures.append(f"{pdf_path.name}: {error}")
        except Exception as error:
            failures.append(str(error))
        self.event_queue.put(("done", (output_dir, successes, failures)))

    @staticmethod
    def _available_destination(source: Path, output_dir: Path) -> Path:
        """Retorna um nome livre, sem permitir sobrescrever um PDF de entrada."""
        candidate = output_dir / source.name
        if candidate.resolve() == source.resolve() or candidate.exists():
            candidate = output_dir / f"{source.stem}_assinado.pdf"
        index = 2
        while candidate.exists() or candidate.resolve() == source.resolve():
            candidate = output_dir / f"{source.stem}_assinado_{index}.pdf"
            index += 1
        return candidate

    @staticmethod
    def _sign_pdf(
        source: Path, signature: Path, destination: Path, width_mm: float, margin_mm: float, aspect_ratio: float,
        position: str, pages: str, manual_position: tuple[float, float] | None = None,
    ) -> None:
        width = width_mm * MM_TO_POINTS
        height = width * aspect_ratio
        margin = margin_mm * MM_TO_POINTS
        document = fitz.open(source)
        try:
            if document.page_count == 0:
                raise ValueError("PDF sem páginas")
            page_numbers = {
                "Última página": [document.page_count - 1],
                "Primeira página": [0],
                "Todas as páginas": list(range(document.page_count)),
            }[pages]
            for page_number in page_numbers:
                page = document[page_number]
                rectangle = AssinadorPMI._signature_rectangle(page.rect, width, height, margin, position, manual_position)
                page.insert_image(rectangle, filename=str(signature), keep_proportion=True, overlay=True)
            document.save(destination, garbage=4, deflate=True)
        finally:
            document.close()

    @staticmethod
    def _signature_rectangle(
        page: fitz.Rect, width: float, height: float, margin: float, position: str,
        manual_position: tuple[float, float] | None = None,
    ) -> fitz.Rect:
        # Mantém a imagem inteiramente na página mesmo em PDFs pequenos.
        available_width = max(1, page.width - 2 * margin)
        available_height = max(1, page.height - 2 * margin)
        scale = min(1, available_width / width, available_height / height)
        width *= scale
        height *= scale
        horizontal_margin = min(margin, max(0, (page.width - width) / 2))
        vertical_margin = min(margin, max(0, (page.height - height) / 2))
        if position == "Manual por PDF" and manual_position is not None:
            x0 = page.x0 + manual_position[0] * page.width
            y0 = page.y0 + manual_position[1] * page.height
            x0 = min(max(x0, page.x0), page.x1 - width)
            y0 = min(max(y0, page.y0), page.y1 - height)
        elif position == "Inferior direita":
            x0, y0 = page.x1 - horizontal_margin - width, page.y1 - vertical_margin - height
        elif position == "Inferior esquerda":
            x0, y0 = page.x0 + horizontal_margin, page.y1 - vertical_margin - height
        elif position == "Superior direita":
            x0, y0 = page.x1 - horizontal_margin - width, page.y0 + vertical_margin
        elif position == "Superior esquerda":
            x0, y0 = page.x0 + horizontal_margin, page.y0 + vertical_margin
        else:
            x0, y0 = page.x0 + (page.width - width) / 2, page.y0 + (page.height - height) / 2
        return fitz.Rect(x0, y0, x0 + width, y0 + height)

    @staticmethod
    def _version_key(version: str) -> tuple[int, ...]:
        """Compara versões simples como 1.2.0 ou v1.2.0 sem nova dependência."""
        numbers = [int(value) for value in re.findall(r"\d+", version)]
        return tuple((numbers + [0, 0, 0, 0])[:4])

    def _check_for_updates(self) -> None:
        if not sys.platform.startswith("win"):
            messagebox.showinfo(
                "Atualizações",
                "A atualização automática instala o pacote do Windows. No Linux, atualize o aplicativo pela versão distribuída para esse sistema.",
                parent=self,
            )
            return
        self.status_var.set("Verificando atualizações...")
        threading.Thread(target=self._fetch_latest_release, daemon=True).start()

    def _fetch_latest_release(self) -> None:
        try:
            request = Request(LATEST_RELEASE_API, headers={"Accept": "application/vnd.github+json", "User-Agent": "AssinaPDF"})
            with urlopen(request, timeout=15) as response:
                release = json.load(response)
            version = str(release.get("tag_name", "")).lstrip("vV")
            if not version:
                raise ValueError("A Release mais recente não possui uma versão válida.")
            if self._version_key(version) <= self._version_key(APP_VERSION):
                self.event_queue.put(("update_current", version))
                return
            asset = next((item for item in release.get("assets", []) if item.get("name") == UPDATE_ASSET_NAME), None)
            if not asset:
                raise ValueError(f"A Release {version} não possui o arquivo {UPDATE_ASSET_NAME}.")
            download_url = str(asset.get("browser_download_url", ""))
            trusted_prefix = f"https://github.com/{GITHUB_REPOSITORY}/"
            if not download_url.startswith(trusted_prefix):
                raise ValueError("O endereço do instalador não pertence ao repositório oficial.")
            self.event_queue.put(("update_available", (version, download_url)))
        except (OSError, URLError, ValueError, json.JSONDecodeError) as error:
            self.event_queue.put(("update_error", str(error)))

    def _offer_update(self, version: str, download_url: str) -> None:
        self.status_var.set(f"Atualização {version} disponível.")
        if messagebox.askyesno(
            "Atualização disponível",
            f"A versão {version} está disponível.\n\nDeseja baixar e instalar agora?",
            parent=self,
        ):
            self.status_var.set("Baixando atualização...")
            threading.Thread(target=self._download_update, args=(version, download_url), daemon=True).start()

    def _download_update(self, version: str, download_url: str) -> None:
        try:
            destination = Path(tempfile.gettempdir()) / f"AssinaPDF-Setup-{version}.exe"
            request = Request(download_url, headers={"User-Agent": "AssinaPDF"})
            with urlopen(request, timeout=60) as response, destination.open("wb") as installer:
                while block := response.read(1024 * 256):
                    installer.write(block)
            self.event_queue.put(("update_downloaded", destination))
        except (OSError, URLError) as error:
            self.event_queue.put(("update_error", str(error)))

    def _install_downloaded_update(self, installer: Path) -> None:
        try:
            # A instalação é visível: assim o usuário pode acompanhar a atualização e
            # nenhum Setup fica parecendo travado em segundo plano.
            subprocess.Popen([str(installer), "/CLOSEAPPLICATIONS"])
            self.status_var.set("Abrindo o instalador da atualização...")
            self.after(500, self.destroy)
        except OSError as error:
            messagebox.showerror("Atualização", f"Não foi possível iniciar o instalador:\n{error}", parent=self)

    def _process_events(self) -> None:
        try:
            while True:
                event, data = self.event_queue.get_nowait()
                if event == "progress":
                    self.status_var.set(str(data))
                elif event == "done":
                    self._finish_signing(*data)  # type: ignore[arg-type]
                elif event == "update_current":
                    self.status_var.set("O AssinaPDF já está atualizado.")
                    messagebox.showinfo("Atualizações", "Você já está usando a versão mais recente.", parent=self)
                elif event == "update_available":
                    self._offer_update(*data)  # type: ignore[arg-type]
                elif event == "update_downloaded":
                    self._install_downloaded_update(data)  # type: ignore[arg-type]
                elif event == "update_error":
                    self.status_var.set("Não foi possível verificar atualizações.")
                    messagebox.showerror("Atualizações", f"Não foi possível concluir a atualização:\n{data}", parent=self)
        except queue.Empty:
            pass
        self.after(120, self._process_events)

    def _finish_signing(self, output_dir: Path, successes: list[str], failures: list[str]) -> None:
        self.is_processing = False
        self.sign_button.configure(state="normal", text="ASSINAR PDFs")
        self.status_var.set(f"Concluído: {len(successes)} arquivo(s) assinado(s).")
        message = f"{len(successes)} arquivo(s) salvo(s) em:\n{output_dir}"
        if failures:
            message += "\n\nNão foi possível processar:\n" + "\n".join(failures)
            messagebox.showwarning("Processamento concluído com avisos", message)
        else:
            messagebox.showinfo("Processamento concluído", message)


class PositionPreview(ctk.CTkToplevel):
    """Exibe como uma posição padrão ficará antes de assinar o lote."""

    def __init__(
        self, app: AssinadorPMI, pdfs: list[Path], signature: Path, width_mm: float, margin_mm: float, position: str,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.pdfs = pdfs
        self.signature = signature
        self.width = width_mm * MM_TO_POINTS
        self.margin = margin_mm * MM_TO_POINTS
        self.position = position
        self.index = 0
        self.preview_image: ImageTk.PhotoImage | None = None
        self.signature_image: ImageTk.PhotoImage | None = None

        self.title("Pré-visualização da assinatura")
        self.geometry("1120x850")
        self.minsize(900, 720)
        self.configure(fg_color=APP_BACKGROUND)
        self.transient(app)

        self.document_var = ctk.StringVar()
        ctk.CTkLabel(
            self, text="Pré-visualização da posição padrão", font=ctk.CTkFont(size=21, weight="bold"), text_color=PRIMARY_TEXT
        ).pack(pady=(18, 3))
        ctk.CTkLabel(
            self, text=f"Posição escolhida: {position}. Nenhum PDF será alterado nesta etapa.", text_color=SECONDARY_TEXT
        ).pack(padx=20)
        ctk.CTkLabel(self, textvariable=self.document_var, font=ctk.CTkFont(size=14, weight="bold")).pack(pady=(13, 4))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=24, pady=(0, 8))
        self.previous_button = ctk.CTkButton(controls, text="← Anterior", width=110, command=self._previous)
        self.previous_button.pack(side="left")
        self.next_button = ctk.CTkButton(controls, text="Próximo →", width=110, command=self._next)
        self.next_button.pack(side="left", padx=8)
        ctk.CTkButton(controls, text="Fechar", command=self.destroy).pack(side="right")

        preview_frame = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#D9E1EC")
        preview_frame.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.canvas = Canvas(preview_frame, bg="white", highlightthickness=0)
        self.canvas.pack(expand=True, padx=8, pady=8)
        self._render_current()

    def _page_number(self, document: fitz.Document) -> int:
        return 0 if self.app.pages_var.get() == "Primeira página" else document.page_count - 1

    def _render_current(self) -> None:
        pdf_path = self.pdfs[self.index]
        self.document_var.set(f"Documento {self.index + 1} de {len(self.pdfs)}: {pdf_path.name}")
        try:
            document = fitz.open(pdf_path)
            try:
                if document.page_count == 0:
                    raise ValueError("PDF sem páginas")
                page = document[self._page_number(document)]
                page_rect = page.rect
                scale = min(1.8, 900 / page_rect.width, 630 / page_rect.height)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            finally:
                document.close()
            page_image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self.preview_image = ImageTk.PhotoImage(page_image)
            self.canvas.configure(width=pixmap.width, height=pixmap.height)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.preview_image, anchor="nw")
            with Image.open(self.signature) as signature_image:
                aspect_ratio = signature_image.height / signature_image.width
                rect = AssinadorPMI._signature_rectangle(
                    page_rect, self.width, self.width * aspect_ratio, self.margin, self.position
                )
                preview = signature_image.convert("RGBA").resize(
                    (max(1, round(rect.width * scale)), max(1, round(rect.height * scale))), Image.Resampling.LANCZOS
                )
            self.signature_image = ImageTk.PhotoImage(preview)
            x = (rect.x0 - page_rect.x0) * scale
            y = (rect.y0 - page_rect.y0) * scale
            self.canvas.create_image(x, y, image=self.signature_image, anchor="nw")
            self.canvas.create_rectangle(x, y, x + preview.width, y + preview.height, outline="#00A650", width=2)
        except Exception as error:
            self.canvas.delete("all")
            self.canvas.configure(width=620, height=260)
            self.canvas.create_text(310, 130, text=f"Não foi possível abrir este PDF:\n{error}", fill="#A32020", justify="center")
        self.previous_button.configure(state="normal" if self.index else "disabled")
        self.next_button.configure(state="normal" if self.index < len(self.pdfs) - 1 else "disabled")

    def _previous(self) -> None:
        self.index -= 1
        self._render_current()

    def _next(self) -> None:
        self.index += 1
        self._render_current()


class ManualPositionEditor(ctk.CTkToplevel):
    """Prévia clicável para uma posição compartilhada ou independente por PDF."""

    def __init__(
        self, app: AssinadorPMI, pdfs: list[Path], signature: Path, width_mm: float, margin_mm: float,
        shared: bool = False,
    ) -> None:
        super().__init__(app)
        self.app = app
        self.all_pdfs = pdfs
        self.shared = shared
        self.pdfs = pdfs[:1] if shared else pdfs
        self.signature = signature
        self.default_width_mm = width_mm
        self.current_width_mm = width_mm
        self.margin = margin_mm * MM_TO_POINTS
        self.index = 0
        self.page_rect: fitz.Rect | None = None
        self.scale = 1.0
        self.signature_width = 0.0
        self.signature_height = 0.0
        self.preview_image: ImageTk.PhotoImage | None = None
        self.signature_image: ImageTk.PhotoImage | None = None

        self.title("Ajustar posição manual da assinatura")
        self.geometry("1120x850")
        self.minsize(900, 720)
        self.configure(fg_color=APP_BACKGROUND)
        self.transient(app)
        self.grab_set()

        self.document_var = ctk.StringVar()
        self.instruction_var = ctk.StringVar()
        self.size_var = ctk.StringVar()

        size_row = ctk.CTkFrame(self, fg_color="transparent")
        size_row.pack(fill="x", padx=105, pady=(20, 0))
        ctk.CTkLabel(size_row, text="Tamanho da assinatura:", text_color=PRIMARY_TEXT).pack(side="left")
        ctk.CTkLabel(size_row, textvariable=self.size_var, font=ctk.CTkFont(weight="bold"), text_color="#00A650").pack(side="right")
        self.size_slider = ctk.CTkSlider(
            self, from_=10, to=250, number_of_steps=240, command=self._change_size, progress_color="#00A650"
        )
        self.size_slider.pack(fill="x", padx=125, pady=(3, 5))

        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.pack(fill="x", padx=24, pady=(5, 8))
        self.shared_checkbox = ctk.CTkCheckBox(
            controls,
            text="Usar a mesma posição e tamanho em todos os PDFs",
            variable=self.app.shared_manual_var,
            command=self._toggle_shared_mode,
            text_color=PRIMARY_TEXT,
        )
        self.shared_checkbox.pack(side="left")
        self.previous_button = ctk.CTkButton(controls, text="← Anterior", width=105, command=self._previous)
        self.next_button = ctk.CTkButton(controls, text="Próximo →", width=105, command=self._next)
        ctk.CTkButton(
            controls, text="Salvar posição", fg_color="#00A650", hover_color="#008A42", command=self._save
        ).pack(side="right")
        ctk.CTkLabel(self, textvariable=self.document_var, font=ctk.CTkFont(size=13, weight="bold")).pack(pady=(0, 5))

        preview_frame = ctk.CTkFrame(self, fg_color="white", border_width=1, border_color="#D9E1EC")
        preview_frame.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        self.canvas = Canvas(preview_frame, bg="white", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(expand=True, padx=8, pady=8)
        self.canvas.bind("<Button-1>", self._choose_position)

        self._sync_shared_controls()
        self._render_current()

    def _page_number(self, document: fitz.Document) -> int:
        if self.app.pages_var.get() == "Primeira página":
            return 0
        # Em "Todas as páginas", a posição escolhida é reaproveitada em todas elas.
        return document.page_count - 1

    def _render_current(self) -> None:
        pdf_path = self.pdfs[self.index]
        label = "Prévia de referência" if self.shared else f"Documento {self.index + 1} de {len(self.pdfs)}"
        self.document_var.set(f"{label}: {pdf_path.name}")
        self.current_width_mm = self._get_width(pdf_path)
        self.size_slider.set(min(250, max(10, self.current_width_mm)))
        self.size_var.set(f"{self.current_width_mm:.0f} mm")
        try:
            document = fitz.open(pdf_path)
            try:
                if document.page_count == 0:
                    raise ValueError("PDF sem páginas")
                page = document[self._page_number(document)]
                self.page_rect = page.rect
                self.scale = min(1.8, 900 / page.rect.width, 610 / page.rect.height)
                pixmap = page.get_pixmap(matrix=fitz.Matrix(self.scale, self.scale), alpha=False)
            finally:
                document.close()
            page_image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            self.preview_image = ImageTk.PhotoImage(page_image)
            self.canvas.configure(width=pixmap.width, height=pixmap.height)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.preview_image, anchor="nw")
            self._draw_signature()
            configured = self._get_position(pdf_path) is not None
            self.instruction_var.set("Posição definida — clique para ajustar." if configured else "Posição pendente — clique sobre a prévia.")
        except Exception as error:
            self.canvas.delete("all")
            self.canvas.configure(width=620, height=260)
            self.canvas.create_text(310, 130, text=f"Não foi possível abrir este PDF:\n{error}", fill="#A32020", justify="center")
            self.instruction_var.set("Escolha outro documento ou corrija o PDF antes de continuar.")
        if not self.shared:
            self.previous_button.configure(state="normal" if self.index else "disabled")
            self.next_button.configure(state="normal" if self.index < len(self.pdfs) - 1 else "disabled")

    def _sync_shared_controls(self) -> None:
        if self.shared:
            self.previous_button.pack_forget()
            self.next_button.pack_forget()
        else:
            self.previous_button.pack(side="left", padx=(12, 0))
            self.next_button.pack(side="left", padx=8)

    def _toggle_shared_mode(self) -> None:
        shared = self.app.shared_manual_var.get()
        if shared == self.shared:
            return
        if not shared and self.app.shared_manual_position is not None:
            # Parte da posição comum e permite ajustar apenas os PDFs necessários.
            for pdf_path in self.all_pdfs:
                self.app.manual_positions.setdefault(str(pdf_path.resolve()), self.app.shared_manual_position)
                if self.app.shared_manual_width is not None:
                    self.app.manual_widths.setdefault(str(pdf_path.resolve()), self.app.shared_manual_width)
        self.shared = shared
        self.pdfs = self.all_pdfs[:1] if shared else self.all_pdfs
        self.index = 0
        self._sync_shared_controls()
        self._render_current()

    def _get_position(self, pdf_path: Path) -> tuple[float, float] | None:
        return self.app.shared_manual_position if self.shared else self.app.manual_positions.get(str(pdf_path.resolve()))

    def _set_position(self, pdf_path: Path, position: tuple[float, float]) -> None:
        if self.shared:
            self.app.shared_manual_position = position
        else:
            self.app.manual_positions[str(pdf_path.resolve())] = position

    def _get_width(self, pdf_path: Path) -> float:
        if self.shared:
            return self.app.shared_manual_width or self.default_width_mm
        return self.app.manual_widths.get(str(pdf_path.resolve()), self.default_width_mm)

    def _set_width(self, pdf_path: Path, width: float) -> None:
        if self.shared:
            self.app.shared_manual_width = width
        else:
            self.app.manual_widths[str(pdf_path.resolve())] = width

    def _draw_signature(self) -> None:
        if self.page_rect is None:
            return
        with Image.open(self.signature) as signature_image:
            aspect_ratio = signature_image.height / signature_image.width
            rect = AssinadorPMI._signature_rectangle(
                self.page_rect, self.current_width_mm * MM_TO_POINTS,
                self.current_width_mm * MM_TO_POINTS * aspect_ratio, self.margin,
                "Manual por PDF", self._get_position(self.pdfs[self.index]),
            )
            self.signature_width = rect.width
            self.signature_height = rect.height
            display_width = max(1, round(rect.width * self.scale))
            display_height = max(1, round(rect.height * self.scale))
            preview = signature_image.convert("RGBA").resize((display_width, display_height), Image.Resampling.LANCZOS)
        self.signature_image = ImageTk.PhotoImage(preview)
        x = (rect.x0 - self.page_rect.x0) * self.scale
        y = (rect.y0 - self.page_rect.y0) * self.scale
        self.canvas.create_image(x, y, image=self.signature_image, anchor="nw")
        self.canvas.create_rectangle(x, y, x + display_width, y + display_height, outline="#00A650", width=2)

    def _change_size(self, value: float) -> None:
        if self.page_rect is None:
            return
        self.current_width_mm = round(float(value))
        self._set_width(self.pdfs[self.index], self.current_width_mm)
        self._render_current()

    def _choose_position(self, event: object) -> None:
        if self.page_rect is None:
            return
        # event é um tkinter.Event; a anotação ampla evita depender do tipo interno do Tk.
        x = float(getattr(event, "x")) / self.scale + self.page_rect.x0 - self.signature_width / 2
        y = float(getattr(event, "y")) / self.scale + self.page_rect.y0 - self.signature_height / 2
        x = min(max(x, self.page_rect.x0), self.page_rect.x1 - self.signature_width)
        y = min(max(y, self.page_rect.y0), self.page_rect.y1 - self.signature_height)
        self._set_position(self.pdfs[self.index], (
            (x - self.page_rect.x0) / self.page_rect.width,
            (y - self.page_rect.y0) / self.page_rect.height,
        ))
        self._render_current()

    def _previous(self) -> None:
        self.index -= 1
        self._render_current()

    def _next(self) -> None:
        self.index += 1
        self._render_current()

    def _save(self) -> None:
        missing = [] if self.shared and self.app.shared_manual_position is not None else [
            path.name for path in self.all_pdfs if self._get_position(path) is None
        ]
        if missing:
            messagebox.showwarning(
                "Posições pendentes",
                "Defina a posição para todos os PDFs antes de salvar:\n" + "\n".join(missing),
                parent=self,
            )
            return
        self.grab_release()
        self.destroy()
        self.app.status_var.set("Posições manuais salvas. Clique em ASSINAR PDFs para iniciar o lote.")


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    app = AssinadorPMI()
    app.mainloop()
