"""BOOK-STRUCTURE fsck: a broken structure is a limitation, not an issue — no context or version depends on it."""
from ..book.structure import arc_order, check_order, scene_arc_list


def check_book_structure(report, stories, scenes):
    for story in stories.values():
        if story.book_structure is None:
            continue
        active = [s for s in scenes.values() if s.story_id == story.id and not s.trashed_at]
        known = arc_order(story.book_structure)
        unknown = [s for s in active if any(a not in known for a in scene_arc_list(story.scene_arcs, s.id))]
        if unknown:
            report.limitations.append(f'{story.id}: book_structure_unknown_arc: {len(unknown)} scenes are bound to arcs that do not exist; '
                                      'save the book structure again.')
        if check_order(story.book_structure, story.scene_arcs, active):
            report.limitations.append(f'{story.id}: book_structure_parts_mixed: book parts are mixed up: a scene without an arc or arcs of different parts meet; '
                                      'fix the structure in the story settings.')
