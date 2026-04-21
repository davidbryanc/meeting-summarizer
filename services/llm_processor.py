import json
from config.settings import settings
from models.schemas import MeetingSummary
from utils.prompt_utils import load_prompt


class LLMProcessorService:

    def __init__(self, provider: str = None):
        self.provider = provider or settings.llm_provider

    def _get_gemini_client(self):
        from google import genai
        return genai.Client(api_key=settings.gemini_api_key)

    async def summarize_stream(self, transcript: str):
        """
        Async generator — yield token satu per satu untuk streaming ke Chainlit.
        """
        prompt = load_prompt("summarize.txt", transcript=transcript)

        if self.provider == "gemini":
            async for token in self._gemini_stream(prompt):
                yield token
        else:
            raise ValueError(f"Provider tidak dikenal: {self.provider}")

    async def _gemini_stream(self, prompt: str):
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key)

        async for chunk in await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
        ):
            if chunk.text:
                yield chunk.text

    def parse_summary(self, raw_json: str) -> MeetingSummary:
        """
        Parse JSON dari LLM jadi MeetingSummary object.
        Handle kalau LLM nambahin backtick atau teks ekstra.
        """
        cleaned = raw_json.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1])

        data = json.loads(cleaned)
        return MeetingSummary(**data)

    async def answer_question_stream(self, transcript: str, question: str, history: list[dict]):
        """
        Streaming Q&A — jawab pertanyaan user tentang isi meeting.
        history: list of {"role": "user"/"assistant", "content": "..."}
        """
        history_text = "\n".join(
            f"{h['role'].capitalize()}: {h['content']}"
            for h in history[-6:]
        )

        prompt = load_prompt(
            "qa.txt",
            transcript=transcript,
            history=history_text,
        )
        prompt += f"\n\nUser: {question}"

        if self.provider == "gemini":
            async for token in self._gemini_stream(prompt):
                yield token
        else:
            raise ValueError(f"Provider tidak dikenal: {self.provider}")