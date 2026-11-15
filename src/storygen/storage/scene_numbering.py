"""SCENE-RENUMBER: plan numbers follow reading order inside the transaction that changes the order."""
import hashlib
from ..domain import VersionRef, new_id
from ..plan_renumber import renumber_plan
from ..scene_description import explicit_scene_number


def renumber_active(repo, db, active, start=0):
    """Give every active numbered scene from `start` the number `index+1`.

    `active` is the reading order; a `None` item holds the place of a scene being created. Unnumbered plans never change.
    A saved plan head gets a new `scene_plan` version (the previous one is invalidated like a manual save); `beats` and
    `author_scene_number` follow. A scene already numbered right is left untouched.
    """
    from .invalidation import invalidate_in_transaction
    from ..domain import Scene
    replaced = []
    for index, scene in enumerate(active):
        if index < start or scene is None:
            continue
        number = index + 1
        head = scene.heads.get('plan')
        text = repo.files.read(*_location(repo, db, head)).decode('utf-8') if head else scene.beats
        written = explicit_scene_number(text)
        # A scene is numbered by its plan heading, or by an explicit number given at creation without one.
        if written is None and scene.author_scene_number is None:
            continue
        if written in {None, number} and scene.author_scene_number == number:
            continue
        if head and written not in {None, number}:
            data = renumber_plan(text, number).encode('utf-8')
            id = new_id()
            version = VersionRef(id=id, story_id=scene.story_id, scene_id=scene.id, kind='scene_plan', format='text',
                                 sha256=hashlib.sha256(data).hexdigest(), relative_path=f'stories/{scene.story_id}/versions/{id}.txt', input_refs=[])
            repo.files.write(version.relative_path, data)
            repo._insert_version_row(db, version)
            scene.heads['plan'] = id
            scene.head_revisions['plan'] = scene.head_revisions.get('plan', 0) + 1
        if explicit_scene_number(scene.beats) is not None:
            scene.beats = renumber_plan(scene.beats, number)
        scene.author_scene_number = number
        scene.revision += 1
        repo._save_scene(db, scene)
        if head:
            replaced.append(head)
    if replaced:
        invalidate_in_transaction(repo, db, replaced)
        # Invalidation marks scenes for review in the database; callers save these same objects again afterwards.
        for scene in active:
            if scene is not None:
                fresh = repo._get(db, 'scenes', scene.id, Scene)
                for field in Scene.model_fields:
                    setattr(scene, field, getattr(fresh, field))


def _location(repo, db, version_id):
    ref = repo._get(db, 'versions', version_id, VersionRef)
    return ref.relative_path, ref.sha256
