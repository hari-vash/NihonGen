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