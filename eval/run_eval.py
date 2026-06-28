import json
import time
import sys
import os

sys.path.append("../orchestrator")
from run_pipeline import run_pipeline

SCHEMA_TEXT = "olist_orders_dataset: order_id, customer_id, order_status, order_purchase_timestamp, order_delivered_customer_date, order_estimated_delivery_date"

def load_questions(path="eval_questions.json"):
    with open(path, "r") as f:
        return json.load(f)

def run_eval(questions):
    eval_results = []

    for item in questions:
        print(f"\n=== Eval Q{item['id']} [{item['category']}]: {item['question']} ===")
        start = time.time()

        try:
            results, final_answer, critique = run_pipeline(item["question"], SCHEMA_TEXT)
            elapsed = time.time() - start

            eval_results.append({
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "ground_truth": item.get("ground_truth", ""),
                "final_answer": final_answer,
                "critique": critique,
                "latency_seconds": round(elapsed, 2),
                "num_steps": len(results),
                "sql_errors": sum(1 for r in results if r.get("type") == "sql_error"),
                "research_errors": sum(1 for r in results if r.get("type") == "research_error"),
                "revised": "REVISE" in critique if critique else False
            })
        except Exception as e:
            eval_results.append({
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "ground_truth": item.get("ground_truth", ""),
                "error": str(e),
                "latency_seconds": round(time.time() - start, 2)
            })

    return eval_results

def print_summary(eval_results):
    total = len(eval_results)
    errors = sum(1 for r in eval_results if "error" in r)
    revised = sum(1 for r in eval_results if r.get("revised"))
    latencies = [r.get("latency_seconds", 0) for r in eval_results]
    avg_latency = sum(latencies) / total if total else 0

    print("\n" + "="*50)
    print("EVAL SUMMARY")
    print("="*50)
    print(f"Total questions: {total}")
    print(f"Pipeline errors: {errors}")
    print(f"Answers revised by Critic: {revised} ({round(revised/total*100,1)}%)")
    print(f"Average latency: {round(avg_latency, 2)}s")

    by_category = {}
    for r in eval_results:
        cat = r["category"]
        by_category.setdefault(cat, []).append(r)

    print("\nBy category:")
    for cat, items in by_category.items():
        cat_errors = sum(1 for i in items if "error" in i)
        print(f"  {cat}: {len(items)} questions, {cat_errors} errors")

if __name__ == "__main__":
    questions = load_questions("eval_questions.json")
    results_log = run_eval(questions)

    os.makedirs("results", exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_path = f"results/eval_run_{timestamp}.json"

    with open(output_path, "w") as f:
        json.dump(results_log, f, indent=2)

    print(f"\nSaved results to {output_path}")
    print_summary(results_log)