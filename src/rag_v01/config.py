"""`RAG2_` 前缀环境变量的唯一读取点(01 篇 §三变量表)。

为什么单独一个文件:
1. 本模块要能整目录拷走 → 不 import 项目的 settings/config.py;
2. 业务代码禁止直读 os.environ —— 变量名散落各处时, 改名/改默认值必然漏改;
3. 单测直接构造 Config(...) 注进函数, 不依赖环境。

字段名 → 变量名是**机械映射**: RAG2_ + 字段名大写(embed_dim ↔ RAG2_EMBED_DIM),
所以新增变量只改这里 + 01 篇变量表两处。

注意: 本文件不读 .env 文件 —— 载入由入口负责(命令行 `uv run --env-file .env`,
或 07 篇定的统一载入方式); 裸 `python -c` 里 os.environ 是看不到 .env 的。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, fields


@dataclass(frozen=True, slots=True)
class Config:
    # —— 解析侧(02 篇)——
    do_ocr: bool = False                 # 扫描件才开; 文本型 pdf 开了只会更慢
    pdf_fast: bool = True                # 默认 FAST 表格模式 + 1.0 倍率;RAG2_PDF_FAST=0 恢复质量档
    pdf_table_structure: bool = True     # 关闭可再快约 2.5x,但表格会拆成文本碎片(质量优先默认开)
    image_dir: str = "data/rag2_images"  # 图片落盘根目录(image_path 存相对它的路径)
    image_format: str = "png"            # png | jpg
    image_desc: str = "off"              # off | vlm | ocr —— 可选增强, 默认不发起外部调用
    short_line_max: int = 30             # clean 规则(5) 的超短行阈值
    hf_geometric: bool = False           # 页眉页脚几何规则开关位(本期未实现, 02 篇规则 C)
    vlm_api_base: str = ""               # 仅 image_desc=vlm 时使用
    vlm_api_key: str = ""
    vlm_model: str = ""
    # —— 嵌入侧(04 篇)——
    embed_mode: str = "api"              # api | local
    embed_model: str = "qwen3-vl-embedding"
    embed_api_base: str = "https://dashscope.aliyuncs.com/api/v1"
    embed_api_key: str = ""
    embed_dim: int = 1024
    embed_batch: int = 20
    embed_img_batch: int = 5
    # —— Milvus 与检索侧(04/05 篇)——
    milvus_uri: str = "http://localhost:19530"
    hnsw_ef: int = 96
    parent_target_chars: int = 1500
    child_target_chars: int = 450
    child_overlap_chars: int = 50
    candidate_top_n: int = 20
    retrieve_top_k: int = 5
    rrf_k: int = 60
    # —— judge(06 篇)——
    judge_api_base: str = ""
    judge_api_key: str = ""
    judge_model: str = ""


def load_config() -> Config:
    """读环境变量构造配置; 未设置的变量用字段默认值。

    因为 `from __future__ import annotations`, `f.type` 是字符串("bool"/"int"/"str"),
    所以这里按字符串比较 —— 以后加字段不用动这段逻辑。
    """
    kwargs: dict[str, object] = {}
    for f in fields(Config):
        raw = os.environ.get("RAG2_" + f.name.upper())
        if raw is None or raw.strip() == "":
            continue
        if f.type == "bool":
            kwargs[f.name] = raw.strip().lower() in {"1", "true", "yes", "on", "y"}
        elif f.type == "int":
            kwargs[f.name] = int(raw)
        else:
            kwargs[f.name] = raw.strip()
    return Config(**kwargs)
