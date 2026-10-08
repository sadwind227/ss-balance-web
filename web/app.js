"use strict";

const token = document.querySelector('meta[name="local-token"]').content;
const form = document.getElementById("balance-form");
const numberInput = document.getElementById("number");
const errorBox = document.getElementById("form-error");
const emptyState = document.getElementById("empty-state");
const resultContent = document.getElementById("result-content");
const statusCard = document.querySelector(".status-card");
const solutionList = document.getElementById("solutions");
const cancelButton = document.getElementById("cancel");
const retryButton = document.getElementById("retry");
const submitButton = document.getElementById("submit");
let currentJob = null;
let pollTimer = null;
let lastOptions = null;
const savedSolutions = new Map();

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "X-Local-Token": token, ...(options.body ? { "Content-Type": "application/json" } : {}) },
    cache: "no-store"
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || "请求失败，请重试");
  return data;
}

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = !message;
}

function keyFor(options) {
  return `${options.number}|${options.mode}|${options.allow_multiple}`;
}

function optionsFromForm() {
  const number = numberInput.value.trim();
  if (!/^(0|[1-9][0-9]*)$/.test(number) || number.length > 256) {
    throw new Error("请输入不超过 256 位、没有前导零的非负十进制整数。");
  }
  const target = Number(document.getElementById("target").value);
  if (!Number.isInteger(target) || target < 1 || target > 20) {
    throw new Error("希望找到的方案数应为 1–20。");
  }
  return {
    number,
    mode: document.getElementById("mode").value,
    allow_multiple: form.elements.equals.value === "multiple",
    target
  };
}

function statusDescription(data, shownCount) {
  if (data.existence === "no") return ["无法平衡化", "按照当前规则与等号设置，这个数字没有可行的等式。", "×"];
  if (data.state === "running") {
    return data.existence === "yes"
      ? ["可以平衡化，正在寻找方案", shownCount ? "已找到的等式均已核验，仍在寻找更多写法。" : "正在计算，复杂数字可能需要一些时间。", "✓"]
      : ["正在判断", "尚未完成搜索，当前不能判定是否有解。", "…"];
  }
  if (data.existence === "yes") {
    const detail = shownCount
      ? `已找到 ${shownCount} 个已验证方案。${data.state === "limit" ? "本次搜索达到时限。" : data.state === "incomplete" ? "更多方案的搜索达到计算资源上限。" : data.state === "cancelled" ? "搜索已取消。" : ""}`
      : (data.state === "limit" ? "本次搜索达到时限，尚未生成等式；可以延长时间再试。" : "根据项目数据或定理可以判定有解，当前尚未生成等式。");
    return [shownCount ? "可以平衡化" : "已知可以平衡化", detail, "✓"];
  }
  return ["尚未判定", data.message || "搜索尚未完成，不能将它视为无解。", "?"];
}

function render(data) {
  currentJob = data.id;
  emptyState.hidden = true;
  resultContent.hidden = false;
  const key = keyFor(data);
  const records = savedSolutions.get(key) || new Map();
  for (const record of data.solutions) records.set(record.expression, record);
  savedSolutions.set(key, records);
  const solutions = [...records.values()];
  const [title, detail, symbol] = statusDescription(data, solutions.length);
  statusCard.dataset.state = data.existence;
  document.getElementById("status-icon").textContent = symbol;
  document.getElementById("status-text").textContent = title;
  document.getElementById("status-detail").textContent = detail;
  document.getElementById("basis").textContent = solutions.length ? "已验证方案" : data.basis;
  document.getElementById("solution-count").textContent = String(solutions.length);
  document.getElementById("elapsed").textContent = `已用 ${data.elapsed_seconds} 秒`;
  solutionList.replaceChildren();
  solutions.forEach((item, index) => {
    const li = document.createElement("li");
    const top = document.createElement("div");
    top.className = "solution-top";
    const label = document.createElement("span");
    label.className = "solution-index";
    label.textContent = `方案 ${String(index + 1).padStart(2, "0")}`;
    const copy = document.createElement("button");
    copy.className = "copy-button";
    copy.type = "button";
    copy.textContent = "复制等式";
    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(item.expression);
        copy.textContent = "已复制";
      } catch {
        copy.textContent = "复制失败";
      }
    });
    top.append(label, copy);
    const equation = document.createElement("div");
    equation.className = "equation";
    equation.textContent = item.expression;
    const meta = document.createElement("div");
    meta.className = "solution-meta";
    meta.textContent = `${item.equals_count} 个等号 · 共同值 ${item.common_value} · 精确验证通过`;
    li.append(top, equation, meta);
    solutionList.append(li);
  });
  const none = document.getElementById("no-solutions");
  none.hidden = solutions.length > 0;
  none.textContent = data.existence === "no" ? "没有符合当前设置的等式。" : "当前还没有生成可展示的方案。";
  cancelButton.hidden = data.state !== "running";
  retryButton.hidden = !["limit", "error"].includes(data.state);
  submitButton.disabled = data.state === "running";
  if (data.state === "running") {
    pollTimer = window.setTimeout(() => poll(data.id), 400);
  }
}

async function poll(id) {
  if (id !== currentJob) return;
  try {
    render(await api(`/api/jobs/${id}`));
  } catch (error) {
    showError(error.message);
    submitButton.disabled = false;
  }
}

async function start(options, budget = 30) {
  window.clearTimeout(pollTimer);
  showError("");
  submitButton.disabled = true;
  try {
    lastOptions = options;
    const data = await api("/api/jobs", { method: "POST", body: JSON.stringify({ ...options, budget }) });
    render(data);
  } catch (error) {
    showError(error.message);
    submitButton.disabled = false;
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  try {
    start(optionsFromForm());
  } catch (error) {
    showError(error.message);
  }
});

cancelButton.addEventListener("click", async () => {
  if (!currentJob) return;
  window.clearTimeout(pollTimer);
  try { render(await api(`/api/jobs/${currentJob}/cancel`, { method: "POST", body: "{}" })); }
  catch (error) { showError(error.message); }
});

retryButton.addEventListener("click", () => { if (lastOptions) start(lastOptions, 90); });
document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    numberInput.value = button.dataset.example;
    if (button.dataset.example === "222") form.elements.equals.value = "multiple";
    numberInput.focus();
  });
});
