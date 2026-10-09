"""Python types for one page of Document IR v1.

These TypedDicts mirror Document IR/ir-v1.schema.json. They describe the JSON
shape for editors and static checkers; validate_ir.py remains the runtime
authority for lengths, regexes, number ranges and cross-field rules.
"""

from __future__ import annotations

from typing import Literal, TypeAlias, TypedDict


Number: TypeAlias = int | float
BBox: TypeAlias = list[Number] | None  # Exactly four numbers; checked at runtime.
PageClass: TypeAlias = Literal[
    "cover", "toc", "letter", "narrative", "kpi", "company_information",
    "auditor_report", "balance_sheet", "income_statement", "cash_flow",
    "notes", "other",
]
Engine: TypeAlias = Literal["TEXT_LAYER", "TESSERACT", "GEMINI", "OPENROUTER", "MERGED"]
VoteEngine: TypeAlias = Literal["TEXT_LAYER", "TESSERACT", "GEMINI", "OPENROUTER"]


class PageSize(TypedDict):
    width: Number
    height: Number
    unit: Literal["pt", "px"]


class Render(TypedDict):
    dpi: Number
    rotation: Literal[0, 90, 180, 270]


class SourceDisplay(TypedDict, total=False):
    file_name: str
    render: Render | None


class SourceOptionalOCR(TypedDict, total=False):
    prompt_version: str | None
    image_sha256: str | None


class SourceCommon(TypedDict):
    tool: str
    document_sha256: str


class TextLayerSource(SourceCommon, SourceDisplay, SourceOptionalOCR):
    engine: Literal["TEXT_LAYER"]


class TesseractExtras(TypedDict, total=False):
    prompt_version: str | None


class TesseractSource(SourceCommon, SourceDisplay, TesseractExtras):
    engine: Literal["TESSERACT"]
    image_sha256: str


class GeminiSource(SourceCommon, SourceDisplay):
    engine: Literal["GEMINI"]
    image_sha256: str
    prompt_version: str


class OpenRouterSource(SourceCommon, SourceDisplay):
    engine: Literal["OPENROUTER"]
    image_sha256: str
    prompt_version: str


class MergedSource(SourceCommon, SourceDisplay, SourceOptionalOCR):
    engine: Literal["MERGED"]


Source: TypeAlias = TextLayerSource | TesseractSource | GeminiSource | OpenRouterSource | MergedSource


class TextFields(TypedDict):
    id: str
    text: str
    bbox: BBox


class HeadingBlock(TextFields):
    type: Literal["heading"]


class ParagraphBlock(TextFields):
    type: Literal["paragraph"]


class KpiBlock(TextFields):
    type: Literal["kpi"]


class StampBlock(TextFields):
    type: Literal["stamp"]


class SignatureBlock(TextFields):
    type: Literal["signature"]


class FormCodeBlock(TextFields):
    type: Literal["form_code"]


class TocBlock(TextFields):
    type: Literal["toc"]


class FurnitureBlock(TextFields):
    type: Literal["furniture"]


TextBlock: TypeAlias = (
    HeadingBlock | ParagraphBlock | KpiBlock | StampBlock | SignatureBlock
    | FormCodeBlock | TocBlock | FurnitureBlock
)


class VoteOptional(TypedDict, total=False):
    conf: Number | None


class Vote(VoteOptional):
    raw: str | None


class CellOptional(TypedDict, total=False):
    votes: dict[VoteEngine, Vote]


class Cell(CellOptional):
    raw: str | None
    bbox: BBox


class Column(TypedDict):
    key: str
    header_lines: list[str]
    bbox: BBox


class RowOptional(TypedDict, total=False):
    indent: Number | None
    bold: bool | None


class Row(RowOptional):
    id: str
    code: str | None
    label_raw: str
    note: str | None
    bbox: BBox
    cells: dict[str, Cell]


class TableOptional(TypedDict, total=False):
    title: str | None
    continued: bool
    logical_table_id: str


class TableBlock(TableOptional):
    id: str
    type: Literal["table"]
    bbox: BBox
    unit_text: str | None
    columns: list[Column]
    rows: list[Row]


Block: TypeAlias = TextBlock | TableBlock


class PageOptional(TypedDict, total=False):
    printed_page: str | None
    page_class: PageClass | None


class PageIR(PageOptional):
    ir_version: Literal["1"]
    page: int
    page_size: PageSize
    source: Source
    blocks: list[Block]
