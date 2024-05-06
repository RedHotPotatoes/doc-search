import asyncio
from typing import Any, Dict, List, Sequence

from langchain.chains.llm import LLMChain
from langchain.chains.sequential import SequentialChain
from langchain.chat_models.base import BaseChatModel
from langchain.prompts import ChatPromptTemplate

from core.formatters.stackoverflow import (format_stackoverflow_answer,
                                           format_stackoverflow_question)
from core.stackoverflow import (StackOverflowAnswer, StackOverflowDocument,
                                StackOverflowQuestion)


class Summarizer:
    _template = ""
    _input_variables = []

    def __init__(self, llm: BaseChatModel) -> None:
        self._llm = llm
        template = ChatPromptTemplate.from_template(self._template)
        summary_chain = LLMChain(llm=llm, prompt=template)
        self._chain = SequentialChain(
            chains=[summary_chain], input_variables=self._input_variables
        )

    def _preprocess_input(self, inputs: Any) -> str:
        raise NotImplementedError

    def summarize(self, inputs: Any):
        return self._chain.run(self._preprocess_input(inputs))

    def summarize_multiple(self, inputs: Sequence[Any]):
        return [self.summarize(input_) for input_ in inputs]

    async def async_summarize(self, inputs: Any):
        result = await self._chain.arun(self._preprocess_input(inputs))
        return result

    async def async_summarize_multiple(self, inputs: Sequence[Any]):
        result = await asyncio.gather(
            *[self.async_summarize(input_) for input_ in inputs]
        )
        return result


class StackOverflowQuestionSummarizer(Summarizer):
    _template = (
        "Summarize the question in one or a couple of sentences. "
        "Make sure to include the main problem and the context. "
        "The question is from the Stackoverlow post. The question may contain code snippets, "
        "tables, and enumerations; all the text is in markdown format. "
        "The language specified in the code block could be wrong or missing; "
        "rely on it sparingly. ## Question: {question_text}. {tags_text}"
    )
    _input_variables = ["question_text", "tags_text"]

    def _preprocess_input(self, inputs: StackOverflowQuestion) -> str:
        tags = inputs.tags
        if len(tags) > 0:
            tags_text = f"User specified tags: {', '.join(tags)}, this tags may be useful for summarization."
        else:
            tags_text = ""

        question_text = format_stackoverflow_question(inputs)
        return {
            "question_text": question_text,
            "tags_text": tags_text,
        }


class StackOverflowAnswerSummarizer(Summarizer):
    _template = (
        "{question_prefix}Give a concise summary of the answer to the question. "
        "Summarize the answer clearly and concisely. If there is no answer to the question, "
        "specify that there is no answer. The answer is from the Stackoverlow post. "
        "The answer may contain code snippets, tables, and enumerations; all the text is in "
        "markdown format. The language specified in the code block could be wrong or missing; "
        "rely on it sparingly. ## Answer: {answer_text}"
    )
    _input_variables = ["question_prefix", "answer_text"]

    def _preprocess_input(self, inputs: StackOverflowAnswer | Dict[str, Any]) -> str:
        if isinstance(inputs, StackOverflowAnswer):
            question = None
            answer = inputs
        else:
            answer = inputs.get("answer")
            question = inputs.get("question", None)
        answer_text = format_stackoverflow_answer(answer)
        prefix = ""
        if question is not None:
            prefix = f"There is an answer to ## Question:  {question}. "
        return {
            "question_prefix": prefix,
            "answer_text": answer_text,
        }


class StackoverflowDocumentSolutionSummarizer(Summarizer):
    _template = (
        "The user faced an error message: {error_message}. There is some Stackoverflow question "
        "that another user asked, and that question contains the error message. "
        "Here are the answers to that question: ## Answers: {answers}. Please provide a solution "
        "to the error message using the answers provided. Note! It should be the solution to the "
        "error message and not the question from the original post! If multiple distinct solutions "
        "can help solve the error message, provide solutions as a bullet list. Do not repeat "
        "solutions. Try to keep the solution list as short as possible."
    )
    _input_variables = ["error_message", "answers"]

    def _concatenate_answers(
        self, answers: List[str] | List[StackOverflowAnswer]
    ) -> str:
        if isinstance(answers[0], StackOverflowAnswer):
            return "\n\n".join(
                format_stackoverflow_answer(answer, index + 1)
                for index, answer in enumerate(answers)
            )
        return "\n\n".join(
            f"**Answer #{index + 1}.** {answer}" for index, answer in enumerate(answers)
        )

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        error_message = inputs.get("error_message")
        inputs = inputs.get("answers")
        if len(inputs) == 0:
            return {
                "error_message": error_message,
                "answers": "*No answers provided.*",
            }
        answers = self._concatenate_answers(inputs)
        return {"error_message": error_message, "answers": answers}


class DocumentsSolutionAggregator(Summarizer):
    _template = (
        "The user faced an error message: {error_message}. There is a list of solutions to the error message. "
        "Select the best solutions, aggregate them, and provide a concise summary of the solutions. "
        "Give some examples if it helps. ## Solutions: \n{solutions}"
    )
    _input_variables = ["error_message", "solutions"]

    def _preprocess_input(self, inputs: Dict[str, Any]) -> str:
        error_message = inputs.get("error_message")
        solutions = inputs.get("solutions")
        return {
            "error_message": error_message,
            "solutions": solutions,
        }


async def summarize_stackoverflow_document(
    error_message: str,
    document: StackOverflowDocument,
    answer_summarizer: Summarizer,
    solution_summarizer: Summarizer,
    question_summarizer: Summarizer | None = None,
):
    if question_summarizer is not None:
        question_summary = await question_summarizer.async_summarize(document.question)
        answers = [{"question": question_summary, "answer": answer} for answer in document.answers]
    else:
        answers = document.answers
    answers_summary = await answer_summarizer.async_summarize_multiple(answers)
    summary = await solution_summarizer.async_summarize(
        {"error_message": error_message, "answers": answers_summary}
    )
    return summary


async def summarize_stackoverflow_documents(
    error_message: str,
    documents: List[StackOverflowDocument],
    answer_summarizer: Summarizer,
    solution_summarizer: Summarizer,
    solution_aggregator: Summarizer,
    question_summarizer: Summarizer | None = None,
):
    def preproc_summary(summary):
        summary = summary.split("\n")
        summary = [line for line in summary if line.startswith("- ")]
        return summary

    solution_summaries = await asyncio.gather(
        *[
            summarize_stackoverflow_document(
                error_message,
                document,
                answer_summarizer,
                solution_summarizer,
                question_summarizer,
            )
            for document in documents
        ]
    )
    solutions = []
    for summary in solution_summaries:
        solutions.extend(preproc_summary(summary))
    inputs = {"error_message": error_message, "solutions": "\n".join(solutions)}
    solution = await solution_aggregator.async_summarize(inputs)
    return solution
