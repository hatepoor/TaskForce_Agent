"""PDF 专属: 布局模型 + TableFormer + 可选 OCR。

与另外两路的差异:
- 有页码(`prov[0].page_no`)、有图片本体、表格靠 TableFormer 从像素里认;
- **首次运行会下载布局 / 表格模型**(数百 MB, 受 `HF_ENDPOINT` 影响), docx/md 不会;
- OCR 默认关(`RAG2_DO_OCR`): 只给扫描件开; 默认引擎对中文一般, 表格经 OCR 基本不可信。
"""
from __future__ import annotations

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import PdfFormatOption

FORMAT = InputFormat.PDF
HAS_LOCAL_IMAGES = True          # 有图片本体 → images.save_picture 会落盘


def build_option(cfg) -> PdfFormatOption:
    """PDF 的 pipeline 参数(其余两路没有这些开关)。

    速度档位(2026-10-18 实测 12 页三季报):
    - ACCURATE + images_scale=2.0:约 100s;
    - FAST + images_scale=1.0:约 49s(表格结构仍保留,默认);
    - 关闭表格结构:约 18s,但表格会被拆成大量文本碎片。
    用 `RAG2_PDF_FAST=0` 回到质量档,`RAG2_PDF_TABLE_STRUCTURE=0` 再关表格。
    """
    fast = getattr(cfg, "pdf_fast", True)
    tables = getattr(cfg, "pdf_table_structure", True)
    p = PdfPipelineOptions()
    p.do_ocr = cfg.do_ocr                                        # 扫描件才开
    p.do_table_structure = tables                                # 表格结构识别(TableFormer)
    if tables:
        p.table_structure_options.mode = (
            TableFormerMode.FAST if fast else TableFormerMode.ACCURATE
        )
    p.images_scale = 1.0 if fast else 2.0                        # 抽图分辨率; 越高越吃内存
    p.generate_picture_images = True                             # 生成图片本体: get_image 的前提
    # 页眉页脚: docling 自己会标 content_layer=FURNITURE, common.walk 里直接丢;
    # `RAG2_HF_GEOMETRIC` 的 bbox 几何规则本期不实现(02 篇规则 C), 只留开关位。
    return PdfFormatOption(pipeline_options=p)
