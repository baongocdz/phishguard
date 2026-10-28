"""Kiểm tra chất lượng bản nháp/bản đã duyệt và chia train/val/test.

    python check.py data/reviewed.jsonl                  # chỉ báo cáo
    python check.py data/reviewed.jsonl --split          # chia 80/10/10 → data/train|val|test.jsonl
    python check.py data/drafts.jsonl --split --allow-unreviewed   # CHỈ để thử quy trình, không dùng train thật

Kiểm tra: đúng định dạng (common.problems), trùng lặp (y hệt / gần giống), độ dài, cờ cần chú ý.
Tập test chia theo từng nhóm và giữ riêng để đánh giá ở Giai đoạn 7; KHÔNG dùng khi fine-tune.
File train/val có thêm system prompt ở đầu (định dạng "messages" mà Unsloth/TRL đọc được).
"""
import argparse
import collections
import random
import re
import unicodedata
from pathlib import Path

from common import CATEGORIES, DATA, SYSTEM_PROMPT, auto_flags, load_jsonl, problems, save_jsonl

NEAR_DUP = 0.8  # tỉ lệ trùng cụm 3 từ của câu hỏi đầu tiên để coi là gần giống


def norm(text: str) -> str:
    text = unicodedata.normalize("NFC", text.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", text)).strip()


def shingles(text: str) -> set[tuple[str, ...]]:
    words = norm(text).split()
    return {tuple(words[i:i + 3]) for i in range(max(1, len(words) - 2))}


def first_user(rec: dict) -> str:
    return rec["messages"][0]["content"] if rec.get("messages") else ""


def find_duplicates(records: list[dict]) -> dict[str, str]:
    """id mẫu trùng -> id mẫu giữ lại. So câu hỏi đầu (nhóm scan so cả câu trả lời vì đầu vào hay lặp lại)."""
    dup, seen_exact = {}, {}
    by_cat = collections.defaultdict(list)
    for r in records:
        key = norm(first_user(r) + (r["messages"][1]["content"] if r["category"] == "scan" else ""))
        if key in seen_exact:
            dup[r["id"]] = seen_exact[key]
            continue
        seen_exact[key] = r["id"]
        by_cat[r["category"]].append(r)
    for recs in by_cat.values():
        kept: list[tuple[str, set]] = []
        for r in recs:
            sh = shingles(first_user(r) if r["category"] != "scan" else r["messages"][1]["content"])
            match = next((rid for rid, s in kept if len(sh & s) / max(1, len(sh | s)) >= NEAR_DUP), None)
            if match:
                dup[r["id"]] = match
            else:
                kept.append((r["id"], sh))
    return dup


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--allow-unreviewed", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    records = load_jsonl(args.path)
    bad = {r.get("id", f"#{i}"): problems(r) for i, r in enumerate(records)}
    bad = {k: v for k, v in bad.items() if v}
    ok = [r for r in records if r.get("id") not in bad]
    dups = find_duplicates(ok)
    clean = [r for r in ok if r["id"] not in dups]
    reviewed = [r for r in clean if r.get("reviewed")]

    print(f"Tổng {len(records)} | lỗi định dạng {len(bad)} | trùng {len(dups)} | dùng được {len(clean)} "
          f"| đã duyệt {len(reviewed)}")
    print(f"{'nhóm':14}{'dùng được':>10}{'đã duyệt':>10}{'TB từ/trả lời':>15}{'có cờ':>8}")
    for c in CATEGORIES:
        rs = [r for r in clean if r["category"] == c]
        words = [len(m["content"].split()) for r in rs for m in r["messages"] if m["role"] == "assistant"]
        flagged = sum(1 for r in rs if auto_flags(r))
        print(f"{c:14}{len(rs):>10}{sum(r.get('reviewed', False) for r in rs):>10}"
              f"{(sum(words) / len(words) if words else 0):>15.0f}{flagged:>8}")
    for rid, errs in list(bad.items())[:15]:
        print(f"  LỖI {rid}: {'; '.join(errs)}")
    for rid, keep in list(dups.items())[:15]:
        print(f"  TRÙNG {rid} ~ {keep}")

    if not args.split:
        return
    pool = clean if args.allow_unreviewed else reviewed
    if not pool:
        raise SystemExit("Chưa có mẫu nào reviewed=true. Duyệt trong review.html trước (hoặc --allow-unreviewed để thử).")
    rnd = random.Random(args.seed)
    parts = {"train": [], "val": [], "test": []}
    for c in CATEGORIES:  # chia theo từng nhóm để tập nào cũng đủ loại
        rs = sorted((r for r in pool if r["category"] == c), key=lambda r: r["id"])
        rnd.shuffle(rs)
        # Tập test là thước đo cuối cùng: ưu tiên mẫu NGƯỜI đã đọc, không lấy mẫu "chấp nhận theo điểm" của model chấm.
        rs.sort(key=lambda r: bool(r.get("auto_accepted")))  # sort ổn định: giữ thứ tự ngẫu nhiên trong mỗi loại
        n_test, n_val = round(len(rs) * 0.1), round(len(rs) * 0.1)
        parts["test"] += rs[:n_test]
        parts["val"] += rs[n_test:n_test + n_val]
        parts["train"] += rs[n_test + n_val:]
    auto_in_test = sum(1 for r in parts["test"] if r.get("auto_accepted"))
    print(f"Chấp nhận theo điểm (không đọc): {sum(1 for r in pool if r.get('auto_accepted'))} mẫu; "
          f"trong tập test: {auto_in_test}" + (" ⚠ nên đọc thêm cho đủ tập test" if auto_in_test else ""))
    for name, rs in parts.items():
        rnd.shuffle(rs)
        if name != "test":  # file để fine-tune: thêm system prompt, chỉ giữ messages
            rs = [{"messages": [{"role": "system", "content": SYSTEM_PROMPT}] + r["messages"]} for r in rs]
        save_jsonl(DATA / f"{name}.jsonl", rs)
        print(f"→ {DATA / (name + '.jsonl')}: {len(rs)} mẫu")


if __name__ == "__main__":
    main()
