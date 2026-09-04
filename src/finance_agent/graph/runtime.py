from __future__ import annotations

import json
import re
import uuid
from typing import Any

from langgraph.graph import END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from finance_agent.audit.audit_logger import AuditLogger, stable_hash
from finance_agent.chat.response_plan import (
    MethodProposal,
    ResponsePlan,
    ResponseValidationResult,
    plan_response_with_llm_and_registry,
    validate_response_plan,
)
from finance_agent.chat.tool_decision import response_plan_to_tool_decision
from finance_agent.config import Settings, get_settings
from finance_agent.executor.executor_registry import ExecutorRegistry, get_default_executor_registry
from finance_agent.graph.state import AgentState
from finance_agent.harness.analysis_schema import (
    AnalysisPlan,
    DataAuthorizationCard,
    MethodDraft,
    PriorResultAuthorizationCard,
)
from finance_agent.harness.method_validator import validate_method_draft
from finance_agent.llm.provider import LlmProvider, build_llm_provider
from finance_agent.memory.private_result_store import PrivateResultStore
from finance_agent.memory.query_candidate_selector import parse_candidate_reply, select_query_candidate
from finance_agent.memory.contracts import MemoryKind
from finance_agent.memory.memory_store import MemoryStore
from finance_agent.memory.public_memory import PublicMemoryEntry
from finance_agent.memory.safe_summary import build_query_history_memory
from finance_agent.memory.selector import select_relevant_memories
from finance_agent.memory.extractor import extract_memories_from_state
from finance_agent.metadata.business_registry import BusinessTermRegistry, load_business_registry_from_catalog
from finance_agent.metadata.business_knowledge import BusinessKnowledge
from finance_agent.metadata.catalog import Catalog, load_catalog
from finance_agent.metadata.policy import Policy, load_policy
from finance_agent.metadata.pruner import prune_catalog
from finance_agent.metadata.schema_selector import select_schema_with_llm
from finance_agent.metadata.table_registry import TableRegistry, get_default_table_registry
from finance_agent.methods.generator import generate_dependent_method, generate_method_drafts
from finance_agent.operations.handler_registry import OperationHandlerRegistry, get_default_registry
from finance_agent.operations.registry import OperationRegistry, load_operation_registry
from finance_agent.planner.analysis_planner import plan_analysis_with_lmstudio, plan_analysis_with_rules
from finance_agent.renderer.method_review_renderer import (
    build_analysis_plan_review_card,
    build_data_authorization_card,
    build_data_authorization_card_for_methods,
    build_execution_result_card,
    build_method_review_card,
    build_method_set_review_card,
    render_analysis_plan_review_data,
    render_data_authorization_data,
    render_execution_result_data,
    render_execution_result_set_data,
    render_method_review_data,
    render_method_set_review_data,
    render_prior_result_authorization_data,
    refuse_method_data,
)
from finance_agent.renderer.reply_generator import generate_reply
from finance_agent.renderer.result_narrator import narrate_execution_result, render_user_narration
from finance_agent.sandbox.mock_sandbox import run_mock_dry_run, run_simulated_real_execution
from finance_agent.session.manager import SessionManager
from finance_agent.session.run_store import RunStore
from finance_agent.skills.registry import SkillRegistry, load_skill_registry
from finance_agent.skills.agent import SkillAgentExecutor
from finance_agent.kyc.local_drafts import KycLocalDraftStore
from finance_agent.kyc.conversation import update_from_conversation


MAX_METHOD_REPAIR_ATTEMPTS = 3


