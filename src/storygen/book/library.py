"""SERIES-LIBRARY: the library list with the books of a series gathered into one group."""
from dataclasses import dataclass, field

from ..domain import Story
from ..series_models import Series


@dataclass(frozen=True)
class LibraryEntry:
    """A standalone story, or a series with its active books (bible first, then by number)."""
    story: Story | None = None
    series: Series | None = None
    books: list[Story] = field(default_factory=list)


def library_entries(stories: list[Story], series: list[Series]) -> list[LibraryEntry]:
    """`stories` are the active stories newest first; a series stands where its newest active book stands."""
    by_id = {item.id: item for item in series}
    groups: dict[str, LibraryEntry] = {}
    entries: list[LibraryEntry] = []
    for story in stories:
        item = by_id.get(story.series_id) if story.series_id else None
        if item is None:
            entries.append(LibraryEntry(story=story))
        elif item.id in groups:
            groups[item.id].books.append(story)
        else:
            groups[item.id] = LibraryEntry(series=item, books=[story])
            entries.append(groups[item.id])
    for entry in groups.values():
        entry.books.sort(key=lambda book: (not book.series_bible, book.series_number or 0))
    return entries
