"""Assinador de PDFs por imagem — Prefeitura de Imperatriz.

Esta aplicação insere uma imagem de assinatura em um ou vários PDFs. Ela não
gera uma assinatura digital criptográfica/certificada (ICP-Brasil).
"""

from __future__ import annotations

import queue
import sys
import threading
from pathlib import Path
from typing import Iterable

import customtkinter as ctk
import fitz  # PyMuPDF
from PIL import Image
from tkinter import filedialog, messagebox


APP_DIR = Path(__file__).resolve().parent
# PyInstaller extrai os recursos em uma pasta temporária (_MEIPASS). Em modo
# desenvolvimento, os arquivos continuam sendo lidos diretamente do projeto.
BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DEFAULT_OUTPUT_NAME = "pdfs_assinados"
MM_TO_POINTS = 72 / 25.4


class AssinadorPMI(ctk.CTk):
    """Janela principal e fluxo de assinatura em lote."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Assinador de PDFs | Prefeitura de Imperatriz")
        self.geometry("1060x760")
        self.minsize(920, 650)
        self.configure(fg_color="#F3F6FA")

        self.pdfs: list[Path] = []
        self.signature_path: Path | None = None
        self.output_dir: Path | None = None
        self.is_processing = False
        self.event_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.logo_image: ctk.CTkImage | None = None

        self.position_var = ctk.StringVar(value="Inferior direita")
        self.pages_var = ctk.StringVar(value="Última página")
        self.width_var = ctk.StringVar(value="45")
        self.margin_var = ctk.StringVar(value="12")
        self.status_var = ctk.StringVar(value="Pronto para selecionar documentos.")
        self.pdf_count_var = ctk.StringVar(value="Nenhum PDF selecionado")
        self.signature_label_var = ctk.StringVar(value="Nenhuma imagem selecionada")
        self.output_label_var = ctk.StringVar(value="Será criada junto aos PDFs")

        self._build_interface()
        self.after(120, self._process_events)

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
            text_color="#4B5B70",
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
        candidates = (
            BUNDLE_DIR / "assets" / "logo_pmi_branca_3.png",
            Path("/home/eikemiranda/Downloads/logo_pmi_branca_3.png"),
        )
        logo_path = next((path for path in candidates if path.exists()), None)
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
        card = ctk.CTkFrame(parent, corner_radius=12, fg_color="white", border_width=1, border_color="#D9E1EC")
        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=16, weight="bold"), text_color="#153B82"
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
            buttons, text="Limpar", width=75, fg_color="transparent", text_color="#153B82", border_width=1,
            border_color="#153B82", command=self._clear_pdfs
        ).pack(side="right")

        ctk.CTkLabel(parent, textvariable=self.pdf_count_var, text_color="#4B5B70").pack(anchor="w", padx=20, pady=(12, 6))
        self.pdf_list = ctk.CTkTextbox(parent, height=310, font=ctk.CTkFont(size=12), wrap="none")
        self.pdf_list.pack(fill="both", expand=True, padx=20, pady=(0, 14))
        self.pdf_list.configure(state="disabled")

        ctk.CTkLabel(parent, text="Pasta de saída", font=ctk.CTkFont(size=13, weight="bold"), text_color="#153B82").pack(
            anchor="w", padx=20
        )
        output_row = ctk.CTkFrame(parent, fg_color="transparent")
        output_row.pack(fill="x", padx=20, pady=(5, 17))
        ctk.CTkLabel(output_row, textvariable=self.output_label_var, anchor="w", text_color="#4B5B70").pack(
            side="left", fill="x", expand=True
        )
        ctk.CTkButton(output_row, text="Alterar", width=84, command=self._choose_output).pack(side="right")

    def _build_signature_section(self, parent: ctk.CTkFrame) -> None:
        ctk.CTkLabel(
            parent,
            text="Escolha PNG, JPG ou JPEG com a assinatura.",
            text_color="#4B5B70",
            wraplength=320,
            justify="left",
        ).pack(anchor="w", padx=20)
        ctk.CTkButton(parent, text="Escolher imagem", command=self._choose_signature).pack(anchor="w", padx=20, pady=12)
        ctk.CTkLabel(
            parent, textvariable=self.signature_label_var, text_color="#153B82", wraplength=320, justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 18))

    def _build_settings_section(self, parent: ctk.CTkFrame) -> None:
        fields = ctk.CTkFrame(parent, fg_color="transparent")
        fields.pack(fill="x", padx=20, pady=(0, 8))
        fields.grid_columnconfigure(0, weight=1)
        fields.grid_columnconfigure(1, weight=1)

        self._option_field(fields, "Posição", self.position_var, [
            "Inferior direita", "Inferior esquerda", "Superior direita", "Superior esquerda", "Centro"
        ], 0, 0)
        self._option_field(fields, "Aplicar em", self.pages_var, ["Última página", "Primeira página", "Todas as páginas"], 0, 1)
        self._entry_field(fields, "Largura (mm)", self.width_var, 1, 0)
        self._entry_field(fields, "Margem (mm)", self.margin_var, 1, 1)
        ctk.CTkLabel(
            parent,
            text="A assinatura é inserida como imagem visível. Para assinaturas certificadas, use um certificado digital apropriado.",
            text_color="#6A778B", justify="left", wraplength=330, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=20, pady=(3, 17))

    @staticmethod
    def _option_field(parent: ctk.CTkFrame, label: str, variable: ctk.StringVar, values: list[str], row: int, column: int) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=6)
        ctk.CTkLabel(holder, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color="#4B5B70").pack(anchor="w")
        ctk.CTkOptionMenu(holder, values=values, variable=variable, height=33).pack(fill="x", pady=(4, 0))

    @staticmethod
    def _entry_field(parent: ctk.CTkFrame, label: str, variable: ctk.StringVar, row: int, column: int) -> None:
        holder = ctk.CTkFrame(parent, fg_color="transparent")
        holder.grid(row=row, column=column, sticky="ew", padx=(0, 8) if column == 0 else (8, 0), pady=6)
        ctk.CTkLabel(holder, text=label, font=ctk.CTkFont(size=12, weight="bold"), text_color="#4B5B70").pack(anchor="w")
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

    def _start_signing(self) -> None:
        if self.is_processing:
            return
        if not self.pdfs:
            messagebox.showwarning("Documentos", "Selecione pelo menos um arquivo PDF.")
            return
        if not self.signature_path or not self.signature_path.exists():
            messagebox.showwarning("Assinatura", "Selecione uma imagem de assinatura válida.")
            return
        try:
            width_mm = float(self.width_var.get().replace(",", "."))
            margin_mm = float(self.margin_var.get().replace(",", "."))
            if width_mm <= 0 or margin_mm < 0:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Medidas", "Informe largura maior que zero e margem igual ou maior que zero.")
            return

        output = self.output_dir or (self.pdfs[0].parent / DEFAULT_OUTPUT_NAME)
        self.is_processing = True
        self.sign_button.configure(state="disabled", text="ASSINANDO...")
        self.status_var.set("Processando documentos...")
        config = (list(self.pdfs), self.signature_path, output, width_mm, margin_mm, self.position_var.get(), self.pages_var.get())
        threading.Thread(target=self._sign_batch, args=config, daemon=True).start()

    def _sign_batch(
        self, pdfs: list[Path], signature: Path, output_dir: Path, width_mm: float, margin_mm: float, position: str, pages: str
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
                    self._sign_pdf(pdf_path, signature, destination, width_mm, margin_mm, aspect_ratio, position, pages)
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
        position: str, pages: str
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
                rectangle = AssinadorPMI._signature_rectangle(page.rect, width, height, margin, position)
                page.insert_image(rectangle, filename=str(signature), keep_proportion=True, overlay=True)
            document.save(destination, garbage=4, deflate=True)
        finally:
            document.close()

    @staticmethod
    def _signature_rectangle(page: fitz.Rect, width: float, height: float, margin: float, position: str) -> fitz.Rect:
        # Mantém a imagem inteiramente na página mesmo em PDFs pequenos.
        available_width = max(1, page.width - 2 * margin)
        available_height = max(1, page.height - 2 * margin)
        scale = min(1, available_width / width, available_height / height)
        width *= scale
        height *= scale
        horizontal_margin = min(margin, max(0, (page.width - width) / 2))
        vertical_margin = min(margin, max(0, (page.height - height) / 2))
        if position == "Inferior direita":
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

    def _process_events(self) -> None:
        try:
            while True:
                event, data = self.event_queue.get_nowait()
                if event == "progress":
                    self.status_var.set(str(data))
                elif event == "done":
                    self._finish_signing(*data)  # type: ignore[arg-type]
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


if __name__ == "__main__":
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("blue")
    app = AssinadorPMI()
    app.mainloop()