class FinanceAgentRuntime:
    def __init__(
        self,
        settings: Settings | None = None,
        catalog: Catalog | None = None,
        policy: Policy | None = None,
        operation_registry: OperationRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        handler_registry: OperationHandlerRegistry | None = None,
        executor_registry: ExecutorRegistry | None = None,
        business_term_registry: BusinessTermRegistry | None = None,
        table_registry: TableRegistry | None = None,
        llm_provider: LlmProvider | None = None,
        session_manager: SessionManager | None = None,
    ):
        self.settings = settings or get_settings()
        self.catalog = catalog or load_catalog(self.settings.catalog_path)
        self.policy = policy or load_policy(self.settings.policy_path)
        self.operation_registry = operation_registry or load_operation_registry(self.settings.operations_path)
        self.skill_registry = skill_registry or load_skill_registry(self.settings.skills_path)
        self.handler_registry = handler_registry or get_default_registry()
        self.executor_registry = executor_registry or get_default_executor_registry()
        self.business_term_registry = business_term_registry or load_business_registry_from_catalog(
            self.catalog.business_terms if hasattr(self.catalog, "business_terms") else {}
        )
        self.table_registry = table_registry or get_default_table_registry()
        self.business_knowledge = BusinessKnowledge(self.table_registry, self.business_term_registry)
        self.llm_provider = llm_provider or build_llm_provider(self.settings)
        self.audit_logger = AuditLogger(self.settings.audit_log_path)
        self.private_result_store = PrivateResultStore(self.settings.private_result_store_path)
        # One canonical store contains both safe query history and semantic
        # memory. Private results, run checkpoints, and audit logs are separate.
        self.memory_store = MemoryStore(self.settings.public_memory_path)
        # Session storage follows the rest of the runtime's configured data
        # paths. This keeps test/runtime instances isolated from user sessions.
        self.session_manager = session_manager or SessionManager(self.settings.session_store_path)
        self.run_store = RunStore(self.settings.run_store_path)
        self.kyc_drafts = KycLocalDraftStore(self.settings.kyc_draft_path)
        self.skill_agent = SkillAgentExecutor(
            session_manager=self.session_manager,
            skill_registry=self.skill_registry,
            llm_provider=self.llm_provider,
        )
        self.checkpointer = MemorySaver()
        # Each request intentionally gets its own graph thread. Keep the mapping
        # so session deletion can remove all in-process checkpoints for a session.
        self._checkpoint_threads_by_session: dict[str, set[str]] = {}
        self.executor = self._build_executor()
        self.graph = self._build_graph()

    def _build_executor(self):
        return self.executor_registry.create(self.settings.executor_mode, self.settings, self.policy)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan_response", self.plan_response)
        graph.add_node("validate_action", self.validate_action)
        graph.add_node("render_direct_response", self.render_direct_response)
        graph.add_node("search_schema", self.search_schema)
        graph.add_node("select_schema", self.select_schema)
        graph.add_node("load_metadata", self.load_metadata)
        graph.add_node("plan_analysis", self.plan_analysis)
        graph.add_node("render_analysis_plan_card", self.render_analysis_plan_card)
        graph.add_node("generate_method", self.generate_method)
        graph.add_node("review_method", self.review_method)
        graph.add_node("synthetic_check", self.synthetic_check)
        graph.add_node("repair_method", self.repair_method)
        graph.add_node("prepare_schema_repair", self.prepare_schema_repair)
        graph.add_node("render_method_card", self.render_method_card)
        graph.add_node("refuse_method", self.refuse_method)
        graph.add_node("load_prior_result", self.load_prior_result)
        graph.add_node("generate_dependent_method", self.generate_dependent_method)
        graph.add_node("audit", self.audit)

        graph.set_entry_point("plan_response")
        graph.add_edge("plan_response", "validate_action")
        graph.add_conditional_edges(
            "validate_action",
            self.after_action_validation,
            {
                "method_flow": "search_schema",
                "direct_response": "render_direct_response",
                "dependent_flow": "load_prior_result",
            },
        )
        graph.add_edge("render_direct_response", "audit")
        graph.add_edge("search_schema", "select_schema")
        graph.add_edge("select_schema", "load_metadata")
        graph.add_edge("load_metadata", "plan_analysis")
        graph.add_conditional_edges(
            "plan_analysis",
            self.after_analysis_plan,
            {"method": "generate_method", "plan_review": "render_analysis_plan_card", "fail": "audit"},
        )
        graph.add_edge("render_analysis_plan_card", "audit")
        graph.add_edge("generate_method", "review_method")
        graph.add_conditional_edges(
            "review_method",
            self.after_method_review,
            {"ok": "synthetic_check", "repair": "prepare_schema_repair", "refuse": "refuse_method"},
        )
        graph.add_conditional_edges(
            "synthetic_check",
            self.after_synthetic_check,
            {"ok": "render_method_card", "repair": "prepare_schema_repair", "refuse": "refuse_method"},
        )
        graph.add_edge("prepare_schema_repair", "search_schema")
        graph.add_edge("repair_method", "review_method")
        graph.add_edge("render_method_card", "audit")
        graph.add_edge("refuse_method", "audit")
        graph.add_edge("load_prior_result", "generate_dependent_method")
        graph.add_edge("generate_dependent_method", "review_method")
        graph.add_edge("audit", END)
        return graph.compile(checkpointer=self.checkpointer)

    def _prepare_invocation(
        self,
        question: str,
        session_id: str | None = None,
        requested_skill_id: str | None = None,
        user_id: str = "local",
        workspace_id: str = "local",
    ) -> tuple[AgentState, dict[str, Any], Any]:
        # 如果没有 session_id，创建新的 session
        if not session_id:
            session = self.session_manager.create_session(user_id=user_id, workspace_id=workspace_id)
            session_id = session["session_id"]
        else:
            # Session IDs are capabilities scoped to the authenticated owner;
            # never silently replace a missing or foreign session.
            session = self.session_manager.get_session(session_id)
            if session is None:
                raise ValueError("session not found")
            metadata = session.get("metadata") or {}
            stored_user_id = str(session.get("user_id") or metadata.get("user_id") or "local")
            stored_workspace_id = str(
                session.get("workspace_id") or metadata.get("workspace_id") or "local"
            )
            if stored_user_id != user_id or stored_workspace_id != workspace_id:
                raise PermissionError("session does not belong to the current principal")

        # 从 SessionManager 读取对话历史
        conversation_history = self.session_manager.get_conversation_history(session_id)
        pending_candidate = self.session_manager.get_pending_query_candidate(session_id)
        selected_candidate = parse_candidate_reply(question) if pending_candidate else None
        resume_query_candidate = None
        if pending_candidate and selected_candidate is not None:
            resume_query_candidate = {
                "candidate": selected_candidate,
                "pending": pending_candidate,
            }
        elif pending_candidate:
            # 用户开始了新的问题，旧的澄清状态不再阻塞当前请求。
            self.session_manager.set_pending_query_candidate(session_id, None)

        # 每次运行使用独立的图状态。会话历史已由 SessionManager 持久化，
        # 不能让上一次运行的 method_draft / SQL 通过 checkpointer 泄漏到本次请求。
        request_id = str(uuid.uuid4())

        # 添加当前用户消息到历史和 UI 事件流。request_id 将待确认卡精确
        # 绑定到这一次请求，而不是绑定到刷新时的最后一条机器人消息。
        conversation_history.append({"role": "user", "content": question})
        self.session_manager.add_message(session_id, "user", question, request_id=request_id)

        config = {"configurable": {"thread_id": f"run_{request_id}"}}
        self._checkpoint_threads_by_session.setdefault(session_id, set()).add(
            config["configurable"]["thread_id"]
        )

        initial: AgentState = {
            "request_id": request_id,
            "review_id": request_id,
            "session_id": session_id,
            "user_id": user_id,
            "workspace_id": workspace_id,
            "user_query": question,
            "requested_skill_id": requested_skill_id,
            "status": "started",
            "errors": [],
            "public_memory_context": self.memory_store.context_for_llm(session_id),
            "conversation_history": conversation_history,
            "repair_attempts": 0,
            "repair_history": [],
            "pending_query_candidate": pending_candidate,
            "resume_query_candidate": resume_query_candidate,
        }
        # Persist the run before invoking the graph so a crash during planning
        # still leaves a durable lifecycle record to inspect or reconcile.
        self.run_store.save(initial, initial)

        conversational_skill = self.skill_registry.get(requested_skill_id) if requested_skill_id else None
        return initial, config, conversational_skill

    def _finish_graph_result(
        self,
        initial: AgentState,
        result: AgentState,
    ) -> AgentState:
        """完成图运行后的会话、候选查询和持久化收尾。"""
        session_id = initial["session_id"]
        request_id = initial["request_id"]
        resume_query_candidate = initial.get("resume_query_candidate")
        candidate_selection = result.get("query_candidate_selection") or {}
        if candidate_selection.get("status") == "ambiguous":
            proposal = (result.get("action_validation") or {}).get("proposal") or {}
            self.session_manager.set_pending_query_candidate(
                session_id,
                {
                    "request_id": result.get("request_id", request_id),
                    "proposal": proposal,
                    "ranked": candidate_selection.get("ranked", [])[:5],
                },
            )
        elif resume_query_candidate:
            self.session_manager.set_pending_query_candidate(session_id, None)

        # 普通回复进入 conversation_history。执行结果由对应的授权执行方法
        # 写入独立的 private_analysis，不进入普通模型上下文。
        answer = result.get("answer")
        if answer:
            self.session_manager.add_message(session_id, "assistant", answer, request_id=request_id)

        self.run_store.save(result, result)
        return result

    async def invoke(
        self,
        question: str,
        session_id: str | None = None,
        requested_skill_id: str | None = None,
        user_id: str = "local",
        workspace_id: str = "local",
    ) -> AgentState:
        initial, config, conversational_skill = self._prepare_invocation(
            question, session_id, requested_skill_id, user_id, workspace_id
        )
        session_id = initial["session_id"]
        if conversational_skill and conversational_skill.card.get("type") in {"intake", "identity"} and question.strip():
            result = self._invoke_kyc_conversation(initial, conversational_skill)
            answer = result.get("answer")
            if answer:
                self.session_manager.add_message(
                    session_id, "assistant", answer, request_id=initial["request_id"]
                )
            self.run_store.save(result, result)
            return result

        # 调用图
        result = await self.graph.ainvoke(initial, config=config)
        return self._finish_graph_result(initial, result)

    async def astream(
        self,
        question: str,
        session_id: str | None = None,
        requested_skill_id: str | None = None,
        user_id: str = "local",
        workspace_id: str = "local",
    ):
        """按 LangGraph 节点产出阶段事件，并在最后产出完整状态。

        这是运行阶段流式：每个节点结束就能通知前端。LLM 当前仍使用
        chat_json 一次性得到结构化结果，因此暂不承诺 token 级流式。
        """
        initial, config, conversational_skill = self._prepare_invocation(
            question, session_id, requested_skill_id, user_id, workspace_id
        )
        if conversational_skill and conversational_skill.card.get("type") in {"intake", "identity"} and question.strip():
            result = self._invoke_kyc_conversation(initial, conversational_skill)
            answer = result.get("answer")
            if answer:
                self.session_manager.add_message(initial["session_id"], "assistant", answer, request_id=initial["request_id"])
            self.run_store.save(result, result)
            yield "skill_agent", result
            yield "complete", result
            return

        current: AgentState = dict(initial)
        async for update in self.graph.astream(initial, config=config, stream_mode="updates"):
            if not isinstance(update, dict):
                continue
            for node, node_update in update.items():
                if isinstance(node_update, dict):
                    current = {**current, **node_update}
                yield str(node), current

        result = self._finish_graph_result(initial, current)
        yield "complete", result

    def _invoke_kyc_conversation(self, state: AgentState, skill) -> AgentState:
        skill_key = skill.card.get("state_key") or skill.name
        current = self.session_manager.get_skill_state(state["session_id"], skill_key) or {}
        try:
            result = update_from_conversation(
                message=state["user_query"],
                card=skill.card,
                state=current,
                provider=self.llm_provider,
            )
            updated_state = {**current, "fields": {**(current.get("fields") or {}), **result["updates"]}}
            self.session_manager.set_skill_state(state["session_id"], skill_key, updated_state)
            answer = result["message"]
            errors: list[str] = []
        except Exception as error:
            updated_state = current
            answer = "这句话暂时无法可靠映射到表单字段，请直接填写卡片，或换一种方式描述。"
            errors = [f"KYC 对话解析失败：{error}"]
        detail = skill.detail_spec()
        return {
            **state,
            "answer": answer,
            "errors": errors,
            "status": "skill_card_ready",
            "response_plan": {"message": answer, "status_hint": "skill_card_ready"},
            "action_validation": {"allowed": True, "route": "direct_response", "status": "skill_card_ready"},
            "selected_skill_detail": detail,
            "skill_card": skill.card,
            "kyc_state": updated_state,
        }

    def open_skill_agent(self, session_id: str, skill_id: str) -> dict[str, Any]:
        """打开或恢复通用侧边 Skill Agent。"""
        return self.skill_agent.open(session_id, skill_id)

    def get_skill_agent(self, skill_session_id: str) -> dict[str, Any]:
        """读取侧边 Skill Agent 的独立消息和共享状态。"""
        return self.skill_agent.messages(skill_session_id)

    def send_skill_agent_message(
        self,
        skill_session_id: str,
        message: str,
        attachment_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """向侧边 Skill Agent 发送消息，不进入主聊天查询链路。"""
        return self.skill_agent.respond(skill_session_id, message, attachment_ids)

    def register_side_agent_handler(self, handler_id: str, handler, *, attachment_access: str = "metadata") -> None:
        """Register an extension handler without modifying the main graph."""
        self.skill_agent.register_handler(handler_id, handler, attachment_access=attachment_access)

    async def delete_session(self, session_id: str) -> dict[str, int] | None:
        """删除会话及其所有会话级记忆与内存检查点。"""
        if self.session_manager.get_session(session_id) is None:
            return None
        deleted = {
            "query_history": self.memory_store.delete_session(session_id, MemoryKind.QUERY_HISTORY),
            "private_results": self.private_result_store.delete_session(session_id),
            "semantic_memory": self.memory_store.delete_session_memories(session_id),
            "kyc_documents": self.kyc_drafts.delete_session(session_id),
        }
        checkpoint_threads = self._checkpoint_threads_by_session.pop(session_id, set())
        checkpoint_threads.add(session_id)  # Compatibility with older session-scoped threads.
        for thread_id in checkpoint_threads:
            await self.checkpointer.adelete_thread(thread_id)
        self.session_manager.delete_session(session_id)
        self.run_store.delete_session(session_id)
        return deleted

    async def approve_method_review(self, state: AgentState) -> AgentState:
        """合并方法确认和数据授权为一步：确认后直接执行。"""
        if state.get("status") != "method_review_ready":
            raise ValueError(f"run is not pending method review: {state.get('status')}")
        if not state.get("method_draft") and not state.get("method_drafts"):
            raise ValueError("run has no method draft")

        original_methods = self._state_methods(state)
        final_methods: list[MethodDraft] = []
        executions: list[Any] = []
        failures: list[str] = []

        # 一个确认卡可以包含多个 draft；确认后按生成顺序逐个执行。
        # 某一步失败时继续执行其余步骤，最后将成功结果与失败原因一起返回。
        for index, method in enumerate(original_methods, start=1):
            method_state = {
                **state,
                "method_draft": method.model_dump(mode="json"),
                "method_drafts": [method.model_dump(mode="json")],
                "sql": method.sql_template,
                "repair_attempts": 0,
                "repair_history": [],
                "errors": [],
            }
            _, final_method, execution, error = self._execute_one_method_with_repair(method_state, method)
            if execution is None or final_method is None:
                failures.append(f"步骤 {index}（{method.name}）执行失败：{error or '未知错误'}")
                continue
            final_methods.append(final_method)
            executions.append(execution)

        if not executions:
            return self.audit({
                **state,
                "status": "method_execution_failed",
                "answer": "所有查询步骤均执行失败：\n" + "\n".join(failures),
                "errors": state.get("errors", []) + failures,
            })

        proposal_params = ((state.get("action_validation") or {}).get("proposal") or {}).get("params") or {}
        source_params = {**(state.get("base_query_params") or {}), **proposal_params}
        cards = []
        private_records = []
        public_entries = []
        narrations = []
        aggregate_authorization = (
            build_data_authorization_card_for_methods(final_methods, row_limit=self.policy.max_rows)
            if len(final_methods) > 1
            else build_data_authorization_card(final_methods[0], row_limit=self.policy.max_rows)
        )
        # 一个方法集合对应一个稳定的聚合引用；各步骤仍保留自己的 result_ref。
        # 聚合引用不包含结果值，只绑定本次请求和最终授权方法集合。
        plan_result_ref = f"plan_{stable_hash({'request_id': state['request_id'], 'method_set_hash': aggregate_authorization.method_hash})}"
        for index, (method, execution) in enumerate(zip(final_methods, executions, strict=True), start=1):
            # 修复后的 SQL 可能与确认时不同，因此基于所有最终方法重新生成授权信息。
            # 多 draft 仍共享一张确认范围卡，但每个步骤保留独立结果卡。
            authorization = aggregate_authorization
            card = build_execution_result_card(method, authorization, execution)
            private_record = self.private_result_store.append(
                request_id=state["request_id"],
                session_id=state["session_id"],
                method_name=method.name,
                method_hash=card.method_hash,
                authorization_hash=stable_hash(authorization.model_dump(mode="json")),
                result=card.result,
                row_count=card.row_count,
                metadata={
                    "execution_mode": card.execution_mode,
                    "real_database_used": card.real_database_used,
                    "method_set_size": len(original_methods),
                    "method_index": index,
                    "plan_result_ref": plan_result_ref,
                    "method_set_hash": aggregate_authorization.method_hash,
                    # 仅供后端下一轮重新生成查询路径恢复参数；不进入任何 LLM 上下文。
                    "source_params": source_params,
                },
            )
            public_memory = self.memory_store.upsert(
                build_query_history_memory(
                    request_id=state["request_id"],
                    session_id=state["session_id"],
                    method=method,
                    execution_card=card,
                    private_record=private_record,
                    user_query=state.get("user_query"),
                    plan_result_ref=plan_result_ref,
                )
            )

            narration = narrate_execution_result(
                card,
                method,
                self.settings,
                self.llm_provider,
                result_ref=private_record.result_ref,
            )
            cards.append(card)
            private_records.append(private_record)
            public_entries.append(public_memory)
            narrations.append(narration)

        answer_parts = []
        for index, narration in enumerate(narrations, start=1):
            rendered = render_user_narration(narration)
            answer_parts.append(f"步骤 {index}：\n{rendered}" if len(narrations) > 1 else rendered)
        if failures:
            answer_parts.append("\n".join(["以下步骤未完成：", *failures]))

        card_data = [card.model_dump(mode="json") for card in cards]
        narration_data = [item.model_dump(mode="json") for item in narrations]
        # Keep the response/audit payload stable while persistence itself uses
        # the canonical MemoryRecord schema.
        public_data = [PublicMemoryEntry.from_record(item).model_dump(mode="json") for item in public_entries]
        next_state: AgentState = {
            **state,
            "status": "method_execution_failed" if failures else "executed_simulated_real",
            "result_ref": private_records[0].result_ref,
            "result_refs": [record.result_ref for record in private_records],
            "plan_result_ref": plan_result_ref,
            "public_memory_entry": public_data[0],
            "execution_result_card": card_data[0],
            "execution_result_cards": card_data,
            "result_narration": narration_data[0],
            "result_narrations": narration_data,
            "public_memory_entries": public_data,
            "method_draft": final_methods[0].model_dump(mode="json"),
            "method_drafts": [method.model_dump(mode="json") for method in final_methods],
            "sql": final_methods[0].sql_template,
            "row_count": sum(card.row_count for card in cards),
            "answer": "\n\n".join(answer_parts),
            "errors": state.get("errors", []) + failures,
        }
        audited = self.audit(next_state)
        self._persist_private_analysis(audited)
        return audited

    def _execute_one_method_with_repair(
        self,
        state: AgentState,
        method: MethodDraft,
    ) -> tuple[AgentState, MethodDraft | None, Any | None, str | None]:
        """执行单个 draft；修复后必须重新经过 review_method 才能执行。"""
        current_state = state
        current_method = method
        last_error: str | None = None

        for attempt in range(MAX_METHOD_REPAIR_ATTEMPTS):
            execution = run_simulated_real_execution(current_method)
            if execution.status == "passed":
                return current_state, current_method, execution, None

            last_error = "; ".join(execution.errors) or f"simulated execution failed: {current_method.name}"
            if attempt >= MAX_METHOD_REPAIR_ATTEMPTS - 1:
                break

            current_sql = current_state.get("sql") or current_method.sql_template or ""
            user_goal = current_state.get("action_user_goal") or current_state["user_query"]
            proposal = (current_state.get("action_validation") or {}).get("proposal") or {}
            merged_params = {
                **(current_state.get("base_query_params") or {}),
                **(proposal.get("params") or {}),
            }
            sql_input_slots = current_state.get("sql_input_slots") or self._sql_input_slots(merged_params)
            sql_planning_goal = self._redact_sql_planning_goal(user_goal, sql_input_slots, merged_params)
            repaired_sql = self._call_llm_for_repair(
                sql_planning_goal,
                current_sql,
                last_error,
                current_state.get("visible_catalog"),
                input_slots=[
                    {"id": slot["id"], "type": slot["type"], "semantic": slot["semantic"]}
                    for slot in sql_input_slots
                ],
            )
            if not repaired_sql:
                break

            table_match = re.search(r"FROM\s+(\w+)", repaired_sql, re.IGNORECASE)
            repaired_method = MethodDraft(
                method_type="sql",
                name="llm_repaired_sql",
                goal=user_goal,
                operation="custom_sql",
                table=table_match.group(1) if table_match else current_method.table,
                data_source="table",
                sql_template=repaired_sql,
                params=self._bound_input_params(current_state),
                required_fields=self._extract_fields_from_sql(repaired_sql),
                output_schema={},
                risk_level="medium",
                logic_summary=[f"已完成查询校验与调整：{user_goal}"],
            )
            candidate_state = {
                **current_state,
                "method_draft": repaired_method.model_dump(mode="json"),
                "method_drafts": [repaired_method.model_dump(mode="json")],
                "sql": repaired_sql,
                "repair_attempts": attempt + 1,
                "errors": [],
            }
            reviewed = self.review_method(candidate_state)
            if reviewed.get("status") != "method_reviewed":
                last_error = "; ".join(reviewed.get("errors", [])[-5:]) or "repaired SQL failed validation"
                break
            current_state = reviewed
            current_method = self._state_methods(reviewed)[0]

        return current_state, None, None, last_error

    async def approve_analysis_plan(self, state: AgentState) -> AgentState:
        if state.get("status") != "analysis_plan_review_ready":
            raise ValueError(f"run is not pending analysis plan review: {state.get('status')}")
        if not state.get("analysis_plan"):
            raise ValueError("run has no analysis plan")

        next_state: AgentState = {
            **state,
            # The approved plan and its generated method card must retain
            # independent, persistent statuses.
            "review_id": str(uuid.uuid4()),
            "status": "analysis_plan_approved",
        }
        return await self._prepare_method_after_analysis_plan(next_state)

    async def revise_method_review(self, state: AgentState, instruction: str) -> AgentState:
        """Create a new pending review version without reading business data."""
        if state.get("status") != "method_review_ready":
            raise ValueError(f"run is not pending method review: {state.get('status')}")
        instruction = instruction.strip()
        if not instruction:
            raise ValueError("revision instruction is empty")

        methods = self._state_methods(state)
        action_validation = state.get("action_validation") or {}
        proposal = action_validation.get("proposal") or {}
        proposal_params = dict(proposal.get("params") or {})
        # Revisions bypass normal response planning.  Capture newly supplied
        # filter values before making opaque SQL slots, otherwise SQL may use
        # :input_1 with no value available to bind.
        proposal_params.update(self._revision_filter_params(instruction))
        original_goal = state.get("action_user_goal") or state.get("user_query") or ""
        revised_goal = self._revision_goal(original_goal, proposal_params)
        revised_proposal = {**proposal, "goal": revised_goal, "params": proposal_params}
        revised_validation = {
            **action_validation,
            "proposal": revised_proposal,
            "user_goal": revised_goal,
        }
        revision_state = self.load_metadata(
            {
                **state,
                "action_validation": revised_validation,
                "action_user_goal": revised_goal,
            }
        )
        merged_params = {
            **(revision_state.get("base_query_params") or {}),
            **proposal_params,
        }
        slots = self._sql_input_slots(merged_params)
        method_context = [
            {
                "step_index": index,
                "operation": method.operation,
                "goal": self._redact_sql_planning_goal(method.goal, slots, merged_params),
                "sql_template": method.sql_template,
                "fields": method.required_fields,
            }
            for index, method in enumerate(methods, start=1)
        ]
        revision_goal = (
            f"原始分析目标：{revised_goal}\n"
            f"当前方法集合：{json.dumps(method_context, ensure_ascii=False)}\n"
            f"用户要求修改：{instruction}\n"
            "请只修改用户明确指出的步骤，其他步骤保持语义不变，并重新输出完整方法集合。"
        )
        sql_planning_goal = self._redact_sql_planning_goal(revision_goal, slots, merged_params)
        action_context = {
            "route": revised_validation.get("route"),
            "entity_id": revised_proposal.get("entity_id"),
            "entity_type": revised_proposal.get("entity_type"),
            "preferred_runtime": revised_proposal.get("preferred_runtime"),
            "selected_skill_detail": revision_state.get("selected_skill_detail"),
            "revision": True,
            "current_method_set": method_context,
            "revision_instruction": self._redact_sql_planning_goal(instruction, slots, merged_params),
        }
        visible = Catalog.model_validate(revision_state["visible_catalog"])
        try:
            plan = plan_analysis_with_lmstudio(
                sql_planning_goal,
                visible,
                self.operation_registry,
                self.settings,
                self.llm_provider,
                action_context=action_context,
                input_slots=[
                    {"id": slot["id"], "type": slot["type"], "semantic": slot["semantic"]}
                    for slot in slots
                ],
                handler_manifest=self.handler_registry.manifest_for_llm(),
                business_term_manifest=self.business_term_registry.manifest_for_llm(),
            )
            planner_used = self.llm_provider.provider_name
        except Exception as exc:
            plan = plan_analysis_with_rules(instruction, visible)
            planner_used = "rule"
            revision_state = {
                **revision_state,
                "errors": revision_state.get("errors", []) + [f"method revision planner failed: {type(exc).__name__}: {exc}"],
            }
        plan = self._apply_action_constraints(plan, revision_state)
        plan = self._apply_skill_constraints(plan, revision_state)
        revised = {
            **revision_state,
            "analysis_plan": plan.model_dump(mode="json"),
            "sql_input_slots": slots,
            "review_id": str(uuid.uuid4()),
            "planner_used": planner_used,
            "action_user_goal": plan.goal,
            "method_draft": None,
            "method_drafts": [],
            "method_review_card": None,
            "method_review_cards": [],
            "method_set_review_card": None,
            "repair_attempts": 0,
            "repair_history": [],
            "errors": [],
            "status": "analysis_planned",
        }
        return await self._prepare_method_after_analysis_plan(revised)

    @staticmethod
    def _revision_filter_params(instruction: str) -> dict[str, Any]:
        """Extract bindable values for the revision path without another LLM call."""
        company = re.search(r"\b(company\s*[A-Za-z0-9_-]+)\b", instruction, re.IGNORECASE)
        if company:
            return {"customer_name": company.group(1).strip()}
        return {}

    @staticmethod
    def _revision_goal(original_goal: str, params: dict[str, Any]) -> str:
        """Keep actual filter values out of the SQL-planning goal."""
        if params.get("customer_name") and "客户" not in original_goal and "公司" not in original_goal:
            return f"{original_goal}，并限定指定客户"
        return original_goal

    async def approve_data_authorization(self, state: AgentState) -> AgentState:
        """保留兼容性，但实际上已合并到 approve_method_review 中。"""
        # 如果状态是 method_review_ready，直接调用 approve_method_review
        if state.get("status") == "method_review_ready":
            return await self.approve_method_review(state)

        # 否则报错
        raise ValueError(f"run is not pending data authorization: {state.get('status')}")

    def plan_response(self, state: AgentState) -> AgentState:
        # 用户正在回答上一轮的历史候选澄清。这里不再让普通响应 LLM
        # 解释“第 2 个”是什么意思，而是由后端恢复原始安全 proposal。
        resume = state.get("resume_query_candidate") or {}
        if resume.get("pending") and resume.get("candidate") is not None:
            pending_proposal = (resume.get("pending") or {}).get("proposal") or {}
            proposal = MethodProposal.model_validate(pending_proposal).model_copy(
                update={"base_query_candidate": resume["candidate"]}
            )
            plan = ResponsePlan(
                message="继续处理你选中的历史查询。",
                method_proposal=proposal,
                confidence=1.0,
            )
            return {
                **state,
                "response_plan": plan.model_dump(mode="json"),
                "tool_decision": response_plan_to_tool_decision(plan).model_dump(mode="json"),
                "status": "response_planned",
            }

        # 显式点击/调用一个没有附加任务的 Skill 时，直接打开它的配置卡片。
        # 这条路径不需要模型判断，保证 @Skill 的 UI 入口稳定且不会产生无意义的 LLM 调用。
        requested_skill = self.skill_registry.get(state.get("requested_skill_id")) if state.get("requested_skill_id") else None
        if requested_skill and requested_skill.card and not state.get("user_query", "").strip():
            plan = ResponsePlan(message=requested_skill.title, status_hint="skill_card_ready")
            return {
                **state,
                "response_plan": plan.model_dump(mode="json"),
                "tool_decision": response_plan_to_tool_decision(plan).model_dump(mode="json"),
                "status": "response_planned",
            }

        # 选择相关记忆（新系统）- 使用同步版本
        from finance_agent.memory.selector import select_relevant_memories_sync
        relevant_memories = select_relevant_memories_sync(
            state["user_query"],
            self.memory_store,
            self.llm_provider,
            state["session_id"],
            max_results=5,
        )

        # 构建记忆上下文
        memory_context = []
        if relevant_memories:
            memory_context = [
                {
                    "type": m.type.value,
                    "name": m.name,
                    "description": m.description,
                    "content": m.content,
                }
                for m in relevant_memories
            ]

        # 当前消息会由响应规划器单独附加；这里只传此前的用户需求。
        # 结果解读的 assistant 消息可能包含真实数据，不能作为后续规划 LLM 的上下文。
        # 连续查询只需回看用户原始问题和后续补充（例如“按金额排序”）。
        conversation_history = list(state.get("conversation_history", []))
        if (
            conversation_history
            and conversation_history[-1].get("role") == "user"
            and conversation_history[-1].get("content") == state["user_query"]
        ):
            conversation_history.pop()
        conversation_history = self._llm_safe_user_history(conversation_history)

        plan = plan_response_with_llm_and_registry(
            state["user_query"],
            self.settings,
            self.llm_provider,
            self.operation_registry,
            self.skill_registry,
            public_memory_context=state.get("public_memory_context", []),
            sent_memory_count=state.get("sent_memory_count", 0),
            handler_registry=self.handler_registry,
            business_term_registry=self.business_term_registry,
            relevant_memories=memory_context,
            conversation_messages=conversation_history,
        )
        requested_skill_id = state.get("requested_skill_id")
        if requested_skill_id:
            skill = self.skill_registry.get(requested_skill_id)
            if skill:
                if skill.kind == "query":
                    proposal = plan.method_proposal or MethodProposal()
                    plan = plan.model_copy(
                        update={
                            "method_proposal": proposal.model_copy(
                                update={
                                    "entity_id": skill.name,
                                    "entity_type": "skill",
                                    "goal": proposal.goal or state["user_query"],
                                    "schema_search_terms": list(
                                        dict.fromkeys(
                                            [*proposal.schema_search_terms, *skill.required_metadata_terms]
                                        )
                                    ),
                                }
                            )
                        }
                    )
                else:
                    plan = plan.model_copy(
                        update={
                            "method_proposal": None,
                            "message": plan.message or skill.title,
                            "status_hint": "skill_card_ready",
                        }
                    )
        legacy_decision = response_plan_to_tool_decision(plan)
        # 更新 sent_memory_count，下次只发增量
        memory_count = len(state.get("public_memory_context", []))
        return {
            **state,
            "response_plan": plan.model_dump(mode="json"),
            "tool_decision": legacy_decision.model_dump(mode="json"),
            "sent_memory_count": memory_count,
            "relevant_memories": memory_context,
            "status": "response_planned",
        }

    @staticmethod
    def after_action_validation(state: AgentState) -> str:
        validation = state["action_validation"]
        if validation.get("route") != "method_flow":
            return "direct_response"
        # 统一走重新生成查询路径：后续请求只参考安全的历史查询记录，重新生成
        # 完整 SQL 并重新查询当前数据。旧的直接基于历史结果计算路径保留在图中
        # 仅用于兼容历史 checkpoint，但新请求不可再进入该路径。
        return "method_flow"

    def validate_action(self, state: AgentState) -> AgentState:
        plan = ResponsePlan.model_validate(state["response_plan"])
        validation = validate_response_plan(plan, state["user_query"], self.operation_registry, self.skill_registry)
        proposal = validation.proposal
        candidate = proposal.base_query_candidate if proposal else None
        candidate_selection = select_query_candidate(
            self.memory_store.context_for_llm(state["session_id"]),
            candidate=candidate,
            current_goal=validation.user_goal,
            user_query=state["user_query"],
            confirmed_candidate=(state.get("resume_query_candidate") or {}).get("candidate"),
        )
        response_plan = dict(state["response_plan"])
        if candidate_selection["status"] == "selected" and proposal is not None:
            validation = validation.model_copy(
                update={
                    "proposal": proposal.model_copy(
                        update={"base_query_candidate": candidate_selection["selected_candidate"]}
                    )
                }
            )
        elif candidate_selection["status"] == "ambiguous":
            response_plan["message"] = candidate_selection["message"]
            validation = validation.model_copy(
                update={
                    "route": "direct_response",
                    "status": "clarification",
                    "warnings": [
                        *validation.warnings,
                        "历史查询候选无法唯一匹配，已暂停重新生成 SQL",
                    ],
                }
            )
        requested_skill = self.skill_registry.get(state.get("requested_skill_id")) if state.get("requested_skill_id") else None
        proposed_skill = None
        if validation.proposal and validation.proposal.entity_type == "skill":
            proposed_skill = self.skill_registry.get(validation.proposal.entity_id or "")
        special_skill = requested_skill or proposed_skill
        # An explicit Skill with no task opens its configured card first. Once
        # the card submits a natural-language goal, the normal query graph is
        # preserved, including table matching, disclosure, SQL checks, and
        # authorization.
        if (
            special_skill
            and special_skill.card
            and validation.allowed
            and (special_skill.kind != "query" or not state.get("user_query", "").strip())
        ):
            validation = validation.model_copy(update={"route": "direct_response", "status": "skill_card_ready"})
        selected_capability_detail = validation.disclosure.get("capability_detail") if validation.disclosure else None
        selected_skill_detail = validation.disclosure.get("skill_detail") if validation.disclosure else None
        if special_skill and special_skill.kind != "query":
            selected_skill_detail = special_skill.detail_spec()
        schema_search_terms = list((validation.proposal.schema_search_terms if validation.proposal else []) or [])
        return {
            **state,
            "response_plan": response_plan,
            "action_validation": validation.model_dump(mode="json"),
            "query_candidate_selection": candidate_selection,
            "selected_capability_detail": selected_capability_detail,
            "selected_skill_detail": selected_skill_detail,
            "schema_search_terms": schema_search_terms,
            "action_user_goal": validation.user_goal,
            "status": validation.status,
            "errors": state.get("errors", []) + validation.errors,
        }

    def render_direct_response(self, state: AgentState) -> AgentState:
        plan = ResponsePlan.model_validate(state["response_plan"])
        candidate_selection = state.get("query_candidate_selection") or {}
        skill_detail = state.get("selected_skill_detail") or {}
        skill_card = skill_detail.get("card") if state.get("status") == "skill_card_ready" else None
        return {
            **state,
            "answer": candidate_selection.get("message") or plan.message,
            "skill_card": skill_card,
            "status": state.get("action_validation", {}).get("status", plan.status_hint),
        }

    def _full_catalog(self) -> Catalog:
        """从注册的真实 Schema 构建仅供后端检索的完整目录。"""
        from finance_agent.metadata.catalog import Catalog, ColumnMeta, TableMeta, RelationshipMeta

        tables = []
        for t in self.table_registry.all_tables():
            columns = [
                ColumnMeta(
                    name=col.name,
                    type=col.type,
                    semantic=col.description,
                    sensitive=col.sensitive,
                )
                for col in t.columns
            ]
            relationships = [
                RelationshipMeta(**rel)
                for rel in t.get_relationships()
            ]
            tables.append(TableMeta(
                name=t.name,
                description=t.description,
                columns=columns,
                relationships=relationships,
            ))

        return Catalog(
            version="dynamic",
            description="Auto-generated from table_registry",
            tables=tables,
            business_terms=self.business_term_registry.to_catalog_dict(),
        )

    def search_schema(self, state: AgentState) -> AgentState:
        """先按业务词典匹配表，再用通用元数据检索作为兜底。"""
        full_catalog = self._full_catalog()
        goal = state.get("action_user_goal") or state["user_query"]
        terms = [term for term in state.get("schema_search_terms", []) if isinstance(term, str)]
        # goal 已在第一阶段脱值；search terms 也已在 response validator 中剔除真实参数值。
        search_query = " ".join([goal, *terms])
        max_candidates = 8 if state.get("repair_attempts", 0) == 0 else 16
        mapped_tables = self.business_knowledge.match_tables(search_query)
        if mapped_tables:
            mapped_names = {table.table for table in mapped_tables}
            matched = Catalog(
                version=full_catalog.version,
                description=full_catalog.description,
                tables=[
                    table for table in full_catalog.tables if table.name in mapped_names
                ][:max_candidates],
                business_terms=full_catalog.business_terms,
            )
        else:
            matched = prune_catalog(search_query, full_catalog, self.policy, max_tables=max_candidates)
        candidates = [
            {"name": table.name, "description": table.description}
            for table in matched.tables
        ]
        return {
            **state,
            "schema_candidates": candidates,
            "status": "schema_candidates_ready",
        }

    def select_schema(self, state: AgentState) -> AgentState:
        """模型从候选表摘要中选择要展开的 Schema，不能直接猜表或字段。"""
        candidates = list(state.get("schema_candidates") or [])
        candidate_names = {candidate.get("name") for candidate in candidates}
        try:
            selection = select_schema_with_llm(
                user_goal=state.get("action_user_goal") or state["user_query"],
                capability_detail=state.get("selected_capability_detail"),
                candidates=candidates,
                repair_errors=state.get("schema_repair_errors") or [],
                llm_provider=self.llm_provider,
            )
            selected = [name for name in selection.selected_tables if name in candidate_names]
            selection_data = selection.model_dump(mode="json")
            source = "llm"
        except Exception as exc:
            # Schema 选择器不可用时不让模型猜表：只退回后端已经检索出的候选。
            selected = [candidate["name"] for candidate in candidates]
            selection_data = {"selected_tables": selected, "reason": f"schema selector fallback: {type(exc).__name__}"}
            source = "fallback"

        if not selected:
            selected = [candidate["name"] for candidate in candidates]
            selection_data["selected_tables"] = selected
            selection_data["reason"] = selection_data.get("reason") or "选择为空，使用后端候选目录"
            source = "fallback"
        return {
            **state,
            "selected_schema_tables": selected,
            "schema_selection": {**selection_data, "source": source},
            "status": "schema_selected",
        }

    def load_metadata(self, state: AgentState) -> AgentState:
        """只展开 schema selector 选中的表的真实字段和关系。"""
        full_catalog = self._full_catalog()
        selected_names = list(state.get("selected_schema_tables") or [])
        if selected_names:
            selected_set = set(selected_names)
            selected_tables = [table for table in full_catalog.tables if table.name in selected_set]
            visible = Catalog(
                version=full_catalog.version,
                description=full_catalog.description,
                tables=selected_tables,
                business_terms=full_catalog.business_terms,
            )
            visible = self._sanitize_catalog(visible)
        else:
            # 兼容直接调用 load_metadata 的旧接口和历史 checkpoint。
            visible = prune_catalog(state.get("action_user_goal") or state["user_query"], full_catalog, self.policy)
        disclosed_tables = list(state.get("selected_schema_tables") or [table.name for table in visible.tables])
        metadata_disclosure = self._metadata_disclosure(
            candidates=list(state.get("schema_candidates") or []),
            visible=visible,
            selected_tables=disclosed_tables,
        )
        return {
            **state,
            "visible_catalog": visible.model_dump(),
            "metadata_disclosure": metadata_disclosure,
            "status": "metadata_loaded",
        }

    @staticmethod
    def _metadata_disclosure(
        *,
        candidates: list[dict[str, Any]],
        visible: Catalog,
        selected_tables: list[str],
    ) -> dict[str, Any]:
        """Expose table summaries first and selected table fields second.

        The visible catalog is already sanitized, so this payload contains
        metadata only and cannot expose query rows or private filter values.
        """
        selected = set(selected_tables)
        details = []
        for table in visible.tables:
            if table.name not in selected:
                continue
            details.append(
                {
                    "name": table.name,
                    "description": table.description,
                    "fields": [
                        {
                            "name": column.name,
                            "qualified_name": f"{table.name}.{column.name}",
                            "type": column.type,
                            "description": column.semantic,
                        }
                        for column in table.columns
                    ],
                    "relationships": [relationship.model_dump(by_alias=True) for relationship in table.relationships],
                }
            )
        return {
            "mode": "table_then_fields",
            "candidate_tables": candidates,
            "selected_tables": [table for table in selected_tables if table in selected],
            "selected_table_details": details,
        }

    def _sanitize_catalog(self, catalog: Catalog) -> Catalog:
        """展开后仍剔除敏感字段，防止 Schema 选择绕过字段策略。"""
        sanitized_tables = []
        for table in catalog.tables:
            columns = [
                column
                for column in table.columns
                if not column.sensitive and not self.policy.is_sensitive_column_name(column.name)
            ]
            sanitized_tables.append(table.model_copy(update={"columns": columns}))
        return catalog.model_copy(update={"tables": sanitized_tables})

    def plan_analysis(self, state: AgentState) -> AgentState:
        visible = Catalog.model_validate(state["visible_catalog"])
        errors = list(state.get("errors", []))
        user_goal = state.get("action_user_goal") or state["user_query"]
        proposal = (state.get("action_validation") or {}).get("proposal") or {}
        base_query_reference, base_query_params = self._resolve_base_query_reference(state)
        merged_params = {**base_query_params, **(proposal.get("params") or {})}
        sql_input_slots = self._sql_input_slots(merged_params)
        sql_planning_goal = self._redact_sql_planning_goal(user_goal, sql_input_slots, merged_params)
        action_context = {
            # 不传完整 response_plan / action_validation：其中可能有用户真实筛选值。
            "route": (state.get("action_validation") or {}).get("route"),
            "entity_id": proposal.get("entity_id"),
            "entity_type": proposal.get("entity_type"),
            "preferred_runtime": proposal.get("preferred_runtime"),
            # 第二层：只把首轮已选中的 capability 规格交给 SQL 规划器。
            # 首轮路由不再携带 173 张表的摘要，避免模型在还没决定能力时
            # 就被完整 schema 索引干扰。
            "selected_capability_detail": state.get("selected_capability_detail"),
            "selected_skill_detail": state.get("selected_skill_detail"),
            "skill_card": state.get("skill_card"),
        }
        if base_query_reference:
            # 只传参数化 SQL、脱敏目标和结构信息，不传 result_ref、参数值或结果行。
            action_context["base_query_reference"] = base_query_reference
        try:
            plan = plan_analysis_with_lmstudio(
                sql_planning_goal,
                visible,
                self.operation_registry,
                self.settings,
                self.llm_provider,
                action_context=action_context,
                input_slots=[{"id": slot["id"], "type": slot["type"], "semantic": slot["semantic"]} for slot in sql_input_slots],
                handler_manifest=self.handler_registry.manifest_for_llm(),
                business_term_manifest=self.business_term_registry.manifest_for_llm(),
            )
            plan = self._apply_action_constraints(plan, state)
            planner_used = self.llm_provider.provider_name
        except Exception as exc:
            errors.append(f"lmstudio analysis planner failed: {type(exc).__name__}: {exc}")
            plan = plan_analysis_with_rules(user_goal, visible)
            plan = self._apply_action_constraints(plan, state)
            planner_used = "rule"
        plan = self._apply_skill_constraints(plan, state)
        return {
            **state,
            "analysis_plan": plan.model_dump(mode="json"),
            "sql_input_slots": sql_input_slots,
            "base_query_params": base_query_params,
            "planner_used": planner_used,
            "status": "analysis_planned",
            "errors": errors,
        }

    @staticmethod
    def _llm_safe_user_history(
        conversation_history: list[dict[str, Any]],
        limit: int = 10,
    ) -> list[dict[str, str]]:
        """为规划阶段构造可发送给 LLM 的历史：仅保留近期用户输入。"""
        return [
            {"role": "user", "content": str(message["content"])}
            for message in conversation_history
            if message.get("role") == "user" and isinstance(message.get("content"), str)
        ][-limit:]

    @staticmethod
    def _sql_input_slots(params: dict[str, Any]) -> list[dict[str, str]]:
        """Create opaque slots for SQL planning; values never leave the backend boundary."""
        slots: list[dict[str, str]] = []
        for index, (source_name, value) in enumerate(sorted(params.items()), start=1):
            if value is None:
                continue
            value_type = "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else "text"
            slots.append(
                {
                    "id": f"input_{index}",
                    "source_param": str(source_name),
                    "type": value_type,
                    # Intent label only; neither a parameter name nor a value.
                    "semantic": str(source_name).replace("_", " "),
                }
            )
        return slots

    @staticmethod
    def _redact_sql_planning_goal(
        goal: str,
        slots: list[dict[str, str]],
        params: dict[str, Any],
    ) -> str:
        """Remove known user values before they reach the SQL-planning LLM."""
        redacted = goal
        for slot in slots:
            value = params.get(slot["source_param"])
            if isinstance(value, str) and value.strip():
                redacted = re.sub(re.escape(value), f"[{slot['id']}]", redacted, flags=re.IGNORECASE)
            elif isinstance(value, (int, float)) and not isinstance(value, bool):
                redacted = redacted.replace(str(value), f"[{slot['id']}]")
        return redacted

    @staticmethod
    def _bound_input_params(state: AgentState) -> dict[str, Any]:
        """Map opaque SQL slots back to values only after SQL planning is complete."""
        proposal = (state.get("action_validation") or {}).get("proposal") or {}
        proposal_params = proposal.get("params") or {}
        base_params = state.get("base_query_params") or {}
        merged_params = {**base_params, **proposal_params}
        slots = state.get("sql_input_slots") or FinanceAgentRuntime._sql_input_slots(merged_params)
        return {
            slot["id"]: merged_params[slot["source_param"]]
            for slot in slots
            if slot.get("source_param") in merged_params
        }

    def _resolve_base_query_reference(self, state: AgentState) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Resolve the safe candidate number to a session-scoped query card."""
        proposal = (state.get("action_validation") or {}).get("proposal") or {}
        candidate = proposal.get("base_query_candidate")
        if candidate is None:
            return None, {}
        if isinstance(candidate, bool) or not isinstance(candidate, int) or candidate < 1:
            return None, {}
        entries = self.memory_store.query_history(state.get("session_id") or "", limit=5)
        if candidate > len(entries):
            return None, {}
        entry = entries[candidate - 1]
        records = self.private_result_store.latest(limit=50, session_id=state.get("session_id"))
        result_ref = str(entry.metadata.get("result_ref") or "")
        record = next((item for item in records if item.result_ref == result_ref), None)
        private_params: dict[str, Any] = {}
        if record:
            source_params = record.metadata.get("source_params")
            if isinstance(source_params, dict):
                private_params = dict(source_params)
        return {
            "goal": entry.metadata.get("goal") or "",
            "sql_template": entry.metadata.get("sql_template") or "",
            "fields": entry.metadata.get("fields") or [],
            "result_shape": entry.metadata.get("result_shape") or {},
            "row_count": entry.metadata.get("row_count") or 0,
            "status": "executed",
        }, private_params

    @staticmethod
    def after_analysis_plan(state: AgentState) -> str:
        if state.get("status") != "analysis_planned":
            return "fail"
        # 分析计划保留为后端内部规划，不再单独阻塞用户确认。
        # 所有请求统一继续生成最终 method_drafts，再进入一次 method review。
        return "method"

    @staticmethod
    def _apply_action_constraints(plan: AnalysisPlan, state: AgentState) -> AnalysisPlan:
        validation = state.get("action_validation") or {}
        proposal = validation.get("proposal") or {}
        capability_id = proposal.get("entity_id") if proposal.get("entity_type") == "capability" else None
        if validation.get("status") != "capability_proposed" or not capability_id:
            return plan
        if not plan.steps:
            return plan

        primary = plan.steps[0]
        if primary.operation == capability_id:
            return plan

        update: dict[str, Any] = {
            "operation": capability_id,
            "rationale": f"System constrained operation to validated capability: {capability_id}.",
        }
        if capability_id == "status_distribution":
            update.update({"metric": None, "dimension": "status", "group_by": None})
        constrained_step = primary.model_copy(update=update)
        return plan.model_copy(update={"steps": [constrained_step, *plan.steps[1:]]})

    @staticmethod
    def _apply_skill_constraints(plan: AnalysisPlan, state: AgentState) -> AnalysisPlan:
        return plan

    def generate_method(self, state: AgentState) -> AgentState:
        try:
            # ResponsePlan 中的 SQL / 代码只是意图提示，不能绕过 schema 约束。
            # 唯一可执行来源是已加载可见元数据后的 AnalysisPlan.steps。
            proposal = (state.get("action_validation") or {}).get("proposal") or {}
            plan = AnalysisPlan.model_validate(state["analysis_plan"])
            methods = generate_method_drafts(plan, self.handler_registry)
            # SQL 规划器只能看到 input_N 槽位；到这里才把真实值映射回来。
            # 校验器会要求每个槽位都被 SQL 引用，避免参数被悄悄丢弃。
            bound_params = self._bound_input_params(state)
            methods = [
                method.model_copy(update={"params": bound_params})
                for method in methods
            ]
            method = methods[0]
            return {
                **state,
                "method_draft": method.model_dump(mode="json"),
                "method_drafts": [method.model_dump(mode="json") for method in methods],
                "sql": method.sql_template,
                "status": "method_generated",
            }
        except Exception as exc:
            return {
                **state,
                "status": "method_generation_failed",
                "errors": state.get("errors", []) + [f"method generation failed: {type(exc).__name__}: {exc}"],
            }

    @staticmethod
    def _extract_fields_from_sql(sql: str) -> list[str]:
        """从 SELECT 表达式中提取字段引用，避免函数参数被截断成伪字段。"""
        import re

        # 解析表别名：FROM account a → {"a": "account"}
        alias_map = {}
        from_match = re.findall(r"(?:FROM|JOIN)\s+(\w+)\s+(?:AS\s+)?(\w+)", sql, re.IGNORECASE)
        for table, alias in from_match:
            if table.lower() not in ("select", "where", "and", "or", "on", "as") and alias.lower() not in ("where", "join", "on", "order", "group", "limit"):
                alias_map[alias.lower()] = table

        # 获取主表名
        main_table_match = re.search(r"FROM\s+(\w+)", sql, re.IGNORECASE)
        main_table = main_table_match.group(1) if main_table_match else "card_transaction"

        # 提取 SELECT 中的字段
        select_match = re.search(r"SELECT\s+(.*?)\s+FROM", sql, re.IGNORECASE | re.DOTALL)
        if not select_match:
            return []
        fields: list[str] = []

        def add(reference: str) -> None:
            reference = reference.strip()
            if not reference or reference == "*":
                return
            if "." in reference:
                prefix, field = reference.split(".", 1)
                fields.append(f"{alias_map.get(prefix.lower(), prefix)}.{field}")
            else:
                fields.append(f"{main_table}.{reference}")

        select_sql = select_match.group(1)
        # SELECT * 不是“未指定字段”：它明确表示读取主表的全部字段。
        if re.search(r"(?:^|,)\s*\*\s*(?:,|$)", select_sql):
            fields.append(f"{main_table}.*")
        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_]*)\.\*", select_sql):
            fields.append(f"{alias_map.get(match.group(1).lower(), match.group(1))}.*")
        direct_pattern = r"(?:^|,)\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*(?:AS\s+\w+)?\s*(?=,|$)"
        for match in re.finditer(direct_pattern, select_sql, re.IGNORECASE):
            add(match.group(1))
        for match in re.finditer(
            r"(?:SUM|AVG|MIN|MAX)\s*\(\s*(?:COALESCE\s*\(\s*)?([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
            select_sql,
            re.IGNORECASE,
        ):
            add(match.group(1))
        for match in re.finditer(
            r"DATE_TRUNC\s*\(\s*'[^']+'\s*,\s*([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)",
            select_sql,
            re.IGNORECASE,
        ):
            add(match.group(1))
        return list(dict.fromkeys(fields))

    @staticmethod
    def _extract_fields_from_code(code: str) -> list[str]:
        """从 Python 代码中提取字段引用（粗略提取）。"""
        import re
        fields = []
        # 匹配 row["field"] 或 row['field']
        pattern = r'''row\[['"](\w+(?:\.\w+)?)['"]\]'''
        matches = re.findall(pattern, code)
        fields.extend(matches)
        # 匹配 row.get("field") 或 row.get('field')
        pattern = r'''row\.get\(['"](\w+(?:\.\w+)?)['"]\]'''
        matches = re.findall(pattern, code)
        fields.extend(matches)
        # 去重
        return list(dict.fromkeys(fields))

    async def render_analysis_plan_card(self, state: AgentState) -> AgentState:
        plan = AnalysisPlan.model_validate(state["analysis_plan"])
        card = build_analysis_plan_review_card(plan, state.get("selected_skill_detail"))
        context = render_analysis_plan_review_data(card, self.handler_registry)
        answer = await generate_reply(context, state["user_query"], self.llm_provider, state.get("conversation_history"))
        return {
            **state,
            "analysis_plan_review_card": card.model_dump(mode="json"),
            "answer": answer,
            "status": "analysis_plan_review_ready",
        }

    def review_method(self, state: AgentState) -> AgentState:
        if not state.get("method_draft") and not state.get("method_drafts"):
            return {**state, "status": "method_review_failed", "errors": state.get("errors", []) + ["no method_draft"]}
        # Dependent methods (result_ref_flow) skip load_metadata, so visible_catalog may be absent.
        visible = Catalog.model_validate(state["visible_catalog"]) if state.get("visible_catalog") else Catalog(version="empty", tables=[], business_terms={})
        methods = self._state_methods(state)
        reviews = [validate_method_draft(method, visible, self.policy, self.operation_registry, self.table_registry) for method in methods]
        errors = [error for review in reviews for error in review.errors]
        if errors:
            return {
                **state,
                "harness_review": reviews[0].model_dump(mode="json"),
                "harness_reviews": [review.model_dump(mode="json") for review in reviews],
                "status": "method_review_failed",
                "errors": state.get("errors", []) + errors,
            }
        return {
            **state,
            "harness_review": reviews[0].model_dump(mode="json"),
            "harness_reviews": [review.model_dump(mode="json") for review in reviews],
            "status": "method_reviewed",
        }

    def after_method_review(self, state: AgentState) -> str:
        if state.get("status") == "method_reviewed":
            return "ok"
        return "repair" if self._should_research_schema(state) else "refuse"

    def synthetic_check(self, state: AgentState) -> AgentState:
        methods = self._state_methods(state)
        extra = state.get("referenced_result_tables") or None
        results = [run_mock_dry_run(method, extra_tables=extra) for method in methods]
        failed = [result for result in results if result.status != "passed"]
        status = "synthetic_check_passed" if not failed else "synthetic_check_failed"
        internal_review = {
            "status": "passed" if not failed else "failed",
            "checks": [
                "static_harness_review",
                "synthetic_method_check",
            ],
            "real_database_used": False,
            "visible_to_user": "summary_only",
            "repair_attempts": state.get("repair_attempts", 0),
            "method_count": len(methods),
        }
        return {
            **state,
            "mock_result": results[0].model_dump(mode="json"),
            "mock_results": [result.model_dump(mode="json") for result in results],
            "internal_method_review": internal_review,
            "row_count": results[0].input_summary.get("row_count") if results else None,
            "status": status,
            "errors": state.get("errors", []) + [error for result in results for error in result.errors],
        }

    def after_synthetic_check(self, state: AgentState) -> str:
        if state.get("status") == "synthetic_check_passed":
            return "ok"
        return "repair" if self._should_research_schema(state) else "refuse"

    @staticmethod
    def _can_schema_repair(state: AgentState) -> bool:
        # 包含首轮在内最多三次 Schema → SQL → 校验循环。
        return state.get("repair_attempts", 0) < MAX_METHOD_REPAIR_ATTEMPTS

    def _should_research_schema(self, state: AgentState) -> bool:
        """仅把可由 Schema/SQL 重规划解决的问题送回循环。

        沙箱连接失败、超时等基础设施错误不是“表没找对”，重跑只会浪费
        两次 LLM 调用并掩盖部署问题，因此直接停止在未通过状态。
        """
        if not self._can_schema_repair(state):
            return False
        error_text = " ".join(str(error).lower() for error in state.get("errors", [])[-5:])
        infrastructure_markers = (
            "failed to connect",
            "connection refused",
            "connection timed out",
            "could not connect",
            "timeout expired",
        )
        return not any(marker in error_text for marker in infrastructure_markers)

    def prepare_schema_repair(self, state: AgentState) -> AgentState:
        """把系统校验错误反馈到下一轮受控 Schema 搜索，而非让模型盲改 SQL。"""
        attempts = state.get("repair_attempts", 0) + 1
        errors = list(state.get("errors", []))
        history = list(state.get("repair_history", []))
        history.append(
            {
                "attempt": attempts,
                "from_status": state.get("status"),
                "errors": errors[-5:] or ["unknown validation failure"],
                "repair_mode": "schema_research",
            }
        )
        return {
            **state,
            "repair_attempts": attempts,
            "repair_history": history,
            "schema_repair_errors": errors[-5:] or ["unknown validation failure"],
            # 上一轮的错误必须被消费，而不能令下一轮无条件失败。
            "errors": [],
            "status": "schema_repair_prepared",
        }

    def repair_method(self, state: AgentState) -> AgentState:
        attempts = state.get("repair_attempts", 0) + 1
        history = list(state.get("repair_history", []))
        errors = list(state.get("errors", []))
        history.append(
            {
                "attempt": attempts,
                "from_status": state.get("status"),
                "errors": errors[-5:],
                "method_name": (state.get("method_draft") or {}).get("name"),
            }
        )
        try:
            # 收集错误信息
            error_messages = errors[-5:] if errors else ["unknown error"]
            error_summary = "; ".join(error_messages)

            # 获取当前的 SQL
            current_sql = state.get("sql") or (state.get("method_draft") or {}).get("sql_template", "")
            user_goal = state.get("action_user_goal") or state["user_query"]
            proposal = (state.get("action_validation") or {}).get("proposal") or {}
            sql_input_slots = state.get("sql_input_slots") or self._sql_input_slots(proposal.get("params") or {})
            sql_planning_goal = self._redact_sql_planning_goal(user_goal, sql_input_slots, proposal.get("params") or {})

            # 调用 LLM 修复 SQL
            repaired_sql = self._call_llm_for_repair(
                sql_planning_goal,
                current_sql,
                error_summary,
                state.get("visible_catalog"),
                input_slots=[{"id": slot["id"], "type": slot["type"], "semantic": slot["semantic"]} for slot in sql_input_slots],
            )

            if repaired_sql:
                # 从 SQL 中提取表名
                import re
                table_match = re.search(r"FROM\s+(\w+)", repaired_sql, re.IGNORECASE)
                table_name = table_match.group(1) if table_match else "card_transaction"

                method = MethodDraft(
                    method_type="sql",
                    name="llm_repaired_sql",
                    goal=user_goal,
                    operation="custom_sql",
                    table=table_name,
                    data_source="table",
                    sql_template=repaired_sql,
                    params=self._bound_input_params(state),
                    required_fields=self._extract_fields_from_sql(repaired_sql),
                    output_schema={},
                    risk_level="medium",
                    logic_summary=[f"已完成查询校验与调整：{user_goal}"],
                )
                return {
                    **state,
                    "method_draft": method.model_dump(mode="json"),
                    "method_drafts": [method.model_dump(mode="json")],
                    "sql": repaired_sql,
                    "repair_attempts": attempts,
                    "repair_history": history,
                    "status": "method_repaired",
                    "errors": [],
                }

            # 如果 LLM 修复失败，回退到原始逻辑
            validation = state.get("action_validation") or {}
            proposal = validation.get("proposal") or {}
            llm_sql = proposal.get("sql")
            llm_code = proposal.get("code")

            if llm_code:
                method = MethodDraft(
                    method_type="code",
                    name="llm_custom_code",
                    goal=user_goal,
                    operation="custom_code",
                    table="card_transaction",
                    data_source="table",
                    code=llm_code,
                    required_fields=self._extract_fields_from_code(llm_code),
                    output_schema={},
                    risk_level="medium",
                    logic_summary=[f"LLM 自写代码: {user_goal}"],
                )
                return {
                    **state,
                    "method_draft": method.model_dump(mode="json"),
                    "method_drafts": [method.model_dump(mode="json")],
                    "repair_attempts": attempts,
                    "repair_history": history,
                    "status": "method_repaired",
                    "errors": [],
                }

            if llm_sql:
                table_match = re.search(r"FROM\s+(\w+)", llm_sql, re.IGNORECASE)
                table_name = table_match.group(1) if table_match else "card_transaction"

                method = MethodDraft(
                    method_type="sql",
                    name="llm_custom_sql",
                    goal=user_goal,
                    operation="custom_sql",
                    table=table_name,
                    data_source="table",
                    sql_template=llm_sql,
                    params=self._bound_input_params(state),
                    required_fields=self._extract_fields_from_sql(llm_sql),
                    output_schema={},
                    risk_level="medium",
                    logic_summary=[f"LLM 自写 SQL: {user_goal}"],
                )
                return {
                    **state,
                    "method_draft": method.model_dump(mode="json"),
                    "method_drafts": [method.model_dump(mode="json")],
                    "sql": llm_sql,
                    "repair_attempts": attempts,
                    "repair_history": history,
                    "status": "method_repaired",
                    "errors": [],
                }

            # 回退：从 analysis_plan 生成
            plan = AnalysisPlan.model_validate(state["analysis_plan"]) if state.get("analysis_plan") else AnalysisPlan(goal=user_goal, steps=[])
            methods = generate_method_drafts(plan, self.handler_registry)
            method = methods[0]
            return {
                **state,
                "method_draft": method.model_dump(mode="json"),
                "method_drafts": [method.model_dump(mode="json") for method in methods],
                "sql": method.sql_template,
                "repair_attempts": attempts,
                "repair_history": history,
                "status": "method_repaired",
                "errors": [],
            }
        except Exception as exc:
            return {
                **state,
                "repair_attempts": attempts,
                "repair_history": history,
                "status": "method_repair_failed",
                "errors": state.get("errors", []) + [f"method repair failed: {type(exc).__name__}: {exc}"],
            }

    def _call_llm_for_repair(
        self,
        user_goal: str,
        current_sql: str,
        error_summary: str,
        visible_catalog: dict[str, Any] | None = None,
        input_slots: list[dict[str, str]] | None = None,
    ) -> str | None:
        """调用 LLM 修复 SQL。"""
        try:
            # 修复只能使用本次请求的可见 schema，避免让模型从 173 张表中猜表名。
            table_manifest = (visible_catalog or {}).get("tables") or self.table_registry.manifest_for_llm()
            table_info = "\n".join([
                f"- {t['name']}: {', '.join(column['name'] if isinstance(column, dict) else str(column) for column in t['columns'])}"
                for t in table_manifest
            ])

            prompt = f"""用户想要查询: {user_goal}

当前 SQL 有问题:
{current_sql}

错误信息:
{error_summary}

请根据错误信息修复 SQL。要求：
1. 只返回修复后的 SQL，不要其他文字
2. 只能使用下方列出的表名和字段名；不得猜测替代表或字段
3. 使用 PostgreSQL 语法
4. 如果需要多表查询，使用 JOIN
5. 只能使用下方 input_slots 里的 :input_N 占位符，绝不把筛选实际值写成 SQL 字符串

可用 input_slots:
{input_slots or []}

可用的表结构:
{table_info}
"""

            messages = [
                {"role": "system", "content": "你是一个 SQL 修复助手。根据错误信息修复 SQL 问题。只返回修复后的 SQL，不要其他文字。"},
                {"role": "user", "content": prompt},
            ]

            response = self.llm_provider.chat(messages, temperature=0, max_tokens=500)
            repaired_sql = response.content.strip()

            # 清理 SQL（移除可能的 markdown 格式）
            if repaired_sql.startswith("```sql"):
                repaired_sql = repaired_sql[6:]
            if repaired_sql.startswith("```"):
                repaired_sql = repaired_sql[3:]
            if repaired_sql.endswith("```"):
                repaired_sql = repaired_sql[:-3]
            repaired_sql = repaired_sql.strip()

            # 验证 SQL 是否有效
            if repaired_sql and repaired_sql.upper().startswith("SELECT"):
                return repaired_sql

            return None
        except Exception:
            return None

    async def render_method_card(self, state: AgentState) -> AgentState:
        plan = AnalysisPlan.model_validate(state["analysis_plan"]) if state.get("analysis_plan") else AnalysisPlan(goal=state.get("action_user_goal") or state["user_query"], steps=[])
        methods = self._state_methods(state)
        mock_results = state.get("mock_results")
        if not mock_results:
            extra = state.get("referenced_result_tables") or None
            mock_results = [run_mock_dry_run(method, extra_tables=extra).model_dump(mode="json") for method in methods]
        cards = [
            build_method_review_card(method, mock_result)
            for method, mock_result in zip(methods, mock_results, strict=False)
        ]
        card = cards[0]
        method_set_card = build_method_set_review_card(plan, cards) if len(cards) > 1 else None

        # 获取之前的查询记录（从文件型 memory）
        prior_queries = self.memory_store.get_recent_queries(limit=3, session_id=state["session_id"])

        context = (
            render_method_set_review_data(plan, methods, cards, self.handler_registry)
            if len(cards) > 1
            else render_method_review_data(plan, methods[0], card, prior_queries=prior_queries)
        )
        answer = await generate_reply(context, state["user_query"], self.llm_provider, state.get("conversation_history"))

        # Dependent method: skip normal data authorization, use prior result auth instead
        primary_method = methods[0]
        if primary_method.data_source == "result_ref":
            refs = state.get("referenced_result_refs") or ([primary_method.result_ref] if primary_method.result_ref else [])
            schemas = state.get("prior_result_schemas") or []
            total_rows = sum(s.get("row_count", 0) for s in schemas) if schemas else len(state.get("referenced_result_data", []))
            all_fields = [f.split(".", 1)[-1] for f in primary_method.required_fields]
            prior_auth_card = PriorResultAuthorizationCard(
                status="pending",
                purpose=primary_method.goal,
                method_name=primary_method.name,
                method_hash=stable_hash(primary_method.model_dump(mode="json")),
                referenced_result_ref=", ".join(refs),
                prior_result_fields=all_fields,
                prior_result_row_count=total_rows,
                operation=primary_method.operation,
                readonly=True,
                new_database_access=False,
                safety_notes=[
                    f"基于 {len(refs)} 个已授权的 prior result 执行，不读取新的数据库。",
                    "prior result 的数据已经在之前的授权中获得批准。",
                    "LLM 不接触真实数据值。",
                ],
            )
            return {
                **state,
                "mock_result": mock_results[0],
                "mock_results": mock_results,
                "method_review_card": method_set_card.model_dump(mode="json") if method_set_card else card.model_dump(mode="json"),
                "method_review_cards": [card.model_dump(mode="json") for card in cards],
                "method_set_review_card": method_set_card.model_dump(mode="json") if method_set_card else None,
                "prior_result_authorization_card": prior_auth_card.model_dump(mode="json"),
                "answer": answer,
                "status": "prior_result_authorization_pending",
            }

        return {
            **state,
            "mock_result": mock_results[0],
            "mock_results": mock_results,
            "method_review_card": method_set_card.model_dump(mode="json") if method_set_card else card.model_dump(mode="json"),
            "method_review_cards": [card.model_dump(mode="json") for card in cards],
            "method_set_review_card": method_set_card.model_dump(mode="json") if method_set_card else None,
            "answer": answer,
            "status": "method_review_ready",
        }

    async def refuse_method(self, state: AgentState) -> AgentState:
        context = refuse_method_data("; ".join(state.get("errors", [])[-5:]))
        answer = await generate_reply(context, state["user_query"], self.llm_provider, state.get("conversation_history"))
        return {
            **state,
            "status": "method_refused",
            "answer": answer,
            "internal_method_review": {
                "status": "refused",
                "checks": ["static_harness_review", "synthetic_method_check"],
                "repair_attempts": state.get("repair_attempts", 0),
                "real_database_used": False,
            },
        }

    def load_prior_result(self, state: AgentState) -> AgentState:
        validation = state.get("action_validation") or {}
        proposal = validation.get("proposal") or {}
        result_refs = list(proposal.get("result_refs") or [])
        if not result_refs:
            return {
                **state,
                "status": "prior_result_not_found",
                "errors": state.get("errors", []) + ["result_ref(s) missing from action"],
            }

        # Look up all prior results from private store
        records = self.private_result_store.latest(limit=50, session_id=state["session_id"])
        found_records = []
        for ref in result_refs:
            record = next((r for r in records if r.result_ref == ref), None)
            if not record:
                return {
                    **state,
                    "status": "prior_result_not_found",
                    "errors": state.get("errors", []) + [f"prior result not found: {ref}"],
                }
            found_records.append(record)

        # Build per-result data, schema, and extra_tables
        result_tables: dict[str, list[dict[str, Any]]] = {}
        schemas: list[dict[str, Any]] = []
        all_data: list[dict[str, Any]] = []  # primary = first result

        for idx, record in enumerate(found_records):
            data = record.result if isinstance(record.result, list) else [record.result]
            table_name = f"prior_result_{idx}" if len(found_records) > 1 else "prior_result"
            result_tables[table_name] = data

            columns = []
            if data:
                for key in data[0].keys():
                    val = data[0][key]
                    col_type = "integer" if isinstance(val, int) else "number" if isinstance(val, float) else "text"
                    columns.append({"name": key, "type": col_type})
            schemas.append({"table_name": table_name, "columns": columns, "row_count": len(data), "result_ref": record.result_ref})

            if idx == 0:
                all_data = data

        return {
            **state,
            "referenced_result_ref": result_refs[0],
            "referenced_result_refs": result_refs,
            "referenced_result_data": all_data,
            "referenced_result_tables": result_tables,
            "prior_result_schema": schemas[0] if schemas else {},
            "prior_result_schemas": schemas,
            "status": "prior_result_loaded",
        }

    def generate_dependent_method(self, state: AgentState) -> AgentState:
        if state.get("status") != "prior_result_loaded":
            return {
                **state,
                "status": "dependent_method_failed",
                "errors": state.get("errors", []) + ["cannot generate dependent method: prior result not loaded"],
            }

        validation = state.get("action_validation") or {}
        proposal = validation.get("proposal") or {}
        user_goal = proposal.get("goal") or state["user_query"]
        operation = proposal.get("entity_id") or "group_by"
        result_ref = state["referenced_result_ref"]
        schemas = state.get("prior_result_schemas") or [state["prior_result_schema"]]

        # Single result: use generate_dependent_method directly
        # Multiple results: generate method for the first, or join if possible
        if len(schemas) == 1:
            method = generate_dependent_method(user_goal, operation, schemas[0], result_ref, self.handler_registry)
        else:
            # Multi-source: use first result as primary, mention others in goal
            method = generate_dependent_method(user_goal, operation, schemas[0], result_ref, self.handler_registry)
            # Update method to reflect multi-source nature
            table_names = [s["table_name"] for s in schemas]
            method = method.model_copy(update={
                "name": f"dependent_multi_{len(schemas)}",
                "goal": f"{user_goal} (基于 {len(schemas)} 个先前结果)",
                "logic_summary": [
                    *method.logic_summary,
                    f"多源依赖：使用 {', '.join(table_names)}",
                ],
            })

        return {
            **state,
            "method_draft": method.model_dump(mode="json"),
            "method_drafts": [method.model_dump(mode="json")],
            "sql": method.sql_template,
            "status": "method_generated",
        }

    async def approve_prior_result_authorization(self, state: AgentState) -> AgentState:
        if state.get("status") != "prior_result_authorization_pending":
            raise ValueError(f"run is not pending prior result authorization: {state.get('status')}")

        methods = self._state_methods(state)
        method = methods[0]
        extra_tables = state.get("referenced_result_tables") or {"prior_result": state.get("referenced_result_data", [])}
        total_rows = sum(len(rows) for rows in extra_tables.values())

        execution = run_simulated_real_execution(method, extra_tables=extra_tables)
        if execution.status != "passed":
            raise RuntimeError("; ".join(execution.errors) or f"dependent execution failed: {method.name}")

        authorization = DataAuthorizationCard(
            status="pending",
            purpose=method.goal,
            method_name=method.name,
            method_hash=stable_hash(method.model_dump(mode="json")),
            tables=list(extra_tables.keys()),
            fields=method.required_fields,
            row_limit=total_rows,
            readonly=True,
            real_data_read=False,
            safety_notes=[],
        )
        card = build_execution_result_card(method, authorization, execution)

        private_record = self.private_result_store.append(
            request_id=state["request_id"],
            session_id=state["session_id"],
            method_name=method.name,
            method_hash=card.method_hash,
            authorization_hash=stable_hash(authorization.model_dump(mode="json")),
            result=card.result,
            row_count=card.row_count,
            metadata={
                "execution_mode": "dependent",
                "source_result_ref": state.get("referenced_result_ref"),
                "real_database_used": False,
            },
        )
        public_memory = self.memory_store.upsert(
            build_query_history_memory(
                request_id=state["request_id"],
                session_id=state["session_id"],
                method=method,
                execution_card=card,
                private_record=private_record,
            )
        )
        narration = narrate_execution_result(
            card,
            method,
            self.settings,
            self.llm_provider,
            result_ref=private_record.result_ref,
        )
        # 兼容旧 B 接口时也不把 prior result 行发送给普通回复 LLM。
        answer = render_user_narration(narration)
        audited = self.audit(
            {
                **state,
                "status": "executed_simulated_real",
                "result_ref": private_record.result_ref,
                "public_memory_entry": PublicMemoryEntry.from_record(public_memory).model_dump(mode="json"),
                "execution_result_card": card.model_dump(mode="json"),
                "execution_result_cards": [card.model_dump(mode="json")],
                "result_narration": narration.model_dump(mode="json"),
                "result_narrations": [narration.model_dump(mode="json")],
                "public_memory_entries": [PublicMemoryEntry.from_record(public_memory).model_dump(mode="json")],
                "row_count": card.row_count,
                "answer": answer,
            }
        )
        self._persist_private_analysis(audited)
        return audited

    @staticmethod
    def _can_repair(state: AgentState) -> bool:
        return state.get("repair_attempts", 0) < MAX_METHOD_REPAIR_ATTEMPTS

    def _persist_private_analysis(self, state: AgentState) -> None:
        """保存真实结果与解读到用户可见私有区，不写入普通会话历史。"""
        if not state.get("session_id") or not state.get("answer"):
            return
        if not (state.get("result_narrations") or state.get("execution_result_cards") or state.get("execution_result_card")):
            return
        self.session_manager.add_private_analysis(
            state["session_id"],
            {
                "request_id": state.get("request_id", ""),
                "answer": state.get("answer", ""),
                "result_ref": state.get("result_ref"),
                "result_refs": state.get("result_refs"),
                "plan_result_ref": state.get("plan_result_ref"),
                "execution_result_card": state.get("execution_result_card"),
                "execution_result_cards": state.get("execution_result_cards"),
                "result_narration": state.get("result_narration"),
                "result_narrations": state.get("result_narrations"),
            },
        )

    async def _prepare_method_after_analysis_plan(self, state: AgentState) -> AgentState:
        next_state = self.generate_method(state)
        while True:
            next_state = self.review_method(next_state)
            if next_state.get("status") == "method_reviewed":
                next_state = self.synthetic_check(next_state)
                if next_state.get("status") == "synthetic_check_passed":
                    return self.audit(await self.render_method_card(next_state))
                if self._can_repair(next_state):
                    next_state = self.repair_method(next_state)
                    continue
                return self.audit(await self.refuse_method(next_state))

            if self._can_repair(next_state):
                next_state = self.repair_method(next_state)
                continue
            return self.audit(await self.refuse_method(next_state))

    @staticmethod
    def _state_methods(state: AgentState) -> list[MethodDraft]:
        if state.get("method_drafts"):
            return [MethodDraft.model_validate(method) for method in state["method_drafts"]]
        return [MethodDraft.model_validate(state["method_draft"])]

    def audit(self, state: AgentState) -> AgentState:
        execution_card = self._safe_audit_execution_card(state.get("execution_result_card"))
        execution_cards = [
            self._safe_audit_execution_card(card)
            for card in (state.get("execution_result_cards") or [])
        ]
        mock_result = self._safe_audit_execution_card(state.get("mock_result"))
        mock_results = [
            self._safe_audit_execution_card(result)
            for result in (state.get("mock_results") or [])
        ]
        narration = state.get("result_narration") or {}
        safe_narration = {
            key: narration.get(key)
            for key in ("title", "source")
            if isinstance(narration, dict) and narration.get(key) is not None
        }
        event: dict[str, Any] = {
            "request_id": state.get("request_id"),
            "user_query": state.get("user_query"),
            "status": state.get("status"),
            "errors": state.get("errors", []),
            "tool_decision": state.get("tool_decision"),
            "response_plan": state.get("response_plan"),
            "action_validation": state.get("action_validation"),
            "selected_skill_detail": state.get("selected_skill_detail"),
            "planner_used": state.get("planner_used"),
            "analysis_plan": state.get("analysis_plan"),
            "analysis_plan_review_card": state.get("analysis_plan_review_card"),
            "method_draft": state.get("method_draft"),
            "method_drafts": state.get("method_drafts"),
            "harness_review": state.get("harness_review"),
            "harness_reviews": state.get("harness_reviews"),
            "mock_result": mock_result,
            "mock_results": mock_results,
            "internal_method_review": state.get("internal_method_review"),
            "repair_attempts": state.get("repair_attempts"),
            "repair_history": state.get("repair_history"),
            "method_review_card": state.get("method_review_card"),
            "method_review_cards": state.get("method_review_cards"),
            "method_set_review_card": state.get("method_set_review_card"),
            "data_authorization_card": state.get("data_authorization_card"),
            "prior_result_authorization_card": state.get("prior_result_authorization_card"),
            "execution_result_card": execution_card,
            "execution_result_cards": execution_cards,
            "result_narration": safe_narration,
            "result_narrations": [
                {
                    key: item.get(key)
                    for key in ("title", "source")
                    if isinstance(item, dict) and item.get(key) is not None
                }
                for item in (state.get("result_narrations") or [])
            ],
            "result_ref": state.get("result_ref"),
            "result_refs": state.get("result_refs"),
            "plan_result_ref": state.get("plan_result_ref"),
            "referenced_result_ref": state.get("referenced_result_ref"),
            "public_memory_entry": state.get("public_memory_entry"),
            "public_memory_context": state.get("public_memory_context"),
            "relevant_memories": state.get("relevant_memories"),
            "visible_schema_hash": stable_hash(state.get("visible_catalog")),
            "raw_plan": state.get("raw_plan"),
            "validated_plan": state.get("validated_plan"),
            "sql": state.get("sql"),
            "result_hash": stable_hash(state.get("mock_result") or state.get("rows")),
            "row_count": state.get("row_count"),
            "elapsed_ms": state.get("elapsed_ms"),
        }
        audit = self.audit_logger.append(event)

        # 提取记忆（新系统）- 使用同步版本
        try:
            from finance_agent.memory.extractor import extract_memories_from_state_sync
            extracted_memories = extract_memories_from_state_sync(state, self.memory_store, self.llm_provider)
            if extracted_memories:
                event["extracted_memories"] = [m.name for m in extracted_memories]
        except Exception as e:
            event["memory_extraction_error"] = str(e)

        # 更新普通对话历史（保存到状态，LangGraph checkpointer 会自动持久化）。
        # 真实结果解读只保存在 private_analysis，不得进入普通上下文状态。
        conversation_history = state.get("conversation_history", [])
        answer = state.get("answer")
        has_private_result = bool(
            state.get("result_narrations")
            or state.get("execution_result_cards")
            or state.get("execution_result_card")
        )
        if answer and not has_private_result:
            conversation_history.append({"role": "assistant", "content": answer})

        return {**state, "audit": audit, "conversation_history": conversation_history}

    @staticmethod
    def _safe_audit_execution_card(value: Any) -> dict[str, Any] | None:
        """Keep audit metadata while excluding result rows/output values."""
        if not isinstance(value, dict):
            return None
        return {key: item for key, item in value.items() if key not in {"result", "output"}}
