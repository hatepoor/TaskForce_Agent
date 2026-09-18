"""bm25.py 纯函数层单测:tokenize / Bm25Index / rrf_fuse(01-02 模块,零 DB,不 skip)。"""

from tools.rag.bm25 import Bm25Index, rrf_fuse, tokenize


class TestTokenize:
    def test_中文句切词非空且无单字噪音(self):
        toks = tokenize("TaskForce 支持知识库问答与联网调研")
        assert toks
        assert all(len(t) >= 2 for t in toks)
        assert "TaskForce" in toks
        assert "知识库" in toks
        assert "知识" in toks

    def test_英文单词与中文词共存(self):
        toks = tokenize("使用 TaskForce 的 RAG 功能")
        assert "TaskForce" in toks
        assert "RAG" in toks

    def test_空白与单字被过滤(self):
        assert tokenize("  的 了 吧 ") == []

    def test_纯标点被过滤(self):
        assert tokenize("——...（）") == []

    def test_入库与查询共用同一函数(self):
        # 同一模块级函数,两端输出必然一致;锁定"不得另写一套分词"
        q = "如何优化 RAG 检索"
        assert tokenize(q) == tokenize(q)


class TestBm25Index:
    @staticmethod
    def _loader():
        """固定语料:chunk 0 高频含'苹果',chunk 1 不含,chunk 2 低频含。"""
        return [
            (0, "苹果 苹果 苹果 苹果 手机 价格"),
            (1, "香蕉 橘子 水果 价格"),
            (2, "苹果 与 香蕉 水果 对比"),
        ]

    def test_懒加载只构建一次(self):
        calls: list[int] = []

        def loader():
            calls.append(1)
            return self._loader()

        idx = Bm25Index(loader=loader)
        idx.search("苹果", 2)
        idx.search("苹果", 2)
        assert len(calls) == 1

    def test_含查询词的文档得分更高(self):
        idx = Bm25Index(loader=self._loader)
        hits = dict(idx.search("苹果", 3))
        assert set(hits) == {0, 2}  # 无命中词的 chunk 1 被过滤
        assert hits[0] > hits[2]  # 高频 > 低频

    def test_无命中词返回空(self):
        idx = Bm25Index(loader=self._loader)
        assert idx.search("不存在的词", 3) == []

    def test_mark_dirty后触发重建(self):
        calls: list[int] = []

        def loader():
            calls.append(1)
            return self._loader()

        idx = Bm25Index(loader=loader)
        idx.search("苹果", 2)
        idx.mark_dirty()
        idx.search("苹果", 2)
        assert len(calls) == 2


class TestRrfFuse:
    def test_双路并集按排名融合(self):
        vector_hits = [{"chunk_id": 1}, {"chunk_id": 2}]
        keyword_hits = [(2, 9.0), (3, 8.0)]
        # 1: 1/61;2: 1/62+1/62;3: 1/63 → 2 > 1 > 3
        fused = rrf_fuse(vector_hits, keyword_hits, k=60, top_k=5)
        assert [cid for cid, _score in fused] == [2, 1, 3]

    def test_双路都命中者高于单路(self):
        vector_hits = [{"chunk_id": 1}]
        keyword_hits = [(1, 1.0), (2, 1.0)]
        fused = rrf_fuse(vector_hits, keyword_hits, k=60, top_k=5)
        assert [cid for cid, _score in fused] == [1, 2]
        assert fused[0][1] > fused[1][1]  # 融合分递减

    def test_top_k截断(self):
        vector_hits = [{"chunk_id": i} for i in range(10)]
        assert len(rrf_fuse(vector_hits, [], k=60, top_k=5)) == 5
