from pydantic import BaseModel, Field

class KanjiExample(BaseModel):
    word: str = Field(description="The example word containing the kanji (e.g., 火山)")
    kana: str = Field(description="The reading in hiragana or katakana (e.g., かざん)")
    romaji: str = Field(description="The romaji reading (e.g., kazan)")
    meaning: str = Field(description="The English meaning of the word (e.g., volcano)")

    def __str__(self):
        return f"{self.word} [{self.kana}] ({self.romaji}) - {self.meaning}"

class KanjiFormat(BaseModel):
    onyomi: str = Field(description="The On'yomi reading(s) in katakana and romaji")
    kunyomi: str = Field(description="The Kunyomi reading(s) in hiragana and romaji")
    kanji_meaning: str = Field(description="The English meaning of the given Kanji")
    onyomi_examples: list[KanjiExample] = Field(description="List of example words using the On'yomi reading")
    kunyomi_examples: list[KanjiExample] = Field(description="List of example words using the Kunyomi reading")
    
    def to_polished_string(self) -> str:
        onyomi_ex_str = ", ".join(str(ex) for ex in self.onyomi_examples)
        kunyomi_ex_str = ", ".join(str(ex) for ex in self.kunyomi_examples)
        
        return (
            f"On'yomi: {self.onyomi}\n"
            f"Kunyomi: {self.kunyomi}\n"
            f"Kanji Meaning: {self.kanji_meaning}\n\n"
            f"Readings and Examples:\n"
            f"On'yomi: {onyomi_ex_str}\n"
            f"Kunyomi: {kunyomi_ex_str}"
        )
        
class MultilingualText(BaseModel):
    japanese: str = Field(description="The text in Japanese using appropriate kanji, hiragana, and katakana.")
    romaji: str = Field(description="The romaji reading of the Japanese text.")
    english: str = Field(description="The English translation.")

class DialogueLine(BaseModel):
    speaker: str = Field(description="The name or role of the speaker (e.g., Akira, Shopkeeper).")
    text: MultilingualText = Field(description="What the speaker says. MUST include at least one vocabulary word using the target kanji.")

class ReadingUsage(BaseModel):
    onyomi_rule: str = Field(
        description="Explanation of when to use the On'yomi reading for this kanji. Often used in multi-kanji compound words (jukugo)."
    )
    kunyomi_rule: str = Field(
        description="Explanation of when to use the Kun'yomi reading for this kanji. Often used for standalone words or with trailing hiragana (okurigana)."
    )

class KanjiLesson(BaseModel):
    usage_guidelines: ReadingUsage = Field(description="Rules of thumb for when to use the On'yomi vs Kun'yomi readings for this specific kanji.")
    kanji_note: str = Field(description="A short, memorable note: a mnemonic, structural breakdown (radicals), or cultural context about the kanji.")
    dialogue: list[DialogueLine] = Field(description="A short, simple 2-4 line conversation demonstrating the target kanji being used naturally in context.")

    def to_polished_string(self) -> str:
        dialogue_str = ""
        for line in self.dialogue:
            dialogue_str += (
                f"**{line.speaker}**: {line.text.japanese}\n"
                f"    ({line.text.romaji})\n"
                f"    *{line.text.english}*\n\n"
            )

        return (
            f"**Kanji Note**\n{self.kanji_note}\n\n"
            f"**When to use which reading?**\n"
            f"- **On'yomi**: {self.usage_guidelines.onyomi_rule}\n"
            f"- **Kun'yomi**: {self.usage_guidelines.kunyomi_rule}\n\n"
            f"**Practice Dialogue**\n{dialogue_str}"
        )