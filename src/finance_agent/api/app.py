from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from finance_agent import __version__
from finance_agent.graph.runtime import FinanceAgentRuntime


class RunRequest(BaseModel):
    question: str
    session_id: str | None = None  # 用于 session 管理


class MethodReviewRevisionRequest(BaseModel):
    instruction: str


class RunResponse(BaseModel):
    request_id: str
    status: str
    answer: str | None = None
    errors: list[str] = []
    result_ref: str | None = None
    referenced_result_ref: str | None = None
    public_memory_entry: dict[str, Any] | None = None
    public_memory_context: list[dict[str, Any]] | None = None
    response_plan: dict[str, Any] | None = None
    action_validation: dict[str, Any] | None = None
    selected_skill_detail: dict[str, Any] | None = None
    tool_decision: dict[str, Any] | None = None
    planner_used: str | None = None
    sql: str | None = None
    row_count: int | None = None
    analysis_plan: dict[str, Any] | None = None
    analysis_plan_review_card: dict[str, Any] | None = None
    method_draft: dict[str, Any] | None = None
    method_drafts: list[dict[str, Any]] | None = None
    harness_review: dict[str, Any] | None = None
    harness_reviews: list[dict[str, Any]] | None = None
    mock_result: dict[str, Any] | None = None
    mock_results: list[dict[str, Any]] | None = None
    internal_method_review: dict[str, Any] | None = None
    method_review_card: dict[str, Any] | None = None
    method_review_cards: list[dict[str, Any]] | None = None
    method_set_review_card: dict[str, Any] | None = None
    data_authorization_card: dict[str, Any] | None = None
    prior_result_authorization_card: dict[str, Any] | None = None
    execution_result_card: dict[str, Any] | None = None
    execution_result_cards: list[dict[str, Any]] | None = None
    result_narration: dict[str, Any] | None = None
    result_narrations: list[dict[str, Any]] | None = None
    audit: dict[str, Any] | None = None


@lru_cache(maxsize=1)
def runtime() -> FinanceAgentRuntime:
    return FinanceAgentRuntime()


app = FastAPI(title="Finance Agent Runtime", version=__version__)

PENDING_RUNS: dict[str, dict[str, Any]] = {}

PENDING_REVIEW_STATUSES = {
    "analysis_plan_review_ready",
    "method_review_ready",
    "data_authorization_pending",
    "prior_result_authorization_pending",
}


