from typing import List
import csv

from ..document import Document


def load_csv(file_path: str) -> List[Document]:

    docs = []

    with open(file_path, "r", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for i, row in enumerate(reader):

            text = " | ".join([f"{k}:{v}" for k, v in row.items()])

            docs.append(
                Document(
                    page_content=text,
                    metadata={
                        "source": file_path,
                        "row": i,
                        "type": "csv"
                    }
                )
            )

    return docs