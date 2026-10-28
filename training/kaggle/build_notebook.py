"""Sinh 2 notebook Kaggle cho dữ liệu chat:
- generate_drafts.ipynb: sinh bản nháp (generate.py)
- judge_drafts.ipynb:    model lớn chấm sơ bộ bản nháp (judge.py) để người duyệt đọc mẫu điểm thấp trước

Mã nguồn và dữ liệu cần dùng được NHÚNG vào notebook (zip → base64), nên trên Kaggle không cần tải dataset.
Sửa code trong training/chat_data rồi chạy lại:

    python training/kaggle/build_notebook.py
"""
import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "chat_data"
HERE = Path(__file__).resolve().parent


def payload(files: list[str]) -> tuple[str, str]:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in files:
            z.writestr(name, (SRC / name).read_bytes())
    # "bản code" đổi mỗi khi code/dữ liệu đổi: nhìn tiêu đề notebook trên Kaggle là biết đang chạy bản nào.
    return base64.b64encode(buf.getvalue()).decode(), hashlib.sha256(buf.getvalue()).hexdigest()[:8]


def md(cells, text):
    cells.append({"cell_type": "markdown", "metadata": {}, "source": text.strip("\n").splitlines(keepends=True)})


def code(cells, text):
    cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": text.strip("\n").splitlines(keepends=True)})


def extract_cell(cells, data: str, version: str, resume_file: str) -> None:
    code(cells, f"""
# Ô 2 – Giải nén mã nguồn + dữ liệu (nhúng sẵn, bản {version}) vào /kaggle/working/chat_data
import base64, io, os, shutil, zipfile

WORK = "/kaggle/working/chat_data"
PAYLOAD = "{data}"
zipfile.ZipFile(io.BytesIO(base64.b64decode(PAYLOAD))).extractall(WORK)  # ghi đè code cũ nếu có
for d, _, files in os.walk("/kaggle/input", followlinks=True):  # chạy tiếp: nạp {resume_file} đã tải lên
    if "{resume_file}" in files and not os.path.exists(f"{{WORK}}/data/{resume_file}"):
        shutil.copy(os.path.join(d, "{resume_file}"), f"{{WORK}}/data/{resume_file}")
        print("Chạy tiếp từ", os.path.join(d, "{resume_file}"))
print("Bản code {version}:", sorted(os.listdir(WORK)), os.listdir(f"{{WORK}}/data"))
""")


def vllm_cell(cells) -> None:
    code(cells, """
# Ô 3 – Cài vLLM và bật server kiểu OpenAI (lần đầu mất ~5–10 phút: cài thư viện + tải model)
!pip install -q vllm
# vLLM kéo PyTorch bản CUDA mới, lệch với TorchAudio có sẵn của Kaggle → transformers nạp TorchAudio là lỗi.
# Không cần xử lý âm thanh nên gỡ đi.
!pip uninstall -y -q torchaudio
import torch
print("torch", torch.__version__, "| CUDA", torch.version.cuda, "| GPU dùng được:", torch.cuda.is_available())
assert torch.cuda.is_available(), "PyTorch không thấy GPU (driver Kaggle cũ hơn bản CUDA của PyTorch?) — gửi dòng trên"
import subprocess, time, urllib.request

log = open("/kaggle/working/vllm.log", "w")
server = subprocess.Popen(
    ["python", "-m", "vllm.entrypoints.openai.api_server", "--model", MODEL, "--port", str(PORT),
     "--tensor-parallel-size", str(TP), "--dtype", "half",          # T4 không có bfloat16
     "--max-model-len", "8192", "--gpu-memory-utilization", "0.92"],
    stdout=log, stderr=subprocess.STDOUT)
ready = False
for i in range(180):
    try:
        urllib.request.urlopen(f"http://localhost:{PORT}/v1/models", timeout=5)
        ready = True
        print(f"Server sẵn sàng sau {i * 10} giây"); break
    except Exception:
        if server.poll() is not None:
            break  # vLLM đã dừng: in log bên dưới
        time.sleep(10)
log.flush()
if not ready:
    print("".join(open("/kaggle/working/vllm.log", encoding="utf-8", errors="replace").readlines()[-60:]))
    raise RuntimeError("vLLM không chạy được — gửi 60 dòng log ở trên")
""")


