"""
Bước 3 — RAGAS Evaluation
===========================
NHIỆM VỤ:
  1. Chạy 50 QA pairs qua CẢ 2 prompt version, lưu answers + contexts
  2. Tạo EvaluationDataset với các SingleTurnSample object
  3. Đánh giá với 4 RAGAS metrics: faithfulness, answer_relevancy,
     context_recall, context_precision
  4. In bảng so sánh V1 vs V2
  5. Lưu kết quả vào data/ragas_report.json

DELIVERABLE: faithfulness ≥ 0.8 cho ít nhất 1 prompt version
             + file data/ragas_report.json được tạo ra

⏰ LƯU Ý: Bước này mất ~15-30 phút. Hãy bắt đầu sớm!
"""
import sys
import json
import warnings
warnings.filterwarnings("ignore")

# Đảm bảo UTF-8 encoding trên Windows console
if sys.stdout is not None and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr is not None and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import config  # ⚠️ phải import trước LangChain

import numpy as np
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from ragas import evaluate, EvaluationDataset, SingleTurnSample
from ragas.metrics import faithfulness, answer_relevancy, context_recall, context_precision
from ragas.run_config import RunConfig
import concurrent.futures

from utils.llm_factory import get_llm, get_embeddings
from utils.data_loader import load_knowledge_base, split_text, build_vectorstore
from qa_pairs import QA_PAIRS


# ── 1. Prompt Templates (copy từ Bước 2) ──────────────────────────────────
SYSTEM_V1 = """Bạn là trợ lý AI hữu ích, trả lời ngắn gọn và súc tích. Chỉ dùng context sau để trả lời.
Giữ câu trả lời trực tiếp, rõ ràng (2-4 câu). Không suy đoán ngoài context.

Context:
{context}"""

PROMPT_V1 = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_V1),
    ("human",  "{question}"),
])

SYSTEM_V2 = """Bạn là chuyên gia AI giàu kinh nghiệm. Đọc kỹ context bên dưới, phân tích các thông tin liên quan và đưa ra câu trả lời có cấu trúc, logic và chặt chẽ (3-5 câu).
Chỉ dựa trên các sự thật có trong context.

Context:
{context}"""

PROMPT_V2 = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_V2),
    ("human",  "{question}"),
])

PROMPTS = {"v1": PROMPT_V1, "v2": PROMPT_V2}


# ── 2. Setup Vectorstore ───────────────────────────────────────────────────
def setup_vectorstore():
    """Tái sử dụng — tạo FAISS vectorstore từ knowledge base."""
    embeddings  = get_embeddings()
    text        = load_knowledge_base()
    chunks      = split_text(text)
    return build_vectorstore(chunks, embeddings)