CHAT_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Finance Agent</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f5; }
    .main { display: flex; height: 100vh; overflow: hidden; }
    .chat-panel { flex: 1; display: flex; flex-direction: column; background: white; border-right: 1px solid #e5e5e5; min-width: 0; overflow: hidden; }
    .debug-panel { width: 400px; min-width: 400px; background: #1e1e1e; color: #d4d4d4; display: flex; flex-direction: column; overflow: hidden; }
    .debug-header { padding: 12px 16px; background: #252526; border-bottom: 1px solid #3c3c3c; display: flex; align-items: center; justify-content: space-between; }
    .debug-header h2 { font-size: 14px; font-weight: 600; color: #cccccc; }
    .debug-content { flex: 1; overflow-y: auto; padding: 12px; font-family: 'Monaco', 'Menlo', monospace; font-size: 12px; line-height: 1.6; }
    .debug-entry { margin-bottom: 12px; padding: 8px; background: #2d2d2d; border-radius: 4px; border-left: 3px solid #007acc; }
    .debug-entry.error { border-left-color: #f44747; }
    .debug-entry.success { border-left-color: #6a9955; }
    .debug-entry .label { color: #569cd6; font-weight: 600; margin-bottom: 4px; }
    .debug-entry .content { color: #d4d4d4; white-space: pre-wrap; word-break: break-word; }
    .debug-entry .content .key { color: #9cdcfe; }
    .debug-entry .content .string { color: #ce9178; }
    .debug-entry .content .number { color: #b5cea8; }
    .debug-entry .content .null { color: #808080; }
    .header { padding: 16px; border-bottom: 1px solid #e5e5e5; display: flex; align-items: center; gap: 8px; }
    .header h1 { font-size: 18px; font-weight: 600; }
    .status { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; }
    .status.loading { background: #3b82f6; animation: pulse 1s infinite; }
    @keyframes pulse { 50% { opacity: 0.5; } }
    .thinking { display: flex; gap: 8px; align-items: center; padding: 8px 0; }
    .thinking-avatar { width: 36px; height: 36px; border-radius: 50%; background: #e5e7eb; display: flex; align-items: center; justify-content: center; font-size: 14px; }
    .thinking-text { color: #6b7280; font-size: 14px; }
    .thinking-dots { display: flex; gap: 4px; }
    .thinking-dots span { width: 8px; height: 8px; border-radius: 50%; background: #9ca3af; animation: thinking 1.4s infinite; }
    .thinking-dots span:nth-child(2) { animation-delay: 0.2s; }
    .thinking-dots span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes thinking { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.5; } 40% { transform: scale(1); opacity: 1; } }
    .messages { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
    .msg { display: flex; gap: 8px; }
    .msg.user { flex-direction: row-reverse; }
    .msg-avatar { width: 36px; height: 36px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; flex-shrink: 0; }
    .msg.user .msg-avatar { background: #3b82f6; color: white; }
    .msg.bot .msg-avatar { background: #e5e7eb; }
    .msg-content { max-width: 70%; padding: 10px 14px; border-radius: 12px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; overflow: hidden; }
    .msg.user .msg-content { background: #3b82f6; color: white; border-bottom-right-radius: 4px; }
    .msg.bot .msg-content { background: #f3f4f6; border-bottom-left-radius: 4px; max-width: 85%; overflow: hidden; }
    .msg-content pre { background: #1e1e1e; color: #d4d4d4; padding: 12px; border-radius: 6px; margin: 8px 0; overflow-x: auto; font-size: 13px; line-height: 1.4; }
    .msg-content .table-wrapper { overflow-x: auto; margin: 8px 0; border: 1px solid #e5e7eb; border-radius: 6px; }
    .msg-content table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 600px; }
    .msg-content th, .msg-content td { padding: 6px 10px; border: 1px solid #e5e7eb; text-align: left; white-space: nowrap; }
    .msg-content th { background: #f9fafb; font-weight: 600; position: sticky; top: 0; }
    .msg-content td.num { text-align: right; }
    .msg-content .note { font-size: 12px; color: #6b7280; margin-top: 4px; }
    .msg-content .sandbox { background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 6px; padding: 8px 12px; margin-top: 8px; font-size: 13px; color: #166534; }
    .msg-actions { display: flex; gap: 8px; margin-top: 10px; }
    .btn { padding: 8px 16px; border-radius: 6px; font-size: 14px; font-weight: 500; cursor: pointer; border: none; }
    .btn-primary { background: #3b82f6; color: white; }
    .btn-primary:hover { background: #2563eb; }
    .btn-secondary { background: white; color: #374151; border: 1px solid #d1d5db; }
    .btn-secondary:hover { background: #f9fafb; }
    .empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #9ca3af; text-align: center; }
    .input-area { padding: 18px 24px; border-top: 1px solid #e5e7eb; }
    .input-form { display: flex; gap: 14px; align-items: center; }
    .input-form input { flex: 1; padding: 16px 20px; border: 1px solid #d1d5db; border-radius: 10px; font-size: 18px; outline: none; transition: border-color 0.2s; }
    .input-form input:focus { border-color: #3b82f6; box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1); }
    .input-form input::placeholder { color: #9ca3af; }
    .input-form button { padding: 16px 32px; background: #3b82f6; color: white; border: none; border-radius: 10px; font-size: 18px; font-weight: 500; cursor: pointer; transition: background 0.2s; }
    .input-form button:hover { background: #2563eb; }
    .input-form button:disabled { opacity: 0.5; cursor: not-allowed; }
    .toggle-debug { padding: 4px 8px; font-size: 11px; background: #3c3c3c; color: #cccccc; border: none; border-radius: 3px; cursor: pointer; }
    .toggle-debug:hover { background: #4c4c4c; }
  </style>
</head>
<body>
  <div class="main">
    <div class="chat-panel">
      <div class="header">
        <div class="status" id="status"></div>
        <h1>Finance Agent</h1>
        <select id="sessionSelect" style="margin-left: 12px; padding: 4px 8px; font-size: 12px; border: 1px solid #ddd; border-radius: 4px; max-width: 200px;" onchange="switchSession(this.value)">
          <option value="">选择会话...</option>
        </select>
        <button onclick="createNewSession()" style="margin-left: 8px; padding: 4px 12px; font-size: 12px; background: #3b82f6; color: white; border: none; border-radius: 4px; cursor:pointer;">新建会话</button>
        <button onclick="deleteCurrentSession()" style="margin-left: 4px; padding: 4px 12px; font-size: 12px; background: #ef4444; color: white; border: none; border-radius: 4px; cursor:pointer;">删除会话</button>
        <button onclick="clearMemory()" style="margin-left:auto;padding:4px 12px;font-size:12px;background:#f5f5f5;border:1px solid #ddd;border-radius:4px;cursor:pointer;">清空记忆</button>
      </div>
      <div class="messages" id="messages">
        <div class="empty" id="empty">输入问题开始分析<br>例如：统计每个交易状态有多少笔</div>
      </div>
      <div class="input-area">
        <form class="input-form" id="form">
          <input type="text" id="input" placeholder="输入问题..." autocomplete="off">
          <button type="submit" id="submit">发送</button>
        </form>
      </div>
    </div>
    <div class="debug-panel" id="debugPanel">
      <div class="debug-header">
        <h2>🔍 LLM 调试看板</h2>
        <button class="toggle-debug" onclick="clearDebug()">清空</button>
      </div>
      <div class="debug-content" id="debugContent">
        <div style="color: #808080; text-align: center; padding: 20px;">发送消息后，LLM 的输出将在这里实时显示</div>
      </div>
    </div>
  </div>
  <script>
    var messagesEl = document.getElementById("messages");
    var emptyEl = document.getElementById("empty");
    var inputEl = document.getElementById("input");
    var submitBtn = document.getElementById("submit");
    var statusEl = document.getElementById("status");
    var debugContent = document.getElementById("debugContent");
    var sessionSelect = document.getElementById("sessionSelect");
    var currentRequestId = null;
    var currentSessionId = null;
    var pendingActions = {};  // request_id -> {approve: fn, cancel: fn}

    // Session 管理函数
    async function loadSessions() {
      try {
        var response = await fetch("/v1/sessions");
        var sessions = await response.json();
        sessionSelect.innerHTML = '<option value="">选择会话...</option>';
        sessions.forEach(function(session) {
          var option = document.createElement("option");
          option.value = session.session_id;
          option.textContent = session.title + " (" + session.message_count + " 条消息)";
          if (session.session_id === currentSessionId) {
            option.selected = true;
          }
          sessionSelect.appendChild(option);
        });
      } catch (e) {
        console.error("加载会话列表失败:", e);
      }
    }

    async function createNewSession() {
      try {
        var response = await fetch("/v1/sessions", { method: "POST" });
        var session = await response.json();
        currentSessionId = session.session_id;
        await loadSessions();
        clearMessages();
        addDebugEntry("✅ 新会话", "已创建: " + session.session_id, "success");
      } catch (e) {
        console.error("创建会话失败:", e);
      }
    }

    async function switchSession(sessionId) {
      if (!sessionId) return;
      currentSessionId = sessionId;
      clearMessages();
      // 加载会话历史
      try {
        var response = await fetch("/v1/sessions/" + sessionId + "/history");
        var data = await response.json();
        data.history.forEach(function(msg) {
          addMsg(msg.role === "user" ? "user" : "bot", escapeHtml(msg.content));
        });
        addDebugEntry("✅ 切换会话", "已切换到: " + sessionId, "success");
      } catch (e) {
        console.error("加载会话历史失败:", e);
      }
    }

    async function deleteCurrentSession() {
      if (!currentSessionId) {
        alert("请先选择一个会话");
        return;
      }
      if (!confirm("确定要删除这个会话吗？")) return;
      try {
        await fetch("/v1/sessions/" + currentSessionId, { method: "DELETE" });
        currentSessionId = null;
        await loadSessions();
        clearMessages();
        addDebugEntry("✅ 删除会话", "会话已删除", "success");
      } catch (e) {
        console.error("删除会话失败:", e);
      }
    }

    function clearMessages() {
      messagesEl.innerHTML = '<div class="empty" id="empty">输入问题开始分析<br>例如：统计每个交易状态有多少笔</div>';
      emptyEl = document.getElementById("empty");
    }

    // 初始化：加载会话列表，如果没有会话则创建一个
    loadSessions().then(function() {
      if (sessionSelect.options.length <= 1) {
        createNewSession();
      } else {
        // 选择第一个会话
        currentSessionId = sessionSelect.options[1].value;
        switchSession(currentSessionId);
      }
    });

    // 调试看板函数
    function addDebugEntry(label, content, type) {
      var entry = document.createElement("div");
      entry.className = "debug-entry" + (type === "error" ? " error" : type === "success" ? " success" : "");
      var labelEl = document.createElement("div");
      labelEl.className = "label";
      labelEl.textContent = label;
      var contentEl = document.createElement("div");
      contentEl.className = "content";
      contentEl.textContent = typeof content === "object" ? JSON.stringify(content, null, 2) : content;
      entry.appendChild(labelEl);
      entry.appendChild(contentEl);
      debugContent.appendChild(entry);
      debugContent.scrollTop = debugContent.scrollHeight;
    }

    function clearDebug() {
      debugContent.innerHTML = '<div style="color: #808080; text-align: center; padding: 20px;">发送消息后，LLM 的输出将在这里实时显示</div>';
    }

    function formatJsonForDebug(obj) {
      if (!obj) return "null";
      return JSON.stringify(obj, null, 2);
    }

    function addMsg(role, html, extraClass) {
      if (emptyEl) emptyEl.style.display = "none";
      var div = document.createElement("div");
      div.className = "msg " + role + (extraClass ? " " + extraClass : "");
      var avatar = document.createElement("div");
      avatar.className = "msg-avatar";
      avatar.textContent = role === "user" ? "U" : "AI";
      var content = document.createElement("div");
      content.className = "msg-content";
      content.innerHTML = html;
      div.appendChild(avatar);
      div.appendChild(content);
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
      return content;
    }

    function escapeHtml(text) {
      return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
    }

    function formatAnswer(answer) {
      if (!answer) return "未生成回复";
      var html = escapeHtml(answer);
      html = html.replace(/```sql\\n([\\s\\S]*?)```/g, function(m, code) { return "<pre>" + code.trim() + "</pre>"; });
      html = html.replace(/```\\n((?:SELECT|INSERT|UPDATE|DELETE)[\\s\\S]*?)```/gi, function(m, code) { return "<pre>" + code.trim() + "</pre>"; });
      html = html.replace(/```python\\n([\\s\\S]*?)```/g, function(m, code) { return "<pre>" + code.trim() + "</pre>"; });
      html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
      return html;
    }

    function formatResult(result) {
      if (!result || !Array.isArray(result) || result.length === 0) return '<div class="sandbox">查询结果为空</div>';
      var rows = result.slice(0, 20);
      var cols = Object.keys(rows[0]);
      var html = '<div class="table-wrapper"><table><thead><tr>';
      cols.forEach(function(c) { html += "<th>" + escapeHtml(c) + "</th>"; });
      html += "</tr></thead><tbody>";
      rows.forEach(function(row) {
        html += "<tr>";
        cols.forEach(function(c) {
          var v = row[c];
          if (typeof v === "number") {
            html += '<td class="num">' + (Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, {maximumFractionDigits: 2})) + "</td>";
          } else {
            html += "<td>" + escapeHtml(String(v == null ? "" : v)) + "</td>";
          }
        });
        html += "</tr>";
      });
      html += "</tbody></table></div>";
      if (result.length > 20) {
        html += '<div class="note">显示前 20 条，共 ' + result.length + " 条</div>";
      }
      return html;
    }

    function addActions(actions, requestId) {
      var div = document.createElement("div");
      div.className = "msg-actions";
      actions.forEach(function(a) {
        var btn = document.createElement("button");
        btn.className = "btn " + (a.primary ? "btn-primary" : "btn-secondary");
        btn.textContent = a.label;
        btn.onclick = a.onClick;
        div.appendChild(btn);
      });
      var lastMsg = messagesEl.querySelector(".msg:last-child .msg-content");
      if (lastMsg) lastMsg.appendChild(div);
    }

    function showThinking() {
      if (emptyEl) emptyEl.style.display = "none";
      var div = document.createElement("div");
      div.className = "thinking";
      div.id = "thinking";
      div.innerHTML = '<div class="thinking-avatar">AI</div><div class="thinking-text">正在思考</div><div class="thinking-dots"><span></span><span></span><span></span></div>';
      messagesEl.appendChild(div);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function hideThinking() {
      var el = document.getElementById("thinking");
      if (el) el.remove();
    }

    function setLoading(loading) {
      submitBtn.disabled = loading;
      submitBtn.textContent = loading ? "..." : "发送";
      statusEl.className = "status" + (loading ? " loading" : "");
      if (loading) showThinking(); else hideThinking();
    }

    async function submit() {
      var text = inputEl.value.trim();
      if (!text) return;

      // 如果没有当前会话，创建一个
      if (!currentSessionId) {
        await createNewSession();
      }

      addMsg("user", escapeHtml(text));
      inputEl.value = "";
      setLoading(true);

      // 清空调试看板
      clearDebug();
      addDebugEntry("📤 用户输入", text);
      addDebugEntry("⏳ 请求状态", "正在连接 SSE...");

      try {
        // 使用 SSE 接收实时事件（GET 请求）
        var eventSource = new EventSource("/v1/runs/stream?question=" + encodeURIComponent(text) + "&session_id=" + encodeURIComponent(currentSessionId));

        eventSource.onmessage = function(event) {
          var data = JSON.parse(event.data);

          switch(data.type) {
            case "start":
              addDebugEntry("🚀 开始处理", data.message);
              break;
            case "response_plan":
              addDebugEntry("🧠 Response Plan", formatJsonForDebug(data.data));
              break;
            case "action_validation":
              addDebugEntry("✅ Action Validation", formatJsonForDebug(data.data));
              break;
            case "method_draft":
              addDebugEntry("📋 Method Draft", formatJsonForDebug(data.data));
              break;
            case "sql":
              addDebugEntry("💾 SQL", data.data);
              break;
            case "errors":
              addDebugEntry("❌ 错误", data.data.join("\\n"), "error");
              break;
            case "complete":
              addDebugEntry("✅ 完成", "状态: " + data.data.status, "success");
              handleResponse(data.data);
              eventSource.close();
              setLoading(false);
              break;
            case "error":
              addDebugEntry("❌ SSE 错误", data.message, "error");
              eventSource.close();
              setLoading(false);
              break;
          }
        };

        eventSource.onerror = function(e) {
          addDebugEntry("❌ SSE 连接错误", "连接断开", "error");
          eventSource.close();
          setLoading(false);
        };

      } catch (e) {
        addMsg("bot", "请求失败：" + escapeHtml(e.message));
        addDebugEntry("❌ 请求失败", e.message, "error");
        setLoading(false);
      }
    }

    function handleResponse(data) {
      var requestId = data.request_id;
      currentRequestId = requestId;
      var answer = data.answer || "未生成回复";
      var status = data.status;
      var html = formatAnswer(answer);

      if (status === "executed_simulated_real" && data.execution_result_card) {
        html += formatResult(data.execution_result_card.result);
        html += '<div class="sandbox">沙箱执行完成 · 未连接真实数据库</div>';
        addMsg("bot", html);
      } else if (status === "method_execution_failed") {
        html += '<div class="sandbox" style="color: red;">执行失败 · 请检查查询条件</div>';
        addMsg("bot", html);
      } else if (status === "analysis_plan_review_ready") {
        addMsg("bot", html);
        addActions([
          { label: "确认计划", primary: true, onClick: function() { approve("analysis-plan", requestId); } },
          { label: "修改", onClick: function() { addMsg("bot", "好的，请告诉我你想怎么修改~"); } }
        ], requestId);
      } else if (status === "method_review_ready") {
        addMsg("bot", html, "pending-approval");
        addActions([
          { label: "确认执行", primary: true, onClick: function() { approve("method-review", requestId); } },
          { label: "修改", onClick: function() { addMsg("bot", "好的，请告诉我你想怎么修改~"); } }
        ], requestId);
      } else if (status === "prior_result_authorization_pending") {
        addMsg("bot", html);
        addActions([
          { label: "授权执行", primary: true, onClick: function() { approve("prior-result-authorization", requestId); } },
          { label: "取消", onClick: function() { addMsg("bot", "好的，已取消执行。"); } }
        ], requestId);
      } else {
        addMsg("bot", html);
      }
    }

    async function approve(action, requestId) {
      if (!requestId) return;
      setLoading(true);
      addDebugEntry("🔘 用户操作", "确认: " + action);
      addDebugEntry("⏳ 执行状态", "正在执行查询...");
      try {
        var res = await fetch("/v1/runs/" + encodeURIComponent(requestId) + "/" + action + "/approve", { method: "POST" });
        var data = await res.json();

        // 更新看板
        addDebugEntry("📥 执行响应", "状态: " + data.status, data.status === "executed_simulated_real" ? "success" : "");

        if (data.execution_result_card) {
          addDebugEntry("🎯 执行结果", formatJsonForDebug(data.execution_result_card));
        }

        if (data.sql) {
          addDebugEntry("💾 执行的 SQL", data.sql);
        }

        if (data.errors && data.errors.length > 0) {
          addDebugEntry("❌ 错误", data.errors.join("\\n"), "error");
        }

        // 执行结果在原框更新，不新增消息
        handleApprovalResponse(data);
      } catch (e) {
        addMsg("bot", "操作失败：" + escapeHtml(e.message));
        addDebugEntry("❌ 操作失败", e.message, "error");
      } finally {
        setLoading(false);
      }
    }

    function handleApprovalResponse(data) {
      var status = data.status;
      var answer = data.answer || "未生成回复";
      var html = formatAnswer(answer);

      if (status === "executed_simulated_real" && data.execution_result_card) {
        html += formatResult(data.execution_result_card.result);
        html += '<div class="sandbox">沙箱执行完成 · 未连接真实数据库</div>';
        addMsg("bot", html);
      } else if (status === "method_execution_failed") {
        html += '<div class="sandbox" style="color: red;">执行失败 · 请检查查询条件</div>';
        addMsg("bot", html);
      } else {
        addMsg("bot", html);
      }
    }

    async function clearMemory() {
      if (!confirm("确定要清空所有记忆吗？这将删除历史分析记录。")) return;
      try {
        var res = await fetch("/api/clear-memory", { method: "POST" });
        var data = await res.json();
        addMsg("bot", "✅ " + data.message);
      } catch (e) {
        addMsg("bot", "清空失败：" + escapeHtml(e.message));
      }
    }

    document.getElementById("form").addEventListener("submit", function(e) { e.preventDefault(); submit(); });
    inputEl.addEventListener("keydown", function(e) {
      if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
        e.preventDefault();
        submit();
      }
    });
  </script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def chat_page() -> str:
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "finance-agent-runtime", "version": __version__}


@app.post("/v1/runs", response_model=RunResponse)
async def create_run(request: RunRequest) -> RunResponse:
    # 不再清除 pending runs，让每个请求独立管理自己的生命周期
    state = await runtime().invoke(request.question, session_id=request.session_id)
    request_id = state.get("request_id", "")
    _sync_pending_review(state)
    return _response_from_state(state)


@app.get("/v1/runs/stream")
async def create_run_stream(question: str, session_id: str | None = None):
    """SSE 端点：实时推送 LLM 处理过程。"""
    async def event_generator():
        try:
            # 发送开始事件
            yield f"data: {json.dumps({'type': 'start', 'message': '开始处理请求...'})}\n\n"

            # 调用 runtime
            state = await runtime().invoke(question, session_id=session_id)

            # 发送 Response Plan
            if state.get("response_plan"):
                yield f"data: {json.dumps({'type': 'response_plan', 'data': state['response_plan']})}\n\n"

            # 发送 Action Validation
            if state.get("action_validation"):
                yield f"data: {json.dumps({'type': 'action_validation', 'data': state['action_validation']})}\n\n"

            # 发送 Method Draft
            if state.get("method_draft"):
                yield f"data: {json.dumps({'type': 'method_draft', 'data': state['method_draft']})}\n\n"

            # 发送 SQL
            if state.get("sql"):
                yield f"data: {json.dumps({'type': 'sql', 'data': state['sql']})}\n\n"

            # 发送错误
            if state.get("errors"):
                yield f"data: {json.dumps({'type': 'errors', 'data': state['errors']})}\n\n"

            # 先把待确认卡/运行详情写入 session，再通知浏览器完成。
            # 否则用户在收到卡片后立刻刷新会中断 SSE 生成器，导致状态尚未落盘。
            _sync_pending_review(state)

            # 发送最终结果
            response = _response_from_state(state)
            yield f"data: {json.dumps({'type': 'complete', 'data': response.model_dump()})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@app.post("/v1/runs/{request_id}/analysis-plan/approve", response_model=RunResponse)
async def approve_analysis_plan(request_id: str) -> RunResponse:
    state = PENDING_RUNS.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="pending analysis plan review not found")
    try:
        state = await runtime().approve_analysis_plan(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _sync_pending_review(state)
    return _response_from_state(state)


@app.post("/v1/runs/{request_id}/method-review/approve", response_model=RunResponse)
async def approve_method_review(request_id: str) -> RunResponse:
    # 优先使用 request_id；兼容旧版 thread_ 缓存键。
    state = PENDING_RUNS.get(request_id)
    if state is None:
        # 兼容旧版 thread_ 缓存键。
        for key, value in PENDING_RUNS.items():
            if key.startswith("thread_") and value.get("request_id") == request_id:
                state = value
                break
    if state is None:
        raise HTTPException(status_code=404, detail="pending method review not found")
    try:
        state = await runtime().approve_method_review(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _sync_pending_review(state)
    return _response_from_state(state)


@app.post("/v1/runs/{request_id}/method-review/revise", response_model=RunResponse)
async def revise_method_review(request_id: str, request: MethodReviewRevisionRequest) -> RunResponse:
    """修订待确认的方法集合；修订后仍需用户再次确认执行。"""
    state = PENDING_RUNS.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="pending method review not found")
    try:
        state = await runtime().revise_method_review(state, request.instruction)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _sync_pending_review(state)
    # 修订本身也是用户消息；只保存修订说明和安全方法卡，不保存结果行。
    session_id = state.get("session_id")
    if session_id:
        runtime().session_manager.add_message(session_id, "user", request.instruction)
        if state.get("answer"):
            runtime().session_manager.add_message(session_id, "assistant", state["answer"])
    return _response_from_state(state)


@app.post("/v1/runs/{request_id}/data-authorization/approve", response_model=RunResponse)
async def approve_data_authorization(request_id: str) -> RunResponse:
    state = PENDING_RUNS.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="pending run not found")
    try:
        state = await runtime().approve_data_authorization(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail={"errors": [str(exc)]}) from exc
    _sync_pending_review(state)
    return _response_from_state(state)


@app.post("/v1/runs/{request_id}/prior-result-authorization/approve", response_model=RunResponse)
async def approve_prior_result_authorization(request_id: str) -> RunResponse:
    state = PENDING_RUNS.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="pending run not found")
    try:
        state = await runtime().approve_prior_result_authorization(state)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail={"errors": [str(exc)]}) from exc
    _sync_pending_review(state)
    return _response_from_state(state)


@app.post("/api/clear-memory")
async def clear_public_memory():
    """清空公共记忆（public_memory.jsonl）。"""
    memory_path = Path(runtime().settings.public_memory_path)
    if memory_path.exists():
        memory_path.write_text("")
    return {"status": "ok", "message": "公共记忆已清空"}


# ---------------------------------------------------------------------------
# Session 管理接口
# ---------------------------------------------------------------------------


class SessionCreateRequest(BaseModel):
    title: str | None = None


class SessionResponse(BaseModel):
    session_id: str
    title: str
    created_at: str
    updated_at: str
    pinned: bool = False
    message_count: int = 0


@app.get("/v1/sessions", response_model=list[SessionResponse])
async def list_sessions():
    """列出所有 session。"""
    return runtime().session_manager.list_sessions()


@app.post("/v1/sessions", response_model=SessionResponse)
async def create_session(request: SessionCreateRequest | None = None):
    """创建新的 session。"""
    title = request.title if request else None
    session = runtime().session_manager.create_session(title)
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


@app.get("/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """获取 session 详情。"""
    session = runtime().session_manager.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


@app.delete("/v1/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除 session 及其会话级记忆、私有结果和内存检查点。"""
    deleted = await runtime().delete_session(session_id)
    if deleted is None:
        raise HTTPException(status_code=404, detail="Session not found")
    for key, state in list(PENDING_RUNS.items()):
        if key == session_id or state.get("session_id") == session_id:
            PENDING_RUNS.pop(key, None)
    return {"status": "ok", "message": "Session deleted", "deleted": deleted}


@app.post("/v1/sessions/{session_id}/pin", response_model=SessionResponse)
async def set_session_pinned(session_id: str, pinned: bool = True):
    """置顶或取消置顶某个会话。"""
    session = runtime().session_manager.set_session_pinned(session_id, pinned)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse(
        session_id=session["session_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"],
        pinned=bool(session.get("metadata", {}).get("pinned", False)),
        message_count=len(session.get("conversation_history", [])),
    )


@app.get("/v1/sessions/{session_id}/history")
async def get_session_history(session_id: str, limit: int | None = None):
    """获取 session 的对话历史。"""
    history = runtime().session_manager.get_conversation_history(session_id, limit)
    pending_review = runtime().session_manager.get_pending_review(session_id)
    # 兼容本次升级前已在内存中等待确认的会话：首次读取历史时补写安全卡片。
    if pending_review is None:
        in_memory_state = PENDING_RUNS.get(session_id)
        if in_memory_state and in_memory_state.get("status") in PENDING_REVIEW_STATUSES:
            _sync_pending_review(in_memory_state)
            pending_review = runtime().session_manager.get_pending_review(session_id)
    return {
        "session_id": session_id,
        "history": history,
        "pending_review": pending_review,
        "run_detail": runtime().session_manager.get_run_detail(session_id),
    }


def _sync_pending_review(state: dict[str, Any]) -> None:
    """同步内存中的可确认状态与 session 中用于界面恢复的安全卡片。"""
    request_id = state.get("request_id", "")
    session_id = state.get("session_id", "")
    is_pending = state.get("status") in PENDING_REVIEW_STATUSES and bool(request_id)

    if session_id:
        runtime().session_manager.set_run_detail(session_id, _safe_run_detail(state))

    if is_pending:
        PENDING_RUNS[request_id] = dict(state)
        if session_id:
            PENDING_RUNS[session_id] = dict(state)
            runtime().session_manager.set_pending_review(
                session_id,
                _response_from_state(state).model_dump(mode="json"),
            )
        return

    if request_id:
        PENDING_RUNS.pop(request_id, None)
    if session_id:
        PENDING_RUNS.pop(session_id, None)
        runtime().session_manager.set_pending_review(session_id, None)


def _safe_run_detail(state: dict[str, Any]) -> dict[str, Any]:
    """构建可在右侧面板恢复的运行追踪，严格排除结果数据与 result_ref。"""
    entries: list[dict[str, Any]] = []
    for label, key in (
        ("响应规划", "response_plan"),
        ("安全校验", "action_validation"),
        ("方法草稿", "method_draft"),
        ("SQL", "sql"),
    ):
        value = state.get(key)
        if value:
            entries.append({"label": label, "content": value})
    if state.get("errors"):
        entries.append({"label": "错误", "content": state["errors"], "type": "error"})
    executions = state.get("execution_result_cards") or (
        [state.get("execution_result_card")] if state.get("execution_result_card") else []
    )
    if executions:
        entries.append(
            {
                "label": "执行完成" if len(executions) == 1 else f"执行完成（{len(executions)} 个步骤）",
                "content": (
                    {
                        "row_count": executions[0].get("row_count"),
                        "execution_mode": executions[0].get("execution_mode"),
                        "real_database_used": executions[0].get("real_database_used", False),
                    }
                    if len(executions) == 1
                    else [
                        {
                            "step": index + 1,
                            "row_count": execution.get("row_count"),
                            "execution_mode": execution.get("execution_mode"),
                            "real_database_used": execution.get("real_database_used", False),
                        }
                        for index, execution in enumerate(executions)
                    ]
                ),
                "type": "success" if state.get("status") == "executed_simulated_real" else "error",
            }
        )

    status = state.get("status", "")
    status_text = {
        "analysis_plan_review_ready": "等待确认分析计划",
        "method_review_ready": "等待确认执行方法",
        "prior_result_authorization_pending": "等待授权使用先前结果",
        "executed_simulated_real": "分析已完成",
        "method_execution_failed": "执行失败",
    }.get(status, "已完成")
    status_type = "error" if status == "method_execution_failed" else ("success" if status == "executed_simulated_real" else "")
    return {"status": status, "status_text": status_text, "status_type": status_type, "entries": entries}


def _response_from_state(state: dict[str, Any]) -> RunResponse:
    return RunResponse(
        request_id=state.get("request_id", ""),
        status=state.get("status", "unknown"),
        answer=state.get("answer"),
        errors=state.get("errors", []),
        result_ref=state.get("result_ref"),
        referenced_result_ref=state.get("referenced_result_ref"),
        public_memory_entry=state.get("public_memory_entry"),
        public_memory_context=state.get("public_memory_context"),
        response_plan=state.get("response_plan"),
        action_validation=state.get("action_validation"),
        selected_skill_detail=state.get("selected_skill_detail"),
        tool_decision=state.get("tool_decision"),
        planner_used=state.get("planner_used"),
        sql=state.get("sql"),
        row_count=state.get("row_count"),
        analysis_plan=state.get("analysis_plan"),
        analysis_plan_review_card=state.get("analysis_plan_review_card"),
        method_draft=state.get("method_draft"),
        method_drafts=state.get("method_drafts"),
        harness_review=state.get("harness_review"),
        harness_reviews=state.get("harness_reviews"),
        mock_result=state.get("mock_result"),
        mock_results=state.get("mock_results"),
        internal_method_review=state.get("internal_method_review"),
        method_review_card=state.get("method_review_card"),
        method_review_cards=state.get("method_review_cards"),
        method_set_review_card=state.get("method_set_review_card"),
        data_authorization_card=state.get("data_authorization_card"),
        prior_result_authorization_card=state.get("prior_result_authorization_card"),
        execution_result_card=state.get("execution_result_card"),
        execution_result_cards=state.get("execution_result_cards"),
        result_narration=state.get("result_narration"),
        result_narrations=state.get("result_narrations"),
        audit=state.get("audit"),
    )
