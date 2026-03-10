# Mục tiêu: phát hiện hallucination khi LLM trả lời.
# Logic:
#   Answer sentence by sentence
#    ↓
#   Check if sentence exists in retrieved docs
#    ↓
#   Flag hallucination

from typing import List, Dict
import re

class HallucinationDetector:

    def split_sentences(self, text: str) -> List[str]:
        sentences = re.split(r"[.!?]\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def detect(self, answer: str, documents: List[Dict]) -> Dict:

        sentences = self.split_sentences(answer)
        doc_text = " ".join([d["content"] for d in documents]).lower()
        hallucinated = []

        for s in sentences:
            s_low = s.lower()
            if s_low not in doc_text:
                hallucinated.append(s)

        score = 1 - (len(hallucinated) / max(len(sentences), 1))

        return {
            "hallucination_score": score,
            "hallucinated_sentences": hallucinated
        }