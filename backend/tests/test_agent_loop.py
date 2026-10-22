import asyncio
import json

from app.agent.loop import SYSTEM_PROMPT, ToolResult, run_agent


def call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


class ScriptedLLM:
    # отдаёт заранее заданные ответы и запоминает, что ему прислали
    def __init__(self, replies):
        self.replies = list(replies)
        self.requests = []

    async def __call__(self, messages, tools):
        self.requests.append({"messages": [dict(m) for m in messages], "tools": tools})
        return self.replies.pop(0)


class FakeToolbox:
    def __init__(self):
        self.calls = []

    def schemas(self):
        return [{"type": "function", "function": {"name": "search_all"}}]

    async def call(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "search_all":
            return ToolResult(
                content=f"найдено по запросу {arguments['query']}",
                sources=[{"chunk_id": 1, "document": "a.pdf"}, {"chunk_id": 2, "document": "b.pdf"}],
            )
        raise ValueError(f"неизвестный инструмент: {name}")


def run(llm, toolbox, **kwargs):
    return asyncio.run(run_agent("Какой срок договора?", llm, toolbox, **kwargs))


def test_answers_directly_without_tools():
    llm = ScriptedLLM([{"content": "Ответ"}])
    result = run(llm, FakeToolbox())

    assert result.text == "Ответ"
    assert result.steps == []
    assert llm.requests[0]["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}


def test_executes_tool_and_feeds_result_back():
    llm = ScriptedLLM([
        {"content": "", "tool_calls": [call("search_all", query="срок договора")]},
        {"content": "Срок — 12 месяцев (a.pdf, стр. 2)"},
    ])
    toolbox = FakeToolbox()
    result = run(llm, toolbox)

    assert toolbox.calls == [("search_all", {"query": "срок договора"})]
    assert result.text == "Срок — 12 месяцев (a.pdf, стр. 2)"
    assert [s.tool for s in result.steps] == ["search_all"]

    second = llm.requests[1]["messages"]
    assert second[-2]["role"] == "assistant" and second[-2]["tool_calls"]
    assert second[-1] == {"role": "tool", "tool_name": "search_all", "content": "найдено по запросу срок договора"}


def test_sources_are_deduplicated_across_calls():
    llm = ScriptedLLM([
        {"content": "", "tool_calls": [call("search_all", query="a"), call("search_all", query="b")]},
        {"content": "готово"},
    ])
    result = run(llm, FakeToolbox())

    assert [s["chunk_id"] for s in result.sources] == [1, 2]
    assert len(result.steps) == 2


def test_accepts_arguments_as_json_string():
    llm = ScriptedLLM([
        {"content": "", "tool_calls": [{"function": {"name": "search_all", "arguments": json.dumps({"query": "x"})}}]},
        {"content": "ok"},
    ])
    toolbox = FakeToolbox()
    run(llm, toolbox)

    assert toolbox.calls == [("search_all", {"query": "x"})]


def test_tool_error_is_reported_to_model_and_loop_continues():
    llm = ScriptedLLM([
        {"content": "", "tool_calls": [call("delete_everything")]},
        {"content": "Не могу этого сделать"},
    ])
    result = run(llm, FakeToolbox())

    assert result.text == "Не могу этого сделать"
    assert result.steps[0].error == "неизвестный инструмент: delete_everything"
    tool_msg = llm.requests[1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "неизвестный инструмент" in tool_msg["content"]


def test_bad_arguments_do_not_crash_the_agent():
    llm = ScriptedLLM([
        {"content": "", "tool_calls": [{"function": {"name": "search_all", "arguments": "{not json"}}]},
        {"content": "ответ"},
    ])
    result = run(llm, FakeToolbox())

    assert result.text == "ответ"
    assert result.steps[0].error


def test_stops_at_iteration_limit_and_asks_for_final_answer():
    looping = {"content": "", "tool_calls": [call("search_all", query="снова")]}
    llm = ScriptedLLM([looping, looping, looping, {"content": "итог по собранному"}])
    result = run(llm, FakeToolbox(), max_iterations=3)

    assert result.stopped_by_limit
    assert result.text == "итог по собранному"
    assert len(result.steps) == 3
    assert llm.requests[-1]["tools"] == []


def test_document_hint_is_added_to_user_message():
    llm = ScriptedLLM([{"content": "ok"}])
    run(llm, FakeToolbox(), document_id=42)

    assert "id=42" in llm.requests[0]["messages"][1]["content"]