def save(name: str, cells: list, version: str) -> None:
    out = HERE / name
    nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
          "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                       "language_info": {"name": "python"}}}
    out.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK {out} (bản code {version}, {out.stat().st_size // 1024} KB)")


def generate_notebook() -> None:
    data, version = payload(["common.py", "generate.py", "check.py", "seeds.json", "system_prompt.txt",
                             "data/scan_inputs.jsonl"])
    cells = []
    md(cells, f"""
# PhishGuard – Sinh bản nháp dữ liệu chat bằng Qwen3 (Giai đoạn 2) · bản code `{version}`

**Trước khi chạy** (khung bên phải của Kaggle → *Settings*): *Accelerator* **GPU T4 x2**, *Internet* **On**.
Không cần thêm dataset: mã nguồn và dữ liệu đã nhúng sẵn trong ô 2.

Chạy lần lượt từng ô. Ô 4 mặc định `LIMIT = 20` để **thử trước** (rải đều 5 nhóm): xem chất lượng ở ô 5,
ổn rồi đặt `LIMIT = 0` và chạy lại ô 4 (mẫu đã có được giữ, không sinh lại).

Kết quả: `/kaggle/working/drafts.jsonl` → tải về (khung *Output* bên phải), chép vào `training/chat_data/data/`.
Phiên Kaggle tối đa ~12 giờ; nên tải `drafts.jsonl` về định kỳ. **Chạy tiếp** lần sau: *Add Input* → *Upload*
file `drafts.jsonl` đã tải về, ô 2 sẽ tự nạp lại.
""")
    code(cells, """
# Ô 1 – Cấu hình
MODEL = "Qwen/Qwen3-14B-AWQ"  # model sinh nháp. Kiểm tra trên huggingface.co/Qwen: bản Instruct mới nhất có AWQ,
                              # giấy phép Apache 2.0. Hết VRAM thì đổi "Qwen/Qwen3-8B-AWQ".
TP = 2           # số GPU (T4 x2)
WORKERS = 32     # số yêu cầu gửi song song (vLLM tự gộp lại xử lý)
PORT = 8000
""")
    extract_cell(cells, data, version, "drafts.jsonl")
    vllm_cell(cells)
    code(cells, """
# Ô 4 – Sinh bản nháp (LIMIT = 20 để thử; ổn rồi đặt 0 và chạy lại ô này)
LIMIT = 20
ARGS = f"--base-url http://localhost:{PORT}/v1 --model {MODEL} --workers {WORKERS} --no-think --temperature 0.8"
if LIMIT:
    ARGS += f" --limit {LIMIT}"
!cd $WORK && python generate.py $ARGS
!cp $WORK/data/drafts.jsonl /kaggle/working/drafts.jsonl
""")
    code(cells, """
# Ô 5 – Thống kê + xem vài mẫu
!cd $WORK && python check.py data/drafts.jsonl
import json, random
rows = [json.loads(l) for l in open(f"{WORK}/data/drafts.jsonl", encoding="utf-8")]
for r in random.sample(rows, min(3, len(rows))):
    print("=" * 80, "\\n", r["id"], r.get("flags"))
    for m in r["messages"]:
        print(f"--- {m['role']}:\\n{m['content'][:1200]}")
""")
    save("generate_drafts.ipynb", cells, version)


def judge_notebook() -> None:
    data, version = payload(["common.py", "generate.py", "judge.py", "system_prompt.txt", "data/to_review.jsonl"])
    cells = []
    md(cells, f"""
# PhishGuard – Model lớn chấm sơ bộ bản nháp (Giai đoạn 2) · bản code `{version}`

Model chấm (mặc định **Qwen3-32B**, lớn hơn model đã sinh nháp) cho mỗi mẫu điểm 1–5 + lỗi + gợi ý sửa.
Người duyệt đọc kỹ mẫu điểm thấp trước (`review.html`); model chấm **không thay** người duyệt.

**Trước khi chạy**: *Accelerator* **GPU T4 x2**, *Internet* **On**. Không cần dataset (dữ liệu nhúng trong ô 2).
Ô 4 mặc định `LIMIT = 30` để **thử trước**; ổn rồi đặt `LIMIT = 0` và chạy lại ô 4.

Kết quả: `/kaggle/working/judged.jsonl` → tải về, chép vào `training/chat_data/data/`. **Chạy tiếp** sau khi bị
ngắt: *Add Input* → *Upload* file `judged.jsonl` đã tải về, ô 2 tự nạp lại.
""")
    code(cells, """
# Ô 1 – Cấu hình
MODEL = "Qwen/Qwen3-32B-AWQ"  # model chấm: nên LỚN HƠN model sinh nháp (Qwen3-14B) để bắt được lỗi của nó.
                              # vLLM báo thiếu bộ nhớ thì đổi "Qwen/Qwen3-14B-AWQ" (yếu hơn nhưng vẫn có ích).
TP = 2
WORKERS = 32
PORT = 8000
""")
    extract_cell(cells, data, version, "judged.jsonl")
    vllm_cell(cells)
    code(cells, """
# Ô 4 – Chấm (LIMIT = 30 để thử, rải đều cả file; ổn rồi đặt 0 và chạy lại ô này)
LIMIT = 30
ARGS = f"--base-url http://localhost:{PORT}/v1 --model {MODEL} --workers {WORKERS} --no-think"
if LIMIT:
    ARGS += f" --limit {LIMIT}"
!cd $WORK && python judge.py $ARGS
!cp $WORK/data/judged.jsonl /kaggle/working/judged.jsonl
""")
    code(cells, """
# Ô 5 – Phân bố điểm theo nhóm + xem vài mẫu điểm thấp
import json, collections, random
rows = [json.loads(l) for l in open(f"{WORK}/data/judged.jsonl", encoding="utf-8")]
by = collections.defaultdict(collections.Counter)
for r in rows:
    by[r["category"]][r["judge"]["score"]] += 1
for c, cnt in by.items():
    print(f"{c:14}", {s: cnt[s] for s in range(1, 6)})
low = [r for r in rows if r["judge"]["score"] <= 3]
for r in random.sample(low, min(3, len(low))):
    print("=" * 80, "\\n", r["id"], "→", r["judge"])
    for m in r["messages"]:
        print(f"--- {m['role']}:\\n{m['content'][:800]}")
""")
    save("judge_drafts.ipynb", cells, version)


if __name__ == "__main__":
    generate_notebook()
    judge_notebook()
