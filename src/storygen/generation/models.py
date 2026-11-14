from pydantic import Field, field_validator

from ..domain import DomainModel, SceneCreate


class StyleProfile(DomainModel):
    ending_goal: str = Field(default='',max_length=12000)
    genre: str = ''
    tone: str = ''
    point_of_view: str = 'третя особа'
    tense: str = 'минулий'
    rules: str = 'Українська мова. Репліки діалогу починай з довгого тире.'
    previous_tail_chars: int = Field(default=1200,ge=0,le=12000)
    tone_sample: str = Field(default='',max_length=3000)  # STYLE-SAMPLE-001: voice sample, its own section in prose stages


def style_without_sample(text: str) -> str:
    """STYLE-SAMPLE-001: the style version as the stages blind to the sample see it — the JSON without `tone_sample`."""
    return StyleProfile.model_validate_json(text).model_dump_json(exclude={'tone_sample'})


class SourceCitation(DomainModel):
    version_id: str
    quote: str = Field(min_length=1)


class CharacterCard(DomainModel):
    id: str
    name: str
    description: str
    sources: list[SourceCitation] = Field(min_length=1)


class StoryBlueprint(DomainModel):
    canon: str
    characters: list[CharacterCard]
    scenes: list[SceneCreate] = Field(min_length=1)
    warnings: list[str] = Field(default_factory=list)


class WritersBrief(DomainModel):
    objective: str
    beats: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    proposed_changes: list[str] = Field(default_factory=list)
    introduced: list[str] | None = None

    @field_validator('introduced')
    @classmethod
    def unique_introduced(cls,value):
        return None if value is None else list(dict.fromkeys(value))
