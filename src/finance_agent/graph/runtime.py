from __future__ import annotations

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
from finance_agent.memory.memory_store import MemoryStore
from finance_agent.memory.private_result_store import PrivateResultStore
from finance_agent.memory.public_memory import PublicMemoryStore
from finance_agent.memory.safe_summary import build_public_memory_entry
from finance_agent.memory.selector import select_relevant_memories
from finance_agent.memory.extractor import extract_memories_from_state
from finance_agent.metadata.business_registry import BusinessTermRegistry, load_business_registry_from_catalog
from finance_agent.metadata.catalog import Catalog, load_catalog
from finance_agent.metadata.policy import Policy, load_policy
from finance_agent.metadata.pruner import prune_catalog
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
from finance_agent.renderer.result_narrator import narrate_execution_result
from finance_agent.sandbox.mock_sandbox import run_mock_dry_run, run_simulated_real_execution
from finance_agent.session.manager import SessionManager, get_session_manager
from finance_agent.skills.registry import SkillRegistry, load_skill_registry


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
        self.llm_provider = llm_provider or build_llm_provider(self.settings)
        self.audit_logger = AuditLogger(self.settings.audit_log_path)
        self.private_result_store = PrivateResultStore(self.settings.private_result_store_path)
        self.public_memory_store = PublicMemoryStore(self.settings.public_memory_path)
        self.memory_store = MemoryStore(self.settings.public_memory_path.parent / "public_memory")
        self.session_manager = session_manager or get_session_manager()
        self.checkpointer = MemorySaver()
        self.executor = self._build_executor()
        self.graph = self._build_graph()

    def _build_executor(self):
        return self.executor_registry.create(self.settings.executor_mode, self.settings, self.policy)

    def _build_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("plan_response", self.plan_response)
        graph.add_node("validate_action", self.validate_action)
        graph.add_node("render_direct_response", self.render_direct_response)
        graph.add_node("load_metadata", self.load_metadata)
        graph.add_node("plan_analysis", self.plan_analysis)
        graph.add_node("render_analysis_plan_card", self.render_analysis_plan_card)
        graph.add_node("generate_method", self.generate_method)
        graph.add_node("review_method", self.review_method)
        graph.add_node("synthetic_check", self.synthetic_check)
        graph.add_node("repair_method", self.repair_method)
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
                "method_flow": "load_metadata",
                "direct_response": "render_direct_response",
                "dependent_flow": "load_prior_result",
            },
        )
        graph.add_edge("render_direct_response", "audit")
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
            {"ok": "synthetic_check", "repair": "repair_method", "refuse": "refuse_method"},
        )
        graph.add_conditional_edges(
            "synthetic_check",
            self.after_synthetic_check,
            {"ok": "render_method_card", "repair": "repair_method", "refuse": "refuse_method"},
        )
        graph.add_edge("repair_method", "review_method")
        graph.add_edge("render_method_card", "audit")
        graph.add_edge("refuse_method", "audit")
        graph.add_edge("load_prior_result", "generate_dependent_method")
        graph.add_edge("generate_dependent_method", "review_method")
        graph.add_edge("audit", END)
        return graph.compile(checkpointer=self.checkpointer)

    async def invoke(self, question: str, session_id: str | None = None) -> AgentState:
        # 如果没有 session_id，创建新的 session
        if not session_id:
            session = self.session_manager.create_session()
            session_id = session["session_id"]
        else:
            # 确保 session 存在
            session = self.session_manager.get_session(session_id)
            if session is None:
                session = self.session_manager.create_session()
                session_id = session["session_id"]

        # 从 SessionManager 读取对话历史
        conversation_history = self.session_manager.get_conversation_history(session_id)

        # 添加当前用户消息到历史
        conversation_history.append({"role": "user", "content": question})

        # 保存用户消息到 session
        self.session_manager.add_message(session_id, "user", question)

        # 使用 session_id 作为 thread_id（保持兼容性）
        config = {"configurable": {"thread_id": session_id}}

        initial: AgentState = {
            "request_id": str(uuid.uuid4()),
            "session_id": session_id,
            "user_query": question,
            "status": "started",
            "errors": [],
            "public_memory_context": self.public_memory_store.context_for_llm(),
            "conversation_history": conversation_history,
            "repair_attempts": 0,
            "repair_history": [],
        }

        # 调用图
        result = await self.graph.ainvoke(initial, config=config)

        # 保存 assistant 回复到 session
        answer = result.get("answer")
        if answer:
            self.session_manager.add_message(session_id, "assistant", answer)

        return result

    async def approve_method_review(self, state: AgentState) -> AgentState:
        """合并方法确认和数据授权为一步：确认后直接执行。"""
        if state.get("status") != "method_review_ready":
            raise ValueError(f"run is not pending method review: {state.get('status')}")
        if not state.get("method_draft") and not state.get("method_drafts"):
            raise ValueError("run has no method draft")

        # 生成授权卡片
        methods = self._state_methods(state)
        card = (
            build_data_authorization_card_for_methods(methods, row_limit=self.policy.max_rows)
            if len(methods) > 1
            else build_data_authorization_card(methods[0], row_limit=self.policy.max_rows)
        )

        # 尝试执行，如果失败则自动修复重试
        max_attempts = 3
        last_error = None
        execution = None

        for attempt in range(max_attempts):
            methods = self._state_methods(state)
            execution = run_simulated_real_execution(methods[0])

            if execution.status == "passed":
                break  # 执行成功

            # 执行失败，尝试修复
            last_error = "; ".join(execution.errors) or f"simulated execution failed: {methods[0].name}"

            if attempt < max_attempts - 1 and self._can_repair(state):
                current_sql = state.get("sql") or (state.get("method_draft") or {}).get("sql_template", "")
                user_goal = state.get("action_user_goal") or state["user_query"]
                repaired_sql = self._call_llm_for_repair(user_goal, current_sql, last_error)

                if repaired_sql:
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
                        required_fields=self._extract_fields_from_sql(repaired_sql),
                        output_schema={},
                        risk_level="medium",
                        logic_summary=[f"LLM 修复 SQL (attempt {attempt + 1}): {last_error}"],
                    )
                    state = {
                        **state,
                        "method_draft": method.model_dump(mode="json"),
                        "method_drafts": [method.model_dump(mode="json")],
                        "sql": repaired_sql,
                        "repair_attempts": state.get("repair_attempts", 0) + 1,
                    }
                    continue

            break  # 无法修复或重试次数用完

        # 如果仍然失败，返回错误信息
        if not execution or execution.status != "passed":
            return self.audit({
                **state,
                "status": "method_execution_failed",
                "answer": f"SQL 执行失败: {last_error}\n\n已尝试 {max_attempts} 次修复，但仍有问题。请检查查询条件或联系管理员。",
                "errors": state.get("errors", []) + [last_error],
            })

        # 执行成功，构建结果
        methods = self._state_methods(state)
        authorization = card

        # 使用已有的执行结果，不重新执行
        card = build_execution_result_card(methods[0], authorization, execution)
        private_record = self.private_result_store.append(
            request_id=state["request_id"],
            method_name=methods[0].name,
            method_hash=card.method_hash,
            authorization_hash=stable_hash(authorization.model_dump(mode="json")),
            result=card.result,
            row_count=card.row_count,
            metadata={
                "execution_mode": card.execution_mode,
                "real_database_used": card.real_database_used,
                "method_set_size": 1,
            },
        )
        public_memory = self.public_memory_store.append(
            build_public_memory_entry(
                request_id=state["request_id"],
                method=methods[0],
                execution_card=card,
                private_record=private_record,
                user_query=state.get("user_query"),
            )
        )

        # 保存查询历史到文件型 memory（保存用户意图，不保存 SQL）
        result_summary = f"返回 {card.row_count} 行"

        # 从 SQL 中提取表名（如果 required_fields 为空）
        import re
        sql_template = methods[0].sql_template or ""
        tables_from_sql = re.findall(r"(?:FROM|JOIN)\s+(\w+)", sql_template, re.IGNORECASE)
        tables = list(set([f.split(".")[0] for f in methods[0].required_fields if "." in f])) or tables_from_sql

        self.memory_store.save_query_history(
            user_query=state.get("user_query", ""),
            result_summary=result_summary,
            tables=tables,
            fields=methods[0].required_fields,
        )
        narration = narrate_execution_result(
            card,
            methods[0],
            self.settings,
            self.llm_provider,
            result_ref=private_record.result_ref,
        )

        context = render_execution_result_data(card, narration, self.handler_registry)
        answer = await generate_reply(context, state["user_query"], self.llm_provider, state.get("conversation_history"))
        next_state: AgentState = {
            **state,
            "status": "executed_simulated_real",
            "result_ref": private_record.result_ref,
            "public_memory_entry": public_memory.model_dump(mode="json"),
            "execution_result_card": card.model_dump(mode="json"),
            "execution_result_cards": [card.model_dump(mode="json")],
            "result_narration": narration.model_dump(mode="json"),
            "result_narrations": [narration.model_dump(mode="json")],
            "public_memory_entries": [public_memory.model_dump(mode="json")],
            "row_count": card.row_count,
            "answer": answer,
        }
        return self.audit(next_state)

    async def approve_analysis_plan(self, state: AgentState) -> AgentState:
        if state.get("status") != "analysis_plan_review_ready":
            raise ValueError(f"run is not pending analysis plan review: {state.get('status')}")
        if not state.get("analysis_plan"):
            raise ValueError("run has no analysis plan")

        next_state: AgentState = {**state, "status": "analysis_plan_approved"}
        return await self._prepare_method_after_analysis_plan(next_state)

    async def approve_data_authorization(self, state: AgentState) -> AgentState:
        """保留兼容性，但实际上已合并到 approve_method_review 中。"""
        # 如果状态是 method_review_ready，直接调用 approve_method_review
        if state.get("status") == "method_review_ready":
            return await self.approve_method_review(state)

        # 否则报错
        raise ValueError(f"run is not pending data authorization: {state.get('status')}")

    def plan_response(self, state: AgentState) -> AgentState:
        # 选择相关记忆（新系统）- 使用同步版本
        from finance_agent.memory.selector import select_relevant_memories_sync
        relevant_memories = select_relevant_memories_sync(
            state["user_query"],
            self.memory_store,
            self.llm_provider,
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
            table_manifest=self.table_registry.manifest_for_llm(),
            relevant_memories=memory_context,
            table_detail_level="summary",  # 第一层：只发送表名和描述
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
        # 有 result_refs → 依赖执行路径
        proposal = validation.get("proposal") or {}
        if proposal.get("result_refs"):
            return "dependent_flow"
        return "method_flow"

    def validate_action(self, state: AgentState) -> AgentState:
        plan = ResponsePlan.model_validate(state["response_plan"])
        validation = validate_response_plan(plan, state["user_query"], self.operation_registry, self.skill_registry)
        selected_skill_detail = validation.disclosure.get("skill_detail") if validation.disclosure else None
        return {
            **state,
            "action_validation": validation.model_dump(mode="json"),
            "selected_skill_detail": selected_skill_detail,
            "action_user_goal": validation.user_goal,
            "status": validation.status,
            "errors": state.get("errors", []) + validation.errors,
        }

    def render_direct_response(self, state: AgentState) -> AgentState:
        plan = ResponsePlan.model_validate(state["response_plan"])
        return {
            **state,
            "answer": plan.message,
            "status": state.get("action_validation", {}).get("status", plan.status_hint),
        }

    def load_metadata(self, state: AgentState) -> AgentState:
        # 从 table_registry 构建完整的 catalog（包含所有表）
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

        full_catalog = Catalog(
            version="dynamic",
            description="Auto-generated from table_registry",
            tables=tables,
            business_terms=self.catalog.business_terms if hasattr(self, 'catalog') else {},
        )

        visible = prune_catalog(state.get("action_user_goal") or state["user_query"], full_catalog, self.policy)
        return {
            **state,
            "visible_catalog": visible.model_dump(),
            "status": "metadata_loaded",
        }

    def plan_analysis(self, state: AgentState) -> AgentState:
        visible = Catalog.model_validate(state["visible_catalog"])
        errors = list(state.get("errors", []))
        user_goal = state.get("action_user_goal") or state["user_query"]
        action_context = {
            "action_validation": state.get("action_validation"),
            "response_plan": state.get("response_plan"),
            "selected_skill_detail": state.get("selected_skill_detail"),
        }
        try:
            plan = plan_analysis_with_lmstudio(
                user_goal,
                visible,
                self.operation_registry,
                self.settings,
                self.llm_provider,
                action_context=action_context,
                handler_manifest=self.handler_registry.manifest_for_llm(),
                business_term_manifest=self.business_term_registry.manifest_for_llm(),
                table_manifest=self.table_registry.manifest_for_llm(),
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
            "planner_used": planner_used,
            "status": "analysis_planned",
            "errors": errors,
        }

    @staticmethod
    def after_analysis_plan(state: AgentState) -> str:
        if state.get("status") != "analysis_planned":
            return "fail"
        validation = state.get("action_validation") or {}
        if validation.get("status") == "skill_proposed":
            return "plan_review"
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
        skill_id = (state.get("selected_skill_detail") or {}).get("skill_id")
        if not skill_id:
            return plan
        if skill_id == "transaction_quality_review":
            existing = list(plan.steps)
            status_index = next(
                (index for index, step in enumerate(existing) if step.operation == "status_distribution"),
                None,
            )
            status_step = existing[status_index] if status_index is not None else None
            if status_step is None:
                base_step = existing[0] if existing else None
                if base_step is None:
                    return plan
                status_step = base_step.model_copy(
                    update={
                        "operation": "status_distribution",
                        "metric": None,
                        "dimension": "status",
                        "group_by": None,
                        "time_field": None,
                        "grain": None,
                        "rationale": "交易质量分析先查看状态分布，用于判断完成、失败、处理中和冲正等占比。",
                    }
                )
            else:
                status_step = status_step.model_copy(
                    update={
                        "metric": None,
                        "dimension": status_step.dimension or status_step.group_by or "status",
                        "group_by": None,
                        "rationale": status_step.rationale or "交易质量分析先查看状态分布。",
                    }
                )
            excluded_index = status_index if status_index is not None else 0
            rest = [step for index, step in enumerate(existing) if index != excluded_index and step.operation != "status_distribution"]
            required = sorted(
                {
                    *plan.required_metadata,
                    "card_transaction.status",
                    "card_transaction.card_channel",
                    "card_transaction.total_amount",
                    "card_transaction.transaction_at",
                }
            )
            has_trend = any(step.operation == "trend" for step in rest)
            has_channel = any(
                (step.group_by == "card_channel" or step.dimension == "card_channel")
                for step in rest
            )
            if not has_trend:
                rest.append(
                    status_step.model_copy(
                        update={
                            "operation": "trend",
                            "metric": "total_amount",
                            "dimension": None,
                            "group_by": None,
                            "time_field": "transaction_at",
                            "grain": "month",
                            "rationale": "交易质量分析需要观察金额随时间变化，识别异常波动。",
                        }
                    )
                )
            if not has_channel:
                rest.append(
                    status_step.model_copy(
                        update={
                            "operation": "group_by",
                            "metric": "total_amount",
                            "dimension": None,
                            "group_by": "card_channel",
                            "time_field": None,
                            "grain": None,
                            "limit": 10,
                            "rationale": "交易质量分析需要按卡渠道拆分，观察不同渠道的交易结构。",
                        }
                    )
                )
            return plan.model_copy(update={"steps": [status_step, *rest], "required_metadata": required})
        return plan

    def generate_method(self, state: AgentState) -> AgentState:
        try:
            # 检查 LLM 是否自写了 SQL 或 Python 代码
            validation = state.get("action_validation") or {}
            proposal = validation.get("proposal") or {}
            llm_sql = proposal.get("sql")
            llm_code = proposal.get("code")

            if llm_code:
                # LLM 自写 Python 代码 → 直接生成 MethodDraft
                user_goal = proposal.get("goal") or state.get("action_user_goal") or state["user_query"]
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
                    "status": "method_generated",
                }

            if llm_sql:
                # LLM 自写 SQL → 直接生成 MethodDraft
                user_goal = proposal.get("goal") or state.get("action_user_goal") or state["user_query"]
                llm_params = proposal.get("params") or {}

                # 从 SQL 中提取表名
                import re
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
                    required_fields=self._extract_fields_from_sql(llm_sql),
                    params=llm_params,
                    output_schema={},
                    risk_level="medium",
                    logic_summary=[f"LLM 自写 SQL: {user_goal}"],
                )
                return {
                    **state,
                    "method_draft": method.model_dump(mode="json"),
                    "method_drafts": [method.model_dump(mode="json")],
                    "sql": llm_sql,
                    "status": "method_generated",
                }

            plan = AnalysisPlan.model_validate(state["analysis_plan"])
            methods = generate_method_drafts(plan, self.handler_registry)
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
            if table.lower() not in ("select", "where", "and", "or", "on", "as"):
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
        return "repair" if self._can_repair(state) else "refuse"

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
        return "repair" if self._can_repair(state) else "refuse"

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

            # 调用 LLM 修复 SQL
            repaired_sql = self._call_llm_for_repair(user_goal, current_sql, error_summary)

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
                    required_fields=self._extract_fields_from_sql(repaired_sql),
                    output_schema={},
                    risk_level="medium",
                    logic_summary=[f"LLM 修复 SQL (attempt {attempts}): {error_summary}"],
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

    def _call_llm_for_repair(self, user_goal: str, current_sql: str, error_summary: str) -> str | None:
        """调用 LLM 修复 SQL。"""
        try:
            # 获取表结构信息
            table_manifest = self.table_registry.manifest_for_llm()
            table_info = "\n".join([
                f"- {t['name']}: {', '.join(t['columns'][:5])}..."
                for t in table_manifest[:10]
            ])

            prompt = f"""用户想要查询: {user_goal}

当前 SQL 有问题:
{current_sql}

错误信息:
{error_summary}

请根据错误信息修复 SQL。要求：
1. 只返回修复后的 SQL，不要其他文字
2. 确保表名和字段名正确（参考下方表结构）
3. 使用 PostgreSQL 语法
4. 如果需要多表查询，使用 JOIN

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

        # 获取之前的查询记录（从文件型 memory）
        prior_queries = self.memory_store.get_recent_queries(limit=3)

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
                "method_review_card": card.model_dump(mode="json"),
                "method_review_cards": [card.model_dump(mode="json") for card in cards],
                "prior_result_authorization_card": prior_auth_card.model_dump(mode="json"),
                "answer": answer,
                "status": "prior_result_authorization_pending",
            }

        return {
            **state,
            "mock_result": mock_results[0],
            "mock_results": mock_results,
            "method_review_card": card.model_dump(mode="json"),
            "method_review_cards": [card.model_dump(mode="json") for card in cards],
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
        records = self.private_result_store.latest(limit=50)
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
        public_memory = self.public_memory_store.append(
            build_public_memory_entry(
                request_id=state["request_id"],
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
        context = render_execution_result_data(card, narration, self.handler_registry)
        answer = await generate_reply(context, state["user_query"], self.llm_provider, state.get("conversation_history"))
        return self.audit(
            {
                **state,
                "status": "executed_simulated_real",
                "result_ref": private_record.result_ref,
                "public_memory_entry": public_memory.model_dump(mode="json"),
                "execution_result_card": card.model_dump(mode="json"),
                "execution_result_cards": [card.model_dump(mode="json")],
                "result_narration": narration.model_dump(mode="json"),
                "result_narrations": [narration.model_dump(mode="json")],
                "public_memory_entries": [public_memory.model_dump(mode="json")],
                "row_count": card.row_count,
                "answer": answer,
            }
        )

    @staticmethod
    def _can_repair(state: AgentState) -> bool:
        return state.get("repair_attempts", 0) < MAX_METHOD_REPAIR_ATTEMPTS

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
            "mock_result": state.get("mock_result"),
            "mock_results": state.get("mock_results"),
            "internal_method_review": state.get("internal_method_review"),
            "repair_attempts": state.get("repair_attempts"),
            "repair_history": state.get("repair_history"),
            "method_review_card": state.get("method_review_card"),
            "method_review_cards": state.get("method_review_cards"),
            "data_authorization_card": state.get("data_authorization_card"),
            "prior_result_authorization_card": state.get("prior_result_authorization_card"),
            "execution_result_card": state.get("execution_result_card"),
            "execution_result_cards": state.get("execution_result_cards"),
            "result_narration": state.get("result_narration"),
            "result_narrations": state.get("result_narrations"),
            "result_ref": state.get("result_ref"),
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

        # 更新对话历史（保存到状态，LangGraph checkpointer 会自动持久化）
        conversation_history = state.get("conversation_history", [])
        answer = state.get("answer")
        if answer:
            conversation_history.append({"role": "assistant", "content": answer})

        return {**state, "audit": audit, "conversation_history": conversation_history}