# ── 3. Chạy RAG và thu thập kết quả ───────────────────────────────────────
def run_rag(retriever, llm, prompt, question: str) -> dict:
    """
    Chạy RAG chain cho 1 câu hỏi.

    ⚠️ QUAN TRỌNG: trả về contexts là LIST of strings, KHÔNG phải string đã ghép!
    RAGAS cần từng đoạn riêng để tính context_recall và context_precision.

    Trả về: {"answer": str, "contexts": list[str]}
    """
    import time
    docs = retriever.invoke(question)
    contexts = [doc.page_content for doc in docs]
    ctx_str = "\n\n".join(contexts)

    chain = prompt | llm | StrOutputParser()
    for attempt in range(5):
        try:
            answer = chain.invoke({
                "context":  ctx_str,
                "question": question,
            })
            return {"answer": answer, "contexts": contexts}
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                wait_time = 2 * (attempt + 1)
                print(f"  ⏳ Rate limit, đợi {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise e

    answer = chain.invoke({
        "context":  ctx_str,
        "question": question,
    })
    return {"answer": answer, "contexts": contexts}


def collect_rag_outputs(vectorstore, prompt_version: str, max_workers: int = 8) -> list:
    """
    Chạy tất cả 50 QA pairs qua prompt version đồng thời (concurrent).
    Trả về: list of dict với keys: question, reference, answer, contexts
    """
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    llm       = get_llm()
    prompt    = PROMPTS[prompt_version]

    print(f"\n🚀 Đang chạy 50 câu hỏi đồng thời (x{max_workers} threads) với prompt {prompt_version} ...")

    def process_qa(item):
        idx, qa = item
        out = run_rag(retriever, llm, prompt, qa["question"])
        print(f"  [{idx:02d}/50] {qa['question'][:60]}")
        return idx, {
            "question":  qa["question"],
            "reference": qa["reference"],
            "answer":    out["answer"],
            "contexts":  out["contexts"],
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        indexed_qas = list(enumerate(QA_PAIRS, 1))
        results_with_idx = list(executor.map(process_qa, indexed_qas))

    # Sắp xếp đúng thứ tự câu hỏi ban đầu
    results_with_idx.sort(key=lambda x: x[0])
    return [r[1] for r in results_with_idx]


# ── 4. Tạo RAGAS EvaluationDataset ────────────────────────────────────────
def build_ragas_dataset(rag_results: list) -> EvaluationDataset:
    """
    Chuyển đổi kết quả RAG thành RAGAS EvaluationDataset.

    Mỗi SingleTurnSample cần 4 trường:
      user_input         → câu hỏi
      response           → câu trả lời đã tạo
      retrieved_contexts → list[str] các đoạn đã retrieve
      reference          → đáp án chuẩn (ground truth)
    """
    samples = [
        SingleTurnSample(
            user_input=r["question"],
            response=r["answer"],
            retrieved_contexts=r["contexts"],
            reference=r["reference"],
        )
        for r in rag_results
    ]

    return EvaluationDataset(samples=samples)


# ── 5. Chạy RAGAS Evaluation ──────────────────────────────────────────────
def run_ragas_eval(rag_results: list, version: str, max_workers: int = 8) -> dict:
    """
    Đánh giá kết quả RAG với 4 RAGAS metrics chạy đồng thời (concurrent).
    Trả về: dict {metric_name: mean_score}
    """
    print(f"\n📐 Đang đánh giá RAGAS đồng thời (x{max_workers} workers) cho prompt {version} ...")

    dataset = build_ragas_dataset(rag_results)

    llm_eval = get_llm(temperature=0)
    emb_eval = get_embeddings()
    run_config = RunConfig(max_workers=max_workers, timeout=120, max_retries=5)

    # DeepSeek API chỉ hỗ trợ n=1 completions mỗi request (mặc định RAGAS n=3 gây lỗi 400)
    answer_relevancy.strictness = 1

    result = evaluate(
        dataset,
        metrics=[faithfulness, answer_relevancy, context_recall, context_precision],
        llm=llm_eval,
        embeddings=emb_eval,
        run_config=run_config,
    )

    scores = {}
    for key in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
        raw = result[key]
        valid_vals = [float(v) for v in raw if v is not None and not np.isnan(v) and not np.isinf(v)]
        scores[key] = float(np.mean(valid_vals)) if valid_vals else 0.0

    print(f"\n📊 Kết quả RAGAS — Prompt {version.upper()}:")
    for k, v in scores.items():
        star = " ⭐" if k == "faithfulness" and v >= 0.8 else ""
        print(f"  {k:30s}: {v:.4f}{star}")

    return scores


# ── 6. Main ────────────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("  Bước 3: RAGAS Evaluation")
    print("=" * 60)

    if not config.validate():
        sys.exit(1)

    vectorstore = setup_vectorstore()

    v1_results = collect_rag_outputs(vectorstore, "v1")
    v2_results = collect_rag_outputs(vectorstore, "v2")

    v1_scores = run_ragas_eval(v1_results, "v1")
    v2_scores = run_ragas_eval(v2_results, "v2")

    print("\n" + "=" * 65)
    print(f"  {'Metric':30s}  {'V1':>8}  {'V2':>8}  Winner")
    print("=" * 65)
    for metric in ["faithfulness", "answer_relevancy", "context_recall", "context_precision"]:
        s1, s2  = v1_scores[metric], v2_scores[metric]
        winner  = "← V1" if s1 > s2 else "← V2"
        print(f"  {metric:30s}  {s1:>8.4f}  {s2:>8.4f}  {winner}")

    best_faith = max(v1_scores["faithfulness"], v2_scores["faithfulness"])
    if best_faith >= 0.8:
        print(f"\n✅ Đạt mục tiêu: faithfulness = {best_faith:.4f} ≥ 0.8")
    else:
        print(f"\n⚠️  Chưa đạt mục tiêu ({best_faith:.4f} < 0.8).")
        print("   Gợi ý: giảm chunk_size, tăng k, hoặc điều chỉnh prompt.")

    report = {
        "prompt_v1_scores": v1_scores,
        "prompt_v2_scores": v2_scores,
        "target_met": best_faith >= 0.8,
    }
    report_path = Path(__file__).parent.parent / "data" / "ragas_report.json"
    evidence_report_path = Path(__file__).parent.parent / "evidence" / "03_ragas_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_report_path.parent.mkdir(parents=True, exist_ok=True)

    report_json_str = json.dumps(report, indent=2, ensure_ascii=False)
    report_path.write_text(report_json_str, encoding="utf-8")
    evidence_report_path.write_text(report_json_str, encoding="utf-8")
    print(f"💾 Đã lưu báo cáo vào {report_path} và {evidence_report_path}")


if __name__ == "__main__":
    main()
